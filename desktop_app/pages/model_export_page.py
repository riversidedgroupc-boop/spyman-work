"""Model export / acceleration page — ONNX and TensorRT export with environment detection."""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QPushButton,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QRadioButton,
    QButtonGroup,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QProgressBar,
    QMessageBox,
    QFileDialog,
)

from core.export_environment import detect_export_environment, ExportEnvironment
from core.model_export import list_export_artifacts, ModelExportArtifact
from core.model_version import list_model_versions
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, I18nManager
from desktop_app.workers.model_export_worker import ModelExportWorker
from desktop_app.theme_manager import ThemeManager


class ModelExportPage(QWidget):
    """Model export / acceleration UI for exporting YOLO models to ONNX/TensorRT."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._worker: ModelExportWorker | None = None
        self._env: ExportEnvironment = ExportEnvironment()
        self._build_ui()
        self._detect_env()
        self._refresh_models()
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    # ── UI Construction ──────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Environment ──────────────────────────────────────────
        env_group = QGroupBox(tr("export.environment"))
        env_form = QFormLayout(env_group)
        env_form.setSpacing(3)

        self._gpu_label = QLabel("—")
        env_form.addRow(tr("export.gpu") + ":", self._gpu_label)
        self._cuda_label = QLabel("—")
        env_form.addRow(tr("export.cuda") + ":", self._cuda_label)
        self._torch_label = QLabel("—")
        env_form.addRow(tr("export.pytorch") + ":", self._torch_label)
        self._ultralytics_label = QLabel("—")
        env_form.addRow(tr("export.ultralytics") + ":", self._ultralytics_label)
        self._tensorrt_label = QLabel("—")
        env_form.addRow(tr("export.tensorrt") + ":", self._tensorrt_label)

        layout.addWidget(env_group)

        # ── Export Configuration ─────────────────────────────────
        config_group = QGroupBox(tr("export.config"))
        config_form = QFormLayout(config_group)
        config_form.setSpacing(4)

        # Model version
        model_row = QHBoxLayout()
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(260)
        model_row.addWidget(self._model_combo, 1)
        self._refresh_model_btn = QPushButton(tr("export.refresh"))
        self._refresh_model_btn.clicked.connect(self._refresh_models)
        model_row.addWidget(self._refresh_model_btn)
        config_form.addRow(tr("export.model_version") + ":", model_row)

        # Backend
        backend_layout = QHBoxLayout()
        backend_layout.setSpacing(12)
        self._onnx_radio = QRadioButton("ONNX")
        self._tensorrt_radio = QRadioButton("TensorRT")
        self._backend_group = QButtonGroup(self)
        self._backend_group.addButton(self._onnx_radio, 0)
        self._backend_group.addButton(self._tensorrt_radio, 1)
        self._onnx_radio.setChecked(True)
        self._backend_group.buttonClicked.connect(self._on_backend_changed)
        backend_layout.addWidget(self._onnx_radio)
        backend_layout.addWidget(self._tensorrt_radio)
        backend_layout.addStretch()
        config_form.addRow(tr("export.backend") + ":", backend_layout)

        # Precision
        precision_layout = QHBoxLayout()
        precision_layout.setSpacing(12)
        self._fp32_radio = QRadioButton("FP32")
        self._fp16_radio = QRadioButton("FP16")
        self._int8_radio = QRadioButton("INT8")
        self._precision_group = QButtonGroup(self)
        self._precision_group.addButton(self._fp32_radio, 0)
        self._precision_group.addButton(self._fp16_radio, 1)
        self._precision_group.addButton(self._int8_radio, 2)
        self._fp32_radio.setChecked(True)
        self._precision_group.buttonClicked.connect(self._on_precision_changed)
        precision_layout.addWidget(self._fp32_radio)
        precision_layout.addWidget(self._fp16_radio)
        precision_layout.addWidget(self._int8_radio)
        precision_layout.addStretch()
        config_form.addRow(tr("export.precision") + ":", precision_layout)

        # Image size
        self._imgsz_spin = QSpinBox()
        self._imgsz_spin.setRange(320, 1280)
        self._imgsz_spin.setValue(640)
        self._imgsz_spin.setSingleStep(32)
        config_form.addRow(tr("export.image_size") + ":", self._imgsz_spin)

        # Workspace GB
        self._workspace_spin = QDoubleSpinBox()
        self._workspace_spin.setRange(1.0, 32.0)
        self._workspace_spin.setValue(4.0)
        self._workspace_spin.setSingleStep(1.0)
        config_form.addRow(tr("export.workspace_gb") + ":", self._workspace_spin)

        # Calibration dir
        calib_row = QHBoxLayout()
        self._calib_dir_edit = QLineEdit()
        self._calib_dir_edit.setPlaceholderText("...")
        calib_row.addWidget(self._calib_dir_edit, 1)
        self._browse_calib_btn = QPushButton(tr("export.browse_calibration"))
        self._browse_calib_btn.clicked.connect(self._on_browse_calib)
        calib_row.addWidget(self._browse_calib_btn)
        config_form.addRow(tr("export.calibration_dir") + ":", calib_row)

        layout.addWidget(config_group)

        # ── Action buttons ───────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self._export_onnx_btn = QPushButton(tr("export.export_onnx"))
        self._export_onnx_btn.clicked.connect(lambda: self._on_export("export_onnx"))
        btn_layout.addWidget(self._export_onnx_btn)

        self._export_trt_btn = QPushButton(tr("export.export_tensorrt"))
        self._export_trt_btn.clicked.connect(lambda: self._on_export("export_tensorrt"))
        btn_layout.addWidget(self._export_trt_btn)

        self._benchmark_btn = QPushButton(tr("export.benchmark"))
        self._benchmark_btn.clicked.connect(self._on_benchmark)
        btn_layout.addWidget(self._benchmark_btn)

        self._deploy_btn = QPushButton(tr("export.generate_package"))
        self._deploy_btn.setObjectName("primaryBtn")
        self._deploy_btn.clicked.connect(self._on_deploy)
        btn_layout.addWidget(self._deploy_btn)

        self._stop_btn = QPushButton(tr("export.stop"))
        self._stop_btn.setObjectName("dangerBtn")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_layout.addWidget(self._stop_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # ── Progress ─────────────────────────────────────────────
        progress_row = QHBoxLayout()
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        progress_row.addWidget(self._progress_bar, 1)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY};")
        progress_row.addWidget(self._status_label)
        layout.addLayout(progress_row)

        # ── Export Artifacts ─────────────────────────────────────
        artifacts_group = QGroupBox(tr("export.artifacts"))
        artifacts_layout = QVBoxLayout(artifacts_group)

        self._artifacts_table = QTableWidget(0, 7)
        self._artifacts_table.setHorizontalHeaderLabels(
            [
                tr("export.col_id"),
                tr("export.col_backend"),
                tr("export.col_precision"),
                tr("export.col_status"),
                tr("export.col_path"),
                tr("export.col_error"),
                tr("export.col_device"),
            ]
        )
        self._artifacts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._artifacts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._artifacts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hh = self._artifacts_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        artifacts_layout.addWidget(self._artifacts_table)
        layout.addWidget(artifacts_group, 1)

        # ── Update guard states ──────────────────────────────────
        self._update_guard_states()

    def _refresh_text(self, lang: str = "") -> None:
        pass  # Bound via tr() at construction

    # ── Events ──────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_models()
        self._refresh_artifacts()

    # ── Environment detection ───────────────────────────────────

    def _detect_env(self) -> None:
        self._env = detect_export_environment()
        self._gpu_label.setText(self._env.gpu_name or tr("export.not_available"))
        if self._env.cuda_available and self._env.cuda_version:
            self._cuda_label.setText(self._env.cuda_version)
        else:
            self._cuda_label.setText(tr("export.not_available"))
        self._torch_label.setText(self._env.torch_version or tr("export.not_available"))
        self._ultralytics_label.setText(self._env.ultralytics_version or tr("export.not_available"))
        if self._env.tensorrt_available:
            self._tensorrt_label.setText(self._env.tensorrt_version or tr("export.not_available"))
        else:
            self._tensorrt_label.setText(tr("export.not_available"))

        self._tensorrt_radio.setEnabled(self._env.tensorrt_available)
        if not self._env.tensorrt_available:
            self._tensorrt_radio.setToolTip(tr("export.tensorrt_unavailable"))

    # ── Model refresh ───────────────────────────────────────────

    def _get_project_id(self) -> str:
        return self._ctx.current_project_id

    def _refresh_models(self) -> None:
        self._model_combo.clear()
        self._model_combo.addItem("", "")
        pid = self._get_project_id()
        if not pid:
            self._update_guard_states()
            return
        models = list_model_versions(project_id=pid)
        for mv in models:
            if mv.model_type == "yolo" and mv.model_path:
                label = f"{mv.model_name} ({mv.model_id})"
                self._model_combo.addItem(label, mv.model_id)
        self._update_guard_states()

    # ── Artifact refresh ────────────────────────────────────────

    def _refresh_artifacts(self) -> None:
        pid = self._get_project_id()
        if not pid:
            self._artifacts_table.setRowCount(0)
            return
        artifacts = list_export_artifacts(project_id=pid)
        self._populate_artifact_table(artifacts)

    def _status_display(self, status: str) -> str:
        """Translate status to display string, falling back to raw status."""
        key = f"export.status_{status}"
        text = tr(key)
        return status if text == key else text

    def _populate_artifact_table(self, artifacts: list[ModelExportArtifact]) -> None:
        self._artifacts_table.setRowCount(len(artifacts))
        for i, a in enumerate(artifacts):
            self._artifacts_table.setItem(i, 0, QTableWidgetItem(a.export_id))
            self._artifacts_table.setItem(i, 1, QTableWidgetItem(a.backend))
            self._artifacts_table.setItem(i, 2, QTableWidgetItem(a.precision))
            self._artifacts_table.setItem(i, 3, QTableWidgetItem(self._status_display(a.status)))
            self._artifacts_table.setItem(i, 4, QTableWidgetItem(a.artifact_path))
            self._artifacts_table.setItem(i, 5, QTableWidgetItem(a.error_message))
            self._artifacts_table.setItem(i, 6, QTableWidgetItem(a.device_name))

    # ── Guard state management ──────────────────────────────────

    def _update_guard_states(self) -> None:
        has_project = bool(self._get_project_id())
        has_model = bool(self._model_combo.currentData())
        tensorrt_ok = self._env.tensorrt_available
        running = self._worker is not None and self._worker.isRunning()

        if running:
            self._set_config_enabled(False)
            self._stop_btn.setEnabled(True)
            return

        self._stop_btn.setEnabled(False)
        self._set_config_enabled(has_project)

        self._export_onnx_btn.setEnabled(has_project and has_model)
        self._export_trt_btn.setEnabled(
            has_project
            and has_model
            and tensorrt_ok
            and not (self._int8_radio.isChecked() and not self._calib_dir_edit.text().strip())
        )
        self._benchmark_btn.setEnabled(has_project)
        self._deploy_btn.setEnabled(has_project)

        # INT8 requires calibration dir and TensorRT
        if self._int8_radio.isChecked():
            has_calib = bool(self._calib_dir_edit.text().strip())
            if not has_calib:
                self._export_onnx_btn.setEnabled(False)
                self._export_trt_btn.setEnabled(False)

    def _set_config_enabled(self, enabled: bool) -> None:
        self._model_combo.setEnabled(enabled)
        self._refresh_model_btn.setEnabled(enabled)
        self._onnx_radio.setEnabled(enabled)
        self._tensorrt_radio.setEnabled(enabled and self._env.tensorrt_available)
        self._fp32_radio.setEnabled(enabled)
        self._fp16_radio.setEnabled(enabled)
        self._int8_radio.setEnabled(enabled)
        self._imgsz_spin.setEnabled(enabled)
        self._workspace_spin.setEnabled(enabled)
        self._calib_dir_edit.setEnabled(enabled)
        self._browse_calib_btn.setEnabled(enabled)
        self._export_onnx_btn.setEnabled(enabled)
        self._export_trt_btn.setEnabled(enabled)
        self._benchmark_btn.setEnabled(enabled)
        self._deploy_btn.setEnabled(enabled)

    # ── Callback: backend / precision change ────────────────────

    def _on_backend_changed(self) -> None:
        self._update_guard_states()

    def _on_precision_changed(self) -> None:
        calib_needed = self._int8_radio.isChecked()
        self._calib_dir_edit.setEnabled(calib_needed)
        self._browse_calib_btn.setEnabled(calib_needed)
        self._update_guard_states()

    # ── Browse calibration dir ──────────────────────────────────

    def _on_browse_calib(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("export.select_calibration_dir"))
        if d:
            self._calib_dir_edit.setText(d)
            self._update_guard_states()

    # ── Export actions ──────────────────────────────────────────

    def _on_export(self, task_type: str) -> None:
        pid = self._get_project_id()
        if not pid:
            QMessageBox.information(self, tr("app.tip"), tr("export.no_project"))
            return
        model_id = self._model_combo.currentData()
        if not model_id:
            QMessageBox.warning(self, tr("app.warning"), tr("export.no_model"))
            return

        if task_type == "export_tensorrt" and not self._env.tensorrt_available:
            QMessageBox.warning(self, tr("app.warning"), tr("export.tensorrt_unavailable"))
            return

        if self._int8_radio.isChecked() and not self._calib_dir_edit.text().strip():
            QMessageBox.warning(self, tr("app.warning"), tr("export.int8_needs_calibration"))
            return

        precision = self._get_selected_precision()
        output_dir = self._get_output_dir()

        config: dict = {
            "model_id": model_id,
            "output_dir": output_dir,
            "imgsz": self._imgsz_spin.value(),
            "precision": precision,
            "workspace_gb": int(self._workspace_spin.value()),
            "calibration_dir": self._calib_dir_edit.text().strip(),
        }

        self._worker = ModelExportWorker(task_type, config)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._set_running(True)
        self._status_label.setText(tr("export.status_running"))
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._worker.start()

    def _on_benchmark(self) -> None:
        QMessageBox.information(self, tr("app.tip"), tr("export.coming_soon"))

    def _on_deploy(self) -> None:
        QMessageBox.information(self, tr("app.tip"), tr("export.coming_soon"))

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._status_label.setText("")

    def _set_running(self, running: bool) -> None:
        self._stop_btn.setEnabled(running)
        self._model_combo.setEnabled(not running)
        self._refresh_model_btn.setEnabled(not running)
        self._onnx_radio.setEnabled(not running)
        self._tensorrt_radio.setEnabled(not running and self._env.tensorrt_available)
        self._fp32_radio.setEnabled(not running)
        self._fp16_radio.setEnabled(not running)
        self._int8_radio.setEnabled(not running)
        self._imgsz_spin.setEnabled(not running)
        self._workspace_spin.setEnabled(not running)
        self._calib_dir_edit.setEnabled(not running)
        self._browse_calib_btn.setEnabled(not running)
        self._export_onnx_btn.setEnabled(not running)
        self._export_trt_btn.setEnabled(not running)
        self._benchmark_btn.setEnabled(not running)
        self._deploy_btn.setEnabled(not running)

    # ── Helpers ─────────────────────────────────────────────────

    def _get_selected_precision(self) -> str:
        precision_map = {0: "fp32", 1: "fp16", 2: "int8"}
        return precision_map[self._precision_group.checkedId()]

    def _get_output_dir(self) -> str:
        import tempfile

        pid = self._get_project_id()
        return os.path.join(tempfile.gettempdir(), "copper_exports", pid)

    # ── Worker callbacks ────────────────────────────────────────

    def _on_progress(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _on_finished(self, result: object) -> None:
        self._set_running(False)
        self._progress_bar.setVisible(False)
        if result is not None:
            status = getattr(result, "status", "")
            self._status_label.setText(self._status_display(status))
        else:
            self._status_label.setText("")
        self._refresh_artifacts()

    def _on_error(self, err: str) -> None:
        self._set_running(False)
        self._progress_bar.setVisible(False)
        self._status_label.setText(tr("export.status_failed"))
        self._refresh_artifacts()
        QMessageBox.critical(self, tr("app.error"), err)

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._status_label.setStyleSheet(f"color: {c.TEXT_SECONDARY};")

