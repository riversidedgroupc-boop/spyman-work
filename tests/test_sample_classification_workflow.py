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


def test_bbox_page_refreshes_label_cache_after_reclassification(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])

    from PySide6.QtGui import QImage

    from core.capture_session import add_captured_image, create_capture_session, set_image_classification
    from core.customer import create_customer
    from core.product_spec import create_product_spec
    from core.project import create_project
    from desktop_app.app_context import AppContext
    from desktop_app.pages.bbox_annotation_page import BboxAnnotationPage

    customer = create_customer("BBox Refresh Co", "BRC")
    project = create_project(customer.customer_id, "BBox Refresh Project")
    spec = create_product_spec(project.project_id, "BBox Refresh Spec", material="copper", geometry_type="tube")
    session = create_capture_session(project.project_id, spec.spec_id, "BBox Refresh Session")

    image_path = str(tmp_path / "sample.png")
    image = QImage(32, 32, QImage.Format.Format_RGB32)
    image.fill(0xFF808080)
    assert image.save(image_path)

    image_id = add_captured_image(session.session_id, project.project_id, image_path, "sample.png")
    set_image_classification(image_id, "油污")

    ctx = AppContext.instance()
    ctx.set_current_customer(customer.customer_id, customer.customer_name)
    ctx.set_current_project(project.project_id, project.project_name)
    ctx.set_current_spec(spec.spec_id, spec.product_name)

    page = BboxAnnotationPage()
    page._current_session_id = session.session_id
    page._load_images(session.session_id)
    assert page._image_labels[image_path] == "油污"

    set_image_classification(image_id, "点伤")
    page._refresh_sessions()
    page._set_filter("needs_bbox")

    assert page._image_labels[image_path] == "点伤"
    assert page._image_list.count() == 1
    assert "点伤" in page._image_list.item(0).text()
    assert "油污" not in page._image_list.item(0).text()

def test_bbox_page_displays_configured_label_text(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])

    from PySide6.QtGui import QImage

    from core.capture_session import add_captured_image, create_capture_session, set_image_classification
    from core.customer import create_customer
    from core.product_spec import create_product_spec
    from core.project import create_project
    from desktop_app.app_context import AppContext
    from desktop_app.pages.bbox_annotation_page import BboxAnnotationPage

    label_config_path = tmp_path / "class_labels.json"
    label_config_path.write_text(
        '[{"value": "OIL_STAIN", "label": "NG-点伤", "color": "#607D8B"}]',
        encoding="utf-8",
    )
    monkeypatch.setenv("COPPER_VISION_LABEL_CONFIG_PATH", str(label_config_path))

    customer = create_customer("BBox Display Co", "BDC")
    project = create_project(customer.customer_id, "BBox Display Project")
    spec = create_product_spec(project.project_id, "BBox Display Spec", material="copper", geometry_type="tube")
    session = create_capture_session(project.project_id, spec.spec_id, "BBox Display Session")

    image_path = str(tmp_path / "sample.png")
    image = QImage(32, 32, QImage.Format.Format_RGB32)
    image.fill(0xFF808080)
    assert image.save(image_path)

    image_id = add_captured_image(session.session_id, project.project_id, image_path, "sample.png")
    set_image_classification(image_id, "OIL_STAIN")

    ctx = AppContext.instance()
    ctx.set_current_customer(customer.customer_id, customer.customer_name)
    ctx.set_current_project(project.project_id, project.project_name)
    ctx.set_current_spec(spec.spec_id, spec.product_name)

    page = BboxAnnotationPage()
    page._current_session_id = session.session_id
    page._load_images(session.session_id)
    page._set_filter("needs_bbox")

    assert page._image_list.count() == 1
    item_text = page._image_list.item(0).text()
    assert "NG-点伤" in item_text
    assert "OIL_STAIN" not in item_text


def test_classification_save_uses_session_project_when_context_project_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])

    from PySide6.QtGui import QImage

    from core.capture_session import add_captured_image, create_capture_session, list_captured_images
    from core.customer import create_customer
    from core.product_spec import create_product_spec
    from core.project import create_project
    from desktop_app.app_context import AppContext

    customer = create_customer("Classify Save Co", "CSC")
    project = create_project(customer.customer_id, "Classify Save Project")
    spec = create_product_spec(project.project_id, "Classify Save Spec", material="copper", geometry_type="tube")
    session = create_capture_session(project.project_id, spec.spec_id, "Classify Save Session")

    image_path = str(tmp_path / "sample.png")
    image = QImage(32, 32, QImage.Format.Format_RGB32)
    image.fill(0xFF808080)
    assert image.save(image_path)
    add_captured_image(session.session_id, project.project_id, image_path, "sample.png")

    ctx = AppContext.instance()
    ctx.clear_project_context()

    page = SampleClassificationPage()
    page._current_session_id = session.session_id
    page._image_paths = [image_path]
    page._cameras = {image_path: ""}
    page._current_index = 0

    page._classify_current("NG_C")

    rows = list_captured_images(session.session_id)
    assert rows[0]["classification_label"] == "NG_C"
