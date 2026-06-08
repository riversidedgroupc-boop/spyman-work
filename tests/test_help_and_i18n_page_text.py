"""Tests for help page freshness and localized dropdown copy."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_help_page_mentions_current_camera_workbench_in_both_languages() -> None:
    from desktop_app.pages.help_page import _build_en_content, _build_zh_content

    zh = _build_zh_content()
    en = _build_en_content()

    assert "相机工作台" in zh
    assert "现场会话" in zh
    assert "Camera Workbench" in en
    assert "Field Session" in en


def test_benchmark_dropdowns_are_localized_in_chinese(qapp: QApplication) -> None:
    from desktop_app.i18n import I18nManager
    from desktop_app.pages.benchmark_page import BenchmarkPage

    mgr = I18nManager.instance()
    previous = mgr.language
    mgr.set_language("zh")
    page = BenchmarkPage()
    try:
        assert page._model_combo.itemText(0) == "YOLO 检测"
        assert page._save_mode.itemText(0) == "仅保存 NG"
        assert page._source_type.itemText(0) == "模拟数据"
    finally:
        page.close()
        mgr.set_language(previous)


def test_benchmark_dropdowns_are_localized_in_english(qapp: QApplication) -> None:
    from desktop_app.i18n import I18nManager
    from desktop_app.pages.benchmark_page import BenchmarkPage

    mgr = I18nManager.instance()
    previous = mgr.language
    mgr.set_language("en")
    page = BenchmarkPage()
    try:
        assert page._model_combo.itemText(0) == "YOLO Detection"
        assert page._save_mode.itemText(0) == "Save NG Only"
        assert page._source_type.itemText(0) == "Simulated Data"
    finally:
        page.close()
        mgr.set_language(previous)
