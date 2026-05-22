"""Tests for core/hybrid_retest.py — Phase D."""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import Generator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _setup_db() -> Generator[None, None, None]:
    """Temp SQLite DB with Phase A + Phase D tables."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    os.environ["COPPER_VISION_DB_PATH"] = db_path
    import importlib
    import core.storage
    importlib.reload(core.storage)
    core.storage.init_db()
    yield
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def ctx() -> dict[str, str]:
    """Create parent rows: customer → project → spec."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    c = create_customer("HR Test Co", "HRT")
    p = create_project(c.customer_id, "HR Test Proj")
    s = create_product_spec(p.project_id, "HR Spec", material="铜", geometry_type="管")
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
    }


def _make_temp_image_dir(n_images: int = 3) -> str:
    """Create a temp directory with dummy PNG files."""
    d = tempfile.mkdtemp()
    for i in range(n_images):
        path = os.path.join(d, f"img_{i:03d}.png")
        with open(path, "wb") as f:
            f.write(b"fake_png")
    return d


# ── Empty directory ──────────────────────────────────────────────────

def test_empty_directory_raises(ctx: dict[str, str]):
    """Empty image directory raises ValueError."""
    from core.hybrid_retest import HybridRetestConfig, run_hybrid_retest

    empty_dir = tempfile.mkdtemp()
    try:
        config = HybridRetestConfig(
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            image_dir=empty_dir,
        )
        with pytest.raises(ValueError, match="No images found"):
            run_hybrid_retest(config)
    finally:
        shutil.rmtree(empty_dir, ignore_errors=True)


# ── Fake YOLO high confidence → NG ──────────────────────────────────

def test_fake_yolo_high_conf_returns_ng(ctx: dict[str, str]):
    """Fake YOLO with high-confidence detection outputs NG."""
    from core.hybrid_retest import (
        HybridRetestConfig, FakeYoloRunner, FakeAnomalyRunner,
        run_hybrid_retest,
    )
    from src.fusion.decision_types import BBoxPrediction

    img_dir = _make_temp_image_dir(1)
    try:
        yolo = FakeYoloRunner(detections=[
            BBoxPrediction(class_name="SCRATCH", confidence=0.95, bbox_xyxy=[10, 10, 50, 50]),
        ])
        anomaly = FakeAnomalyRunner(score=0.1)  # low anomaly

        config = HybridRetestConfig(
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            image_dir=img_dir,
        )
        result = run_hybrid_retest(config, yolo_runner=yolo, anomaly_runner=anomaly)
        assert result.total_count == 1
        assert result.ng_count == 1
        assert result.ok_count == 0
        assert result.items[0].final_decision == "NG"
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


# ── Fake anomaly high + no YOLO → UNKNOWN + anomaly_review ──────────

def test_anomaly_high_no_yolo_creates_review(ctx: dict[str, str]):
    """High anomaly score with no YOLO → UNKNOWN + anomaly_review created."""
    from core.hybrid_retest import (
        HybridRetestConfig, FakeAnomalyRunner, run_hybrid_retest,
    )

    img_dir = _make_temp_image_dir(1)
    try:
        anomaly = FakeAnomalyRunner(score=0.92)  # high anomaly

        config = HybridRetestConfig(
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            image_dir=img_dir,
        )
        result = run_hybrid_retest(config, anomaly_runner=anomaly)
        assert result.unknown_count == 1
        assert result.items[0].final_decision == "UNKNOWN"
        assert result.items[0].review_id is not None
        assert result.items[0].review_id.startswith("ARV_")

        # Verify anomaly_review exists in DB
        from core.anomaly_review import get_anomaly_review
        ar = get_anomaly_review(result.items[0].review_id)
        assert ar is not None
        assert ar.review_status == "unknown_pending"
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


# ── Medium anomaly → NEEDS_REVIEW ────────────────────────────────────

def test_medium_anomaly_returns_needs_review(ctx: dict[str, str]):
    """Medium anomaly score → NEEDS_REVIEW + anomaly_review created."""
    from core.hybrid_retest import (
        HybridRetestConfig, FakeAnomalyRunner, run_hybrid_retest,
    )

    img_dir = _make_temp_image_dir(1)
    try:
        anomaly = FakeAnomalyRunner(score=0.70)  # medium

        config = HybridRetestConfig(
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            image_dir=img_dir,
        )
        result = run_hybrid_retest(config, anomaly_runner=anomaly)
        assert result.needs_review_count == 1
        assert result.items[0].final_decision == "NEEDS_REVIEW"
        assert result.items[0].review_id is not None
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


# ── Low anomaly + no YOLO → OK, no review ───────────────────────────

