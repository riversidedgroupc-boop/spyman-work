"""Regression tests for review findings fixed after initial upload."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.dataset.dataset_loader import DatasetLoader
from src.fusion.decision_types import AnomalyResult, FinalDecision, FusionStrategy, UnifiedPrediction
from src.fusion.rule_engine import RuleEngine
from src.inference.patchcore_runner import PatchCoreRunner
from src.postprocess.candidate_builder import build_defect_candidates


def test_dataset_loader_keeps_annotations_normalized():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        image_dir = root / "images"
        label_dir = root / "labels"
        image_dir.mkdir()
        label_dir.mkdir()
        image_path = image_dir / "sample.jpg"
        image_path.write_bytes(b"not a real image; scan only needs extension")
        (label_dir / "sample.txt").write_text("3 0.5 0.5 0.2 0.4\n", encoding="utf-8")

        record = DatasetLoader(image_dir, label_dir).scan()[0]

    assert record.annotations[0].bbox_xyxy == pytest.approx([0.4, 0.3, 0.6, 0.7])


def test_candidate_builder_enables_rule_based_geometry_decision():
    anomaly = UnifiedPrediction(
        image_path="sample.jpg",
        model_name="patchcore",
        anomaly=AnomalyResult(image_score=0.8, threshold=0.65),
    )

    candidates = build_defect_candidates(patchcore_result=anomaly, image_width=120, image_height=20)
    decision = RuleEngine(
        {
            "anomaly": {"patchcore_score_threshold": 0.65},
            "geometry": {"ng_area_px": 200, "ng_scratch_length_mm": 1.0},
        }
    ).decide(
        "sample.jpg",
        strategy=FusionStrategy.RULE_BASED,
        patchcore_result=anomaly,
        candidates=candidates,
    )

    assert candidates
    assert candidates[0].is_long_scratch_like
    assert decision.final_decision == FinalDecision.NG


def test_real_patchcore_mode_raises_until_inference_is_implemented():
    runner = PatchCoreRunner({"mode": "real"})
    runner._is_loaded = True

    with pytest.raises(NotImplementedError):
        runner.predict("sample.jpg")


def test_patchcore_mock_score_is_stable_for_same_path():
    runner = PatchCoreRunner({"mode": "mock"})
    runner.load_model()

    first = runner.predict("sample.jpg").anomaly.image_score
    second = runner.predict("sample.jpg").anomaly.image_score

    assert first == second


def test_patchcore_runner_loads_statistical_json_model(tmp_path):
    import cv2
    import numpy as np

    model_path = tmp_path / "patchcore_model.json"
    image_path = tmp_path / "sample.png"
    image = np.full((16, 16, 3), 128, dtype=np.uint8)
    assert cv2.imwrite(str(image_path), image)

    model_path.write_text(
        """
        {
          "model_type": "patchcore",
          "feature_backend": "statistical_patch_features",
          "image_size": 16,
          "threshold": 0.25,
          "coreset": [[0.5, 0.0, 0.5, 0.5, 0.5, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.501960813999176, 0.0,
                       0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0,
                       0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0,
                       0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0,
                       0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0]]
        }
        """,
        encoding="utf-8",
    )

    runner = PatchCoreRunner({"mode": "statistical", "model_path": str(model_path)})
    runner.load_model()
    prediction = runner.predict(image_path)
    image_prediction = runner.predict_image(image_path)

    assert runner.is_loaded is True
    assert prediction.model_name == "patchcore"
    assert prediction.anomaly.image_score < 0.1
    assert image_prediction.image_score == prediction.anomaly.image_score
