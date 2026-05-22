"""Tests for YOLO bbox read/write at the annotation widget + I/O layer."""
from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

import desktop_app.label_config as label_config
from desktop_app.widgets.bbox_annotation_widget import (
    BboxAnnotationWidget,
    CLASS_COLORS,
    BACKGROUND_VALUES,
)


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication exists for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def widget(qapp, tmp_path, monkeypatch):
    """Create a BboxAnnotationWidget with mock label options."""
    # Mock label options to include known defect classes
    mock_opts = [
        label_config.LabelOption(value="裂纹", label="裂纹", color="#FF0000"),
        label_config.LabelOption(value="油污", label="油污", color="#00FF00"),
        label_config.LabelOption(value="点伤", label="点伤", color="#0000FF"),
    ]

    def _mock_load():
        return mock_opts

    monkeypatch.setattr(label_config, "load_label_options", _mock_load)

    w = BboxAnnotationWidget()
    return w


@pytest.fixture
def sample_image(tmp_path):
    """Create a small test PNG image."""
    from PySide6.QtGui import QImage
    img = QImage(640, 480, QImage.Format.Format_RGB32)
    img.fill(0xFF808080)
    path = str(tmp_path / "test_image.png")
    img.save(path)
    return path


# ── Background values filter ──────────────────────────────────────

def test_background_values_are_filtered():
    assert "OK" in BACKGROUND_VALUES
    assert "UNKNOWN" in BACKGROUND_VALUES
    assert "IGNORE" in BACKGROUND_VALUES
    assert "裂纹" not in BACKGROUND_VALUES


# ── CLASS_COLORS ──────────────────────────────────────────────────

def test_class_colors_has_entries():
    assert len(CLASS_COLORS) >= 10


# ── Widget creation ───────────────────────────────────────────────

def test_widget_creates_without_image(widget, qapp):
    assert widget is not None
    assert widget.get_bboxes() == []
    assert widget.get_image_path() == ""


def test_widget_load_image(widget, sample_image):
    widget.load_image(sample_image)
    assert widget.get_image_path() == sample_image


# ── Bbox CRUD ─────────────────────────────────────────────────────

