"""Thumbnail grid widget for browsing and selecting captured images."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt, QSize

from desktop_app.display import CLASS_LABEL_OPTIONS, class_label
from desktop_app.i18n import tr, bind, I18nManager
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QComboBox, QLabel,
)


class ThumbnailGrid(QWidget):
    """Shows image thumbnails in a grid with selection, filtering, and label badges."""

    image_selected = Signal(str)  # image path
    selection_changed = Signal(list)  # list of image paths

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image_paths: dict[str, str] = {}  # display_key -> full_path
        self._image_labels: dict[str, str] = {}  # full_path -> label
        self._image_cameras: dict[str, str] = {}  # full_path -> camera_id
        self._label_options = list(CLASS_LABEL_OPTIONS)
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Filter bar
        filter_layout = QHBoxLayout()
        self._camera_filter_label = QLabel()
        bind(self._camera_filter_label, "thumb.filter_camera")
        filter_layout.addWidget(self._camera_filter_label)
        self._camera_filter = QComboBox()
        self._camera_filter.addItem(tr("app.all"), "")
        self._camera_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self._camera_filter)

        self._label_filter_label = QLabel()
        bind(self._label_filter_label, "thumb.filter_label")
        filter_layout.addWidget(self._label_filter_label)
        self._label_filter = QComboBox()
        self._label_filter.addItem(tr("app.all"), "")
        for value, label in CLASS_LABEL_OPTIONS:
            self._label_filter.addItem(label, value)
        self._label_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self._label_filter)

        filter_layout.addStretch()

        self._count_label = QLabel()
        bind(self._count_label, "thumb.count", count=0)
        filter_layout.addWidget(self._count_label)
        layout.addLayout(filter_layout)

        # Grid
        self._list = QListWidget()
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setIconSize(QSize(120, 120))
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.setGridSize(QSize(140, 160))
        self._list.setSpacing(4)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

    def _refresh_text(self, lang: str = "") -> None:
        """Rebuild filter combo items on language change."""
        self._camera_filter.blockSignals(True)
        self._camera_filter.clear()
        self._camera_filter.addItem(tr("app.all"), "")
        cam_set: set[str] = set()
        for _name, path in self._image_paths.items():
            cam = self._image_cameras.get(path, "")
            cam_set.add(cam)
        for c in sorted(cam_set):
            if c:
                self._camera_filter.addItem(c, c)
        self._camera_filter.blockSignals(False)

        self._label_filter.blockSignals(True)
        self._label_filter.clear()
        self._label_filter.addItem(tr("app.all"), "")
        for value, label in self._label_options:
            self._label_filter.addItem(label, value)
        self._label_filter.blockSignals(False)

        self._apply_filter()

    def set_images(self, paths: list[str], cameras: dict[str, str] | None = None,
                   labels: dict[str, str] | None = None) -> None:
        """Load images into the grid. cameras: {path: cam_id}, labels: {path: label}"""
        self._image_paths.clear()
        self._image_labels.clear()
        self._image_cameras.clear()
        if cameras:
            self._image_cameras = dict(cameras)
        if labels:
            self._image_labels = dict(labels)

        cam_set: set[str] = set()
        for p in paths:
            self._image_paths[Path(p).name] = p
            cam = self._image_cameras.get(p, "")
            cam_set.add(cam)

        self._camera_filter.blockSignals(True)
        self._camera_filter.clear()
        self._camera_filter.addItem(tr("app.all"), "")
        for c in sorted(cam_set):
            if c:
                self._camera_filter.addItem(c, c)
        self._camera_filter.blockSignals(False)

        self._apply_filter()

    def set_label_options(self, options: list[tuple[str, str]]) -> None:
        self._label_options = list(options)
        self._refresh_text()

    def select_path(self, path: str) -> None:
        self._list.clearSelection()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self._list.setCurrentItem(item)
                item.setSelected(True)
                self._list.scrollToItem(item)
                break

    def _apply_filter(self) -> None:
        cam_filter = self._camera_filter.currentData()
        label_filter = self._label_filter.currentData()

        self._list.clear()
        for display_key, full_path in self._image_paths.items():
            cam = self._image_cameras.get(full_path, "")
            lbl = self._image_labels.get(full_path, "")
            if cam_filter and cam != cam_filter:
                continue
            if label_filter and lbl != label_filter:
                continue

            thumb = QPixmap(full_path)
            if not thumb.isNull():
                thumb = thumb.scaled(
                    120, 120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            item = QListWidgetItem()
            item.setIcon(QIcon(thumb))
            label_text = class_label(lbl) if lbl else ""
            badge = f"[{label_text}] " if label_text else ""
            cam_text = f"({cam})" if cam else ""
            item.setText(f"{badge}{display_key}\n{cam_text}")
            item.setData(Qt.ItemDataRole.UserRole, full_path)
            item.setData(Qt.ItemDataRole.UserRole + 1, lbl)
            self._list.addItem(item)

        bind(self._count_label, "thumb.count", count=self._list.count())

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        self.image_selected.emit(path)

    def _on_selection_changed(self) -> None:
        paths = [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
            if self._list.item(i).isSelected()
        ]
        self.selection_changed.emit(paths)

    def get_selected_paths(self) -> list[str]:
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
            if self._list.item(i).isSelected()
        ]

    def get_all_labels(self) -> dict[str, str]:
        return dict(self._image_labels)

    def update_label(self, path: str, label: str) -> None:
        self._image_labels[path] = label
        self._apply_filter()
