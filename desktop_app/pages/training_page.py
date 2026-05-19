"""Training page — dataset preparation and YOLO training configuration."""
from __future__ import annotations

import json, os
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QSpinBox, QPushButton, QLabel,
    QMessageBox, QProgressBar, QLineEdit,
)

from core.capture_session import list_capture_sessions, session_output_root, get_capture_session
from core.dataset_builder import build_yolo_dataset_from_session
from core.training_job import create_training_job
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.workers.training_worker import TrainingWorker


class TrainingPage(QWidget):
    data_changed = Signal()
    FIELD_WIDTH = 460

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._worker: TrainingWorker | None = None
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        ds_group = QGroupBox()
        bind(ds_group, "training.dataset_group", setter="setTitle")
        ds_form = QFormLayout(ds_group)
        ds_source_label = QLabel()
        bind(ds_source_label, "training.dataset_source")
        self._session_combo = QComboBox()
        self._set_field_width(self._session_combo)
        ds_form.addRow(ds_source_label, self._session_combo)
        refresh_btn = QPushButton()
        bind(refresh_btn, "app.refresh")
        self._set_field_width(refresh_btn)
        refresh_btn.clicked.connect(self._refresh_sessions)
        ds_form.addRow("", refresh_btn)
        self._ds_path_label = QLabel()
        bind(self._ds_path_label, "app.not_selected")
        self._ds_path_label.setStyleSheet("color: #888;")
        ds_path_label = QLabel()
        bind(ds_path_label, "training.dataset_path")
        ds_form.addRow(ds_path_label, self._ds_path_label)
        layout.addWidget(ds_group)

        tr_group = QGroupBox()
        bind(tr_group, "training.param_group", setter="setTitle")
        tr_form = QFormLayout(tr_group)
        base_model_label = QLabel()
        bind(base_model_label, "training.base_model")
        self._model_combo = QComboBox()
        self._model_combo.addItems(["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt"])
        self._set_field_width(self._model_combo)
        tr_form.addRow(base_model_label, self._model_combo)
        epochs_label = QLabel()
        bind(epochs_label, "training.epochs")
        self._epochs_spin = QSpinBox(); self._epochs_spin.setRange(1, 1000); self._epochs_spin.setValue(100)
        self._set_field_width(self._epochs_spin)
        tr_form.addRow(epochs_label, self._epochs_spin)
        imgsz_label = QLabel()
        bind(imgsz_label, "training.imgsz")
        self._imgsz_spin = QSpinBox(); self._imgsz_spin.setRange(320, 1920); self._imgsz_spin.setSingleStep(32); self._imgsz_spin.setValue(640)
        self._set_field_width(self._imgsz_spin)
        tr_form.addRow(imgsz_label, self._imgsz_spin)
        batch_label = QLabel()
        bind(batch_label, "training.batch")
        self._batch_spin = QSpinBox(); self._batch_spin.setRange(1, 128); self._batch_spin.setValue(8)
        self._set_field_width(self._batch_spin)
        tr_form.addRow(batch_label, self._batch_spin)
        device_label = QLabel()
        bind(device_label, "training.device")
        self._device_combo = QComboBox(); self._device_combo.addItems(["cpu", "cuda:0"])
        self._set_field_width(self._device_combo)
        tr_form.addRow(device_label, self._device_combo)
        job_name_label = QLabel()
        bind(job_name_label, "training.job_name")
        self._job_name_edit = QLineEdit(); self._job_name_edit.setPlaceholderText(tr("training.job_name_placeholder"))
        self._set_field_width(self._job_name_edit)
        tr_form.addRow(job_name_label, self._job_name_edit)
        layout.addWidget(tr_group)

        self._progress = QProgressBar(); self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._status_label = QLabel(""); self._status_label.setStyleSheet("color: #888;")
        layout.addWidget(self._status_label)

        btn_layout = QHBoxLayout()
        self._start_btn = QPushButton()
        bind(self._start_btn, "training.start")
        self._start_btn.clicked.connect(self._start_training)
        btn_layout.addWidget(self._start_btn)
        self._stop_btn = QPushButton()
        bind(self._stop_btn, "training.stop")
        self._stop_btn.setObjectName("dangerBtn"); self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_training)
        btn_layout.addWidget(self._stop_btn); btn_layout.addStretch()
        layout.addLayout(btn_layout); layout.addStretch()

    def _set_field_width(self, widget) -> None:
        widget.setFixedWidth(self.FIELD_WIDTH)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set combo placeholder on language change."""
        self._refresh_sessions()

    def showEvent(self, event):
        super().showEvent(event); self._refresh_sessions()

    def _refresh_sessions(self):
        self._session_combo.clear(); self._session_combo.addItem(tr("classify.select_session"), "")
        pid = self._ctx.current_project_id
        if pid:
            for s in list_capture_sessions(pid):
                self._session_combo.addItem(s.session_name, s.session_id)

    def _start_training(self):
        pid = self._ctx.current_project_id
        if not pid: QMessageBox.information(self, tr("app.tip"), tr("app.select_project")); return
        sid = self._session_combo.currentData()
        if not sid: QMessageBox.information(self, tr("app.tip"), tr("app.select_session")); return
        sess = get_capture_session(sid)
        if not sess: return
        output_root = sess.output_dir or session_output_root(pid)
        job_name = self._job_name_edit.text().strip() or f"train_{sid[:12]}"
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        dataset_dir = os.path.join(output_root, sid, "dataset_yolo")
        try:
            dataset = build_yolo_dataset_from_session(sid, dataset_dir)
        except Exception as e:
            QMessageBox.warning(self, tr("app.error"), str(e))
            return
        if dataset.missing_bbox_count:
            QMessageBox.warning(
                self,
                tr("app.warning"),
                f"{dataset.missing_bbox_count} 张 NG 图片缺少 YOLO bbox 标注，训练将只把它们作为背景样本处理。",
            )
        output_dir = os.path.join("outputs", "train", f"{job_name}_{date_str}")
        job = create_training_job(
            project_id=pid, spec_id=self._ctx.current_spec_id or "",
            job_name=job_name, dataset_path=dataset.dataset_dir,
            base_model=self._model_combo.currentText(),
            training_config=json.dumps({"epochs": self._epochs_spin.value(), "imgsz": self._imgsz_spin.value(), "batch": self._batch_spin.value(), "device": self._device_combo.currentText()}),
            output_dir=output_dir,
        )
        self._worker = TrainingWorker(
            job_id=job.job_id, dataset_yaml=dataset.yaml_path,
            base_model=self._model_combo.currentText(), epochs=self._epochs_spin.value(),
            imgsz=self._imgsz_spin.value(), batch=self._batch_spin.value(),
            device=self._device_combo.currentText(), output_dir=output_dir,
        )
        self._worker.message.connect(self._on_message)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._progress.setVisible(True); self._progress.setMaximum(0)
        self._start_btn.setEnabled(False); self._stop_btn.setEnabled(True)
        self._worker.start()

    def _stop_training(self):
        if self._worker and self._worker.isRunning(): self._worker.cancel(); self._worker.wait(3000)

    def _on_message(self, msg): self._status_label.setText(msg)

    def _on_finished(self):
        self._progress.setVisible(False); self._start_btn.setEnabled(True); self._stop_btn.setEnabled(False)
        bind(self._status_label, "training.complete_label"); self.data_changed.emit()

    def _on_error(self, err):
        self._progress.setVisible(False); self._start_btn.setEnabled(True); self._stop_btn.setEnabled(False)
        QMessageBox.critical(self, tr("training.error_title"), err)
