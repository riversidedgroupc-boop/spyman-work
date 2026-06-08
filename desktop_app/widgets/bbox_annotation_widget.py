"""Interactive bbox annotation widget — mouse drag to draw, right-click to delete."""

from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QColor,
    QPen,
    QFont,
    QPainter,
    QPixmap,
    QWheelEvent,
    QMouseEvent,
    QAction,
    QCursor,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QComboBox,
    QPushButton,
    QLabel,
    QMenu,
    QApplication,
)

from desktop_app.label_config import load_label_options, LabelOption
from desktop_app.i18n import tr, I18nManager
from desktop_app.theme_manager import ThemeManager

CLASS_COLORS = [
    QColor("#FF4444"),
    QColor("#44FF44"),
    QColor("#4488FF"),
    QColor("#FFAA00"),
    QColor("#FF44FF"),
    QColor("#00CCCC"),
    QColor("#FFFF44"),
    QColor("#FF8888"),
    QColor("#88FF88"),
    QColor("#8888FF"),
]

BACKGROUND_VALUES = {"OK", "UNKNOWN", "INTERFERENCE", "UNCERTAIN", "IGNORE"}


class _AnnotationScene(QGraphicsScene):
    """QGraphicsScene subclass that handles mouse events for bbox drawing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drawing = False
        self._start_point: QPointF | None = None
        self._rubber_band: QGraphicsRectItem | None = None
        self._draw_mode = False
        self._bbox_added_callback: Any = None
        self._bbox_right_click_callback: Any = None

    def set_draw_mode(self, enabled: bool) -> None:
        self._draw_mode = enabled
        if not enabled:
            self._cancel_drawing()

    def set_bbox_added_callback(self, cb: Any) -> None:
        self._bbox_added_callback = cb

    def set_bbox_right_click_callback(self, cb: Any) -> None:
        self._bbox_right_click_callback = cb

    def _cancel_drawing(self) -> None:
        if self._rubber_band is not None:
            self.removeItem(self._rubber_band)
            self._rubber_band = None
        self._drawing = False
        self._start_point = None

    def mousePressEvent(self, event: "QMouseEvent | Any") -> None:
        if self._draw_mode and event.button() == Qt.MouseButton.LeftButton:
            # Check if clicking on an existing bbox rect for deletion
            item = self.itemAt(event.scenePos(), self.views()[0].transform())
            if isinstance(item, QGraphicsRectItem) and item != self._rubber_band:
                # Right-click on bbox is handled via context menu
                pass
            self._drawing = True
            self._start_point = event.scenePos()
            self._rubber_band = None
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: "QMouseEvent | Any") -> None:
        if self._drawing and self._draw_mode:
            if self._rubber_band is not None:
                self.removeItem(self._rubber_band)
            if self._start_point is not None:
                rect = QRectF(self._start_point, event.scenePos()).normalized()
                pen = QPen(QColor("#00FF00"), 2, Qt.PenStyle.DashLine)
                self._rubber_band = self.addRect(rect, pen)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: "QMouseEvent | Any") -> None:
        if self._drawing and self._draw_mode and event.button() == Qt.MouseButton.LeftButton:
            self._drawing = False
            if self._rubber_band is not None:
                self.removeItem(self._rubber_band)
                self._rubber_band = None

            if self._start_point is not None:
                end_point = event.scenePos()
                dx = abs(end_point.x() - self._start_point.x())
                dy = abs(end_point.y() - self._start_point.y())
                if dx > 5 and dy > 5:  # minimum bbox size
                    rect = QRectF(self._start_point, end_point).normalized()
                    if self._bbox_added_callback:
                        self._bbox_added_callback(rect)
            self._start_point = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: "Any") -> None:
        """Right-click on a bbox to offer delete."""
        item = self.itemAt(event.scenePos(), self.views()[0].transform())
        if isinstance(item, QGraphicsRectItem) and item.data(0) is not None:
            idx = item.data(0)  # bbox index
            if self._bbox_right_click_callback:
                menu = QMenu()
                delete_action = menu.addAction(tr("bbox.delete_bbox"))
                chosen = menu.exec(event.screenPos())
                if chosen == delete_action:
                    self._bbox_right_click_callback(idx)
            event.accept()
            return
        super().contextMenuEvent(event)


class BboxAnnotationWidget(QWidget):
    """Interactive bbox drawing widget for YOLO-format annotation.

    Features:
    - Mouse drag (in draw mode) to create bounding boxes
    - Right-click on existing bbox to delete
    - Class selector for new bboxes
    - Save/load YOLO .txt sidecar files
    - Zoom with mouse wheel, pan with scroll-hand drag (when not in draw mode)
    """

    bboxes_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # State
        self._image_path: str = ""
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._bboxes: list[
            dict
        ] = []  # normalized: class_id, class_name, x_center, y_center, width, height
        self._overlay_items: list[QGraphicsRectItem] = []
        self._label_items: list[Any] = []
        self._draw_mode = True
        self._zoom_factor = 1.15
        self._current_zoom = 1.0

        # Class options (exclude background labels)
        self._class_options: list[LabelOption] = []
        self._refresh_class_options()

        self._setup_ui()
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _refresh_class_options(self) -> None:
        """Reload label options, filtering out background labels."""
        all_opts = load_label_options()
        self._class_options = [
            o for o in all_opts if o.value.upper() not in BACKGROUND_VALUES and o.value.strip()
        ]
        if not self._class_options:
            self._class_options = all_opts  # fallback

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Scene + View
        self._scene = _AnnotationScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        layout.addWidget(self._view, 1)

        # Wire callbacks
        self._scene.set_bbox_added_callback(self._on_bbox_drawn)
        self._scene.set_bbox_right_click_callback(self._on_bbox_right_click)

        # Control bar
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        ctrl.addWidget(QLabel(tr("bbox.filter_label")))
        self._class_combo = QComboBox()
        self._class_combo.setMinimumWidth(120)
        self._rebuild_class_combo()
        ctrl.addWidget(self._class_combo)

        self._draw_mode_btn = QPushButton(tr("bbox.draw_mode"))
        self._draw_mode_btn.setCheckable(True)
        self._draw_mode_btn.setChecked(True)
        self._draw_mode_btn.toggled.connect(self._on_draw_mode_toggled)
        self._draw_mode_btn.setStyleSheet(
            f"QPushButton:checked {{ background-color: {ThemeManager.current().SUCCESS}; color: white; }}"
        )
        ctrl.addWidget(self._draw_mode_btn)

        self._clear_btn = QPushButton(tr("bbox.clear_all"))
        self._clear_btn.clicked.connect(self.clear_bboxes)
        ctrl.addWidget(self._clear_btn)

        self._save_btn = QPushButton(tr("bbox.save"))
        self._save_btn.setObjectName("primaryBtn")
        self._save_btn.clicked.connect(self.save_to_file)
        ctrl.addWidget(self._save_btn)

        ctrl.addStretch()

        self._stats_label = QLabel("Bboxes: 0")
        self._stats_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; font-size: 11px;")
        ctrl.addWidget(self._stats_label)
        layout.addLayout(ctrl)

        # Info label
        self._info_label = QLabel(self)
        self._info_label.setStyleSheet(
            "background: rgba(0,0,0,0.7); color: #CCC; padding: 2px 8px; border-radius: 3px; font-size: 11px;"
        )
        self._info_label.hide()

    def _rebuild_class_combo(self) -> None:
        self._class_combo.clear()
        for i, opt in enumerate(self._class_options):
            self._class_combo.addItem(f"{opt.label}")
            self._class_combo.setItemData(i, QColor(opt.color), Qt.ItemDataRole.DecorationRole)

    # ------------------------------------------------------------------
    # Image Loading
    # ------------------------------------------------------------------

    def load_image(self, image_path: str) -> None:
        """Load an image and its existing bboxes (if any)."""
        self._image_path = image_path
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self._info_label.setText(f"Failed to load: {image_path}")
            self._info_label.show()
            return

        self._scene.clear()
        self._overlay_items.clear()
        self._label_items.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self._current_zoom = 1.0
        self._view.resetTransform()
        self._fit_to_window()

        # Load existing bboxes
        self._bboxes = []
        self.load_from_file()

        # Redraw overlays
        self._redraw_overlay()

        basename = os.path.basename(image_path)
        self._info_label.setText(f"{pixmap.width()}×{pixmap.height()} | {basename}")
        self._info_label.adjustSize()
        self._info_label.move(8, self._view.height() - self._info_label.height() - 8)
        self._info_label.show()

    def _fit_to_window(self) -> None:
        if self._pixmap_item:
            self._view.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._current_zoom = self._view.transform().m11()

    # ------------------------------------------------------------------
    # Drawing Mode
    # ------------------------------------------------------------------

    def _on_draw_mode_toggled(self, checked: bool) -> None:
        self._draw_mode = checked
        self._scene.set_draw_mode(checked)
        if checked:
            self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self._view.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            self._draw_mode_btn.setText(tr("bbox.draw_mode_on"))
        else:
            self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self._view.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self._draw_mode_btn.setText(tr("bbox.draw_mode_off"))

    # ------------------------------------------------------------------
    # Bbox Drawing Callbacks
    # ------------------------------------------------------------------

    def _on_bbox_drawn(self, scene_rect: QRectF) -> None:
        """Called when user finishes drawing a rectangle in the scene."""
        if self._pixmap_item is None:
            return
        pixmap = self._pixmap_item.pixmap()
        img_w = pixmap.width()
        img_h = pixmap.height()

        # Clamp to image bounds
        x1 = max(0.0, min(float(scene_rect.left()), float(img_w)))
        y1 = max(0.0, min(float(scene_rect.top()), float(img_h)))
        x2 = max(0.0, min(float(scene_rect.right()), float(img_w)))
        y2 = max(0.0, min(float(scene_rect.bottom()), float(img_h)))

        if x2 - x1 < 3 or y2 - y1 < 3:
            return  # too small

        # Convert to normalized YOLO coordinates
        x_center = ((x1 + x2) / 2.0) / img_w
        y_center = ((y1 + y2) / 2.0) / img_h
        width = (x2 - x1) / img_w
        height = (y2 - y1) / img_h

        # Get selected class
        idx = self._class_combo.currentIndex()
        if idx < 0 or idx >= len(self._class_options):
            return
        opt = self._class_options[idx]

        bbox = {
            "class_id": idx,
            "class_name": opt.value,
            "x_center": x_center,
            "y_center": y_center,
            "width": width,
            "height": height,
            "color": opt.color,
        }
        self._bboxes.append(bbox)
        self._redraw_overlay()
        self._update_stats()
        self.bboxes_changed.emit()

    def _on_bbox_right_click(self, bbox_index: int) -> None:
        """Delete a bbox by index."""
        if 0 <= bbox_index < len(self._bboxes):
            self._bboxes.pop(bbox_index)
            self._redraw_overlay()
            self._update_stats()
            self.bboxes_changed.emit()

    # ------------------------------------------------------------------
    # Overlay Rendering
    # ------------------------------------------------------------------

    def _redraw_overlay(self) -> None:
        """Redraw all bbox rectangles and labels on the scene."""
        # Clear old overlay items
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()
        for item in self._label_items:
            self._scene.removeItem(item)
        self._label_items.clear()

        if self._pixmap_item is None:
            return

        pixmap = self._pixmap_item.pixmap()
        img_w = pixmap.width()
        img_h = pixmap.height()

        for i, bbox in enumerate(self._bboxes):
            # Convert normalized to pixel coordinates
            x_center = bbox["x_center"] * img_w
            y_center = bbox["y_center"] * img_h
            w = bbox["width"] * img_w
            h = bbox["height"] * img_h
            x1 = x_center - w / 2.0
            y1 = y_center - h / 2.0

            color = CLASS_COLORS[bbox["class_id"] % len(CLASS_COLORS)]
            pen = QPen(color, 2)
            rect_item = self._scene.addRect(QRectF(x1, y1, w, h), pen)
            rect_item.setData(0, i)  # store index for right-click lookup
            self._overlay_items.append(rect_item)

            # Label
            label_text = f"{bbox['class_name']}"
            text_item = self._scene.addText(label_text)
            text_item.setDefaultTextColor(color)
            text_item.setPos(x1, max(0.0, y1 - 18))
            font = QFont("Arial", 10, QFont.Weight.Bold)
            text_item.setFont(font)
            self._label_items.append(text_item)

    def _update_stats(self) -> None:
        """Update the stats label."""
        stats = self.get_stats()
        parts = [f"{name}×{count}" for name, count in sorted(stats.items())]
        self._stats_label.setText(f"Bboxes: {len(self._bboxes)} ({', '.join(parts)})")

    # ------------------------------------------------------------------
    # I/O: YOLO .txt sidecar
    # ------------------------------------------------------------------

    def save_to_file(self) -> None:
        """Save bboxes as YOLO .txt sidecar file next to the image."""
        if not self._image_path:
            return
        stem, _ = os.path.splitext(self._image_path)
        txt_path = stem + ".txt"
        lines = []
        for bbox in self._bboxes:
            lines.append(
                f"{bbox['class_id']} "
                f"{bbox['x_center']:.6f} {bbox['y_center']:.6f} "
                f"{bbox['width']:.6f} {bbox['height']:.6f}"
            )
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
        self._stats_label.setStyleSheet(f"color: {ThemeManager.current().SUCCESS}; font-size: 11px;")
        self._stats_label.setText(f"Saved: {txt_path}")

    def load_from_file(self) -> None:
        """Load bboxes from YOLO .txt sidecar file next to the image."""
        if not self._image_path:
            return
        stem, _ = os.path.splitext(self._image_path)
        txt_path = stem + ".txt"
        if not os.path.isfile(txt_path):
            return

        self._bboxes = []
        try:
            with open(txt_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    class_id = int(parts[0])
                    x_center = float(parts[1])
                    y_center = float(parts[2])
                    width = float(parts[3])
                    height = float(parts[4])
                    class_name = ""
                    color = "#FF4444"
                    if class_id < len(self._class_options):
                        class_name = self._class_options[class_id].value
                        color = self._class_options[class_id].color
                    self._bboxes.append(
                        {
                            "class_id": class_id,
                            "class_name": class_name,
                            "x_center": x_center,
                            "y_center": y_center,
                            "width": width,
                            "height": height,
                            "color": color,
                        }
                    )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_bboxes(self) -> list[dict]:
        """Return current bboxes (normalized coordinates)."""
        return list(self._bboxes)

    def set_bboxes(self, bboxes: list[dict]) -> None:
        """Replace current bboxes."""
        self._bboxes = bboxes
        self._redraw_overlay()
        self._update_stats()
        self.bboxes_changed.emit()

    def clear_bboxes(self) -> None:
        """Remove all bboxes."""
        self._bboxes = []
        self._redraw_overlay()
        self._update_stats()
        self.bboxes_changed.emit()

    def get_stats(self) -> dict[str, int]:
        """Return per-class bbox counts."""
        counts: dict[str, int] = {}
        for bbox in self._bboxes:
            name = bbox.get("class_name", "?")
            counts[name] = counts.get(name, 0) + 1
        return counts

    def get_image_path(self) -> str:
        return self._image_path

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap_item is None:
            return
        if event.angleDelta().y() > 0:
            factor = self._zoom_factor
        else:
            factor = 1.0 / self._zoom_factor
        new_zoom = self._current_zoom * factor
        if 0.05 < new_zoom < 20:
            self._view.scale(factor, factor)
            self._current_zoom = new_zoom

    def fit_to_window(self) -> None:
        self._fit_to_window()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if self._info_label and self._pixmap_item:
            self._info_label.move(8, self._view.height() - self._info_label.height() - 8)

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._draw_mode_btn.setStyleSheet(
            f"QPushButton:checked {{ background-color: {c.SUCCESS}; color: white; }}"
        )
        self._stats_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 11px;")
