"""Tests for classification-driven bbox filter in bbox_annotation_page.py."""
from __future__ import annotations

import os
import tempfile
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def page(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    """Create a BboxAnnotationPage with mocked DB dependencies."""
    from desktop_app.app_context import AppContext
    from desktop_app.pages.bbox_annotation_page import BboxAnnotationPage

    ctx = AppContext.instance()
    ctx.set_current_project("PROJ_TEST", "Test Project")

    # Mock list_capture_sessions to return an empty list
    monkeypatch.setattr(
        "desktop_app.pages.bbox_annotation_page.list_capture_sessions",
        lambda pid: [],
    )

    w = BboxAnnotationPage()
    yield w
    w.close()
    ctx.clear_all()


def _make_image_with_label(tmpdir: str, fname: str, label: str) -> str:
    """Create a dummy image file and return its path."""
    path = os.path.join(tmpdir, fname)
    with open(path, "wb") as f:
        f.write(b"\x00")
    return path


def _make_image_with_bbox(tmpdir: str, fname: str, label: str) -> tuple[str, str]:
    """Create a dummy image + sidecar .txt with one bbox."""
    img_path = os.path.join(tmpdir, fname)
    with open(img_path, "wb") as f:
        f.write(b"\x00")
    stem, _ = os.path.splitext(fname)
    txt_path = os.path.join(tmpdir, stem + ".txt")
    with open(txt_path, "w") as f:
        f.write("0 0.5 0.5 0.2 0.2\n")
    return img_path, txt_path


class TestBboxFilterModes:
    """Test that classification labels drive bbox filter modes correctly."""

    def test_needs_bbox_shows_only_defect_without_bbox(self, page, monkeypatch):
        """Default filter: only NG/defect images without bbox appear."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ok_img = _make_image_with_label(tmpdir, "ok_001.jpg", "OK")
            ng_no_bbox = _make_image_with_label(tmpdir, "ng_001.jpg", "裂纹")
            ng_with_bbox, _ = _make_image_with_bbox(tmpdir, "ng_002.jpg", "油污")
            review_img = _make_image_with_label(tmpdir, "unk_001.jpg", "UNKNOWN")

            page._image_paths = [ok_img, ng_no_bbox, ng_with_bbox, review_img]
            page._image_labels = {
                ok_img: "OK",
                ng_no_bbox: "裂纹",
                ng_with_bbox: "油污",
                review_img: "UNKNOWN",
            }
            page._filter_mode = "needs_bbox"

            filtered = page._get_filtered_paths()

            assert ng_no_bbox in filtered, "NG without bbox should appear"
            assert ok_img not in filtered, "OK should not appear"
            assert ng_with_bbox not in filtered, "NG with bbox should not appear in needs_bbox"
            assert review_img not in filtered, "UNKNOWN should not appear in needs_bbox"

    def test_all_defects_shows_all_defect_images(self, page):
        """all_defects filter: all NG/defect images regardless of bbox."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ok_img = _make_image_with_label(tmpdir, "ok.jpg", "OK")
            ng_no_bbox = _make_image_with_label(tmpdir, "ng_no.jpg", "裂纹")
            ng_with_bbox, _ = _make_image_with_bbox(tmpdir, "ng_yes.jpg", "油污")

            page._image_paths = [ok_img, ng_no_bbox, ng_with_bbox]
            page._image_labels = {
                ok_img: "OK",
                ng_no_bbox: "裂纹",
                ng_with_bbox: "油污",
            }
            page._filter_mode = "all_defects"

            filtered = page._get_filtered_paths()

            assert ng_no_bbox in filtered
            assert ng_with_bbox in filtered
            assert ok_img not in filtered

    def test_has_bbox_shows_only_defect_with_bbox(self, page):
        """has_bbox filter: only defect images that already have bbox."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ng_no_bbox = _make_image_with_label(tmpdir, "ng_no.jpg", "裂纹")
            ng_with_bbox, _ = _make_image_with_bbox(tmpdir, "ng_yes.jpg", "油污")

            page._image_paths = [ng_no_bbox, ng_with_bbox]
            page._image_labels = {
                ng_no_bbox: "裂纹",
                ng_with_bbox: "油污",
            }
            page._filter_mode = "has_bbox"

            filtered = page._get_filtered_paths()

            assert ng_with_bbox in filtered
            assert ng_no_bbox not in filtered

    def test_review_shows_only_unknown_uncertain(self, page):
        """review filter: only UNKNOWN / UNCERTAIN images."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ok_img = _make_image_with_label(tmpdir, "ok.jpg", "OK")
            ng_img = _make_image_with_label(tmpdir, "ng.jpg", "裂纹")
            unk_img = _make_image_with_label(tmpdir, "unk.jpg", "UNKNOWN")
            unc_img = _make_image_with_label(tmpdir, "unc.jpg", "UNCERTAIN")

            page._image_paths = [ok_img, ng_img, unk_img, unc_img]
            page._image_labels = {
                ok_img: "OK",
                ng_img: "裂纹",
                unk_img: "UNKNOWN",
                unc_img: "UNCERTAIN",
            }
            page._filter_mode = "review"

            filtered = page._get_filtered_paths()

            assert unk_img in filtered
            assert unc_img in filtered
            assert ok_img not in filtered
            assert ng_img not in filtered

    def test_all_shows_everything(self, page):
        """all filter: every image regardless of label or bbox."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ok_img = _make_image_with_label(tmpdir, "ok.jpg", "OK")
            ng_img = _make_image_with_label(tmpdir, "ng.jpg", "裂纹")
            unk_img = _make_image_with_label(tmpdir, "unk.jpg", "UNKNOWN")

            page._image_paths = [ok_img, ng_img, unk_img]
            page._image_labels = {
                ok_img: "OK",
                ng_img: "裂纹",
                unk_img: "UNKNOWN",
            }
            page._filter_mode = "all"

            filtered = page._get_filtered_paths()

            assert len(filtered) == 3
            assert ok_img in filtered
            assert ng_img in filtered
            assert unk_img in filtered

    def test_ng_with_bbox_leaves_needs_bbox_queue(self, page):
        """After adding bbox, an NG image disappears from needs_bbox."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ng_img, txt_path = _make_image_with_bbox(tmpdir, "ng_now_bbox.jpg", "裂纹")

            page._image_paths = [ng_img]
            page._image_labels = {ng_img: "裂纹"}
            page._filter_mode = "needs_bbox"

            filtered = page._get_filtered_paths()
            assert ng_img not in filtered, "NG with bbox should leave needs_bbox queue"

            # But should still appear in all_defects
            page._filter_mode = "all_defects"
            filtered2 = page._get_filtered_paths()
            assert ng_img in filtered2

    def test_unlabeled_images_are_not_defects(self, page):
        """Images with no classification label are not treated as defects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            unlabeled = _make_image_with_label(tmpdir, "no_label.jpg", "")

            page._image_paths = [unlabeled]
            page._image_labels = {unlabeled: ""}
            page._filter_mode = "needs_bbox"

            filtered = page._get_filtered_paths()
            assert unlabeled not in filtered

    def test_legacy_no_bbox_filter_works(self, page):
        """Legacy 'no_bbox' filter still works (treated like needs_bbox)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ng_img, _ = _make_image_with_bbox(tmpdir, "ng.jpg", "裂纹")
            ng_no = _make_image_with_label(tmpdir, "ng_no.jpg", "油污")

            page._image_paths = [ng_img, ng_no]
            page._image_labels = {ng_img: "裂纹", ng_no: "油污"}
            page._filter_mode = "no_bbox"

            filtered = page._get_filtered_paths()
            # The old 'no_bbox' filter only excluded has_bbox, didn't check labels
            # So both should appear
            assert ng_img not in filtered, "Has bbox should be filtered out"
            # ng_no has no bbox, and is also a defect — should appear
            assert ng_no in filtered