def test_widget_set_get_bboxes(widget, sample_image):
    widget.load_image(sample_image)
    bboxes = [
        {"class_id": 0, "class_name": "裂纹", "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1, "color": "#FF0000"},
        {"class_id": 1, "class_name": "油污", "x_center": 0.3, "y_center": 0.3, "width": 0.2, "height": 0.15, "color": "#00FF00"},
    ]
    widget.set_bboxes(bboxes)
    assert len(widget.get_bboxes()) == 2
    assert widget.get_bboxes()[0]["class_name"] == "裂纹"


def test_widget_clear_bboxes(widget, sample_image):
    widget.load_image(sample_image)
    widget.set_bboxes([
        {"class_id": 0, "class_name": "裂纹", "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1, "color": "#FF0000"},
    ])
    widget.clear_bboxes()
    assert widget.get_bboxes() == []


# ── Save / Load YOLO .txt ────────────────────────────────────────

def test_widget_save_to_file(widget, sample_image):
    widget.load_image(sample_image)
    widget.set_bboxes([
        {"class_id": 0, "class_name": "裂纹", "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.1, "color": "#FF0000"},
    ])
    widget.save_to_file()

    stem, _ = os.path.splitext(sample_image)
    txt_path = stem + ".txt"
    assert os.path.isfile(txt_path)

    with open(txt_path, encoding="utf-8") as f:
        content = f.read().strip()
    assert content == "0 0.500000 0.500000 0.200000 0.100000"


def test_widget_save_empty_bboxes(widget, sample_image, tmp_path):
    widget.load_image(sample_image)
    widget.clear_bboxes()
    widget.save_to_file()

    stem, _ = os.path.splitext(sample_image)
    txt_path = stem + ".txt"
    # Should create empty file
    assert os.path.isfile(txt_path)
    with open(txt_path, encoding="utf-8") as f:
        assert f.read().strip() == ""


def test_widget_load_from_file(widget, sample_image, monkeypatch):
    # First save with mock options
    widget.load_image(sample_image)
    widget.set_bboxes([
        {"class_id": 0, "class_name": "裂纹", "x_center": 0.3, "y_center": 0.4, "width": 0.15, "height": 0.12, "color": "#FF0000"},
        {"class_id": 1, "class_name": "油污", "x_center": 0.7, "y_center": 0.6, "width": 0.1, "height": 0.08, "color": "#00FF00"},
    ])
    widget.save_to_file()

    # Reload into fresh widget with same class mapping
    mock_opts = [
        label_config.LabelOption(value="裂纹", label="裂纹", color="#FF0000"),
        label_config.LabelOption(value="油污", label="油污", color="#00FF00"),
        label_config.LabelOption(value="点伤", label="点伤", color="#0000FF"),
    ]
    monkeypatch.setattr(label_config, "load_label_options", lambda: mock_opts)

    w2 = BboxAnnotationWidget()
    # Ensure _class_options is what we expect (bypass the real load_label_options)
    w2._class_options = mock_opts
    w2._rebuild_class_combo()
    w2.load_image(sample_image)

    bboxes = w2.get_bboxes()
    assert len(bboxes) == 2
    assert bboxes[0]["class_id"] == 0
    assert bboxes[0]["class_name"] == "裂纹"
    assert abs(bboxes[0]["x_center"] - 0.3) < 0.001
    assert abs(bboxes[0]["y_center"] - 0.4) < 0.001
    assert abs(bboxes[0]["width"] - 0.15) < 0.001
    assert abs(bboxes[0]["height"] - 0.12) < 0.001


def test_widget_load_nonexistent_file(widget, sample_image):
    """Loading when no .txt exists should produce empty bboxes."""
    # Ensure no sidecar
    stem, _ = os.path.splitext(sample_image)
    txt_path = stem + ".txt"
    if os.path.isfile(txt_path):
        os.remove(txt_path)

    widget.load_image(sample_image)
    assert widget.get_bboxes() == []


def test_widget_load_invalid_txt(widget, sample_image):
    """Invalid .txt content should not crash."""
    stem, _ = os.path.splitext(sample_image)
    txt_path = stem + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("garbage without proper format\n")
        f.write("999 0.5 0.5 0.1 0.1\n")  # class_id out of range, but should load (gets default color/name)

    widget.load_image(sample_image)
    bboxes = widget.get_bboxes()
    # Garbage line skipped, out-of-range class_id still loads with default color
    assert len(bboxes) >= 1


# ── Stats ─────────────────────────────────────────────────────────

def test_widget_get_stats(widget, sample_image):
    widget.load_image(sample_image)
    widget.set_bboxes([
        {"class_id": 0, "class_name": "裂纹", "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1, "color": "#FF0000"},
        {"class_id": 0, "class_name": "裂纹", "x_center": 0.3, "y_center": 0.3, "width": 0.1, "height": 0.1, "color": "#FF0000"},
        {"class_id": 1, "class_name": "油污", "x_center": 0.7, "y_center": 0.7, "width": 0.1, "height": 0.1, "color": "#00FF00"},
    ])
    stats = widget.get_stats()
    assert stats == {"裂纹": 2, "油污": 1}


# ── Bbox normalize round-trip ─────────────────────────────────────

def test_bbox_normalize_round_trip(widget, sample_image, monkeypatch):
    """Bboxes saved in normalized coords should reload identically."""
    widget.load_image(sample_image)
    original = [
        {"class_id": 0, "class_name": "裂纹", "x_center": 0.123456, "y_center": 0.654321, "width": 0.080000, "height": 0.120000, "color": "#FF0000"},
    ]
    widget.set_bboxes(original)
    widget.save_to_file()

    # Reload with same mock label options
    mock_opts = [
        label_config.LabelOption(value="裂纹", label="裂纹", color="#FF0000"),
        label_config.LabelOption(value="油污", label="油污", color="#00FF00"),
        label_config.LabelOption(value="点伤", label="点伤", color="#0000FF"),
    ]
    monkeypatch.setattr(label_config, "load_label_options", lambda: mock_opts)

    w2 = BboxAnnotationWidget()
    w2._class_options = mock_opts
    w2._rebuild_class_combo()
    w2.load_image(sample_image)
    loaded = w2.get_bboxes()
    assert len(loaded) == 1
    for key in ("x_center", "y_center", "width", "height"):
        assert abs(loaded[0][key] - original[0][key]) < 0.0001, f"{key} mismatch"
