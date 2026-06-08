"""Theme manager — dual palette (light/dark) with dynamic QSS generation.

Phase H: Win11 Fluent Design light theme as default, dark theme toggle capability.
Replaces the single-theme module constants in theme.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class ThemePalette:
    """Immutable color palette for a single theme."""

    PRIMARY: str
    PRIMARY_LIGHT: str
    PRIMARY_DARK: str
    ACCENT: str
    SUCCESS: str
    WARNING: str
    ERROR: str
    BG_MAIN: str
    BG_PANEL: str
    BG_INPUT: str
    TEXT_PRIMARY: str
    TEXT_SECONDARY: str
    BORDER: str

    # Gauge/status indicator colors (stable across themes)
    GAUGE_GREEN: str = "#4CAF50"
    GAUGE_ORANGE: str = "#FF9800"
    GAUGE_RED: str = "#F44336"

    # Nav selected background tint (light blue bg for light theme)
    NAV_SELECTED_BG: str = "#E5F0FF"
    NAV_HOVER_BG: str = "#F0F0F0"

    # Link / accent text
    LINK_COLOR: str = "#0078D4"

    @property
    def input_focus_border(self) -> str:
        return f"2px solid {self.PRIMARY}"


# ── Predefined palettes ──────────────────────────────────────────────

PALETTE_LIGHT = ThemePalette(
    PRIMARY="#0078D4",
    PRIMARY_LIGHT="#106EBE",
    PRIMARY_DARK="#005A9E",
    ACCENT="#0078D4",
    SUCCESS="#107C10",
    WARNING="#FF8C00",
    ERROR="#C42B1C",
    BG_MAIN="#F5F5F5",
    BG_PANEL="#FFFFFF",
    BG_INPUT="#FFFFFF",
    TEXT_PRIMARY="#1A1A1A",
    TEXT_SECONDARY="#666666",
    BORDER="#E0E0E0",
    GAUGE_GREEN="#4CAF50",
    GAUGE_ORANGE="#FF9800",
    GAUGE_RED="#F44336",
    NAV_SELECTED_BG="#E5F0FF",
    NAV_HOVER_BG="#F0F0F0",
    LINK_COLOR="#0078D4",
)

PALETTE_DARK = ThemePalette(
    PRIMARY="#1565C0",
    PRIMARY_LIGHT="#1E88E5",
    PRIMARY_DARK="#0D47A1",
    ACCENT="#FF6F00",
    SUCCESS="#2E7D32",
    WARNING="#F57F17",
    ERROR="#C62828",
    BG_MAIN="#1E1E1E",
    BG_PANEL="#252526",
    BG_INPUT="#333333",
    TEXT_PRIMARY="#FFFFFF",
    TEXT_SECONDARY="#B0B0B0",
    BORDER="#3E3E3E",
    GAUGE_GREEN="#4CAF50",
    GAUGE_ORANGE="#FF9800",
    GAUGE_RED="#F44336",
    NAV_SELECTED_BG="#1A3350",
    NAV_HOVER_BG="#3A3A3A",
    LINK_COLOR="#64B5F6",
)

# Chinese-first font stack
_FONT_FAMILY = (
    '"Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", '
    '"WenQuanYi Micro Hei", system-ui, sans-serif'
)
_FONT_SIZE = "13px"
_FONT_SIZE_SMALL = "11px"
_FONT_SIZE_LARGE = "15px"


class ThemeManager(QObject):
    """Singleton managing active theme palette and QSS stylesheet generation."""

    theme_changed = Signal()

    _instance: ThemeManager | None = None

    def __init__(self) -> None:
        super().__init__()
        self._current: ThemePalette = PALETTE_LIGHT
        ThemeManager._instance = self

    @classmethod
    def instance(cls) -> ThemeManager:
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    @classmethod
    def current(cls) -> ThemePalette:
        return cls.instance()._current

    @property
    def palette(self) -> ThemePalette:
        return self._current

    def set_theme(self, palette: ThemePalette) -> None:
        if palette is self._current:
            return
        self._current = palette
        self.theme_changed.emit()

    def toggle(self) -> None:
        if self.is_dark():
            self.set_theme(PALETTE_LIGHT)
        else:
            self.set_theme(PALETTE_DARK)

    def is_dark(self) -> bool:
        return self._current is PALETTE_DARK

    # ── QSS generation ───────────────────────────────────────────────

    def get_stylesheet(self) -> str:
        c = self._current
        return f"""
        /* ── Global defaults ─────────────────────────────────── */
        QMainWindow {{
            background-color: {c.BG_MAIN};
        }}
        QWidget {{
            background-color: {c.BG_MAIN};
            color: {c.TEXT_PRIMARY};
            font-family: {_FONT_FAMILY};
            font-size: {_FONT_SIZE};
        }}

        /* ── Navigation sidebar ──────────────────────────────── */
        QListWidget {{
            background-color: {c.BG_PANEL};
            border: none;
            outline: none;
            padding: 2px 0;
        }}
        QListWidget::item {{
            padding: 10px 8px;
            border-left: 3px solid transparent;
            color: {c.TEXT_SECONDARY};
            font-size: {_FONT_SIZE};
        }}
        QListWidget::item:selected {{
            background-color: {c.PRIMARY};
            color: #FFFFFF;
            border-left: 3px solid {c.ACCENT};
        }}
        QListWidget::item:hover {{
            background-color: {c.BG_INPUT};
            color: {c.TEXT_PRIMARY};
        }}
        QListWidget#navList {{
            background-color: {c.BG_PANEL};
            border: none;
            padding: 6px 6px;
        }}
        QListWidget#navList::item {{
            font-size: {_FONT_SIZE};
            font-weight: bold;
            padding: 0;
            margin: 3px 6px;
            background-color: transparent;
            border-radius: 6px;
            border-left: 3px solid transparent;
            color: {c.TEXT_SECONDARY};
        }}
        QListWidget#navList::item:selected {{
            background-color: {c.NAV_SELECTED_BG};
            color: {c.PRIMARY};
            border-left: 3px solid {c.PRIMARY};
        }}
        QListWidget#navList::item:hover:!selected {{
            background-color: {c.NAV_HOVER_BG};
            color: {c.TEXT_PRIMARY};
        }}

        /* ── Buttons ─────────────────────────────────────────── */
        QPushButton {{
            background-color: {c.PRIMARY};
            color: #FFFFFF;
            border: none;
            padding: 7px 16px;
            border-radius: 6px;
            font-weight: bold;
            font-size: {_FONT_SIZE};
            min-height: 24px;
        }}
        QPushButton:hover {{
            background-color: {c.PRIMARY_LIGHT};
        }}
        QPushButton:pressed {{
            background-color: {c.PRIMARY_DARK};
        }}
        QPushButton:disabled {{
            background-color: {c.BORDER};
            color: {c.TEXT_SECONDARY};
        }}
        QPushButton#dangerBtn {{
            background-color: {c.ERROR};
            color: #FFFFFF;
        }}
        QPushButton#dangerBtn:hover {{
            background-color: #D32F2F;
        }}
        QPushButton#secondaryBtn {{
            background-color: {c.BG_INPUT};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER};
        }}
        QPushButton#secondaryBtn:hover {{
            background-color: {c.BORDER};
        }}
        QPushButton#sidebarToggleBtn {{
            background-color: {c.BG_PANEL};
            color: {c.TEXT_SECONDARY};
            border: 1px solid {c.BORDER};
            border-radius: 6px;
            padding: 0;
            font-size: 16px;
            font-weight: normal;
        }}
        QPushButton#sidebarToggleBtn:hover {{
            background-color: {c.BG_INPUT};
            color: {c.TEXT_PRIMARY};
        }}

        /* ── Inputs ──────────────────────────────────────────── */
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background-color: {c.BG_INPUT};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER};
            padding: 6px 10px;
            border-radius: 4px;
            font-size: {_FONT_SIZE};
            min-height: 24px;
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {c.PRIMARY};
        }}

        /* ── ComboBox dropdown ───────────────────────────────── */
        QComboBox QAbstractItemView {{
            background-color: {c.BG_PANEL};
            color: {c.TEXT_PRIMARY};
            selection-background-color: {c.PRIMARY};
            selection-color: #FFFFFF;
            border: 1px solid {c.BORDER};
            font-size: {_FONT_SIZE};
            padding: 4px;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid {c.BORDER};
        }}

        /* ── Table ───────────────────────────────────────────── */
        QTableWidget {{
            background-color: {c.BG_PANEL};
            alternate-background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            gridline-color: {c.BORDER};
            selection-background-color: {c.PRIMARY};
            selection-color: #FFFFFF;
            font-size: {_FONT_SIZE};
        }}
        QTableWidget::item {{
            padding: 5px 8px;
        }}
        QTableWidget::item:selected {{
            background-color: {c.PRIMARY};
            color: #FFFFFF;
        }}
        QHeaderView::section {{
            background-color: {c.BG_MAIN};
            color: {c.TEXT_SECONDARY};
            padding: 7px 8px;
            border: none;
            border-bottom: 2px solid {c.BORDER};
            font-weight: bold;
            font-size: {_FONT_SIZE};
        }}

        /* ── Group box ───────────────────────────────────────── */
        QGroupBox {{
            border: 1px solid {c.BORDER};
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 16px;
            font-size: {_FONT_SIZE};
            font-weight: bold;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: {c.TEXT_PRIMARY};
        }}
        QGroupBox#cardGroupBox {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.BORDER};
            border-radius: 8px;
            margin-top: 8px;
            padding-top: 16px;
        }}
        QGroupBox#cardGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: {c.TEXT_PRIMARY};
            font-weight: bold;
        }}

        /* ── Card frames ─────────────────────────────────────── */
        QFrame#cardFrame {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.BORDER};
            border-radius: 8px;
            padding: 12px;
        }}
        QFrame#workbenchCard {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.BORDER};
            border-radius: 8px;
            padding: 14px;
            min-width: 150px;
        }}
        QFrame#workbenchStateFrame {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.BORDER};
            border-radius: 8px;
            padding: 12px;
        }}

        /* ── Labels ──────────────────────────────────────────── */
        QLabel {{
            color: {c.TEXT_PRIMARY};
            font-size: {_FONT_SIZE};
            background-color: transparent;
        }}
        QLabel#secondaryLabel {{
            color: {c.TEXT_SECONDARY};
            font-size: 11px;
            background-color: transparent;
        }}
        QLabel#navBrandLabel {{
            font-size: 10px;
            font-weight: bold;
            color: {c.TEXT_SECONDARY};
            padding: 0 8px 1px 8px;
            background-color: transparent;
        }}
        QLabel#navVersionLabel {{
            font-size: 9px;
            color: {c.TEXT_SECONDARY};
            padding: 0 8px 4px 8px;
            background-color: transparent;
        }}

        /* ── Tab widget ──────────────────────────────────────── */
        QTabWidget::pane {{
            border: 1px solid {c.BORDER};
            background-color: {c.BG_PANEL};
            border-radius: 4px;
        }}
        QTabBar::tab {{
            background-color: {c.BG_MAIN};
            color: {c.TEXT_SECONDARY};
            padding: 8px 18px;
            border: 1px solid transparent;
            border-bottom: none;
            font-size: {_FONT_SIZE};
            min-width: 60px;
        }}
        QTabBar::tab:selected {{
            background-color: {c.BG_PANEL};
            color: {c.TEXT_PRIMARY};
            border-bottom: 2px solid {c.PRIMARY};
            font-weight: bold;
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {c.BG_INPUT};
            color: {c.TEXT_PRIMARY};
        }}

        /* ── Status bar ──────────────────────────────────────── */
        QStatusBar {{
            background-color: {c.BG_PANEL};
            color: {c.TEXT_SECONDARY};
            border-top: 1px solid {c.BORDER};
            font-size: {_FONT_SIZE_SMALL};
        }}

        /* ── Scroll bar ──────────────────────────────────────── */
        QScrollBar:vertical {{
            background-color: {c.BG_MAIN};
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {c.BORDER};
            border-radius: 5px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: #999;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background-color: {c.BG_MAIN};
            height: 10px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {c.BORDER};
            border-radius: 5px;
            min-width: 20px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: #999;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}

        /* ── Progress bar ────────────────────────────────────── */
        QProgressBar {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: 4px;
            text-align: center;
            font-size: {_FONT_SIZE_SMALL};
            color: {c.TEXT_PRIMARY};
        }}
        QProgressBar::chunk {{
            background-color: {c.PRIMARY};
            border-radius: 3px;
        }}

        /* ── Tooltip ─────────────────────────────────────────── */
        QToolTip {{
            background-color: {c.BG_PANEL};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER};
            padding: 4px 8px;
            font-size: {_FONT_SIZE_SMALL};
        }}

        /* ── Splitter ────────────────────────────────────────── */
        QSplitter::handle {{
            background-color: {c.BORDER};
            width: 1px;
        }}

        /* ── Text edit (logs, reports) ───────────────────────── */
        QTextEdit, QPlainTextEdit {{
            background-color: {c.BG_INPUT};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER};
            border-radius: 4px;
            padding: 6px;
            font-size: {_FONT_SIZE_SMALL};
            selection-background-color: {c.PRIMARY};
            selection-color: #FFFFFF;
        }}

        /* ── Spinbox specifics ───────────────────────────────── */
        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 20px;
        }}
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 20px;
        }}

        /* ── Workbench overview bar ──────────────────────────── */
        QFrame#workbenchOverview {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.BORDER};
            border-radius: 8px;
            padding: 12px 16px;
        }}

        /* ── Workbench step items ───────────────────────────── */
        QFrame#workbenchStepItem {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.BORDER};
            border-left: 3px solid transparent;
            border-radius: 6px;
            padding: 10px 14px;
        }}
        QFrame#workbenchStepItem:hover {{
            background-color: {c.BG_INPUT};
        }}
        QFrame#workbenchStepItemCurrent {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.PRIMARY};
            border-left: 3px solid {c.PRIMARY};
            border-radius: 6px;
            padding: 10px 14px;
        }}
        QFrame#workbenchStepItemDone {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.BORDER};
            border-left: 3px solid {c.SUCCESS};
            border-radius: 6px;
            padding: 10px 14px;
        }}
        QFrame#workbenchStepItemBlocked {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.WARNING};
            border-left: 3px solid {c.WARNING};
            border-radius: 6px;
            padding: 10px 14px;
        }}

        /* ── Workbench detail panel ─────────────────────────── */
        QFrame#workbenchStepDetail {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.BORDER};
            border-radius: 8px;
            padding: 16px;
        }}

        /* ── Workbench bottom hint ──────────────────────────── */
        QFrame#workbenchNextHint {{
            background-color: {c.BG_PANEL};
            border: 1px solid {c.BORDER};
            border-radius: 8px;
            padding: 10px 16px;
        }}

        /* ── Workbench action buttons ───────────────────────── */
        QPushButton[objectName^="workbenchAction_"] {{
            text-align: left;
            padding: 10px 14px;
            font-size: {_FONT_SIZE_LARGE};
            min-height: 38px;
        }}

        /* ── Menu bar ────────────────────────────────────────── */
        QMenuBar {{
            background-color: {c.BG_MAIN};
            color: {c.TEXT_PRIMARY};
            font-size: {_FONT_SIZE};
        }}
        QMenuBar::item:selected {{
            background-color: {c.PRIMARY};
            color: #FFFFFF;
        }}
        QMenu {{
            background-color: {c.BG_PANEL};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER};
            font-size: {_FONT_SIZE};
            padding: 4px 0;
        }}
        QMenu::item {{
            padding: 6px 24px;
        }}
        QMenu::item:selected {{
            background-color: {c.PRIMARY};
            color: #FFFFFF;
        }}

        /* ── Checkbox / Radio ────────────────────────────────── */
        QCheckBox, QRadioButton {{
            color: {c.TEXT_PRIMARY};
            font-size: {_FONT_SIZE};
            spacing: 6px;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 16px;
            height: 16px;
        }}

        /* ── File dialog ─────────────────────────────────────── */
        QFileDialog {{
            background-color: {c.BG_PANEL};
            color: {c.TEXT_PRIMARY};
        }}
        """
