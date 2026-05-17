"""Zoomable, draggable image viewer using QGraphicsView."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QRectF

from desktop_app.i18n import tr
from PySide6.QtGui import QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QVBoxLayout, QWidget, QLabel,
)


class ImageViewer(QWidget):
    """Displays an image with zoom (wheel), pan (drag), and fit-to-window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._zoom_factor = 1.15
        self._current_zoom = 1.0
        self._pixmap_item: QGraphicsPixmapItem | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._view)

        # Info label overlaying bottom-left
        self._info_label = QLabel(self)
        self._info_label.setStyleSheet(
            "background: rgba(0,0,0,0.6); color: #CCC; padding: 2px 8px; border-radius: 3px; font-size: 11px;"
        )
        self._info_label.hide()

    def load_image(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._info_label.setText(tr("image.load_error"))
            self._info_label.show()
            return
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self._current_zoom = 1.0
        self._view.resetTransform()
        self.fit_to_window()
        self._info_label.setText(
            f"{pixmap.width()}×{pixmap.height()} | {os.path.basename(path)}"
        )
        self._info_label.adjustSize()
        self._info_label.move(8, self.height() - self._info_label.height() - 8)
        self._info_label.show()

    def fit_to_window(self) -> None:
        if self._pixmap_item:
            self._view.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._current_zoom = self._view.transform().m11()

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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._info_label:
            self._info_label.move(8, self.height() - self._info_label.height() - 8)

    def clear(self) -> None:
        self._scene.clear()
        self._pixmap_item = None
        self._info_label.hide()
