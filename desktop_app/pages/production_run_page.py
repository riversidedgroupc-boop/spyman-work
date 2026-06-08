"""Production run page — multi-camera real-time detection with encoder tracking.

Supports both area-scan adapters (via BaseCameraAdapter) and line-scan devices
(via LineScanDevice + BlockBuilder).

Phase F: parameterized with runtime_mode so the same UI serves baseline capture,
anomaly-assisted capture, hybrid capture, and stable production.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QGroupBox,
    QGridLayout,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDoubleSpinBox,
)

from camera_adapters import create_adapter
from core.camera_config import list_camera_configs, CameraConfig
from core.product_spec import get_product_spec
from core.model_version import list_model_versions, get_model_version
from core.production_event import record_ng_event
from core.sampling_controller import SamplingController
from core.runtime_mode import (
    RuntimeMode,
    mode_requires_model,
    mode_allows_manual_triage,
    validate_model_selection,
    cpp_runtime_paths,
)
from runtime.acquisition_pipeline import AcquisitionPipeline
from runtime.inference_pipeline import InferencePipeline
from runtime.health_monitor import HealthMonitor
from runtime.encoder_reader import SimulatedEncoderReader
from runtime.runtime_backend import RuntimeBackend, create_backend
from desktop_app.display import model_type_label
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.theme_manager import ThemeManager


_SAMPLING_OPTIONS = [
    ("production.sampling_continuous", "directory_watch"),
    ("production.sampling_by_time", "by_time"),
    ("production.sampling_by_distance", "by_distance"),
    ("production.sampling_manual", "manual"),
]


def _replace_combo_options(combo: QComboBox, options: list[tuple[str, str]]) -> None:
    current = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    for label_key, value in options:
        combo.addItem(tr(label_key), value)
    if current is not None:
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    combo.blockSignals(False)


class _RuntimeFusionRunner:
    """Single-camera runner that merges optional YOLO and PatchCore results."""

    runner_name = "runtime_fusion"

    def __init__(
        self,
        *,
        yolo_runner: object | None = None,
        anomaly_runner: object | None = None,
        anomaly_threshold: float = 0.65,
    ) -> None:
        self._yolo_runner = yolo_runner
        self._anomaly_runner = anomaly_runner
        self._anomaly_threshold = anomaly_threshold

    def predict_image(self, image_path: str) -> object:
        from core.schema import DetectionBox, ImagePrediction

        detections: list[DetectionBox] = []
        if self._yolo_runner is not None:
            yolo_pred = self._yolo_runner.predict_image(image_path)
            detections.extend(getattr(yolo_pred, "detections", []))

        anomaly_score = 0.0
        heatmap_path = ""
        if self._anomaly_runner is not None:
            anomaly_pred = self._anomaly_runner.predict_image(image_path)
            anomaly_score = float(getattr(anomaly_pred, "image_score", 0.0))
            heatmap_path = str(getattr(anomaly_pred, "heatmap_path", "") or "")
            if anomaly_score >= self._anomaly_threshold:
                import cv2

                img = cv2.imread(str(image_path))
                height, width = img.shape[:2] if img is not None else (1, 1)
                detections.append(
                    DetectionBox(
                        image_name=os.path.basename(str(image_path)),
                        class_id=-1,
                        class_name="unknown_anomaly",
                        confidence=min(max(anomaly_score, 0.0), 1.0),
                        bbox=[0.0, 0.0, float(width), float(height)],
                    )
                )

        prediction = ImagePrediction(
            image_name=os.path.basename(str(image_path)),
            detections=detections,
        )
        prediction.image_score = anomaly_score
        prediction.heatmap_path = heatmap_path
        return prediction


class ProductionRunPage(QWidget):
    """Multi-camera production runtime with live view grid and encoder tracking.

    Parameterized with RuntimeMode so the same UI serves the full workflow:
    baseline capture -> anomaly-assisted -> hybrid -> stable production.
    """

    data_changed = Signal()

    MAX_CAMERAS = 6

    def __init__(self, parent=None, runtime_mode: RuntimeMode = RuntimeMode.STABLE_PRODUCTION):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._runtime_mode = runtime_mode
        self._acq = AcquisitionPipeline(buffer_size=200)
        self._buffer = self._acq.get_buffer()
        self._inference = InferencePipeline(self._buffer)
        self._health = HealthMonitor()
        self._encoder: Any = None
        self._sampling_ctrl = SamplingController()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_display)

        self._ng_images: list[str] = []
        self._events: list[dict] = []
        self._camera_count = 0
        self._configured_adapters: dict[str, CameraConfig] = {}
        self._active_model_version = ""
        self._active_anomaly_model_id = ""
        self._run_output_root = ""
        self._manual_label: str = ""  # current manual triage label
        self._linked_session_id: str = ""  # capture session linked from capture page

        # Dev-mode runtime backend selection (env-controlled for now).
        self._runtime_backend: RuntimeBackend | None = None
        self._runtime_backend_name: str = os.environ.get(
            "CX_RUNTIME_BACKEND", "python_runtime"
        )
        self._runtime_exe_path: str = os.environ.get("CX_RUNTIME_EXE_PATH", "")
        self._runtime_state_file: str = ""
        self._runtime_config_file: str = ""

        self._build_ui()
        self._apply_mode_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Top control bar ----
        ctrl = QHBoxLayout()

        # Runtime mode label
        self._mode_label = QLabel()
        c = ThemeManager.current()
        self._mode_label.setStyleSheet(
            f"font-weight: bold; color: {c.PRIMARY}; padding: 2px 8px;"
            f"background: {c.NAV_SELECTED_BG}; border-radius: 4px; font-size: 12px;"
        )
        ctrl.addWidget(self._mode_label)

        model_label = QLabel()
        bind(model_label, "production.model")
        ctrl.addWidget(model_label)
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(200)
        ctrl.addWidget(self._model_combo)

        # Anomaly model selector (visible only in hybrid mode)
        self._anomaly_model_label = QLabel()
        bind(self._anomaly_model_label, "production.anomaly_model")
        self._anomaly_model_label.setVisible(False)
        ctrl.addWidget(self._anomaly_model_label)
        self._anomaly_model_combo = QComboBox()
        self._anomaly_model_combo.setMinimumWidth(200)
        self._anomaly_model_combo.setVisible(False)
        ctrl.addWidget(self._anomaly_model_combo)

        # Sampling mode
        sampling_label = QLabel()
        bind(sampling_label, "production.sampling_mode")
        ctrl.addWidget(sampling_label)
        self._sampling_combo = QComboBox()
        _replace_combo_options(self._sampling_combo, _SAMPLING_OPTIONS)
        self._sampling_combo.currentIndexChanged.connect(self._on_sampling_mode_changed)
        ctrl.addWidget(self._sampling_combo)

        # Interval / distance controls
        self._interval_spin = QDoubleSpinBox()
        self._interval_spin.setRange(0.1, 3600.0)
        self._interval_spin.setValue(1.0)
        self._interval_spin.setSuffix(" s")
        self._interval_spin.setVisible(False)
        ctrl.addWidget(self._interval_spin)

        self._distance_spin = QDoubleSpinBox()
        self._distance_spin.setRange(0.01, 1000.0)
        self._distance_spin.setValue(1.0)
        self._distance_spin.setSuffix(" m")
        self._distance_spin.setDecimals(3)
        self._distance_spin.setVisible(False)
        ctrl.addWidget(self._distance_spin)

        self._manual_btn = QPushButton()
        bind(self._manual_btn, "production.manual_trigger")
        self._manual_btn.setVisible(False)
        self._manual_btn.clicked.connect(self._manual_capture)
        ctrl.addWidget(self._manual_btn)

        ctrl.addStretch()

        # Manual triage buttons (baseline / setup modes)
        self._triage_ok_btn = QPushButton("OK")
        self._triage_ok_btn.setObjectName("okBtn")
        self._triage_ok_btn.setVisible(False)
        self._triage_ok_btn.clicked.connect(lambda: self._on_manual_triage("OK"))
        ctrl.addWidget(self._triage_ok_btn)

        self._triage_ng_btn = QPushButton("NG")
        self._triage_ng_btn.setObjectName("dangerBtn")
        self._triage_ng_btn.setVisible(False)
        self._triage_ng_btn.clicked.connect(lambda: self._on_manual_triage("NG"))
        ctrl.addWidget(self._triage_ng_btn)

        self._triage_uncertain_btn = QPushButton(tr("classify.uncertain"))
        self._triage_uncertain_btn.setVisible(False)
        self._triage_uncertain_btn.clicked.connect(lambda: self._on_manual_triage("Uncertain"))
        ctrl.addWidget(self._triage_uncertain_btn)

        # Encoder status
        self._encoder_label = QLabel()
        bind(self._encoder_label, "production.encoder_position", pos=0.0)
        c = ThemeManager.current()
        self._encoder_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-family: monospace;")
        ctrl.addWidget(self._encoder_label)

        self._start_btn = QPushButton()
        bind(self._start_btn, "production.start")
        self._start_btn.clicked.connect(self._start)
        ctrl.addWidget(self._start_btn)

        self._stop_btn = QPushButton()
        bind(self._stop_btn, "production.stop")
        self._stop_btn.setObjectName("dangerBtn")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        ctrl.addWidget(self._stop_btn)

        layout.addLayout(ctrl)

        # ---- Main area ----
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: live view grid for each camera
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._live_grid = QGridLayout()
        self._live_grid.setSpacing(6)
        self._live_labels: dict[str, QLabel] = {}  # camera_id -> QLabel
        self._cam_status_labels: dict[str, QLabel] = {}  # camera_id -> status text
        left_layout.addLayout(self._live_grid, 1)

        # Camera status group
        self._cam_status_group = QGroupBox()
        bind(self._cam_status_group, "production.cam_status", setter="setTitle")
        cs_layout = QGridLayout(self._cam_status_group)
        cs_layout.setSpacing(4)
        self._status_grid: dict[str, QLabel] = {}
        left_layout.addWidget(self._cam_status_group)

        splitter.addWidget(left)

        # Right panel: NG images + events
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        ng_group = QGroupBox()
        bind(ng_group, "production.recent_ng", setter="setTitle")
        ng_layout = QVBoxLayout(ng_group)
        self._ng_label = QLabel()
        bind(self._ng_label, "production.no_ng")
        self._ng_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ng_label.setMinimumHeight(180)
        c = ThemeManager.current()
        self._ng_label.setStyleSheet(
            f"background-color: {c.BG_INPUT}; border: 1px solid {c.BORDER}; color: {c.TEXT_SECONDARY};"
        )
        ng_layout.addWidget(self._ng_label)
        right_layout.addWidget(ng_group)

        evt_group = QGroupBox()
        bind(evt_group, "production.defect_events", setter="setTitle")
        evt_layout = QVBoxLayout(evt_group)
        self._event_table = QTableWidget(0, 6)
        self._event_table.setHorizontalHeaderLabels(
            [
                tr("production.col_time"),
                tr("production.col_camera"),
                tr("defect.defect_type"),
                tr("production.col_dets"),
                tr("defect.position_meter"),
                tr("production.col_ng"),
            ]
        )
        self._event_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        evt_layout.addWidget(self._event_table)
        right_layout.addWidget(evt_group)

        splitter.addWidget(right)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    # Runtime mode
    # ------------------------------------------------------------------

    def set_runtime_mode(self, mode: RuntimeMode) -> None:
        self._runtime_mode = mode
        self._apply_mode_ui()

    def link_capture_session(self, session_id: str) -> None:
        """Link a capture session so manual triage images are recorded to it."""
        self._linked_session_id = session_id

    def _apply_mode_ui(self) -> None:
        mode = self._runtime_mode
        mode_keys: dict[RuntimeMode, str] = {
            RuntimeMode.SETUP_CAPTURE: "production.mode_setup_capture",
            RuntimeMode.BASELINE_CAPTURE: "production.mode_baseline_capture",
            RuntimeMode.ANOMALY_ASSISTED_CAPTURE: "production.mode_anomaly_assisted",
            RuntimeMode.HYBRID_CAPTURE: "production.mode_hybrid_detection",
            RuntimeMode.STABLE_PRODUCTION: "production.mode_stable_production",
            RuntimeMode.BENCHMARK_REPLAY: "production.mode_benchmark_replay",
        }
        self._mode_label.setText(tr(mode_keys.get(mode, "")) if mode in mode_keys else mode.value)

        needs_model = mode_requires_model(mode)
        self._model_combo.setEnabled(needs_model)
        if not needs_model:
            self._model_combo.setToolTip(tr("production.model_optional"))

        show_triage = mode_allows_manual_triage(mode)
        self._triage_ok_btn.setVisible(show_triage)
        self._triage_ng_btn.setVisible(show_triage)
        self._triage_uncertain_btn.setVisible(show_triage)

        show_anomaly = mode in (RuntimeMode.HYBRID_CAPTURE, RuntimeMode.ANOMALY_ASSISTED_CAPTURE)
        self._anomaly_model_label.setVisible(show_anomaly)
        self._anomaly_model_combo.setVisible(show_anomaly)

    # ------------------------------------------------------------------
    # Text refresh (i18n)
    # ------------------------------------------------------------------

    def _refresh_text(self, lang: str = "") -> None:
        _replace_combo_options(self._sampling_combo, _SAMPLING_OPTIONS)
        self._apply_mode_ui()
        self._event_table.setHorizontalHeaderLabels(
            [
                tr("production.col_time"),
                tr("production.col_camera"),
                tr("defect.defect_type"),
                tr("production.col_dets"),
                tr("defect.position_meter"),
                tr("production.col_ng"),
            ]
        )
        self._model_combo.clear()
        self._model_combo.addItem(tr("app.select_model"), "")
        pid = self._ctx.current_project_id
        if pid:
            for m in list_model_versions(pid):
                self._model_combo.addItem(
                    f"{m.model_name} ({model_type_label(m.model_type)})", m.model_id
                )

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._mode_label.setStyleSheet(
            f"font-weight: bold; color: {c.PRIMARY}; padding: 2px 8px;"
            f"background: {c.NAV_SELECTED_BG}; border-radius: 4px; font-size: 12px;"
        )
        self._encoder_label.setStyleSheet(
            f"color: {c.TEXT_SECONDARY}; font-family: monospace;"
        )
        self._ng_label.setStyleSheet(
            f"background-color: {c.BG_INPUT}; border: 1px solid {c.BORDER};"
            f" color: {c.TEXT_SECONDARY};"
        )
        for tile in self._live_labels.values():
            tile.setStyleSheet(
                f"background-color: {c.BG_INPUT}; border: 1px solid {c.BORDER};"
                f" color: {c.TEXT_SECONDARY}; font-size: 11px;"
            )
        for st_lbl in self._cam_status_labels.values():
            st_lbl.setStyleSheet(f"color: {c.TEXT_SECONDARY};")

    def showEvent(self, event):
        super().showEvent(event)
        pid = self._ctx.current_project_id

        self._model_combo.clear()
        self._model_combo.addItem(tr("app.select_model"), "")
        if pid:
            for m in list_model_versions(pid):
                if m.model_type in ("yolo",):
                    self._model_combo.addItem(
                        f"{m.model_name} ({model_type_label(m.model_type)})", m.model_id
                    )

        self._anomaly_model_combo.clear()
        self._anomaly_model_combo.addItem(tr("app.select_model"), "")
        if pid:
            for m in list_model_versions(pid):
                if m.model_type in ("patchcore", "anomaly", "unsupervised"):
                    self._anomaly_model_combo.addItem(
                        f"{m.model_name} ({model_type_label(m.model_type)})", m.model_id
                    )

        self._apply_mode_ui()
        self._rebuild_camera_grid()

    # ------------------------------------------------------------------
    # Camera grid
    # ------------------------------------------------------------------

    def _rebuild_camera_grid(self):
        """Create / recreate live view tiles based on current spec."""
        # Clear old grid
        while self._live_grid.count():
            item = self._live_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Clear old status grid
        while self._cam_status_group.layout().count():
            item = self._cam_status_group.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._live_labels.clear()
        self._cam_status_labels.clear()
        self._status_grid.clear()

        spec_id = self._ctx.current_spec_id
        if not spec_id:
            return

        spec = get_product_spec(spec_id)
        if spec is None:
            return

        self._camera_count = spec.camera_count
        cols = min(self._camera_count, 3)

        cs_layout = self._cam_status_group.layout()

        for idx in range(1, self._camera_count + 1):
            camera_id = f"cam{idx}"

            # Live view tile
            tile = QLabel()
            bind(tile, "production.live_view")
            tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile.setMinimumSize(180, 140)
            c = ThemeManager.current()
            tile.setStyleSheet(
                f"background-color: {c.BG_INPUT}; border: 1px solid {c.BORDER};"
                f" color: {c.TEXT_SECONDARY}; font-size: 11px;"
            )
            self._live_labels[camera_id] = tile
            row = (idx - 1) // cols
            col = (idx - 1) % cols
            self._live_grid.addWidget(tile, row, col)

            # Status label (in status group)
            st_lbl = QLabel()
            bind(st_lbl, "production.cam_offline", i=idx)
            c = ThemeManager.current()
            st_lbl.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
            self._cam_status_labels[camera_id] = st_lbl
            srow = (idx - 1) // 3
            scol = (idx - 1) % 3
            cs_layout.addWidget(st_lbl, srow, scol)

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def _uses_external_runtime_backend(self) -> bool:
        return self._runtime_backend_name != "python_runtime"

    def _build_runtime_config(
        self,
        *,
        run_id: str,
        project_id: str,
        spec_id: str,
        camera_configs: dict[str, CameraConfig],
        yolo_model_id: str,
        anomaly_model_id: str,
        output_dir: str,
    ) -> RuntimeConfig:
        """Build a full RuntimeConfig from live page state."""
        from core.runtime_contracts import CameraRuntimeConfig, RuntimeConfig

        cameras: list[CameraRuntimeConfig] = []
        for camera_id, cfg in camera_configs.items():
            atype = cfg.adapter_type or "folder_watcher"
            if atype in ("line_scan", "hikrobot_line_scan"):
                camera_type = "line_scan"
                default_width = 2048
            else:
                camera_type = "area_scan"
                default_width = 1920

            cameras.append(
                CameraRuntimeConfig(
                    camera_id=camera_id,
                    camera_type=camera_type,
                    serial_number=cfg.serial_number or "",
                    ip_address=cfg.ip_address or "",
                    width=cfg.resolution_width or default_width,
                    height=cfg.resolution_height or 0,
                    block_height=cfg.image_block_height or 1024,
                    pixel_format=cfg.pixel_format or "Mono8",
                    exposure_us=cfg.exposure_us,
                    gain_db=cfg.gain_db,
                    line_rate=cfg.line_rate,
                )
            )

        model_artifacts: dict[str, str] = {}
        if yolo_model_id:
            model = get_model_version(yolo_model_id)
            if model is not None:
                model_artifacts["yolo"] = model.model_path
        if anomaly_model_id:
            model = get_model_version(anomaly_model_id)
            if model is not None:
                model_artifacts["anomaly"] = model.model_path

        return RuntimeConfig(
            run_id=run_id,
            project_id=project_id,
            spec_id=spec_id,
            backend=self._runtime_backend_name,
            cameras=cameras,
            model_artifacts=model_artifacts,
            confidence=0.5,
            iou=0.45,
            output_dir=output_dir,
        )

    def _start(self):
        mode = self._runtime_mode
        spec_id = self._ctx.current_spec_id
        if not spec_id:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_spec_first"))
            return

        spec = get_product_spec(spec_id)
        if spec is None:
            return

        project_id = self._ctx.current_project_id or "unknown"

        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # --- Instantiate runtime backend if dev-mode cpp_runtime is selected ---
        self._runtime_backend = None
        if self._runtime_backend_name != "python_runtime":
            # Resolve state/config file paths (write-once per run).
            from pathlib import Path
            import tempfile as _tmp

            base = Path(_tmp.gettempdir()) / "cx_runtime"
            base.mkdir(parents=True, exist_ok=True)
            state_f, config_f = cpp_runtime_paths(base, run_id)

            kwargs: dict = {}
            if self._runtime_backend_name == "cpp_runtime":
                if not self._runtime_exe_path:
                    QMessageBox.critical(
                        self,
                        tr("app.error"),
                        "CX_RUNTIME_EXE_PATH environment variable is required for cpp_runtime backend.",
                    )
                    return
                kwargs["executable_path"] = self._runtime_exe_path

            self._runtime_state_file = str(state_f)
            self._runtime_config_file = str(config_f)

            try:
                self._runtime_backend = create_backend(
                    self._runtime_backend_name,
                    executable_path=kwargs.get("executable_path"),
                    state_file_path=self._runtime_state_file,
                    config_file_path=self._runtime_config_file,
                )
            except ValueError as e:
                QMessageBox.critical(self, tr("app.error"), str(e))
                return

        # Determine model requirements by mode
        yolo_model_id = self._model_combo.currentData() or ""
        anomaly_model_id = self._anomaly_model_combo.currentData() or ""

        if not validate_model_selection(
            mode,
            yolo_model_id=yolo_model_id,
            anomaly_model_id=anomaly_model_id,
        ):
            QMessageBox.information(self, tr("app.tip"), tr("app.select_model"))
            return

        # Resolve output root via workspace
        from core.workspace_paths import get_project_dir, ensure_dir
        from core.project import get_project as _gp

        proj = _gp(project_id)
        customer_id = proj.customer_id if proj else "unknown"
        ws_root = ensure_dir(get_project_dir(customer_id, project_id))
        self._run_output_root = ensure_dir(
            os.path.join(
                ws_root,
                "production_records",
                f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            )
        )

        # --- Load camera configs from DB (read-only, no hardware connection yet) ---
        cfgs = list_camera_configs(spec_id)
        cfg_by_index: dict[int, CameraConfig] = {c.camera_index: c for c in cfgs if c.enabled}

        # --- External runtime backend: skip all Python hardware / model init ---
        if self._uses_external_runtime_backend():
            ext_cfgs: dict[str, CameraConfig] = {}
            for idx in range(1, spec.camera_count + 1):
                camera_id = f"cam{idx}"
                cfg = cfg_by_index.get(idx)
                if cfg is None:
                    cfg = CameraConfig(
                        config_id="",
                        spec_id=spec_id,
                        camera_index=idx,
                        adapter_type="folder_watcher",
                        connection_params="{}",
                    )
                ext_cfgs[camera_id] = cfg

            if self._runtime_backend is not None:
                try:
                    cfg = self._build_runtime_config(
                        run_id=run_id,
                        project_id=project_id,
                        spec_id=spec_id,
                        camera_configs=ext_cfgs,
                        yolo_model_id=yolo_model_id,
                        anomaly_model_id=anomaly_model_id,
                        output_dir=self._run_output_root,
                    )
                    status = self._runtime_backend.start(cfg)
                    if status.error_code:
                        QMessageBox.warning(
                            self,
                            tr("app.warning"),
                            f"Runtime backend start error: [{status.error_code}] {status.error_message or status.state}",
                        )
                        self._runtime_backend = None
                        return
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        tr("app.error"),
                        f"Runtime backend start failed: {e}",
                    )
                    self._runtime_backend = None
                    return

            self._timer.start(500)
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
            return

        # --- Python runtime: model loading and hardware init below ---
        if yolo_model_id:
            model = get_model_version(yolo_model_id)
            if model is None:
                return
            self._active_model_version = model.model_id
        else:
            self._active_model_version = ""

        if anomaly_model_id:
            self._active_anomaly_model_id = anomaly_model_id
        else:
            self._active_anomaly_model_id = ""

        self._configured_adapters.clear()

        for idx in range(1, spec.camera_count + 1):
            camera_id = f"cam{idx}"
            cfg = cfg_by_index.get(idx)
            if cfg is None:
                # Auto-create default config based on adapter_type
                cfg = CameraConfig(
                    config_id="",
                    spec_id=spec_id,
                    camera_index=idx,
                    adapter_type="folder_watcher",
                    connection_params="{}",
                )

            atype = cfg.adapter_type or "folder_watcher"
            try:
                if atype in ("line_scan", "hikrobot_line_scan"):
                    self._connect_line_scan(camera_id, cfg)
                else:
                    self._connect_area_scan(camera_id, cfg)
                self._configured_adapters[camera_id] = cfg
            except Exception as e:
                QMessageBox.warning(
                    self, tr("app.error"), tr("camera.connect_failed", cam=camera_id, err=str(e))
                )
                continue

        if not self._configured_adapters:
            QMessageBox.critical(self, tr("production.no_cameras"), tr("production.no_cameras_msg"))
            return

        # --- Setup encoder (simulated for now) ---
        self._encoder = SimulatedEncoderReader()
        self._encoder.connect(
            {
                "line_speed_mpm": spec.target_speed_mpm,
                "pulses_per_meter": 1000.0,
            }
        )
        self._acq.set_encoder(self._encoder)

        # --- Setup sampling controller ---
        mode = self._sampling_combo.currentData() or "directory_watch"
        self._sampling_ctrl.configure(
            mode=mode,
            interval_seconds=self._interval_spin.value(),
            distance_meters=self._distance_spin.value(),
        )
        self._sampling_ctrl.set_enabled(True)
        self._acq.set_sampling_controller(self._sampling_ctrl)

        # --- Setup inference runners (mode-aware) ---
        yolo_runner: object | None = None
        anomaly_runner: object | None = None

        if self._active_model_version:
            model = get_model_version(self._active_model_version)
            try:
                from model_runners.yolo_runner import YoloModelRunner

                yolo_runner = YoloModelRunner(
                    model_path=model.model_path if model else "",
                    config={"confidence": 0.5, "device": "cpu"},
                )
                yolo_runner.load()
            except Exception as e:
                QMessageBox.critical(self, tr("production.model_load_failed"), str(e))
                return

        if self._active_anomaly_model_id:
            try:
                from src.inference.patchcore_runner import PatchCoreRunner

                anomaly_model = get_model_version(self._active_anomaly_model_id)
                if anomaly_model:
                    anomaly_runner = PatchCoreRunner(
                        {
                            "mode": "statistical",
                            "model_path": anomaly_model.model_path,
                            "score_threshold": 0.65,
                        }
                    )
                    anomaly_runner.load_model()
            except Exception as e:
                QMessageBox.warning(
                    self,
                    tr("app.warning"),
                    f"Anomaly model load failed: {e}",
                )
                return

        if yolo_runner is not None or anomaly_runner is not None:
            for cam_id in self._configured_adapters:
                self._inference.set_runner(
                    _RuntimeFusionRunner(
                        yolo_runner=yolo_runner,
                        anomaly_runner=anomaly_runner,
                        anomaly_threshold=0.65,
                    ),
                    camera_id=cam_id,
                )
            self._inference.set_on_ng(self._on_ng_detected)

        # --- Start Python pipelines ---
        self._acq.start()
        if yolo_runner is not None or anomaly_runner is not None:
            self._inference.start()
        self._timer.start(200)

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Camera connection helpers
    # ------------------------------------------------------------------

    def _connect_area_scan(self, camera_id: str, cfg: CameraConfig) -> None:
        """Connect a camera via the existing adapter system (area-scan / folder-watcher)."""
        conn = json.loads(cfg.connection_params) if cfg.connection_params else {}
        adapter = create_adapter(cfg.adapter_type)
        adapter.connect(conn)
        self._acq.add_camera(camera_id, adapter)

    def _connect_line_scan(self, camera_id: str, cfg: CameraConfig) -> None:
        """Connect a line-scan camera (virtual or real) with block builder."""
        serial = cfg.serial_number or ""
        block_height = cfg.image_block_height or 1024

        # Choose device type
        if cfg.adapter_type == "hikrobot_line_scan" and serial:
            from src.device.camera.hikrobot.hikrobot_camera import HikrobotLineScanCamera

            device = HikrobotLineScanCamera()
            if not device.open(serial):
                code, msg = device.get_last_error()
                raise RuntimeError(f"Hikrobot open failed 0x{code:08X}: {msg}")
            # Apply stored parameters
            if cfg.exposure_us is not None:
                device.set_param("ExposureTime", float(cfg.exposure_us))
            if cfg.gain_db is not None:
                device.set_param("Gain", float(cfg.gain_db))
            if cfg.line_rate is not None:
                device.set_param("LineRate", int(cfg.line_rate))
            if cfg.pixel_format:
                device.set_param("PixelFormat", cfg.pixel_format)
            if cfg.trigger_mode:
                device.set_param("TriggerMode", cfg.trigger_mode)
            try:
                roi = json.loads(cfg.roi) if cfg.roi else {}
            except json.JSONDecodeError:
                roi = {}
            if roi.get("trigger_source"):
                device.set_param("TriggerSource", roi["trigger_source"])
        else:
            from src.device.camera.simulator.virtual_line_scan import VirtualLineScanCamera

            device = VirtualLineScanCamera(
                width=cfg.resolution_width or 2048,
                line_rate=float(cfg.line_rate or 20000),
            )
            device.open(serial or f"VIRTUAL_{camera_id}")

        self._acq.add_line_scan_camera(
            camera_id,
            device,
            block_height=block_height,
        )

    def _stop(self):
        self._timer.stop()
        if self._uses_external_runtime_backend():
            # External runtime: stop backend only, no Python pipeline
            pass
        else:
            self._inference.stop()
            self._acq.stop()

        # --- Notify runtime backend ---
        if self._runtime_backend is not None:
            try:
                status = self._runtime_backend.stop()
                if status.error_code:
                    QMessageBox.warning(
                        self,
                        tr("app.warning"),
                        f"Runtime backend stop error: [{status.error_code}] {status.error_message or status.state}",
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    tr("app.error"),
                    f"Runtime backend stop failed: {e}",
                )
            self._runtime_backend = None

        self._sampling_ctrl.set_enabled(False)
        self._acq.set_sampling_controller(None)

        if self._encoder:
            self._encoder.disconnect()
            self._encoder = None

        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Sampling mode
    # ------------------------------------------------------------------

    def _on_sampling_mode_changed(self, _index: int):
        mode = self._sampling_combo.currentData()
        self._interval_spin.setVisible(mode == "by_time")
        self._distance_spin.setVisible(mode == "by_distance")
        self._manual_btn.setVisible(mode == "manual")

    def _manual_capture(self):
        if self._sampling_ctrl.state.enabled:
            self._sampling_ctrl.trigger_manual()

    def _on_manual_triage(self, label: str) -> None:
        """Record manual OK/NG/Uncertain classification for current frame."""
        self._manual_label = label
        project_id = self._ctx.current_project_id or "unknown"
        # Record the last visible frame as a classified capture
        for cid in self._live_labels:
            frame = self._buffer.get_per_camera(cid)
            if frame is not None:
                import cv2

                img = frame["image"]
                if img is not None:
                    save_dir = os.path.join(self._run_output_root, "classified", label.lower())
                    os.makedirs(save_dir, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    fname = f"{cid}_{ts}_{label}.jpg"
                    fpath = os.path.join(save_dir, fname)
                    if img.ndim == 2:
                        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                    cv2.imwrite(fpath, img)
                    # Also record in capture session if active
                    try:
                        from core.capture_session import (
                            add_captured_image,
                            set_image_classification,
                        )

                        image_id = add_captured_image(
                            session_id=getattr(self, "_linked_session_id", ""),
                            project_id=project_id,
                            image_path=fpath,
                            image_name=fname,
                            camera_id=cid,
                        )
                        set_image_classification(image_id, label)
                    except Exception:
                        pass

    # ------------------------------------------------------------------
    # NG event handling
    # ------------------------------------------------------------------

    def _on_ng_detected(self, result: dict):
        camera_id = result.get("camera_id", "")
        cfg = self._configured_adapters.get(camera_id)
        position = result.get("position_meter")
        block = result.get("block")
        block_id = getattr(block, "block_id", "")
        prediction = result.get("prediction")
        detections = getattr(prediction, "detections", []) if prediction is not None else []
        tile_id = getattr(detections[0], "tile_id", "") if detections else ""

        if cfg and not cfg.save_ng_image:
            return

        evt = record_ng_event(
            project_id=self._ctx.current_project_id or "unknown",
            spec_id=self._ctx.current_spec_id,
            batch_id="default",
            camera_id=camera_id,
            image=result.get("image"),
            prediction=prediction,
            output_root=self._run_output_root,
            model_version=self._active_model_version,
            position_meter=position,
            block_id=block_id,
            tile_id=tile_id,
        )
        self._ng_images.append(evt.ng_image_path)
        self._events.append(
            {
                "time": evt.event_time,
                "camera": evt.camera_id,
                "defect_type": evt.defect_type,
                "dets": evt.detection_count,
                "position": evt.position_meter,
                "ng": True,
            }
        )
        if len(self._ng_images) > 20:
            self._ng_images = self._ng_images[-20:]

    # ------------------------------------------------------------------
    # Display refresh (called by QTimer)
    # ------------------------------------------------------------------

    def _refresh_display(self):
        if self._uses_external_runtime_backend():
            self._refresh_external_runtime_display()
            return

        # --- Encoder position ---
        if self._encoder:
            try:
                pos = self._encoder.read_position_meter()
                bind(
                    self._encoder_label,
                    "production.encoder_position",
                    setter="setText",
                    pos=f"{pos:.3f}",
                )
            except Exception:
                pass

        # --- Camera status ---
        acq_statuses = self._acq.get_status()
        for st in acq_statuses:
            cid = st.get("camera_id", "")
            lbl = self._cam_status_labels.get(cid)
            if lbl:
                is_line_scan = st.get("type") == "line_scan"
                if is_line_scan:
                    fps = st.get("fps", 0)
                    frames = st.get("frame_count", 0)
                    conn = "✓" if st.get("connected") else "✗"
                    lbl.setText(f"{cid}  行频:{fps:.0f}Hz  行数:{frames}  连接:{conn}")
                else:
                    fps = st.get("fps", 0)
                    frames = st.get("frame_count", 0)
                    pos = st.get("encoder_position_m", 0.0)
                    lbl.setText(
                        tr(
                            "production.cam_status_fmt",
                            cam=cid,
                            fps=f"{fps:.1f}",
                            frames=frames,
                            pos=f"{pos:.2f}",
                        )
                    )

        # Inference stats
        inf_statuses = self._inference.get_all_statuses()
        for inf in inf_statuses:
            cid = inf.get("camera_id", "")
            lbl = self._cam_status_labels.get(cid)
            if lbl and inf.get("ng_count", 0) > 0:
                current = lbl.text()
                lbl.setText(f"{current}  NG:{inf['ng_count']}")

        # --- Live views per camera ---
        for cid, lbl in self._live_labels.items():
            frame = self._buffer.get_per_camera(cid)
            if frame is not None:
                import cv2

                img = frame["image"]
                if img.ndim == 2:
                    # Grayscale line-scan block → display as BGR
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg).scaled(
                    lbl.width(),
                    lbl.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                lbl.setPixmap(pixmap)

        # --- Recent NG image ---
        if self._ng_images:
            ng_path = self._ng_images[-1]
            if os.path.isfile(ng_path):
                self._ng_label.setPixmap(
                    QPixmap(ng_path).scaled(
                        self._ng_label.width(),
                        self._ng_label.height(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

        # --- Event table ---
        recent = self._events[-20:]
        self._event_table.setRowCount(len(recent))
        for row, evt in enumerate(reversed(recent)):
            self._event_table.setItem(row, 0, QTableWidgetItem(str(evt.get("time", ""))[-12:]))
            self._event_table.setItem(row, 1, QTableWidgetItem(evt.get("camera", "")))
            self._event_table.setItem(row, 2, QTableWidgetItem(evt.get("defect_type", "")))
            self._event_table.setItem(row, 3, QTableWidgetItem(str(evt.get("dets", 0))))
            pos_val = evt.get("position")
            self._event_table.setItem(
                row,
                4,
                QTableWidgetItem(
                    f"{pos_val:.3f}" if isinstance(pos_val, (int, float)) else str(pos_val or "")
                ),
            )
            self._event_table.setItem(row, 5, QTableWidgetItem("NG" if evt.get("ng") else "OK"))

    def _refresh_external_runtime_display(self) -> None:
        """Refresh display from RuntimeBackend.status() for external runtime modes."""
        if self._runtime_backend is None:
            return
        try:
            status = self._runtime_backend.status()
        except Exception as exc:
            self._encoder_label.setText(f"Runtime status error: {exc}")
            return

        self._encoder_label.setText(
            f"Runtime: {status.state}  "
            f"uptime:{status.uptime_ms}ms  "
            f"queue:{status.queue_size}  "
            f"dropped:{status.dropped_frames}  "
            f"NG:{status.ng_count}"
        )
        for camera_id, fps in status.fps_by_camera.items():
            lbl = self._cam_status_labels.get(camera_id)
            if lbl is not None:
                lbl.setText(f"{camera_id}  FPS:{fps:.1f}  Runtime:{status.state}")
