"""QSS theme compatibility shim — delegates to theme_manager.

Phase H: This module is retained for backward compatibility during migration.
All new code should use ThemeManager from desktop_app.theme_manager directly.
"""

from __future__ import annotations

from desktop_app.theme_manager import ThemeManager, ThemePalette, PALETTE_LIGHT, PALETTE_DARK


def get_stylesheet() -> str:
    """Legacy entry point — delegates to ThemeManager."""
    return ThemeManager.instance().get_stylesheet()


# Re-export color constants from the default (light) palette for backward compat
_c = PALETTE_LIGHT
PRIMARY = _c.PRIMARY
PRIMARY_LIGHT = _c.PRIMARY_LIGHT
PRIMARY_DARK = _c.PRIMARY_DARK
ACCENT = _c.ACCENT
SUCCESS = _c.SUCCESS
WARNING = _c.WARNING
ERROR = _c.ERROR
BG_DARK = _c.BG_MAIN
BG_PANEL = _c.BG_PANEL
BG_INPUT = _c.BG_INPUT
TEXT_PRIMARY = _c.TEXT_PRIMARY
TEXT_SECONDARY = _c.TEXT_SECONDARY
BORDER = _c.BORDER
