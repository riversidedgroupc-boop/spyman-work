"""Tests for core/fusion.py."""

from __future__ import annotations

from core.fusion import (
    fuse_predictions_union,
    fuse_predictions_intersection,
    mark_review_candidates,
    fuse_weighted_merge,
    evaluate_fusion_strategy,
)
from core.schema import DetectionBox


def _box(img="img.jpg", cid=0, cname="defect", conf=0.9, bbox=None):
    if bbox is None:
        bbox = [0, 0, 100, 100]
    return DetectionBox(img, cid, cname, conf, bbox)


def _preds_dict(boxes_list):
    """Helper to create predictions dict from list of boxes."""
    result: dict[str, list[DetectionBox]] = {}
    for box in boxes_list:
        img = box.image_name
        if img not in result:
            result[img] = []
        result[img].append(box)
    return result


class TestFusePredictionsUnion:
    def test_basic(self):
        a = _preds_dict([_box(bbox=[0, 0, 100, 100])])
        b = _preds_dict([_box(bbox=[90, 90, 150, 150])])
        result = fuse_predictions_union(a, b, iou_threshold=0.5)
        assert len(result["img.jpg"]) >= 1

    def test_non_overlapping(self):
        a = _preds_dict([_box(bbox=[0, 0, 10, 10])])
        b = _preds_dict([_box(bbox=[50, 50, 60, 60])])
        result = fuse_predictions_union(a, b, iou_threshold=0.5)
        assert len(result["img.jpg"]) == 2

    def test_different_images(self):
        a = _preds_dict([_box(img="img1.jpg")])
        b = _preds_dict([_box(img="img2.jpg")])
        result = fuse_predictions_union(a, b, iou_threshold=0.5)
        assert "img1.jpg" in result
        assert "img2.jpg" in result


class TestFusePredictionsIntersection:
    def test_overlapping(self):
        a = _preds_dict([_box(bbox=[0, 0, 100, 100], conf=0.9)])
        b = _preds_dict([_box(bbox=[10, 10, 90, 90], conf=0.8)])
        result = fuse_predictions_intersection(a, b, iou_threshold=0.5)
        assert len(result["img.jpg"]) == 1
        assert result["img.jpg"][0].confidence == 0.9

    def test_no_overlap(self):
        a = _preds_dict([_box(bbox=[0, 0, 10, 10])])
        b = _preds_dict([_box(bbox=[50, 50, 60, 60])])
        result = fuse_predictions_intersection(a, b, iou_threshold=0.5)
        assert len(result["img.jpg"]) == 0


class TestMarkReviewCandidates:
    def test_basic(self):
        primary = _preds_dict([_box(bbox=[0, 0, 100, 100])])
        secondary = _preds_dict([_box(bbox=[90, 90, 150, 150])])
        result = mark_review_candidates(primary, secondary, iou_threshold=0.5)
        assert len(result["img.jpg"]) >= 1

    def test_secondary_only(self):
        primary = _preds_dict([])
        secondary = _preds_dict([_box(bbox=[50, 50, 60, 60])])
        result = mark_review_candidates(primary, secondary, iou_threshold=0.5)
        assert len(result["img.jpg"]) == 1
        # Review candidates have confidence=0.0
        assert result["img.jpg"][0].confidence == 0.0


class TestFuseWeightedMerge:
    def test_basic(self):
        a = _preds_dict([_box(bbox=[0, 0, 100, 100], conf=0.9)])
        b = _preds_dict([_box(bbox=[10, 10, 90, 90], conf=0.7)])
        result = fuse_weighted_merge([a, b], weights=[1.0, 1.0], iou_threshold=0.5)
        assert len(result["img.jpg"]) == 1
        assert result["img.jpg"][0].confidence == 0.8

    def test_empty_inputs(self):
        result = fuse_weighted_merge([])
        assert result == {}


class TestEvaluateFusionStrategy:
    def test_union(self):
        gt = {"img.jpg": [_box()]}
        preds = [
            _preds_dict([_box(bbox=[10, 10, 90, 90])]),
            _preds_dict([_box(bbox=[50, 50, 60, 60])]),
        ]
        result = evaluate_fusion_strategy("union", preds, gt)
        assert result["strategy_name"] == "union"
        assert "fused_predictions" in result

    def test_unknown_strategy(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown fusion strategy"):
            evaluate_fusion_strategy("invalid", [], {})
