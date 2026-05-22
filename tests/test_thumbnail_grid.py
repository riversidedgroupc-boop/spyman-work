"""Tests for the thumbnail grid widget."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def test_unlabeled_filter_shows_only_images_without_label(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])

    from desktop_app.widgets.thumbnail_grid import ThumbnailGrid, UNLABELED_FILTER_VALUE

    paths = [str(tmp_path / name) for name in ["a.png", "b.png", "c.png"]]
    for path in paths:
        open(path, "wb").close()

    grid = ThumbnailGrid()
    grid.set_images(paths, labels={paths[1]: "OK", paths[2]: ""})

    index = grid._label_filter.findData(UNLABELED_FILTER_VALUE)
    grid._label_filter.setCurrentIndex(index)

    visible_paths = [
        grid._list.item(row).data(Qt.ItemDataRole.UserRole)
        for row in range(grid._list.count())
    ]

    assert app is not None
    assert visible_paths == [paths[0], paths[2]]


def test_label_filter_selection_survives_label_option_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])

    from desktop_app.widgets.thumbnail_grid import ThumbnailGrid

    grid = ThumbnailGrid()
    grid.set_label_options([("OK", "OK"), ("OIL", "油污")])
    grid._label_filter.setCurrentIndex(grid._label_filter.findData("OIL"))

    grid.set_label_options([("OK", "OK"), ("OIL", "油污"), ("DIRTY", "污渍")])

    assert grid._label_filter.currentData() == "OIL"


def test_thumbnail_list_does_not_steal_spacebar_navigation_focus(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])

    from desktop_app.widgets.thumbnail_grid import ThumbnailGrid

    grid = ThumbnailGrid()

    assert grid._list.focusPolicy() == Qt.FocusPolicy.NoFocus
