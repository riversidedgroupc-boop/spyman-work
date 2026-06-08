"""Left navigation bar widget."""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal, Qt, QSize, QEvent
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
)

from desktop_app.constants import (
    NAV_ITEMS,
    NAV_WIDTH,
    NAV_COLLAPSED_WIDTH,
    NAV_ITEM_MIN_HEIGHT,
    NAV_ITEM_MAX_HEIGHT,
)
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


def _make_nav_icon(icon_name: str, color: str) -> QIcon:
    try:
        import qtawesome as qta
    except ImportError:
        return QIcon()
    try:
        return qta.icon(icon_name, color=color)
    except Exception:
        logger.warning("Failed to create nav icon %s", icon_name, exc_info=True)
        return QIcon()


class NavigationBar(QWidget):
    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._collapsed = False
        self.setFixedWidth(NAV_WIDTH)
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # App title
        self._title_label = QLabel()
        self._title_label.setText("CX-vision")
        self._title_label.setToolTip(tr("app.title"))
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(
            "font-size: 17px; font-weight: bold; padding: 8px 8px 0 8px;"
        )
        self._title_label.setWordWrap(False)
        layout.addWidget(self._title_label)

        self._brand_label = QLabel()
        bind(self._brand_label, "nav.brand")
        self._brand_label.setObjectName("navBrandLabel")
        self._brand_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._brand_label)

        self._version_label = QLabel()
        bind(self._version_label, "app.version")
        self._version_label.setObjectName("navVersionLabel")
        self._version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._version_label)

        # Nav list
        self._list = QListWidget()
        self._list.setObjectName("navList")
        self._list.viewport().installEventFilter(self)
        self._rebuild_nav_items()
        self._list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

    def _rebuild_nav_items(self) -> None:
        self._list.clear()
        palette = ThemeManager.current()
        for item in NAV_ITEMS:
            label = tr(f"nav.{item['id']}")
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            list_item.setToolTip(label)
            self._list.addItem(list_item)
            self._list.setItemWidget(
                list_item,
                self._build_nav_item_widget(
                    icon_name=item.get("icon", ""),
                    label=label,
                    color=palette.TEXT_SECONDARY,
                ),
            )
        self._update_item_sizes()

    def _build_nav_item_widget(self, *, icon_name: str, label: str, color: str) -> QWidget:
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0 if self._collapsed else 14, 0, 0 if self._collapsed else 10, 0)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = _make_nav_icon(icon_name, color).pixmap(QSize(18, 18))
        icon_label.setPixmap(pixmap)

        if self._collapsed:
            layout.addStretch(1)
            layout.addWidget(icon_label)
            layout.addStretch(1)
            return row

        text_label = QLabel(label)
        text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        text_label.setStyleSheet(f"color: {color}; background: transparent;")
        font = QFont()
        font.setPointSize(10 if I18nManager.instance().language == "en" else 11)
        font.setBold(True)
        text_label.setFont(font)

        layout.addWidget(icon_label)
        layout.addWidget(text_label, 1)
        return row

    def _update_item_sizes(self) -> None:
        count = self._list.count()
        if count <= 0:
            return
        viewport_height = self._list.viewport().height()
        if viewport_height <= 0:
            viewport_height = self.height()
        base_height = max(NAV_ITEM_MIN_HEIGHT, min(NAV_ITEM_MAX_HEIGHT, viewport_height // count))
        item_width = NAV_COLLAPSED_WIDTH if self._collapsed else NAV_WIDTH
        for row in range(count):
            item = self._list.item(row)
            if item is not None:
                item.setSizeHint(QSize(item_width, base_height))

    def _refresh_text(self, lang: str = "") -> None:
        self._title_label.setToolTip(tr("app.title"))
        self._brand_label.setText(tr("nav.brand"))
        self._rebuild_nav_items()

    def _on_theme_changed(self) -> None:
        """Re-apply any dynamic style changes when theme toggles."""
        pass  # Nav items are styled entirely by global QSS, no inline stylesheet cleanup needed

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.setFixedWidth(NAV_COLLAPSED_WIDTH if collapsed else NAV_WIDTH)
        self._title_label.setVisible(not collapsed)
        self._brand_label.setVisible(not collapsed)
        self._version_label.setVisible(not collapsed)
        self._rebuild_nav_items()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_item_sizes()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._list.viewport() and event.type() == QEvent.Type.Resize:
            self._update_item_sizes()
        return super().eventFilter(obj, event)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _on_selection_changed(self, row: int) -> None:
        if row >= 0:
            item = self._list.item(row)
            page_id = item.data(Qt.ItemDataRole.UserRole)
            self.page_selected.emit(page_id)

    def select_page(self, page_id: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == page_id:
                self._list.setCurrentRow(i)
                break
