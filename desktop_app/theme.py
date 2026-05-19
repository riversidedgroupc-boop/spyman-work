"""QSS theme and color palette for the desktop application."""
from __future__ import annotations

# Color palette
PRIMARY = "#1565C0"
PRIMARY_LIGHT = "#1E88E5"
PRIMARY_DARK = "#0D47A1"
ACCENT = "#FF6F00"
SUCCESS = "#2E7D32"
WARNING = "#F57F17"
ERROR = "#C62828"
BG_DARK = "#1E1E1E"
BG_PANEL = "#252526"
BG_INPUT = "#333333"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#B0B0B0"
BORDER = "#3E3E3E"


def get_stylesheet() -> str:
    return f"""
    QMainWindow {{
        background-color: {BG_DARK};
    }}
    QWidget {{
        background-color: {BG_DARK};
        color: {TEXT_PRIMARY};
        font-size: 12px;
    }}
    QListWidget {{
        background-color: {BG_PANEL};
        border: none;
        outline: none;
        padding: 5px 0;
    }}
    QListWidget::item {{
        padding: 10px 6px;
        border-left: 3px solid transparent;
        color: {TEXT_SECONDARY};
        font-size: 13px;
    }}
    QListWidget::item:selected {{
        background-color: {PRIMARY};
        color: {TEXT_PRIMARY};
        border-left: 3px solid {ACCENT};
    }}
    QListWidget::item:hover {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
    }}
    QListWidget#navList::item {{
        font-size: 16px;
        font-weight: bold;
        padding: 13px 4px;
        margin: 3px 4px;
        border-radius: 6px;
        border-left: 4px solid transparent;
    }}
    QListWidget#navList::item:selected {{
        background-color: {PRIMARY};
        color: {TEXT_PRIMARY};
        border-left: 4px solid {ACCENT};
    }}
    QListWidget#navList::item:hover {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
    }}
    QPushButton {{
        background-color: {PRIMARY};
        color: {TEXT_PRIMARY};
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {PRIMARY_LIGHT};
    }}
    QPushButton:pressed {{
        background-color: {PRIMARY_DARK};
    }}
    QPushButton#dangerBtn {{
        background-color: {ERROR};
    }}
    QPushButton#dangerBtn:hover {{
        background-color: #D32F2F;
    }}
    QPushButton#secondaryBtn {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
    }}
    QPushButton#secondaryBtn:hover {{
        background-color: #444;
    }}
    QPushButton#sidebarToggleBtn {{
        background-color: {BG_PANEL};
        color: {TEXT_SECONDARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 0;
        font-size: 16px;
        font-weight: normal;
    }}
    QPushButton#sidebarToggleBtn:hover {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        padding: 4px 8px;
        border-radius: 4px;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1px solid {PRIMARY};
    }}
    QTableWidget {{
        background-color: {BG_PANEL};
        alternate-background-color: {BG_INPUT};
        border: 1px solid {BORDER};
        gridline-color: {BORDER};
        selection-background-color: {PRIMARY};
        selection-color: {TEXT_PRIMARY};
    }}
    QTableWidget::item {{
        padding: 4px;
    }}
    QTableWidget::item:selected {{
        background-color: {PRIMARY};
        color: {TEXT_PRIMARY};
    }}
    QHeaderView::section {{
        background-color: {BG_DARK};
        color: {TEXT_SECONDARY};
        padding: 6px;
        border: none;
        border-bottom: 2px solid {BORDER};
        font-weight: bold;
    }}
    QLabel {{
        color: {TEXT_PRIMARY};
    }}
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: 6px;
        margin-top: 9px;
        padding-top: 15px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {TEXT_PRIMARY};
    }}
    QTabWidget::pane {{
        border: 1px solid {BORDER};
        background-color: {BG_PANEL};
    }}
    QTabBar::tab {{
        background-color: {BG_DARK};
        color: {TEXT_SECONDARY};
        padding: 6px 12px;
        border: 1px solid {BORDER};
    }}
    QTabBar::tab:selected {{
        background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        border-bottom: 2px solid {PRIMARY};
    }}
    QStatusBar {{
        background-color: {BG_PANEL};
        color: {TEXT_SECONDARY};
        border-top: 1px solid {BORDER};
    }}
    QScrollBar:vertical {{
        background-color: {BG_DARK};
        width: 10px;
    }}
    QScrollBar::handle:vertical {{
        background-color: #555;
        border-radius: 5px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: #777;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
"""
