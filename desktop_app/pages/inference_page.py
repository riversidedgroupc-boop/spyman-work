"""Inference page — run model inference on images and view results."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QComboBox,
    QLabel,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QFileDialog,
)

from core.model_version import list_model_versions, get_model_version
from desktop_app.app_context import AppContext
from desktop_app.display import model_type_label
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.workers.inference_worker import InferenceWorker
from desktop_app.widgets.defect_overlay_view import DefectOverlayView
from desktop_app.theme_manager import ThemeManager


class InferencePage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._worker: InferenceWorker | None = None
        self._image_paths: list[str] = []
        self._current_index = -1
        self._predictions: dict[str, object] = {}
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        model_label = QLabel()
        bind(model_label, "inference.model")
        top.addWidget(model_label)
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(200)
        top.addWidget(self._model_combo)
        img_dir_label = QLabel()
        bind(img_dir_label, "inference.image_dir")
        top.addWidget(img_dir_label)
        self._dir_label = QLabel()
        bind(self._dir_label, "app.not_selected")
        self._dir_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY};")
        top.addWidget(self._dir_label)
        browse_btn = QPushButton()
        bind(browse_btn, "inference.select_dir")
        browse_btn.clicked.connect(self._browse_dir)
        top.addWidget(browse_btn)
        run_btn = QPushButton()
        bind(run_btn, "inference.run")
        run_btn.clicked.connect(self._run_inference)
        top.addWidget(run_btn)
        top.addStretch()
        layout.addLayout(top)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._viewer = DefectOverlayView()
        splitter.addWidget(self._viewer)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        nav = QHBoxLayout()
        prev_btn = QPushButton()
        bind(prev_btn, "inference.prev")
        prev_btn.clicked.connect(lambda: self._navigate(-1))
        nav.addWidget(prev_btn)
        next_btn = QPushButton()
        bind(next_btn, "inference.next")
        next_btn.clicked.connect(lambda: self._navigate(1))
        nav.addWidget(next_btn)
        self._pos_label = QLabel()
        bind(self._pos_label, "inference.position", current=0, total=0)
        nav.addWidget(self._pos_label)
        nav.addStretch()
        right_layout.addLayout(nav)

        self._det_table = QTableWidget(0, 4)
        self._det_table.setHorizontalHeaderLabels(
            [
                tr("inference.col_class"),
                tr("inference.col_conf"),
                tr("inference.col_bbox"),
                tr("inference.col_area"),
            ]
        )
        self._det_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right_layout.addWidget(self._det_table, 1)
        splitter.addWidget(right)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter, 1)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set table headers and combo placeholder on language change."""
        self._det_table.setHorizontalHeaderLabels(
            [
                tr("inference.col_class"),
                tr("inference.col_conf"),
                tr("inference.col_bbox"),
                tr("inference.col_area"),
            ]
        )
        self._refresh_models()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_models()

    def _refresh_models(self):
        self._model_combo.clear()
        self._model_combo.addItem(tr("app.select_model"), "")
        pid = self._ctx.current_project_id
        if pid:
            for m in list_model_versions(pid):
                self._model_combo.addItem(
                    f"{m.model_name} ({model_type_label(m.model_type)})", m.model_id
                )

    def _browse_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, tr("dialog.select_image_dir"))
        if not dir_path:
            return
        self._dir_label.setText(dir_path)
        exts = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        self._image_paths = sorted(
            [
                os.path.join(dir_path, f)
                for f in os.listdir(dir_path)
                if os.path.splitext(f)[1].lower() in exts
            ]
        )
        self._predictions.clear()
        bind(self._pos_label, "inference.position", current=0, total=len(self._image_paths))
        if self._image_paths:
            self._current_index = 0
            self._viewer.load_image(self._image_paths[0])
            self._viewer.clear_detections()

    def _run_inference(self):
        model_id = self._model_combo.currentData()
        if not model_id:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_model"))
            return
        if not self._image_paths:
            QMessageBox.information(self, tr("app.tip"), tr("inference.select_image_dir_first"))
            return
        model = get_model_version(model_id)
        if not model or not model.model_path:
            QMessageBox.warning(self, tr("app.error"), tr("inference.model_path_empty"))
            return

        self._worker = InferenceWorker(
            model_path=model.model_path,
            image_paths=self._image_paths,
            model_type=model.model_type,
            confidence=0.25,
        )
        self._worker.progress.connect(lambda c, t: self._progress.setValue(c))
        self._worker.result_ready.connect(self._on_result)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._predictions.clear()
        self._progress.setVisible(True)
        self._progress.setMaximum(len(self._image_paths))
        self._worker.start()

    def _on_result(self, image_path, prediction):
        self._predictions[image_path] = prediction
        if self._current_index >= 0 and image_path == self._image_paths[self._current_index]:
            self._show_prediction(prediction)

    def _on_finished(self):
        self._progress.setVisible(False)
        if self._image_paths and self._current_index >= 0:
            self._show_current()

    def _on_error(self, err):
        self._progress.setVisible(False)
        QMessageBox.critical(self, tr("inference.inference_error"), err)

    def _navigate(self, delta):
        if not self._image_paths:
            return
        self._current_index = (self._current_index + delta) % len(self._image_paths)
        self._show_current()

    def _show_current(self):
        if self._current_index < 0 or self._current_index >= len(self._image_paths):
            return
        path = self._image_paths[self._current_index]
        self._viewer.load_image(path)
        bind(
            self._pos_label,
            "inference.position",
            current=self._current_index + 1,
            total=len(self._image_paths),
        )
        pred = self._predictions.get(path)
        if pred:
            self._show_prediction(pred)
        else:
            self._viewer.clear_detections()
            self._det_table.setRowCount(0)

    def _show_prediction(self, prediction):
        dets = prediction.detections if hasattr(prediction, "detections") else []
        self._viewer.set_detections(dets)
        self._det_table.setRowCount(len(dets))
        for row, det in enumerate(dets):
            cls_name = getattr(det, "class_name", "") or str(getattr(det, "class_id", ""))
            self._det_table.setItem(row, 0, QTableWidgetItem(cls_name))
            conf = getattr(det, "confidence", 0) or 0
            self._det_table.setItem(row, 1, QTableWidgetItem(f"{conf:.3f}"))
            bbox = getattr(det, "bbox", [0, 0, 0, 0])
            self._det_table.setItem(
                row,
                2,
                QTableWidgetItem(f"[{bbox[0]:.0f},{bbox[1]:.0f},{bbox[2]:.0f},{bbox[3]:.0f}]"),
            )
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) if len(bbox) >= 4 else 0
            self._det_table.setItem(row, 3, QTableWidgetItem(f"{area:.0f}"))

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._dir_label.setStyleSheet(f"color: {c.TEXT_SECONDARY};")

