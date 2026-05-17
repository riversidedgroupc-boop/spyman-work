"""Tests for core/sample_export.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.review import create_review_record
from core.sample_export import build_export_manifest, export_reviewed_samples


class TestBuildExportManifest:
    def test_basic(self):
        recs = [
            create_review_record("img_001.jpg", "d1", "scratch", 0.9, [0, 0, 10, 10], "true_defect"),
            create_review_record("img_002.jpg", "d2", "scratch", 0.5, [0, 0, 10, 10], "false_positive"),
        ]
        manifest = build_export_manifest(recs, "/images", "/output")
        assert len(manifest) == 2
        assert manifest[0]["review_label"] == "true_defect"
        assert "hard_positive" in manifest[0]["export_path"]
        assert "img_001.jpg" in manifest[0]["export_path"]
        assert manifest[1]["review_label"] == "false_positive"
        assert "hard_negative" in manifest[1]["export_path"]
        assert "img_002.jpg" in manifest[1]["export_path"]

    def test_ignore_unknown_label(self):
        recs = [
            create_review_record("img.jpg", "d1", "x", 0.9, [0, 0, 10, 10], "ignore"),
        ]
        manifest = build_export_manifest(recs, "/images", "/output")
        assert len(manifest) == 0  # "ignore" is not in LABEL_TO_FOLDER

    def test_manifest_fields(self):
        recs = [
            create_review_record(
                "img.jpg", "d1", "scratch", 0.9, [10, 20, 100, 200],
                "true_defect", reviewer_note="test note",
            ),
        ]
        manifest = build_export_manifest(recs, "/images", "/output")
        assert len(manifest) == 1
        m = manifest[0]
        assert m["image_name"] == "img.jpg"
        assert m["review_label"] == "true_defect"
        assert m["class_name"] == "scratch"
        assert m["confidence"] == 0.9
        assert m["bbox"] == [10, 20, 100, 200]
        assert m["reviewer_note"] == "test note"


class TestExportReviewedSamples:
    def test_export_no_copy(self):
        recs = [
            create_review_record("img_001.jpg", "d1", "scratch", 0.9, [0, 0, 10, 10], "true_defect"),
            create_review_record("img_002.jpg", "d2", "scratch", 0.5, [0, 0, 10, 10], "false_positive"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            result = export_reviewed_samples(
                recs, image_root="/nonexistent", output_dir=tmpdir, copy_images=False,
            )
            assert result["exported"] == 2
            assert result["copied"] == 0
            assert Path(tmpdir, "manifest.csv").exists()
            assert Path(tmpdir, "manifest.json").exists()

    def test_export_with_missing_sources(self):
        recs = [
            create_review_record("img_missing.jpg", "d1", "x", 0.9, [0, 0, 10, 10], "true_defect"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            result = export_reviewed_samples(
                recs, image_root="/nonexistent", output_dir=tmpdir, copy_images=True,
            )
            assert result["skipped"] >= 1
            assert len(result["errors"]) >= 1
