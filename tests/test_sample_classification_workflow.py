"""Tests for the sample classification queue workflow."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desktop_app.pages.sample_classification_page import (
    BATCH_SIZE,
    SampleClassificationPage,
    batch_start_for_index,
    next_index_after_label,
)


def test_batch_start_uses_twelve_image_pages():
    assert BATCH_SIZE == 12
    assert batch_start_for_index(0) == 0
    assert batch_start_for_index(11) == 0
    assert batch_start_for_index(12) == 12
    assert batch_start_for_index(23) == 12


def test_labeling_advances_to_next_image_and_stops_at_end():
    assert next_index_after_label(0, 5) == 1
    assert next_index_after_label(10, 12) == 11
    assert next_index_after_label(11, 12) == 11


def test_label_filter_searches_all_images_not_only_current_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])

    paths = [str(tmp_path / f"image_{index:02d}.png") for index in range(15)]
    for path in paths:
        open(path, "wb").close()

    page = SampleClassificationPage()
    page._image_paths = paths
    page._labels = {paths[14]: "CRACK"}
    page._label_options = [
        type("LabelOptionStub", (), {"value": "OK", "label": "OK"})(),
        type("LabelOptionStub", (), {"value": "CRACK", "label": "NG-裂纹"})(),
    ]
    page._current_index = 0
    page._batch_start = 0
    page._render_batch()

    page._grid._label_filter.setCurrentIndex(page._grid._label_filter.findData("CRACK"))

    visible_paths = [page._grid._list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(page._grid._list.count())]

    assert visible_paths == [paths[14]]


def test_relabeling_filtered_image_advances_within_current_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])

    paths = [str(tmp_path / f"image_{index:02d}.png") for index in range(6)]
    for path in paths:
        open(path, "wb").close()

    page = SampleClassificationPage()
    page._image_paths = paths
    page._labels = {
        paths[1]: "CRACK",
        paths[3]: "CRACK",
        paths[5]: "CRACK",
    }
    page._label_options = [
        type("LabelOptionStub", (), {"value": "OK", "label": "OK"})(),
        type("LabelOptionStub", (), {"value": "CRACK", "label": "NG-裂纹"})(),
    ]
    page._current_index = 1
    page._batch_start = 0
    page._render_batch()
    page._grid._label_filter.setCurrentIndex(page._grid._label_filter.findData("CRACK"))

    page._classify_current("OK")

    assert page._image_paths[page._current_index] == paths[3]

    page._navigate(1)

    assert page._image_paths[page._current_index] == paths[5]


def test_filtered_navigation_selects_visible_items_in_order(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])

    paths = [str(tmp_path / f"image_{index:02d}.png") for index in range(8)]
    for path in paths:
        open(path, "wb").close()

    page = SampleClassificationPage()
    page._image_paths = paths
    page._labels = {path: "CRACK" for path in paths}
    page._label_options = [type("LabelOptionStub", (), {"value": "CRACK", "label": "NG-裂纹"})()]
    page._current_index = 0
    page._batch_start = 0
    page._render_batch()
    page._grid._label_filter.setCurrentIndex(page._grid._label_filter.findData("CRACK"))

    visited = [page._image_paths[page._current_index]]
    for _ in range(3):
        page._navigate(1)
        visited.append(page._image_paths[page._current_index])

    assert visited == paths[:4]
