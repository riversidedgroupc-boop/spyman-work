"""Tests for core/experiment.py."""

from __future__ import annotations

from core.experiment import (
    ModelRunConfig,
    ModelRunResult,
    Experiment,
    create_run_id,
    create_experiment_id,
    model_run_to_summary_row,
    experiment_to_dataframe_rows,
    now_iso,
)
from core.schema import DetectionBox


def _make_config(**kwargs) -> ModelRunConfig:
    defaults = {
        "model_name": "test_model",
        "model_type": "YOLO",
        "model_path": "models/test.pt",
        "confidence": 0.5,
        "iou": 0.5,
        "image_size": 640,
        "device": "cpu",
    }
    defaults.update(kwargs)
    return ModelRunConfig(**defaults)


def _make_boxes() -> list[DetectionBox]:
    return [
        DetectionBox("img_001.jpg", 0, "scratch", 0.9, [10, 20, 100, 200]),
        DetectionBox("img_002.jpg", 1, "dent", 0.8, [50, 50, 150, 150]),
    ]


class TestModelRunConfig:
    def test_create_default(self):
        c = _make_config()
        assert c.model_name == "test_model"
        assert c.model_type == "YOLO"
        assert c.confidence == 0.5

    def test_extra_config_default(self):
        c = _make_config()
        assert c.extra_config == {}

    def test_extra_config_custom(self):
        c = _make_config(extra_config={"batch_size": 8})
        assert c.extra_config == {"batch_size": 8}


class TestModelRunResult:
    def test_create(self):
        config = _make_config()
        boxes = _make_boxes()
        preds = {"img_001.jpg": [boxes[0]], "img_002.jpg": [boxes[1]]}
        result = ModelRunResult(
            run_id="test_001",
            config=config,
            predictions_by_image=preds,
            metrics={"map_50": 0.85},
            timing={"avg_ms": 18.4},
            created_at=now_iso(),
        )
        assert result.run_id == "test_001"
        assert result.config.model_name == "test_model"
        assert len(result.predictions_by_image) == 2


class TestExperiment:
    def test_create(self):
        config = _make_config()
        boxes = _make_boxes()
        preds = {"img_001.jpg": [boxes[0]]}
        run = ModelRunResult(
            run_id="r1", config=config, predictions_by_image=preds,
            metrics={}, timing={}, created_at=now_iso(),
        )
        exp = Experiment(
            experiment_id="exp_001",
            name="Test Experiment",
            dataset_name="test_dataset",
            ground_truths_by_image={"img_001.jpg": [boxes[0]]},
            model_runs=[run],
            created_at=now_iso(),
        )
        assert exp.experiment_id == "exp_001"
        assert len(exp.model_runs) == 1


class TestCreateRunId:
    def test_generates_unique_id(self):
        c1 = _make_config(model_name="model_a")
        c2 = _make_config(model_name="model_b")
        id1 = create_run_id(c1)
        id2 = create_run_id(c2)
        assert id1 != id2
        assert "model_a" in id1

    def test_sanitizes_name(self):
        c = _make_config(model_name="a/b c")
        rid = create_run_id(c)
        assert "/" not in rid
        assert " " not in rid


class TestCreateExperimentId:
    def test_generates_unique_id(self):
        eid = create_experiment_id("My Experiment", "dataset_v1")
        assert "My_Experiment" in eid
        assert "dataset_v1" in eid


class TestModelRunToSummaryRow:
    def test_basic(self):
        config = _make_config()
        run = ModelRunResult(
            run_id="r1", config=config,
            predictions_by_image={},
            metrics={"map_50": 0.85, "map": 0.78},
            timing={"avg_ms": 18.4, "total_ms": 1840},
            created_at=now_iso(),
        )
        row = model_run_to_summary_row(run)
        assert row["run_id"] == "r1"
        assert row["model_name"] == "test_model"
        assert row["map_50"] == 0.85
        assert row["avg_inference_ms"] == 18.4

    def test_empty_metrics(self):
        config = _make_config()
        run = ModelRunResult(
            run_id="r2", config=config,
            predictions_by_image={},
            metrics={}, timing={},
            created_at=now_iso(),
        )
        row = model_run_to_summary_row(run)
        assert row["map_50"] is None


class TestExperimentToDataframeRows:
    def test_basic(self):
        config = _make_config()
        run = ModelRunResult(
            run_id="r1", config=config,
            predictions_by_image={},
            metrics={}, timing={},
            created_at=now_iso(),
        )
        exp = Experiment(
            experiment_id="e1", name="Test",
            dataset_name="ds",
            ground_truths_by_image={},
            model_runs=[run],
            created_at=now_iso(),
        )
        rows = experiment_to_dataframe_rows(exp)
        assert len(rows) == 1
        assert rows[0]["experiment_id"] == "e1"
        assert rows[0]["experiment_name"] == "Test"
        assert rows[0]["dataset_name"] == "ds"