def test_low_anomaly_no_yolo_returns_ok(ctx: dict[str, str]):
    """Low anomaly + no YOLO → OK, no anomaly_review created."""
    from core.hybrid_retest import (
        HybridRetestConfig, FakeAnomalyRunner, run_hybrid_retest,
    )

    img_dir = _make_temp_image_dir(1)
    try:
        anomaly = FakeAnomalyRunner(score=0.2)  # low

        config = HybridRetestConfig(
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            image_dir=img_dir,
        )
        result = run_hybrid_retest(config, anomaly_runner=anomaly)
        assert result.ok_count == 1
        assert result.items[0].final_decision == "OK"
        assert result.items[0].review_id is None
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


# ── run_id and summary persisted ────────────────────────────────────

def test_run_id_and_summary_persisted(ctx: dict[str, str]):
    """run_id is valid, summary_json stored in DB."""
    from core.hybrid_retest import (
        HybridRetestConfig, FakeYoloRunner, FakeAnomalyRunner,
        run_hybrid_retest, list_retest_runs, list_retest_items,
    )
    from src.fusion.decision_types import BBoxPrediction

    img_dir = _make_temp_image_dir(2)
    try:
        yolo = FakeYoloRunner(detections=[
            BBoxPrediction(class_name="DEF", confidence=0.9, bbox_xyxy=[0, 0, 10, 10]),
        ])
        anomaly = FakeAnomalyRunner(score=0.3)

        config = HybridRetestConfig(
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            image_dir=img_dir,
        )
        result = run_hybrid_retest(config, yolo_runner=yolo, anomaly_runner=anomaly)
        assert result.run_id.startswith("HRR_")
        assert result.total_count == 2

        # Verify run record
        runs = list_retest_runs(ctx["project_id"])
        assert len(runs) == 1
        assert runs[0]["run_id"] == result.run_id
        assert runs[0]["status"] == "completed"

        # Verify items
        items = list_retest_items(result.run_id)
        assert len(items) == 2
        for item in items:
            assert item["run_id"] == result.run_id
            assert item["image_path"].startswith(img_dir)
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


# ── Field session auto-creation ──────────────────────────────────────

def test_auto_creates_field_session(ctx: dict[str, str]):
    """When no field_session_id given, auto-creates production_retest session."""
    from core.hybrid_retest import (
        HybridRetestConfig, FakeAnomalyRunner, run_hybrid_retest,
    )

    img_dir = _make_temp_image_dir(1)
    try:
        anomaly = FakeAnomalyRunner(score=0.2)

        config = HybridRetestConfig(
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            image_dir=img_dir,
            field_session_id="",  # empty → auto-create
        )
        result = run_hybrid_retest(config, anomaly_runner=anomaly)
        assert result.total_count == 1

        # Check that a production_retest session was created
        from core.field_session import list_field_sessions
        sessions = list_field_sessions(project_id=ctx["project_id"])
        retest_sessions = [s for s in sessions if s.session_type == "production_retest"]
        assert len(retest_sessions) >= 1
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


# ── Multiple images ──────────────────────────────────────────────────

def test_multiple_images(ctx: dict[str, str]):
    """Batch processing handles multiple images correctly."""
    from core.hybrid_retest import (
        HybridRetestConfig, FakeAnomalyRunner, run_hybrid_retest,
    )

    img_dir = _make_temp_image_dir(5)
    try:
        anomaly = FakeAnomalyRunner(score=0.2)

        config = HybridRetestConfig(
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            image_dir=img_dir,
        )
        result = run_hybrid_retest(config, anomaly_runner=anomaly)
        assert result.total_count == 5
        assert result.ok_count == 5  # all low anomaly
        assert len(result.items) == 5
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


# ── Config serialization ─────────────────────────────────────────────

def test_config_serialization_roundtrip():
    """HybridRetestConfig can be created and all fields accessed."""
    from core.hybrid_retest import HybridRetestConfig

    config = HybridRetestConfig(
        project_id="P1",
        spec_id="S1",
        field_session_id="F1",
        yolo_model_id="M1",
        anomaly_model_id="A1",
        image_dir="/images",
        yolo_conf_threshold=0.6,
        anomaly_score_threshold=0.7,
        anomaly_high_threshold=0.9,
    )
    assert config.project_id == "P1"
    assert config.yolo_conf_threshold == 0.6
    assert config.anomaly_score_threshold == 0.7
    assert config.anomaly_high_threshold == 0.9
    assert config.route_review_statuses == ("UNKNOWN", "NEEDS_REVIEW", "SUSPECT")


# ── P2: route_review_statuses config-driven ─────────────────────────────

