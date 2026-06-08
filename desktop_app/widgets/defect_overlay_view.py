"""ImageViewer with defect bounding box and label overlay."""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF

from desktop_app.i18n import tr, bind
from PySide6.QtGui import QColor, QPen, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QCheckBox,
    QHBoxLayout,
    QLabel,
)

from desktop_app.widgets.image_viewer import ImageViewer
from desktop_app.theme_manager import ThemeManager

# Default per-class colors
CLASS_COLORS = [
    QColor("#FF4444"),  # red
    QColor("#44FF44"),  # green
    QColor("#4488FF"),  # blue
    QColor("#FFAA00"),  # orange
    QColor("#FF44FF"),  # magenta
    QColor("#00CCCC"),  # cyan
    QColor("#FFFF44"),  # yellow
    QColor("#FF8888"),  # pink
    QColor("#88FF88"),  # light green
    QColor("#8888FF"),  # light blue
]


class DefectOverlayView(QWidget):
    """ImageViewer + bbox overlay with toggle controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._detections: list = []
        self._show_boxes = True
        self._overlay_items: list = []
        self._build_ui()
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._viewer = ImageViewer()
        layout.addWidget(self._viewer, 1)

        # Control bar
        ctrl = QHBoxLayout()
        self._show_cb = QCheckBox()
        bind(self._show_cb, "defect.show_boxes")
        self._show_cb.setChecked(True)
        self._show_cb.toggled.connect(self._toggle_boxes)
        ctrl.addWidget(self._show_cb)
        self._count_label = QLabel()
        bind(self._count_label, "defect.detection_count", count=0)
        self._count_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; font-size: 11px;")
        ctrl.addWidget(self._count_label)
        ctrl.addStretch()
        layout.addLayout(ctrl)

    def load_image(self, path: str) -> None:
        self._viewer.load_image(path)
        self._redraw_overlay()

    def set_detections(self, detections: list) -> None:
        """Set DetectionBox list and redraw."""
        self._detections = detections or []
        bind(self._count_label, "defect.detection_count", count=len(self._detections))
        self._redraw_overlay()

    def clear_detections(self) -> None:
        self._detections = []
        bind(self._count_label, "defect.detection_count", count=0)
        self._clear_overlay_items()

    def _redraw_overlay(self) -> None:
        self._clear_overlay_items()
        if not self._detections or not self._show_boxes:
            return

        scene = self._viewer._scene
        pixmap_item = self._viewer._pixmap_item
        if pixmap_item is None:
            return

        pixmap = pixmap_item.pixmap()
        img_w = pixmap.width()
        img_h = pixmap.height()

        for i, det in enumerate(self._detections):
            # DetectionBox has bbox [x1, y1, x2, y2] in pixel coordinates
            bbox = det.bbox  # [x1, y1, x2, y2]
            x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]

            # Clamp to image bounds
            x1 = max(0, min(x1, img_w))
            y1 = max(0, min(y1, img_h))
            x2 = max(0, min(x2, img_w))
            y2 = max(0, min(y2, img_h))

            if x2 <= x1 or y2 <= y1:
                continue

            color = CLASS_COLORS[i % len(CLASS_COLORS)]
            pen = QPen(color, 2)
            rect_item = scene.addRect(QRectF(x1, y1, x2 - x1, y2 - y1), pen)
            self._overlay_items.append(rect_item)

            # Label
            class_name = getattr(det, "class_name", "") or ""
            confidence = getattr(det, "confidence", 0.0) or 0.0
            label_text = f"{class_name} {confidence:.2f}"
            text_item = scene.addText(label_text)
            text_item.setDefaultTextColor(color)
            text_item.setPos(x1, max(0, y1 - 18))
            font = QFont("Arial", 10, QFont.Weight.Bold)
            text_item.setFont(font)
            self._overlay_items.append(text_item)

    def _clear_overlay_items(self) -> None:
        scene = self._viewer._scene
        for item in self._overlay_items:
            scene.removeItem(item)
        self._overlay_items.clear()

    def _toggle_boxes(self, checked: bool) -> None:
        self._show_boxes = checked
        self._redraw_overlay()

    def clear(self) -> None:
        self._viewer.clear()
        self.clear_detections()

    def fit_to_window(self) -> None:
        self._viewer.fit_to_window()

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._count_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 11px;")
