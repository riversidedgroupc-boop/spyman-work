"""Production run page — multi-camera real-time detection with encoder tracking.

Supports both area-scan adapters (via BaseCameraAdapter) and line-scan devices
(via LineScanDevice + BlockBuilder).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QGroupBox, QGridLayout, QMessageBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSpinBox, QDoubleSpinBox,
)

from camera_adapters import create_adapter
from core.camera_config import list_camera_configs, CameraConfig
from core.product_spec import get_product_spec
from core.model_version import list_model_versions, get_model_version
from core.production_event import record_ng_event
from core.sampling_controller import SamplingController, SAMPLING_MODES
from runtime.frame_buffer import FrameBuffer
from runtime.acquisition_pipeline import AcquisitionPipeline
from runtime.inference_pipeline import InferencePipeline
from runtime.health_monitor import HealthMonitor
from runtime.encoder_reader import SimulatedEncoderReader
from desktop_app.display import model_type_label
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, bind, I18nManager


class ProductionRunPage(QWidget):
    """Multi-camera production runtime with live view grid and encoder tracking."""

    data_changed = Signal()

    MAX_CAMERAS = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
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
        self._run_output_root = ""

        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Top control bar ----
        ctrl = QHBoxLayout()

        model_label = QLabel()
        bind(model_label, "production.model")
        ctrl.addWidget(model_label)
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(200)
        ctrl.addWidget(self._model_combo)

        # Sampling mode
        sampling_label = QLabel()
        bind(sampling_label, "production.sampling_mode")
        ctrl.addWidget(sampling_label)
        self._sampling_combo = QComboBox()
        self._sampling_combo.addItem(tr("production.sampling_continuous"), "directory_watch")
        self._sampling_combo.addItem(tr("production.sampling_by_time"), "by_time")
        self._sampling_combo.addItem(tr("production.sampling_by_distance"), "by_distance")
        self._sampling_combo.addItem(tr("production.sampling_manual"), "manual")
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

        # Encoder status
        self._encoder_label = QLabel()
        bind(self._encoder_label, "production.encoder_position", pos=0.0)
        self._encoder_label.setStyleSheet("color: #888; font-family: monospace;")
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
        self._live_labels: dict[str, QLabel] = {}     # camera_id -> QLabel
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
        self._ng_label.setStyleSheet("background-color: #111; border: 1px solid #3E3E3E; color: #888;")
        ng_layout.addWidget(self._ng_label)
        right_layout.addWidget(ng_group)

        evt_group = QGroupBox()
        bind(evt_group, "production.defect_events", setter="setTitle")
        evt_layout = QVBoxLayout(evt_group)
        self._event_table = QTableWidget(0, 6)
        self._event_table.setHorizontalHeaderLabels([
            tr("production.col_time"), tr("production.col_camera"),
            tr("defect.defect_type"), tr("production.col_dets"),
            tr("defect.position_meter"), tr("production.col_ng"),
        ])
        self._event_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        evt_layout.addWidget(self._event_table)
        right_layout.addWidget(evt_group)

        splitter.addWidget(right)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    # Text refresh (i18n)
    # ------------------------------------------------------------------

    def _refresh_text(self, lang: str = "") -> None:
        self._event_table.setHorizontalHeaderLabels([
            tr("production.col_time"), tr("production.col_camera"),
            tr("defect.defect_type"), tr("production.col_dets"),
            tr("defect.position_meter"), tr("production.col_ng"),
        ])
        self._model_combo.clear()
        self._model_combo.addItem(tr("app.select_model"), "")
        pid = self._ctx.current_project_id
        if pid:
            for m in list_model_versions(pid):
                self._model_combo.addItem(
                    f"{m.model_name} ({model_type_label(m.model_type)})", m.model_id
                )

    def showEvent(self, event):
        super().showEvent(event)
        self._model_combo.clear()
        self._model_combo.addItem(tr("app.select_model"), "")
        pid = self._ctx.current_project_id
        if pid:
            for m in list_model_versions(pid):
                self._model_combo.addItem(
                    f"{m.model_name} ({model_type_label(m.model_type)})", m.model_id
                )
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
            tile.setStyleSheet(
                "background-color: #111; border: 1px solid #3E3E3E; color: #555;"
                "font-size: 11px;"
            )
            self._live_labels[camera_id] = tile
            row = (idx - 1) // cols
            col = (idx - 1) % cols
            self._live_grid.addWidget(tile, row, col)

            # Status label (in status group)
            st_lbl = QLabel()
            bind(st_lbl, "production.cam_offline", i=idx)
            st_lbl.setStyleSheet("color: #888;")
            self._cam_status_labels[camera_id] = st_lbl
            srow = (idx - 1) // 3
            scol = (idx - 1) % 3
            cs_layout.addWidget(st_lbl, srow, scol)

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def _start(self):
        model_id = self._model_combo.currentData()
        if not model_id:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_model"))
            return

        spec_id = self._ctx.current_spec_id
        if not spec_id:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_spec_first"))
            return

        spec = get_product_spec(spec_id)
        if spec is None:
            return

        model = get_model_version(model_id)
        if model is None:
            return
        self._active_model_version = model.model_id
        self._run_output_root = os.path.join(
            "outputs",
            spec.spec_id,
            f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )

        # --- Load camera configs from DB ---
        cfgs = list_camera_configs(spec_id)
        cfg_by_index: dict[int, CameraConfig] = {
            c.camera_index: c for c in cfgs if c.enabled
        }

        self._configured_adapters.clear()

        for idx in range(1, spec.camera_count + 1):
            camera_id = f"cam{idx}"
            cfg = cfg_by_index.get(idx)
            if cfg is None:
                # Auto-create default config based on adapter_type
                cfg = CameraConfig(
                    config_id="", spec_id=spec_id, camera_index=idx,
                    adapter_type="folder_watcher", connection_params="{}",
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
                    self, tr("app.error"),
                    tr("camera.connect_failed", cam=camera_id, err=str(e))
                )
                continue

        if not self._configured_adapters:
            QMessageBox.critical(self, tr("production.no_cameras"), tr("production.no_cameras_msg"))
            return

        # --- Setup encoder (simulated for now) ---
        self._encoder = SimulatedEncoderReader()
        self._encoder.connect({
            "line_speed_mpm": spec.target_speed_mpm,
            "pulses_per_meter": 1000.0,
        })
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

        # --- Setup inference runners ---
        try:
            from model_runners.yolo_runner import YoloModelRunner

            for cam_id in self._configured_adapters:
                runner = YoloModelRunner(
                    model_path=model.model_path,
                    config={"confidence": 0.5, "device": "cpu"},
                )
                runner.load()
                self._inference.set_runner(runner, camera_id=cam_id)
        except Exception as e:
            QMessageBox.critical(self, tr("production.model_load_failed"), str(e))
            return

        self._inference.set_on_ng(self._on_ng_detected)

        # --- Start ---
        self._acq.start()
        self._inference.start()
        self._timer.start(200)  # Refresh at 5 FPS

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
            camera_id, device, block_height=block_height,
        )

    def _stop(self):
        self._timer.stop()
        self._inference.stop()
        self._acq.stop()

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
        self._events.append({
            "time": evt.event_time,
            "camera": evt.camera_id,
            "defect_type": evt.defect_type,
            "dets": evt.detection_count,
            "position": evt.position_meter,
            "ng": True,
        })
        if len(self._ng_images) > 20:
            self._ng_images = self._ng_images[-20:]

    # ------------------------------------------------------------------
    # Display refresh (called by QTimer)
    # ------------------------------------------------------------------

    def _refresh_display(self):
        # --- Encoder position ---
        if self._encoder:
            try:
                pos = self._encoder.read_position_meter()
                bind(self._encoder_label, "production.encoder_position",
                     setter="setText", pos=f"{pos:.3f}")
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
                    lbl.setText(
                        f"{cid}  行频:{fps:.0f}Hz  行数:{frames}  连接:{conn}"
                    )
                else:
                    fps = st.get("fps", 0)
                    frames = st.get("frame_count", 0)
                    pos = st.get("encoder_position_m", 0.0)
                    lbl.setText(
                        tr("production.cam_status_fmt",
                           cam=cid, fps=f"{fps:.1f}",
                           frames=frames, pos=f"{pos:.2f}")
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
                    lbl.width(), lbl.height(),
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
                        self._ng_label.width(), self._ng_label.height(),
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
            self._event_table.setItem(row, 4, QTableWidgetItem(
                f"{pos_val:.3f}" if isinstance(pos_val, (int, float)) else str(pos_val or "")
            ))
            self._event_table.setItem(row, 5, QTableWidgetItem("NG" if evt.get("ng") else "OK"))