def test_route_review_statuses_custom_only_unknown(ctx: dict[str, str]):
    """Custom route_review_statuses only routes 'UNKNOWN', not 'NEEDS_REVIEW'."""
    from core.hybrid_retest import (
        HybridRetestConfig, FakeAnomalyRunner, run_hybrid_retest,
    )

    img_dir = _make_temp_image_dir(1)
    try:
        # Medium anomaly → normally NEEDS_REVIEW, but we exclude it
        anomaly = FakeAnomalyRunner(score=0.70)

        config = HybridRetestConfig(
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            image_dir=img_dir,
            route_review_statuses=("UNKNOWN",),  # only UNKNOWN
        )
        result = run_hybrid_retest(config, anomaly_runner=anomaly)
        # With NEEDS_REVIEW excluded, item gets decision but no review_id
        assert result.items[0].final_decision == "NEEDS_REVIEW"
        assert result.items[0].review_id is None
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


def test_route_review_statuses_includes_ng(
    ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    """Custom route_review_statuses can include 'NG' for special review flows."""
    from core.hybrid_retest import (
        HybridRetestConfig, FakeYoloRunner, FakeAnomalyRunner,
        run_hybrid_retest,
    )
    from src.fusion.decision_types import BBoxPrediction

    img_dir = _make_temp_image_dir(1)
    try:
        yolo = FakeYoloRunner(detections=[
            BBoxPrediction(class_name="DEF", confidence=0.95, bbox_xyxy=[0, 0, 10, 10]),
        ])
        anomaly = FakeAnomalyRunner(score=0.1)

        config = HybridRetestConfig(
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            image_dir=img_dir,
            route_review_statuses=("NG",),  # also route NG to review
        )
        result = run_hybrid_retest(config, yolo_runner=yolo, anomaly_runner=anomaly)
        # High-conf YOLO → NG, but NG is now routed to review
        assert result.items[0].final_decision == "NG"
        assert result.items[0].review_id is not None
        assert result.items[0].review_id.startswith("ARV_")
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


# ── Runner protocol ──────────────────────────────────────────────────

def test_fake_yolo_runner_empty():
    """FakeYoloRunner with no preset returns empty detections."""
    from core.hybrid_retest import FakeYoloRunner, _run_yolo

    runner = FakeYoloRunner()
    dets, runtime = _run_yolo(runner, "/fake/path")
    assert dets == []
    assert runtime >= 0


def test_fake_yolo_runner_with_detections():
    """FakeYoloRunner with preset detections returns them."""
    from core.hybrid_retest import FakeYoloRunner, _run_yolo
    from src.fusion.decision_types import BBoxPrediction

    runner = FakeYoloRunner(detections=[
        BBoxPrediction(class_name="PIT", confidence=0.8, bbox_xyxy=[1, 2, 3, 4]),
    ])
    dets, runtime = _run_yolo(runner, "/fake/path")
    assert len(dets) == 1
    assert dets[0].class_name == "PIT"
    assert runtime >= 0


def test_fake_anomaly_runner():
    """FakeAnomalyRunner returns preset score."""
    from core.hybrid_retest import FakeAnomalyRunner, _run_anomaly

    runner = FakeAnomalyRunner(score=0.75)
    result, runtime = _run_anomaly(runner, "/fake/path")
    assert result.image_score == 0.75
    assert runtime >= 0


# ── P1: _run_yolo converts DetectionBox.bbox → BBoxPrediction.bbox_xyxy ─

def test_run_yolo_converts_detection_box_bbox():
    """DetectionBox uses .bbox (not .bbox_xyxy) — ensure conversion works."""
    from core.hybrid_retest import _run_yolo
    from core.schema import DetectionBox, ImagePrediction

    # Simulate a YoloModelRunner result: ImagePrediction with DetectionBox items
    class FakeRealYoloRunner:
        def predict_image(self, image_path: str) -> ImagePrediction:
            return ImagePrediction(
                image_name="test.png",
                detections=[
                    DetectionBox(
                        image_name="test.png",
                        class_id=0,
                        class_name="SCRATCH",
                        confidence=0.88,
                        bbox=[10.0, 20.0, 100.0, 200.0],
                    ),
                ],
            )

    runner = FakeRealYoloRunner()
    dets, runtime = _run_yolo(runner, "/fake/path")
    assert len(dets) == 1
    assert dets[0].class_name == "SCRATCH"
    assert dets[0].confidence == 0.88
    assert dets[0].bbox_xyxy == [10.0, 20.0, 100.0, 200.0]
    assert runtime >= 0


def test_run_yolo_converts_detection_box_bbox_any_duck_type():
    """Any object with .bbox (not .bbox_xyxy) gets converted correctly."""
    from core.hybrid_retest import _run_yolo

    class _DuckDetection:
        class_name = "PIT"
        confidence = 0.55
        bbox = [5.0, 10.0, 50.0, 60.0]

    class DuckRunner:
        def predict_image(self, image_path: str):
            class _Result:
                detections = [_DuckDetection()]
            return _Result()

    dets, runtime = _run_yolo(DuckRunner(), "/fake/path")
    assert len(dets) == 1
    assert dets[0].class_name == "PIT"
    assert dets[0].confidence == 0.55
    assert dets[0].bbox_xyxy == [5.0, 10.0, 50.0, 60.0]


# ── P1: _build_yolo_runner ───────────────────────────────────────────

def test_build_yolo_runner_none_for_empty_id():
    """_build_yolo_runner returns None for empty model_id."""
    from core.hybrid_retest import _build_yolo_runner
    assert _build_yolo_runner("") is None


def test_build_yolo_runner_raises_for_missing_model(ctx: dict[str, str]):
    """_build_yolo_runner fails loudly for non-existent model ID."""
    from core.hybrid_retest import _build_yolo_runner
    with pytest.raises(ValueError, match="YOLO model version"):
        _build_yolo_runner("MODEL_nonexistent")


def test_build_yolo_runner_raises_for_model_without_path(ctx: dict[str, str]):
    """_build_yolo_runner fails loudly when model has no model_path."""
    from core.hybrid_retest import _build_yolo_runner
    from core.model_version import create_model_version

    mv = create_model_version(
        project_id=ctx["project_id"],
        model_name="no-path-model",
        model_type="yolo",
        model_path="",  # empty path
    )
    with pytest.raises(ValueError, match="model_path"):
        _build_yolo_runner(mv.model_id)


def test_build_yolo_runner_raises_for_missing_model_file(ctx: dict[str, str]):
    """_build_yolo_runner fails loudly when the selected model file is missing."""
    from core.hybrid_retest import _build_yolo_runner
    from core.model_version import create_model_version

    mv = create_model_version(
        project_id=ctx["project_id"],
        model_name="missing-file-model",
        model_type="yolo",
        model_path="D:/missing/model.pt",
    )
    with pytest.raises(FileNotFoundError, match="YOLO model file not found"):
        _build_yolo_runner(mv.model_id)


def test_build_yolo_runner_passes_confidence_to_runner(
    ctx: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    """UI/fusion threshold is propagated to YoloModelRunner config."""
    import core.hybrid_retest as hybrid_retest
    from core.model_version import create_model_version

    model_path = tmp_path / "model.pt"
    model_path.write_bytes(b"fake")
    mv = create_model_version(
        project_id=ctx["project_id"],
        model_name="threshold-model",
        model_type="yolo",
        model_path=str(model_path),
    )
    captured: dict[str, object] = {}

    class _FakeRunner:
        def __init__(self, model_path: str, config: dict | None = None) -> None:
            captured["model_path"] = model_path
            captured["config"] = config

        def load(self) -> None:
            captured["loaded"] = True

    monkeypatch.setattr(
        "model_runners.yolo_runner.YoloModelRunner",
        _FakeRunner,
    )

    runner = hybrid_retest._build_yolo_runner(mv.model_id, confidence=0.12)

    assert isinstance(runner, _FakeRunner)
    assert captured["model_path"] == str(model_path)
    assert captured["config"] == {"confidence": 0.12}
    assert captured["loaded"] is True


def test_build_anomaly_runner_loads_patchcore_model(ctx: dict[str, str], tmp_path):
    """_build_anomaly_runner returns a loaded PatchCoreRunner for patchcore model versions."""
    from core.hybrid_retest import _build_anomaly_runner
    from core.model_version import create_model_version

    model_path = tmp_path / "patchcore_model.json"
    model_path.write_text(
        """
        {
          "model_type": "patchcore",
          "feature_backend": "statistical_patch_features",
          "image_size": 16,
          "threshold": 0.25,
          "coreset": [[0.0]]
        }
        """,
        encoding="utf-8",
    )
    mv = create_model_version(
        project_id=ctx["project_id"],
        model_name="patchcore-model",
        model_type="patchcore",
        model_path=str(model_path),
    )

    runner = _build_anomaly_runner(mv.model_id, score_threshold=0.42)

    assert runner is not None
    assert runner.is_loaded is True
    assert runner.score_threshold == 0.42


def test_build_anomaly_runner_raises_for_missing_model(ctx: dict[str, str]):
    """_build_anomaly_runner fails loudly for invalid anomaly model IDs."""
    from core.hybrid_retest import _build_anomaly_runner

    with pytest.raises(ValueError, match="anomaly model version"):
        _build_anomaly_runner("MODEL_missing")
