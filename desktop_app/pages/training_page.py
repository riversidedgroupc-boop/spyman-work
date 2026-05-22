"""Training page — dataset preparation and YOLO training configuration."""
from __future__ import annotations

import json
import os
from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.capture_session import list_capture_sessions, session_output_root, get_capture_session, get_session_task_type
from core.dataset_builder import build_yolo_dataset_from_session
from core.dataset_version import list_dataset_versions, get_dataset_version
from core.training_job import create_training_job
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.workers.training_worker import TrainingWorker


def yolo_missing_bbox_message(missing_bbox_count: int) -> str:
    return (
        f"{missing_bbox_count} 张 NG 图片缺少 YOLO bbox 标注。\n\n"
        "已停止训练：YOLO 检测训练需要缺陷框坐标，不能只使用整图标签。"
        "如果继续把这些 NG 图写成空标签，模型会把缺陷区域当成背景样本学习，"
        "训练结果会失真。\n\n"
        "请先为 NG 图片补充 YOLO bbox 标注，或改用整图分类训练流程。"
    )


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
        self._session_combo.currentIndexChanged.connect(self._on_session_selected)
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

        # Task type display
        self._task_type_label = QLabel("")
        self._task_type_label.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 12px; padding: 4px 0;")
        ds_form.addRow(QLabel("任务类型:"), self._task_type_label)

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
        self._epochs_spin = QSpinBox()
        self._epochs_spin.setRange(1, 1000)
        self._epochs_spin.setValue(100)
        self._set_field_width(self._epochs_spin)
        tr_form.addRow(epochs_label, self._epochs_spin)
        imgsz_label = QLabel()
        bind(imgsz_label, "training.imgsz")
        self._imgsz_spin = QSpinBox()
        self._imgsz_spin.setRange(320, 1920)
        self._imgsz_spin.setSingleStep(32)
        self._imgsz_spin.setValue(640)
        self._set_field_width(self._imgsz_spin)
        tr_form.addRow(imgsz_label, self._imgsz_spin)
        batch_label = QLabel()
        bind(batch_label, "training.batch")
        self._batch_spin = QSpinBox()
        self._batch_spin.setRange(1, 128)
        self._batch_spin.setValue(8)
        self._set_field_width(self._batch_spin)
        tr_form.addRow(batch_label, self._batch_spin)
        device_label = QLabel()
        bind(device_label, "training.device")
        self._device_combo = QComboBox()
        self._device_combo.addItems(["cpu", "cuda:0"])
        self._set_field_width(self._device_combo)
        tr_form.addRow(device_label, self._device_combo)
        job_name_label = QLabel()
        bind(job_name_label, "training.job_name")
        self._job_name_edit = QLineEdit()
        self._job_name_edit.setPlaceholderText(tr("training.job_name_placeholder"))
        self._set_field_width(self._job_name_edit)
        tr_form.addRow(job_name_label, self._job_name_edit)
        layout.addWidget(tr_group)

        # ── Task-type-specific parameter placeholders ──
        self._cls_placeholder = QLabel(
            "整图分类训练暂未实现。\n\n请使用「样本集版本」页面生成分类数据集，"
            "然后通过 CLI 或后续版本进行训练。"
        )
        self._cls_placeholder.setStyleSheet(
            "color: #888; font-size: 13px; padding: 24px; "
            "background: #1a1a1a; border-radius: 4px;"
        )
        self._cls_placeholder.setWordWrap(True)
        self._cls_placeholder.hide()
        layout.addWidget(self._cls_placeholder)

        self._anomaly_placeholder = QLabel(
            "异常检测训练暂未实现。\n\n请使用「样本集版本」页面生成异常检测数据集，"
            "然后通过 CLI 或后续版本进行训练。"
        )
        self._anomaly_placeholder.setStyleSheet(
            "color: #888; font-size: 13px; padding: 24px; "
            "background: #1a1a1a; border-radius: 4px;"
        )
        self._anomaly_placeholder.setWordWrap(True)
        self._anomaly_placeholder.hide()
        layout.addWidget(self._anomaly_placeholder)

        monitor_group = QGroupBox("训练监控")
        monitor_layout = QVBoxLayout(monitor_group)
        monitor_grid = QGridLayout()
        self._monitor_state = QLabel("空闲")
        self._monitor_state.setStyleSheet("color: #888; font-weight: bold;")
        self._monitor_job = QLabel("-")
        self._monitor_epoch = QLabel("0/0")
        self._monitor_message = QLabel("未开始训练")
        self._monitor_message.setStyleSheet("color: #888;")
        monitor_grid.addWidget(QLabel("状态:"), 0, 0)
        monitor_grid.addWidget(self._monitor_state, 0, 1)
        monitor_grid.addWidget(QLabel("任务:"), 0, 2)
        monitor_grid.addWidget(self._monitor_job, 0, 3)
        monitor_grid.addWidget(QLabel("Epoch:"), 1, 0)
        monitor_grid.addWidget(self._monitor_epoch, 1, 1)
        monitor_grid.addWidget(QLabel("信息:"), 1, 2)
        monitor_grid.addWidget(self._monitor_message, 1, 3)
        monitor_layout.addLayout(monitor_grid)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        monitor_layout.addWidget(self._progress)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumHeight(160)
        self._log_view.setPlaceholderText("训练日志会显示在这里")
        monitor_layout.addWidget(self._log_view)
        layout.addWidget(monitor_group)

        btn_layout = QHBoxLayout()
        self._start_btn = QPushButton()
        bind(self._start_btn, "training.start")
        self._start_btn.clicked.connect(self._start_training)
        btn_layout.addWidget(self._start_btn)
        self._stop_btn = QPushButton()
        bind(self._stop_btn, "training.stop")
        self._stop_btn.setObjectName("dangerBtn")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_training)
        btn_layout.addWidget(self._stop_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()

    def _set_field_width(self, widget) -> None:
        widget.setFixedWidth(self.FIELD_WIDTH)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set combo placeholder on language change."""
        self._refresh_sessions()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_sessions()

    def _refresh_sessions(self):
        self._session_combo.clear()
        self._session_combo.addItem(tr("classify.select_session"), "")
        pid = self._ctx.current_project_id
        if pid:
            for s in list_capture_sessions(pid):
                self._session_combo.addItem(s.session_name, s.session_id)
            # Phase C: also list field_reviews dataset versions
            for dv in list_dataset_versions(project_id=pid):
                if dv.source_type == "field_reviews":
                    self._session_combo.addItem(
                        f"[现场首训] {dv.version_name or dv.version_id}", dv.version_id
                    )

    def _on_session_selected(self, _index: int) -> None:
        """When a data source is selected, read its type and update UI."""
        sid = self._session_combo.currentData()
        if not sid:
            self._task_type_label.setText("")
            self._show_yolo_params(True)
            self._cls_placeholder.hide()
            self._anomaly_placeholder.hide()
            return

        # Phase C: dataset_version entries
        is_dataset_version = isinstance(sid, str) and sid.startswith("DSVER_")
        if is_dataset_version:
            self._task_type_label.setText("YOLO 检测 (现场首训)")
            self._show_yolo_params(True)
            self._cls_placeholder.hide()
            self._anomaly_placeholder.hide()
            self._start_btn.setEnabled(True)
            self._start_btn.setToolTip("")
            # Show dataset path from version record
            dv = get_dataset_version(sid)
            if dv:
                self._ds_path_label.setText(dv.yaml_path or dv.dataset_path)
            return

        task_type = get_session_task_type(sid) or "yolo_detection"  # default to YOLO for backward compat

        type_names = {
            "yolo_detection": "YOLO 检测",
            "image_classification": "整图分类",
            "anomaly_detection": "异常检测",
        }
        self._task_type_label.setText(type_names.get(task_type, task_type))

        # Show/hide appropriate parameter panels
        is_yolo = task_type in ("yolo_detection", "")
        self._show_yolo_params(is_yolo)
        self._cls_placeholder.setVisible(task_type == "image_classification")
        self._anomaly_placeholder.setVisible(task_type == "anomaly_detection")

        # Enable/disable start button based on task type
        if task_type == "image_classification":
            self._start_btn.setEnabled(False)
            self._start_btn.setToolTip("整图分类训练暂未实现")
        elif task_type == "anomaly_detection":
            self._start_btn.setEnabled(False)
            self._start_btn.setToolTip("异常检测训练暂未实现")
        else:
            self._start_btn.setEnabled(True)
            self._start_btn.setToolTip("")

    def _show_yolo_params(self, visible: bool) -> None:
        """Show or hide YOLO-specific training parameter widgets."""
        # The tr_group contains base model, epochs, imgsz, batch, device, job name
        # Find the group box that contains YOLO params (second group box in layout)
        tr_group = None
        for i in range(self.layout().count()):
            w = self.layout().itemAt(i).widget()
            if isinstance(w, QGroupBox):
                title = w.title()
                if title in (tr("training.param_group"), "训练参数", "Training Parameters"):
                    tr_group = w
                    break
        if tr_group:
            tr_group.setVisible(visible)
        # Also hide/show monitor group which is YOLO-specific
        for i in range(self.layout().count()):
            w = self.layout().itemAt(i).widget()
            if isinstance(w, QGroupBox) and w.title() in ("训练监控", "Training Monitor"):
                w.setVisible(visible)
                break

    def _start_training(self):
        pid = self._ctx.current_project_id
        if not pid:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_project"))
            return
        sid = self._session_combo.currentData()
        if not sid:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_session"))
            return

        is_dataset_version = isinstance(sid, str) and sid.startswith("DSVER_")

        # ── Phase C: field_reviews dataset ──────────────────────────
        if is_dataset_version:
            dv = get_dataset_version(sid)
            if not dv:
                QMessageBox.warning(self, tr("app.error"), "数据集版本未找到")
                return
            if not dv.yaml_path or not os.path.isfile(dv.yaml_path):
                QMessageBox.warning(self, tr("app.error"), "数据集 YAML 路径无效")
                return

            job_name = self._job_name_edit.text().strip() or f"train_field_{dv.version_id[:20]}"
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join("outputs", "train", f"{job_name}_{date_str}")

            # Parse class_mapping from class_names JSON
            class_mapping: dict[str, int] = {}
            try:
                class_names_list = json.loads(dv.class_names) if dv.class_names else []
                for idx, name in enumerate(class_names_list):
                    class_mapping[name] = idx
            except (json.JSONDecodeError, TypeError):
                class_mapping = {}

            training_config = {
                "epochs": self._epochs_spin.value(),
                "imgsz": self._imgsz_spin.value(),
                "batch": self._batch_spin.value(),
                "device": self._device_combo.currentText(),
                "source_type": "field_reviews",
                "dataset_version_id": dv.version_id,
            }
            job = create_training_job(
                project_id=pid, spec_id=self._ctx.current_spec_id or "",
                job_name=job_name, dataset_path=dv.dataset_path,
                base_model=self._model_combo.currentText(),
                training_config=json.dumps(training_config),
            )
            self._worker = TrainingWorker(
                job_id=job.job_id, dataset_yaml=dv.yaml_path,
                base_model=self._model_combo.currentText(),
                epochs=self._epochs_spin.value(),
                imgsz=self._imgsz_spin.value(), batch=self._batch_spin.value(),
                device=self._device_combo.currentText(), output_dir=output_dir,
                dataset_version_id=dv.version_id,
                class_mapping=class_mapping,
                spec_id=self._ctx.current_spec_id or "",
            )
            self._worker.message.connect(self._on_message)
            self._worker.progress.connect(self._on_progress)
            self._worker.log_line.connect(self._append_log_line)
            self._worker.finished.connect(self._on_finished)
            self._worker.error.connect(self._on_error)
            self._monitor_state.setText("训练中")
            self._monitor_state.setStyleSheet("color: #ff9800; font-weight: bold;")
            self._monitor_job.setText(f"{job.job_name} ({job.job_id})")
            self._monitor_epoch.setText(f"0/{self._epochs_spin.value()}")
            self._monitor_message.setText("准备启动训练 (现场首训)")
            self._log_view.clear()
            self._progress.setRange(0, 100)
            self._progress.setValue(0)
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
            self._worker.start()
            return

        # ── Existing flow: capture_session ──────────────────────────
        sess = get_capture_session(sid)
        if not sess:
            return

        task_type = get_session_task_type(sid) or "yolo_detection"

        # Dispatch based on task type
        if task_type == "image_classification":
            QMessageBox.information(
                self, tr("app.tip"),
                "整图分类训练暂未实现。请使用「样本集版本」页面生成分类数据集。"
            )
            return
        if task_type == "anomaly_detection":
            QMessageBox.information(
                self, tr("app.tip"),
                "异常检测训练暂未实现。请使用「样本集版本」页面生成异常检测数据集。"
            )
            return

        # YOLO detection training (existing flow)
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
            QMessageBox.critical(
                self,
                tr("app.warning"),
                yolo_missing_bbox_message(dataset.missing_bbox_count),
            )
            return
        output_dir = os.path.join("outputs", "train", f"{job_name}_{date_str}")
        job = create_training_job(
            project_id=pid, spec_id=self._ctx.current_spec_id or "",
            job_name=job_name, dataset_path=dataset.dataset_dir,
            base_model=self._model_combo.currentText(),
            training_config=json.dumps({"epochs": self._epochs_spin.value(), "imgsz": self._imgsz_spin.value(), "batch": self._batch_spin.value(), "device": self._device_combo.currentText()}),
        )
        self._worker = TrainingWorker(
            job_id=job.job_id, dataset_yaml=dataset.yaml_path,
            base_model=self._model_combo.currentText(), epochs=self._epochs_spin.value(),
            imgsz=self._imgsz_spin.value(), batch=self._batch_spin.value(),
            device=self._device_combo.currentText(), output_dir=output_dir,
        )
        self._worker.message.connect(self._on_message)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_line.connect(self._append_log_line)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._monitor_state.setText("训练中")
        self._monitor_state.setStyleSheet("color: #ff9800; font-weight: bold;")
        self._monitor_job.setText(f"{job.job_name} ({job.job_id})")
        self._monitor_epoch.setText(f"0/{self._epochs_spin.value()}")
        self._monitor_message.setText("准备启动训练")
        self._log_view.clear()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._worker.start()

    def _stop_training(self):
        if self._worker and self._worker.isRunning():
            self._monitor_state.setText("停止中")
            self._monitor_state.setStyleSheet("color: #ff9800; font-weight: bold;")
            self._monitor_message.setText("已请求停止，等待训练进程退出")
            self._worker.cancel()
            self._worker.wait(3000)

    def _on_message(self, msg):
        self._monitor_message.setText(msg)

    def _on_progress(self, current: int, total: int) -> None:
        self._monitor_epoch.setText(f"{current}/{total}")
        percent = int(current * 100 / total) if total else 0
        self._progress.setValue(max(0, min(percent, 100)))

    def _append_log_line(self, line: str) -> None:
        self._log_view.append(line)
        self._log_view.ensureCursorVisible()

    def _on_finished(self):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        if self._progress.value() >= 100:
            self._monitor_state.setText("已完成")
            self._monitor_state.setStyleSheet("color: #4caf50; font-weight: bold;")
            self._monitor_message.setText(tr("training.complete_label"))
        elif self._monitor_state.text() == "停止中":
            self._monitor_state.setText("已停止")
            self._monitor_state.setStyleSheet("color: #888; font-weight: bold;")
        self.data_changed.emit()

    def _on_error(self, err):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._monitor_state.setText("失败")
        self._monitor_state.setStyleSheet("color: #f44336; font-weight: bold;")
        self._monitor_message.setText(err)
        self._append_log_line(f"ERROR: {err}")
        QMessageBox.critical(self, tr("training.error_title"), err)
