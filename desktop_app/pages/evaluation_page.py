"""Evaluation page — mAP, PR curve, confusion matrix display."""

from __future__ import annotations

import os
from collections import defaultdict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QFileDialog,
)

from core.model_version import list_model_versions, get_model_version
from core.schema import DetectionBox
from core.matcher import match_detections
from core.metrics import compute_map
from desktop_app.app_context import AppContext
from desktop_app.display import model_type_label
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.workers.inference_worker import InferenceWorker
from desktop_app.theme_manager import ThemeManager


class EvaluationPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._worker: InferenceWorker | None = None
        self._image_paths: list[str] = []
        self._label_dir = ""
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        eval_model_label = QLabel()
        bind(eval_model_label, "eval.model")
        top.addWidget(eval_model_label)
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(200)
        top.addWidget(self._model_combo)

        img_dir_label = QLabel()
        bind(img_dir_label, "eval.image_dir")
        top.addWidget(img_dir_label)
        self._img_label = QLabel()
        bind(self._img_label, "app.not_selected")
        self._img_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY};")
        top.addWidget(self._img_label)
        browse_img = QPushButton()
        bind(browse_img, "eval.select_images")
        browse_img.clicked.connect(lambda: self._browse_dir("img"))
        top.addWidget(browse_img)

        lbl_dir_label = QLabel()
        bind(lbl_dir_label, "eval.label_dir")
        top.addWidget(lbl_dir_label)
        self._lbl_label = QLabel()
        bind(self._lbl_label, "app.not_selected")
        self._lbl_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY};")
        top.addWidget(self._lbl_label)
        browse_lbl = QPushButton()
        bind(browse_lbl, "eval.select_labels")
        browse_lbl.clicked.connect(lambda: self._browse_dir("label"))
        top.addWidget(browse_lbl)

        run_btn = QPushButton()
        bind(run_btn, "eval.run")
        run_btn.clicked.connect(self._run_evaluation)
        top.addWidget(run_btn)
        top.addStretch()
        layout.addLayout(top)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        splitter = QSplitter(Qt.Orientation.Vertical)
        metrics_w = QWidget()
        ml = QVBoxLayout(metrics_w)
        self._map50_label = QLabel()
        bind(self._map50_label, "eval.map50_na")
        self._map50_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {ThemeManager.current().SUCCESS};")
        ml.addWidget(self._map50_label)
        self._map50_95_label = QLabel()
        bind(self._map50_95_label, "eval.map50_95", value="—")
        self._map50_95_label.setStyleSheet(f"font-size: 16px; color: {ThemeManager.current().PRIMARY};")
        ml.addWidget(self._map50_95_label)
        self._per_class_table = QTableWidget(0, 2)
        self._per_class_table.setHorizontalHeaderLabels([tr("eval.col_class"), tr("eval.col_ap50")])
        self._per_class_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        ml.addWidget(self._per_class_table, 1)
        splitter.addWidget(metrics_w)

        self._summary_label = QLabel()
        bind(self._summary_label, "eval.waiting")
        self._summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._summary_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; font-size: 14px;")
        splitter.addWidget(self._summary_label)
        splitter.setSizes([300, 200])
        layout.addWidget(splitter, 1)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set table headers and combo placeholder on language change."""
        self._per_class_table.setHorizontalHeaderLabels([tr("eval.col_class"), tr("eval.col_ap50")])
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

    def _browse_dir(self, kind):
        dir_path = QFileDialog.getExistingDirectory(
            self, tr("dialog.select_image_dir" if kind == "img" else "dialog.select_label_dir")
        )
        if not dir_path:
            return
        if kind == "img":
            self._img_label.setText(dir_path)
            exts = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
            self._image_paths = sorted(
                [
                    os.path.join(dir_path, f)
                    for f in os.listdir(dir_path)
                    if os.path.splitext(f)[1].lower() in exts
                ]
            )
        else:
            self._lbl_label.setText(dir_path)
            self._label_dir = dir_path

    def _run_evaluation(self):
        model_id = self._model_combo.currentData()
        if not model_id:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_model"))
            return
        if not self._image_paths:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_project"))
            return
        model = get_model_version(model_id)
        if not model or not model.model_path:
            QMessageBox.warning(self, tr("app.error"), tr("inference.model_path_empty"))
            return

        self._worker = InferenceWorker(
            model_path=model.model_path,
            image_paths=self._image_paths,
            model_type=model.model_type,
            confidence=0.01,
        )
        self._worker.finished.connect(self._on_eval_finished)
        self._worker.error.connect(self._on_error)
        self._worker.progress.connect(lambda c, t: self._progress.setValue(c))
        self._progress.setVisible(True)
        self._progress.setMaximum(len(self._image_paths))
        self._worker.start()

    def _on_eval_finished(self):
        self._progress.setVisible(False)
        preds = self._worker.get_predictions()

        preds_by_image: dict[str, list] = defaultdict(list)
        for img_path, pred in preds:
            dets = pred.detections if hasattr(pred, "detections") else []
            preds_by_image[os.path.basename(img_path)] = dets

        gts_by_image: dict[str, list] = defaultdict(list)
        if self._label_dir and os.path.isdir(self._label_dir):
            for fname in sorted(os.listdir(self._label_dir)):
                if not fname.endswith(".txt"):
                    continue
                # Find matching image name (label is .txt, image could be .bmp/.jpg)
                for ext in [".bmp", ".jpg", ".png"]:
                    img_name = fname.replace(".txt", ext)
                gts = []
                with open(os.path.join(self._label_dir, fname)) as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cls_id = int(parts[0])
                            xc, yc, w, h = map(float, parts[1:5])
                            gts.append(
                                DetectionBox(
                                    image_name=img_name,
                                    class_id=cls_id,
                                    class_name=str(cls_id),
                                    confidence=1.0,
                                    bbox=[xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2],
                                )
                            )
                gts_by_image[img_name] = gts

        if gts_by_image:
            try:
                image_names = sorted(set(list(gts_by_image.keys())))
                all_gts = {n: gts_by_image.get(n, []) for n in image_names}
                all_preds = {n: preds_by_image.get(n, []) for n in image_names}
                class_ids = set()
                for gts in gts_by_image.values():
                    for gt in gts:
                        class_ids.add(gt.class_id)
                if not class_ids:
                    class_ids = {0}
                map_result = compute_map(all_gts, all_preds, list(class_ids), [0.5, 0.75])
                if "mAP@0.5" in map_result:
                    bind(
                        self._map50_label, "eval.map50", value=f"{map_result.get('mAP@0.5', 0):.4f}"
                    )
                else:
                    bind(self._map50_label, "eval.map50_na")
                self._map50_95_label.setText(
                    tr("eval.map50_95", value=f"{map_result.get('mAP@0.5:0.95', 0):.4f}")
                    if "mAP@0.5:0.95" in map_result
                    else ""
                )
                # Per-class
                per_class = map_result.get("per_class", {})
                self._per_class_table.setRowCount(len(per_class))
                for row, (cid, ap) in enumerate(sorted(per_class.items())):
                    self._per_class_table.setItem(row, 0, QTableWidgetItem(str(cid)))
                    self._per_class_table.setItem(row, 1, QTableWidgetItem(f"{ap:.4f}"))
            except Exception as e:
                bind(self._map50_label, "eval.eval_error", error=str(e))
        else:
            bind(self._map50_label, "eval.need_gt")

        total_pred_boxes = sum(len(v) for v in preds_by_image.values())
        self._summary_label.setText(
            tr(
                "eval.completed",
                images=len(preds),
                gt_images=len(gts_by_image),
                boxes=total_pred_boxes,
            )
        )

    def _on_error(self, err):
        self._progress.setVisible(False)
        QMessageBox.critical(self, tr("eval.error_title"), err)

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._img_label.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        self._lbl_label.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        self._summary_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 14px;")
        self._map50_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c.SUCCESS};")
        self._map50_95_label.setStyleSheet(f"font-size: 16px; color: {c.PRIMARY};")

