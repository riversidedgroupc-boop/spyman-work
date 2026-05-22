"""Bbox annotation page — image list + bbox drawing widget + completeness check."""
from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.capture_session import (
    get_capture_session,
    list_captured_images,
    list_capture_sessions,
    session_output_root,
)
from core.dataset_validation import validate_yolo_detection
from core.label_policy import is_defect_label, is_review_label, needs_bbox
from desktop_app.app_context import AppContext
from desktop_app.i18n import I18nManager, tr
from desktop_app.widgets.bbox_annotation_widget import BboxAnnotationWidget

IMAGE_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


class BboxAnnotationPage(QWidget):
    """Full page for YOLO bbox annotation workflow.

    Layout:
      Top:    session selector
      Middle: image list (left) | BboxAnnotationWidget (right)
      Bottom: navigation + completeness check + stats
    """

    data_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._current_session_id = ""
        self._image_paths: list[str] = []
        self._image_labels: dict[str, str] = {}  # image_path → classification_label
        self._current_index = -1
        self._filter_mode = "needs_bbox"  # needs_bbox | all_defects | has_bbox | review | all
        self._filter_class: str = ""  # empty = all classes

        self._build_ui()
        self._install_shortcuts()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # ── Top: session selector ──
        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(QLabel(tr("bbox.session_label")))

        self._session_combo = QComboBox()
        self._session_combo.setMinimumWidth(280)
        self._session_combo.currentIndexChanged.connect(self._on_session_changed)
        top.addWidget(self._session_combo, 1)

        refresh_btn = QPushButton(tr("app.refresh"))
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self._refresh_sessions)
        top.addWidget(refresh_btn)

        top.addStretch()
        layout.addLayout(top)

        # ── Middle: image list + bbox widget ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: image list + filters
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # Filter buttons
        filter_row1 = QHBoxLayout()
        filter_row1.setSpacing(4)

        self._filter_needs_bbox_btn = QPushButton(tr("bbox.filter_needs_bbox"))
        self._filter_needs_bbox_btn.setCheckable(True)
        self._filter_needs_bbox_btn.setChecked(True)
        self._filter_needs_bbox_btn.clicked.connect(lambda: self._set_filter("needs_bbox"))
        filter_row1.addWidget(self._filter_needs_bbox_btn)

        self._filter_all_defects_btn = QPushButton(tr("bbox.filter_all_defects"))
        self._filter_all_defects_btn.setCheckable(True)
        self._filter_all_defects_btn.clicked.connect(lambda: self._set_filter("all_defects"))
        filter_row1.addWidget(self._filter_all_defects_btn)

        self._filter_has_bbox_btn = QPushButton(tr("bbox.filter_has_bbox"))
        self._filter_has_bbox_btn.setCheckable(True)
        self._filter_has_bbox_btn.clicked.connect(lambda: self._set_filter("has_bbox"))
        filter_row1.addWidget(self._filter_has_bbox_btn)

        left_layout.addLayout(filter_row1)

        filter_row2 = QHBoxLayout()
        filter_row2.setSpacing(4)

        self._filter_review_btn = QPushButton(tr("bbox.filter_review"))
        self._filter_review_btn.setCheckable(True)
        self._filter_review_btn.clicked.connect(lambda: self._set_filter("review"))
        filter_row2.addWidget(self._filter_review_btn)

        self._filter_all_btn = QPushButton(tr("bbox.filter_all"))
        self._filter_all_btn.setCheckable(True)
        self._filter_all_btn.clicked.connect(lambda: self._set_filter("all"))
        filter_row2.addWidget(self._filter_all_btn)

        left_layout.addLayout(filter_row2)

        # Class filter combo
        class_filter_layout = QHBoxLayout()
        class_filter_layout.setSpacing(4)
        class_filter_layout.addWidget(QLabel(tr("bbox.filter_label")))
        self._class_filter_combo = QComboBox()
        self._class_filter_combo.currentIndexChanged.connect(self._on_class_filter_changed)
        class_filter_layout.addWidget(self._class_filter_combo, 1)
        left_layout.addLayout(class_filter_layout)

        # Image list
        self._image_list = QListWidget()
        self._image_list.currentRowChanged.connect(self._on_image_list_selection_changed)
        left_layout.addWidget(self._image_list, 1)

        splitter.addWidget(left_panel)

        # Right panel: bbox annotation widget
        self._bbox_widget = BboxAnnotationWidget()
        self._bbox_widget.bboxes_changed.connect(self._on_bboxes_changed)
        splitter.addWidget(self._bbox_widget)

        splitter.setSizes([260, 920])
        layout.addWidget(splitter, 1)

        # ── Bottom: navigation + actions ──
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self._prev_btn = QPushButton(tr("bbox.prev_image"))
        self._prev_btn.clicked.connect(lambda: self._navigate(-1))
        bottom.addWidget(self._prev_btn)

        self._progress_label = QLabel("0/0")
        self._progress_label.setStyleSheet("color: #CCC; font-size: 12px; padding: 0 12px;")
        bottom.addWidget(self._progress_label)

        self._next_btn = QPushButton(tr("bbox.next_image"))
        self._next_btn.clicked.connect(lambda: self._navigate(1))
        bottom.addWidget(self._next_btn)

        bottom.addStretch()

        self._check_btn = QPushButton(tr("bbox.check_completeness"))
        self._check_btn.setObjectName("primaryBtn")
        self._check_btn.clicked.connect(self._check_completeness)
        bottom.addWidget(self._check_btn)

        self._validation_label = QLabel("")
        self._validation_label.setStyleSheet("font-size: 11px; padding: 0 8px;")
        bottom.addWidget(self._validation_label)

        layout.addLayout(bottom)

    def _install_shortcuts(self) -> None:
        """Keyboard shortcuts for navigation and common actions."""
        for key, handler in [
            ("N", lambda: self._navigate(1)),
            ("P", lambda: self._navigate(-1)),
            ("Right", lambda: self._navigate(1)),
            ("Left", lambda: self._navigate(-1)),
            ("Ctrl+S", self._save_current),
        ]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(handler)

    # ------------------------------------------------------------------
    # Session / Image Loading
    # ------------------------------------------------------------------

    def _refresh_text(self, lang: str = "") -> None:
        self._refresh_sessions()

    def _refresh_sessions(self) -> None:
        self._session_combo.blockSignals(True)
        current = self._current_session_id
        self._session_combo.clear()
        self._session_combo.addItem("-- " + tr("classify.select_session") + " --", "")
        pid = self._ctx.current_project_id
        if pid:
            for session in list_capture_sessions(pid):
                self._session_combo.addItem(session.session_name, session.session_id)
        if current:
            idx = self._session_combo.findData(current)
            if idx >= 0:
                self._session_combo.setCurrentIndex(idx)
        self._session_combo.blockSignals(False)

    def _on_session_changed(self, index: int) -> None:
        session_id = self._session_combo.itemData(index)
        if not session_id:
            return
        # Auto-save before switching sessions
        self._auto_save_current()
        self._current_session_id = session_id
        self._load_images(session_id)

    def _load_images(self, session_id: str) -> None:
        session = get_capture_session(session_id)
        if not session:
            return

        paths: list[str] = []
        labels: dict[str, str] = {}
        output_root = session.output_dir or session_output_root(session.project_id)
        raw_dir = os.path.join(output_root, session_id, "raw")

        # Load from raw directory
        if os.path.isdir(raw_dir):
            for cam_dir in sorted(os.listdir(raw_dir)):
                cam_path = os.path.join(raw_dir, cam_dir)
                if not os.path.isdir(cam_path):
                    continue
                for fname in sorted(os.listdir(cam_path)):
                    path = os.path.join(cam_path, fname)
                    if self._is_image_file(path):
                        paths.append(path)

        # Also load from captured_images DB entries not already in paths
        for image in list_captured_images(session_id):
            image_path = image.get("image_path", "")
            if image_path and os.path.isfile(image_path) and image_path not in paths:
                paths.append(image_path)
            if image_path:
                label = image.get("classification_label", "")
                if label:
                    labels[image_path] = label

        self._image_paths = paths
        self._image_labels = labels
        self._current_index = 0 if paths else -1
        self._rebuild_class_filter()
        self._rebuild_image_list()

        # Load first image
        if self._image_paths:
            self._image_list.setCurrentRow(0)
        else:
            self._bbox_widget.load_image("")

    def _is_image_file(self, path: str) -> bool:
        return os.path.isfile(path) and os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS

    # ------------------------------------------------------------------
    # Class Filter
    # ------------------------------------------------------------------

    def _rebuild_class_filter(self) -> None:
        self._class_filter_combo.blockSignals(True)
        self._class_filter_combo.clear()
        self._class_filter_combo.addItem(tr("app.all"), "")

        classes_seen: set[str] = set()
        for path in self._image_paths:
            cls_name = self._get_bbox_class_name(path)
            if cls_name and cls_name not in classes_seen:
                classes_seen.add(cls_name)
                self._class_filter_combo.addItem(cls_name, cls_name)

        self._class_filter_combo.blockSignals(False)

    def _get_bbox_class_name(self, image_path: str) -> str:
        """Get the class name from the first bbox in the sidecar .txt, if any."""
        stem, _ = os.path.splitext(image_path)
        txt_path = stem + ".txt"
        if not os.path.isfile(txt_path):
            return ""
        try:
            with open(txt_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) >= 5:
                        class_id = int(parts[0])
                        from desktop_app.label_config import load_label_options
                        from core.label_policy import is_background_label, is_review_label

                        opts = [
                            o for o in load_label_options()
                            if not is_background_label(o.value) and not is_review_label(o.value) and o.value.strip()
                        ]
                        if 0 <= class_id < len(opts):
                            return opts[class_id].label
                        return str(class_id)
        except Exception:
            return ""
        return ""

    def _on_class_filter_changed(self, _index: int) -> None:
        self._filter_class = self._class_filter_combo.currentData() or ""
        self._rebuild_image_list()

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def _set_filter(self, mode: str) -> None:
        self._filter_mode = mode
        self._filter_needs_bbox_btn.setChecked(mode == "needs_bbox")
        self._filter_all_defects_btn.setChecked(mode == "all_defects")
        self._filter_has_bbox_btn.setChecked(mode == "has_bbox")
        self._filter_review_btn.setChecked(mode == "review")
        self._filter_all_btn.setChecked(mode == "all")
        self._rebuild_image_list()

    def _has_bbox(self, image_path: str) -> bool:
        stem, _ = os.path.splitext(image_path)
        txt_path = stem + ".txt"
        if not os.path.isfile(txt_path):
            return False
        try:
            with open(txt_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and len(line.split()) >= 5:
                        return True
        except Exception:
            return False
        return False

    def _get_filtered_paths(self) -> list[str]:
        """Return image paths matching current filter mode and class."""
        filtered: list[str] = []
        for path in self._image_paths:
            label = self._image_labels.get(path, "")
            has_bbox = self._has_bbox(path)

            # Classification-driven filter modes
            if self._filter_mode == "needs_bbox":
                # Only NG/defect images that don't yet have bbox
                if not needs_bbox(label) or has_bbox:
                    continue
            elif self._filter_mode == "all_defects":
                # All NG/defect images regardless of bbox status
                if not is_defect_label(label):
                    continue
            elif self._filter_mode == "has_bbox":
                # Defect images that already have bbox
                if not is_defect_label(label) or not has_bbox:
                    continue
            elif self._filter_mode == "review":
                # UNKNOWN / UNCERTAIN images
                if not is_review_label(label):
                    continue
            elif self._filter_mode == "all":
                pass  # No filter — show everything
            else:
                # Legacy compatibility: "no_bbox" treated as "needs_bbox"
                if self._filter_mode == "no_bbox" and has_bbox:
                    continue

            # Class filter (bbox class name, unchanged)
            if self._filter_class:
                cls_name = self._get_bbox_class_name(path)
                if cls_name != self._filter_class:
                    continue
            filtered.append(path)
        return filtered

    # ------------------------------------------------------------------
    # Image List
    # ------------------------------------------------------------------

    def _rebuild_image_list(self) -> None:
        self._image_list.blockSignals(True)
        self._image_list.clear()

        filtered = self._get_filtered_paths()
        for path in filtered:
            basename = os.path.basename(path)
            label = self._image_labels.get(path, "")
            has_bbox = self._has_bbox(path)

            # Icon prefix: ◇ defect/no bbox, ◆ defect/has bbox, ? review
            if is_review_label(label):
                prefix = "? "
            elif has_bbox:
                prefix = "◆ "
            else:
                prefix = "◇ "

            # Show label after filename
            display_text = f"{prefix}{basename}    {label}" if label else f"{prefix}{basename}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, path)

            # Color coding
            if is_review_label(label):
                item.setForeground(Qt.GlobalColor.yellow)
            elif has_bbox:
                item.setForeground(Qt.GlobalColor.green)
            # else: no bbox defect = default (white)

            self._image_list.addItem(item)

        self._image_list.blockSignals(False)
        self._update_progress()

        # Try to restore selection
        if self._image_paths and self._current_index >= 0:
            current_path = self._image_paths[self._current_index]
            if current_path in filtered:
                row = filtered.index(current_path)
                self._image_list.setCurrentRow(row)

    def _on_image_list_selection_changed(self, row: int) -> None:
        if row < 0:
            return
        item = self._image_list.item(row)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and path in self._image_paths:
            # Auto-save current before switching
            self._auto_save_current()
            self._current_index = self._image_paths.index(path)
            self._bbox_widget.load_image(path)
            self._update_progress()
            self._validation_label.setText("")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate(self, delta: int) -> None:
        filtered = self._get_filtered_paths()
        if not filtered:
            return

        if self._current_index < 0 or self._image_paths[self._current_index] not in filtered:
            target_filtered_idx = 0 if delta > 0 else len(filtered) - 1
        else:
            current_path = self._image_paths[self._current_index]
            current_filtered_idx = filtered.index(current_path)
            target_filtered_idx = max(0, min(current_filtered_idx + delta, len(filtered) - 1))

        target_path = filtered[target_filtered_idx]
        # Auto-save before navigating
        self._auto_save_current()
        self._current_index = self._image_paths.index(target_path)
        self._bbox_widget.load_image(target_path)
        self._update_progress()
        self._validation_label.setText("")

        # Update list selection
        self._image_list.blockSignals(True)
        row = filtered.index(target_path)
        self._image_list.setCurrentRow(row)
        self._image_list.blockSignals(False)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _auto_save_current(self) -> None:
        """Save bboxes for the current image before navigating away."""
        if self._current_index < 0:
            return
        if not self._bbox_widget.get_image_path():
            return
        self._bbox_widget.save_to_file()

    def _save_current(self) -> None:
        """Manual save."""
        self._bbox_widget.save_to_file()
        self._validation_label.setText(tr("bbox.auto_saved"))
        self._validation_label.setStyleSheet("color: #4CAF50; font-size: 11px; padding: 0 8px;")

    def _on_bboxes_changed(self) -> None:
        """Called when bboxes change in the widget."""
        self._update_progress()

    # ------------------------------------------------------------------
    # Stats / Progress
    # ------------------------------------------------------------------

    def _update_progress(self) -> None:
        filtered = self._get_filtered_paths()
        total = len(self._image_paths)
        filtered_total = len(filtered)

        bbox_count = len(self._bbox_widget.get_bboxes())

        if self._current_index >= 0 and self._image_paths:
            current_path = self._image_paths[self._current_index]
            if current_path in filtered:
                current_pos = filtered.index(current_path) + 1
            else:
                current_pos = 0
        else:
            current_pos = 0

        self._progress_label.setText(
            f"{current_pos}/{filtered_total}"
            + (f" (全部: {total})" if filtered_total != total else "")
            + f" | Bbox: {bbox_count}"
        )

    # ------------------------------------------------------------------
    # Completeness Check
    # ------------------------------------------------------------------

    def _check_completeness(self) -> None:
        """Run YOLO detection validation on current session."""
        if not self._current_session_id:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_session"))
            return

        # Auto-save current bboxes first
        self._auto_save_current()

        result = validate_yolo_detection(self._current_session_id)

        if result.can_train:
            self._validation_label.setText(tr("bbox.validation_passed"))
            self._validation_label.setStyleSheet(
                "color: #4CAF50; font-size: 11px; font-weight: bold; padding: 0 8px;"
            )
            QMessageBox.information(
                self,
                tr("app.tip"),
                f"✓ 校验通过\n\n"
                f"总图片: {result.total_images}\n"
                f"OK: {result.ok_images}  NG: {result.ng_images}\n"
                f"未标注: {result.unlabeled_images}\n"
                f"缺 bbox 的 NG: {result.missing_bbox_ng_images}\n\n"
                f"可以开始 YOLO 训练。",
            )
        else:
            reason = "; ".join(result.errors) if result.errors else "未知原因"
            self._validation_label.setText(
                tr("bbox.validation_failed").format(reason=reason[:60])
            )
            self._validation_label.setStyleSheet(
                "color: #F44336; font-size: 11px; font-weight: bold; padding: 0 8px;"
            )
            QMessageBox.warning(
                self,
                tr("app.warning"),
                "✗ 校验失败\n\n"
                + result.summary(),
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        self._refresh_sessions()

    def hideEvent(self, event: Any) -> None:
        """Auto-save when leaving the page."""
        self._auto_save_current()
        super().hideEvent(event)
