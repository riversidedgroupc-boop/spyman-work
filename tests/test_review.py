"""Tests for core/review.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from core.review import (
    ReviewRecord,
    REVIEW_LABELS,
    create_review_record,
    save_review_records,
    load_review_records,
    summarize_review_records,
    filter_records_for_retraining,
)


class TestCreateReviewRecord:
    def test_basic(self):
        rec = create_review_record(
            image_name="img_001.jpg",
            detection_id="det_001",
            class_name="scratch",
            confidence=0.9,
            bbox=[10, 20, 100, 200],
            review_label="true_defect",
            reviewer_note="correct",
        )
        assert rec.image_name == "img_001.jpg"
        assert rec.review_label == "true_defect"
        assert rec.review_id != ""

    def test_invalid_label(self):
        with pytest.raises(ValueError, match="Invalid review_label"):
            create_review_record(
                image_name="img.jpg",
                detection_id="d1",
                class_name="x",
                confidence=0.5,
                bbox=[0, 0, 10, 10],
                review_label="invalid_label",
            )

    def test_all_valid_labels(self):
        for label in REVIEW_LABELS:
            rec = create_review_record(
                image_name="img.jpg",
                detection_id="d1",
                class_name="x",
                confidence=0.5,
                bbox=[0, 0, 10, 10],
                review_label=label,
            )
            assert rec.review_label == label


class TestSaveAndLoadReviewRecords:
    def test_save_and_load(self):
        recs = [
            create_review_record(
                image_name=f"img_{i:03d}.jpg",
                detection_id=f"det_{i}",
                class_name="scratch",
                confidence=0.9,
                bbox=[10, 20, 100, 200],
                review_label="true_defect",
            )
            for i in range(3)
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            path = f.name

        try:
            save_review_records(recs, path)
            loaded = load_review_records(path)
            assert len(loaded) == 3
            assert loaded[0].image_name == "img_000.jpg"
            assert loaded[0].review_label == "true_defect"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_load_nonexistent(self):
        records = load_review_records("/nonexistent/path.jsonl")
        assert records == []


class TestSummarizeReviewRecords:
    def test_basic(self):
        recs = [
            create_review_record("a.jpg", "d1", "x", 0.9, [0, 0, 10, 10], "true_defect"),
            create_review_record("b.jpg", "d2", "x", 0.5, [0, 0, 10, 10], "false_positive"),
            create_review_record("c.jpg", "d3", "x", 0.5, [0, 0, 10, 10], "false_positive"),
        ]
        summary = summarize_review_records(recs)
        assert summary["total"] == 3
        assert summary["by_label"]["true_defect"] == 1
        assert summary["by_label"]["false_positive"] == 2
        assert summary["by_label"]["ignore"] == 0


class TestFilterRecordsForRetraining:
    def test_filters_correctly(self):
        recs = [
            create_review_record("a.jpg", "d1", "x", 0.9, [0, 0, 10, 10], "true_defect"),
            create_review_record("b.jpg", "d2", "x", 0.5, [0, 0, 10, 10], "false_positive"),
            create_review_record("c.jpg", "d3", "x", 0.7, [0, 0, 10, 10], "retrain_candidate"),
            create_review_record("d.jpg", "d4", "x", 0.8, [0, 0, 10, 10], "label_error"),
        ]
        filtered = filter_records_for_retraining(recs)
        assert len(filtered) == 3
        labels = {r.review_label for r in filtered}
        assert labels == {"false_positive", "retrain_candidate", "label_error"}
