"""Left navigation bar widget."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel

from desktop_app.constants import NAV_ITEMS, NAV_WIDTH, NAV_COLLAPSED_WIDTH
from desktop_app.i18n import tr, bind, I18nManager


class NavigationBar(QWidget):
    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._collapsed = False
        self.setFixedWidth(NAV_WIDTH)
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

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
            "font-size: 19px; font-weight: bold; padding: 14px 8px 1px 8px;"
        )
        self._title_label.setWordWrap(False)
        layout.addWidget(self._title_label)

        self._brand_label = QLabel()
        bind(self._brand_label, "nav.brand")
        self._brand_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._brand_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #B0B0B0; padding: 0 8px 2px 8px;")
        layout.addWidget(self._brand_label)

        self._version_label = QLabel()
        bind(self._version_label, "app.version")
        self._version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._version_label.setStyleSheet("font-size: 10px; color: #888; padding: 0 8px 9px 8px;")
        layout.addWidget(self._version_label)

        # Nav list
        self._list = QListWidget()
        self._list.setObjectName("navList")
        self._rebuild_nav_items()
        self._list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

    def _rebuild_nav_items(self) -> None:
        self._list.clear()
        lang = I18nManager.instance().language
        for item in NAV_ITEMS:
            label = tr(f'nav.{item["id"]}')
            text = f"{item['icon']}" if self._collapsed else f"{item['icon']}  {label}"
            list_item = QListWidgetItem(text)
            font = QFont()
            font.setPointSize(10 if lang == "en" else 11)
            font.setBold(True)
            list_item.setFont(font)
            list_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            list_item.setToolTip(label)
            list_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list.addItem(list_item)

    def _refresh_text(self, lang: str = "") -> None:
        self._title_label.setToolTip(tr("app.title"))
        self._brand_label.setText(tr("nav.brand"))
        self._rebuild_nav_items()

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.setFixedWidth(NAV_COLLAPSED_WIDTH if collapsed else NAV_WIDTH)
        self._title_label.setVisible(not collapsed)
        self._brand_label.setVisible(not collapsed)
        self._version_label.setVisible(not collapsed)
        self._rebuild_nav_items()

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
