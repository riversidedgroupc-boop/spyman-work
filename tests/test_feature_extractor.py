"""Tests for feature extractor."""

from __future__ import annotations

import pytest

from src.fusion.decision_types import DefectCandidate, ModelSource
from src.postprocess.feature_extractor import FeatureExtractor


def test_extract_basic_features():
    extractor = FeatureExtractor()
    candidate = DefectCandidate(
        image_path="/test/img.jpg",
        bbox_xyxy=[10, 20, 50, 80],
        area_px=900.0,
    )

    result = extractor.extract_features(candidate, pixel_size_mm=(0.01, 0.01))

    assert result.area_px == 900.0
    assert result.area_mm2 is not None
    assert result.area_mm2 == pytest.approx(0.09, rel=1e-2)  # 900 * 0.01 * 0.01
    assert result.bbox_width == 40.0  # 50 - 10
    assert result.bbox_height == 60.0  # 80 - 20
    assert result.aspect_ratio > 0


def test_extract_long_scratch_like():
    extractor = FeatureExtractor()
    candidate = DefectCandidate(
        image_path="/test/img.jpg",
        bbox_xyxy=[10, 10, 14, 110],  # 4x100, AR=25
    )

    result = extractor.extract_features(candidate)
    assert result.is_long_scratch_like
    assert not result.is_point_like


def test_extract_point_like():
    extractor = FeatureExtractor()
    candidate = DefectCandidate(
        image_path="/test/img.jpg",
        bbox_xyxy=[10, 10, 12, 12],  # 2x2
    )

    result = extractor.extract_features(candidate)
    assert result.is_point_like
    assert not result.is_long_scratch_like


def test_extract_all():
    extractor = FeatureExtractor()
    candidates = [
        DefectCandidate(image_path="/test/img.jpg", bbox_xyxy=[10, 20, 50, 80]),
        DefectCandidate(image_path="/test/img.jpg", bbox_xyxy=[100, 200, 150, 250]),
    ]

    results = extractor.extract_all(candidates)
    assert len(results) == 2
    for r in results:
        assert r.area_px > 0
        assert r.width_mm is not None
        assert r.length_mm is not None
