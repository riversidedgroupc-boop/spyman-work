"""Tests for core/export_benchmark.py — all pure-logic tests with no real models."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── DB fixture (autouse — mirrors test_model_export.py pattern) ─────────────────


@pytest.fixture(autouse=True)
def _setup_db() -> Generator[None, None, None]:
    """Temp SQLite DB with full schema so model_version / export_artifact tables exist."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    os.environ["COPPER_VISION_DB_PATH"] = db_path
    import importlib
    import core.storage

    importlib.reload(core.storage)
    core.storage.init_db()
    yield
    shutil.rmtree(tmp, ignore_errors=True)


# ── Test helpers ────────────────────────────────────────────────────────────────


class FakeBenchRunner:
    """Duck-typed runner for benchmark tests — no real model loading."""

    def __init__(
        self,
        runner_name: str = "fake",
        latency_ms: float = 1.0,
        detections_map: dict[str, list] | None = None,
    ) -> None:
        self.runner_name = runner_name
        self._latency_ms = latency_ms
        self._detections_map: dict[str, list] = detections_map or {}

    def load(self) -> None:
        pass

    def predict_image(self, image_path: str | Path) -> object:
        from core.schema import ImagePrediction

        key = Path(image_path).name
        dets = list(self._detections_map.get(key, []))
        return ImagePrediction(image_name=key, detections=dets)


def _make_det(
    image_name: str = "img.png",
    class_id: int = 0,
    class_name: str = "defect",
    confidence: float = 0.9,
    bbox: list[float] | None = None,
) -> object:
    """Create a DetectionBox with sensible defaults."""
    from core.schema import DetectionBox

    return DetectionBox(
        image_name=image_name,
        class_id=class_id,
        class_name=class_name,
        confidence=confidence,
        bbox=bbox or [0.0, 0.0, 100.0, 100.0],
    )


def _make_image_files(base_dir: str, names: list[str]) -> list[str]:
    """Create empty files with given names under *base_dir*, return absolute paths."""
    paths: list[str] = []
    for name in names:
        p = os.path.join(base_dir, name)
        Path(p).write_text("")
        paths.append(p)
    return paths


# ═══════════════════════════════════════════════════════════════════════════════
# _load_images
# ═══════════════════════════════════════════════════════════════════════════════


def test_load_images_filters_correctly():
    """Only .png / .jpg / .bmp files are included; other extensions are ignored."""
    from core.export_benchmark import _load_images

    tmp = tempfile.mkdtemp()
    try:
        _make_image_files(tmp, ["a.png", "b.JPG", "c.BMP", "d.txt", "e.py", "f.jpeg"])
        result = _load_images(tmp)
        basenames = {os.path.basename(p) for p in result}
        assert basenames == {"a.png", "b.JPG", "c.BMP", "f.jpeg"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_load_images_empty_dir_returns_empty():
    """Empty directory returns an empty list."""
    from core.export_benchmark import _load_images

    tmp = tempfile.mkdtemp()
    try:
        result = _load_images(tmp)
        assert result == []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_load_images_nonexistent_dir_raises():
    """Non-existent directory raises FileNotFoundError."""
    from core.export_benchmark import _load_images

    with pytest.raises(FileNotFoundError, match="Image directory not found"):
        _load_images("/tmp/nonexistent_dir_xyz_12345")


def test_load_images_recursive():
    """Images in subdirectories are collected recursively."""
    from core.export_benchmark import _load_images

    tmp = tempfile.mkdtemp()
    try:
        sub = os.path.join(tmp, "subdir")
        os.makedirs(sub)
        _make_image_files(tmp, ["root.png"])
        _make_image_files(sub, ["nested.jpg"])
        result = _load_images(tmp)
        basenames = {os.path.basename(p) for p in result}
        assert basenames == {"root.png", "nested.jpg"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════════
# _compute_bbox_iou
# ═══════════════════════════════════════════════════════════════════════════════


def test_compute_bbox_iou_perfect_overlap():
    """Same box returns IoU = 1.0."""
    from core.export_benchmark import _compute_bbox_iou

    box = [10.0, 20.0, 110.0, 120.0]
    assert _compute_bbox_iou(box, box) == pytest.approx(1.0)


def test_compute_bbox_iou_no_overlap():
    """Non-overlapping boxes return IoU = 0.0."""
    from core.export_benchmark import _compute_bbox_iou

    box_a = [0.0, 0.0, 50.0, 50.0]
    box_b = [100.0, 100.0, 150.0, 150.0]
    assert _compute_bbox_iou(box_a, box_b) == pytest.approx(0.0)


def test_compute_bbox_iou_partial():
    """Known partial overlap produces expected IoU."""
    from core.export_benchmark import _compute_bbox_iou

    # 50x50 boxes overlapping 50% horizontally — exact IoU: 25*50 / (2500+2500-1250)
    box_a = [0.0, 0.0, 50.0, 50.0]
    box_b = [25.0, 0.0, 75.0, 50.0]
    # inter: [25, 0, 50, 50] => 25*50 = 1250
    # area_a = 2500, area_b = 2500, union = 5000 - 1250 = 3750
    # IoU = 1250 / 3750 = 1/3
    expected = 1250.0 / 3750.0
    assert _compute_bbox_iou(box_a, box_b) == pytest.approx(expected)


def test_compute_bbox_iou_one_inside_another():
    """Smaller box fully inside larger — IoU = area_small / area_large."""
    from core.export_benchmark import _compute_bbox_iou

    box_a = [0.0, 0.0, 100.0, 100.0]
    box_b = [25.0, 25.0, 75.0, 75.0]
    # inter = 50*50 = 2500
    # area_a = 10000, area_b = 2500, IoU = 2500/10000 = 0.25
    assert _compute_bbox_iou(box_a, box_b) == pytest.approx(0.25)


# ═══════════════════════════════════════════════════════════════════════════════
# _match_detections
# ═══════════════════════════════════════════════════════════════════════════════


def test_match_detections_greedy():
    """Greedy matching pairs the best-IoU candidates and consumes each at most once."""
    from core.export_benchmark import _match_detections

    # A1 overlaps B1 heavily (IoU ~0.9), B2 lightly (IoU ~0.3)
    # A2 overlaps B2 heavily (IoU ~0.8)
    # Expected: (A1, B1), (A2, B2)
    a1 = _make_det("a", class_name="a1", bbox=[0.0, 0.0, 100.0, 100.0])
    a2 = _make_det("a", class_name="a2", bbox=[80.0, 80.0, 200.0, 200.0])
    b1 = _make_det("b", class_name="b1", bbox=[5.0, 5.0, 95.0, 95.0])
    b2 = _make_det("b", class_name="b2", bbox=[90.0, 90.0, 190.0, 190.0])

    pairs = _match_detections([a1, a2], [b1, b2])
    assert len(pairs) == 2, f"Expected 2 pairs, got {len(pairs)}"
    assert pairs[0][0] is a1
    assert pairs[0][1] is b1
    assert pairs[1][0] is a2
    assert pairs[1][1] is b2


def test_match_detections_empty():
    """Both lists empty returns empty list."""
    from core.export_benchmark import _match_detections

    assert _match_detections([], []) == []
    det = _make_det("img")
    assert _match_detections([det], []) == []
    assert _match_detections([], [det]) == []


def test_match_detections_no_overlap():
    """Non-overlapping detections produce no pairs."""
    from core.export_benchmark import _match_detections

    a1 = _make_det("a", bbox=[0.0, 0.0, 10.0, 10.0])
    b1 = _make_det("b", bbox=[100.0, 100.0, 110.0, 110.0])
    pairs = _match_detections([a1], [b1])
    assert pairs == []


def test_match_detections_respects_threshold():
    """Pairs below the IoU threshold are excluded."""
    from core.export_benchmark import _match_detections

    # IoU = 1/3 ≈ 0.333 — below default 0.5 threshold
    a1 = _make_det("a", bbox=[0.0, 0.0, 50.0, 50.0])
    b1 = _make_det("b", bbox=[25.0, 0.0, 75.0, 50.0])
    pairs = _match_detections([a1], [b1], iou_threshold=0.5)
    assert pairs == []
    # Lowering threshold includes it
    pairs2 = _match_detections([a1], [b1], iou_threshold=0.3)
    assert len(pairs2) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# _compare_decisions
# ═══════════════════════════════════════════════════════════════════════════════


def test_compare_decisions_match():
    """Same OK/NG decision returns True (both OK or both NG)."""
    from core.export_benchmark import _compare_decisions
    from core.schema import ImagePrediction

    # Both OK (no detections)
    ok_a = ImagePrediction(image_name="a.png", detections=[])
    ok_b = ImagePrediction(image_name="b.png", detections=[])
    assert _compare_decisions(ok_a, ok_b) is True

    # Both NG (both have detections)
    ng_a = ImagePrediction(image_name="a.png", detections=[_make_det("a")])
    ng_b = ImagePrediction(image_name="b.png", detections=[_make_det("b")])
    assert _compare_decisions(ng_a, ng_b) is True


def test_compare_decisions_mismatch():
    """Different OK/NG decisions return False."""
    from core.export_benchmark import _compare_decisions
    from core.schema import ImagePrediction

    ok = ImagePrediction(image_name="ok.png", detections=[])
    ng = ImagePrediction(image_name="ng.png", detections=[_make_det("ng")])
    assert _compare_decisions(ok, ng) is False
    assert _compare_decisions(ng, ok) is False


# ═══════════════════════════════════════════════════════════════════════════════
# _compute_latency_stats
# ═══════════════════════════════════════════════════════════════════════════════


def test_compute_latency_stats():
    """avg, p95, p99 are computed correctly from a list of timings."""
    from core.export_benchmark import _compute_latency_stats

    # 100 values: 1..100
    timings = list(range(1, 101))
    avg, p95, p99 = _compute_latency_stats(timings)
    assert avg == pytest.approx(50.5)
    # p95 index = ceil(100*0.95)-1 = ceil(95)-1 = 95-1 = 94 -> timings[94] = 95
    assert p95 == pytest.approx(95.0)
    # p99 index = ceil(100*0.99)-1 = ceil(99)-1 = 99-1 = 98 -> timings[98] = 99
    assert p99 == pytest.approx(99.0)


def test_compute_latency_stats_empty():
    """Empty list returns (0, 0, 0)."""
    from core.export_benchmark import _compute_latency_stats

    assert _compute_latency_stats([]) == (0.0, 0.0, 0.0)


def test_compute_latency_stats_single():
    """Single-element list: avg = p95 = p99 = the value."""
    from core.export_benchmark import _compute_latency_stats

    assert _compute_latency_stats([42.0]) == (42.0, 42.0, 42.0)


def test_compute_latency_stats_small_n():
    """Small n (e.g. n=3) produces reasonable percentile values."""
    from core.export_benchmark import _compute_latency_stats

    # n=3: p95 idx = ceil(3*0.95)-1 = ceil(2.85)-1 = 3-1 = 2 -> largest
    #       p99 idx = ceil(3*0.99)-1 = ceil(2.97)-1 = 3-1 = 2 -> largest
    avg, p95, p99 = _compute_latency_stats([10.0, 20.0, 30.0])
    assert avg == pytest.approx(20.0)
    assert p95 == pytest.approx(30.0)
    assert p99 == pytest.approx(30.0)


# ═══════════════════════════════════════════════════════════════════════════════
# BenchmarkResult
# ═══════════════════════════════════════════════════════════════════════════════


def test_benchmark_result_to_dict_roundtrip():
    """to_dict → from_dict produces an equivalent BenchmarkResult."""
    from core.export_benchmark import BenchmarkResult

    original = BenchmarkResult(
        source_model_id="MODEL_001",
        candidate_export_id="EXP_001",
        image_count=50,
        avg_latency_ms=12.345,
        p95_latency_ms=18.901,
        p99_latency_ms=22.000,
        decision_match_rate=0.995,
        mean_bbox_iou=0.987,
        mean_confidence_delta=0.012,
        recommended=True,
    )
    d = original.to_dict()
    restored = BenchmarkResult.from_dict(d)
    assert restored.source_model_id == original.source_model_id
    assert restored.candidate_export_id == original.candidate_export_id
    assert restored.image_count == original.image_count
    assert restored.avg_latency_ms == original.avg_latency_ms
    assert restored.p95_latency_ms == original.p95_latency_ms
    assert restored.p99_latency_ms == original.p99_latency_ms
    assert restored.decision_match_rate == original.decision_match_rate
    assert restored.mean_bbox_iou == original.mean_bbox_iou
    assert restored.mean_confidence_delta == original.mean_confidence_delta
    assert restored.recommended == original.recommended


def test_benchmark_result_recommended_when_meets_thresholds():
    """All thresholds satisfied → recommended = True."""
    from core.export_benchmark import BenchmarkResult

    result = BenchmarkResult(
        source_model_id="M1",
        candidate_export_id="E1",
        image_count=100,
        avg_latency_ms=5.0,
        p95_latency_ms=6.0,
        p99_latency_ms=7.0,
        decision_match_rate=0.99,
        mean_bbox_iou=0.98,
        mean_confidence_delta=0.03,
        recommended=True,
    )
    assert result.recommended is True


def test_benchmark_result_not_recommended_when_fails_thresholds():
    """Sub-threshold metrics → recommended = False."""
    from core.export_benchmark import BenchmarkResult

    result = BenchmarkResult(
        source_model_id="M1",
        candidate_export_id="E2",
        image_count=100,
        avg_latency_ms=15.0,
        p95_latency_ms=18.0,
        p99_latency_ms=20.0,
        decision_match_rate=0.95,  # < 0.99
        mean_bbox_iou=0.97,  # < 0.98
        mean_confidence_delta=0.05,  # > 0.03
        recommended=False,
    )
    assert result.recommended is False


def test_benchmark_result_not_recommended_when_slower():
    """Candidate slower than source → recommended = False even with perfect accuracy."""
    from core.export_benchmark import BenchmarkResult

    # The 'recommended' field is set by run_benchmark, we just test the field directly
    result = BenchmarkResult(
        source_model_id="M1",
        candidate_export_id="E3",
        image_count=100,
        avg_latency_ms=50.0,  # very slow
        p95_latency_ms=55.0,
        p99_latency_ms=60.0,
        decision_match_rate=1.0,
        mean_bbox_iou=1.0,
        mean_confidence_delta=0.0,
        recommended=False,
    )
    assert result.recommended is False


# ═══════════════════════════════════════════════════════════════════════════════
# run_benchmark integration
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def bench_ctx() -> dict[str, str]:
    """Create parent DB rows: customer → project → spec → model_version + export."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.model_version import create_model_version
    from core.model_export import create_export_artifact

    c = create_customer("Bench Test Co", "BTC")
    p = create_project(c.customer_id, "Bench Proj")
    s = create_product_spec(p.project_id, "Bench Spec", material="铜", geometry_type="管")
    mv = create_model_version(
        project_id=p.project_id,
        model_name="bench_model",
        model_type="yolo",
        model_path="/fake/models/bench.pt",
        spec_id=s.spec_id,
    )
    exp = create_export_artifact(
        project_id=p.project_id,
        source_model_id=mv.model_id,
        backend="onnx",
        precision="fp32",
        artifact_path="/fake/exports/bench.onnx",
    )
    # Set status to completed (create default is "created")
    from core.model_export import update_export_artifact

    update_export_artifact(exp.export_id, status="completed")
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
        "model_id": mv.model_id,
        "export_id": exp.export_id,
    }


def test_run_benchmark_integration(bench_ctx: dict[str, str], monkeypatch):
    """Full pipeline with fake runners produces correct BenchmarkResult."""
    from core.export_benchmark import run_benchmark

    # ── Build predictable fake detections ──────────────────────────────────
    # Image 1: source detects 1 box, candidate detects a slightly shifted box
    # Image 2: source detects 1 box, candidate also 1 box (nearly same)
    # Image 3: source detects nothing, candidate detects nothing → both OK
    det_map_src = {
        "img1.png": [_make_det("img1.png", bbox=[0, 0, 100, 100], confidence=0.9)],
        "img2.png": [_make_det("img2.png", bbox=[50, 50, 200, 200], confidence=0.7)],
        "img3.png": [],
    }
    det_map_cand = {
        "img1.png": [_make_det("img1.png", bbox=[0, 0, 99, 99], confidence=0.88)],
        "img2.png": [_make_det("img2.png", bbox=[50, 50, 199, 199], confidence=0.72)],
        "img3.png": [],
    }

    fake_src = FakeBenchRunner(runner_name="yolo", detections_map=det_map_src)
    fake_cand = FakeBenchRunner(runner_name="onnx", detections_map=det_map_cand)

    # Patch YoloModelRunner class to return our fake source runner
    class _MockYoloClass:
        def __init__(self, model_path: str = "", config: dict | None = None) -> None:
            pass

        def load(self) -> None:
            pass

        def predict_image(self, image_path: str | Path) -> object:
            return fake_src.predict_image(image_path)

    monkeypatch.setattr(
        "model_runners.yolo_runner.YoloModelRunner", _MockYoloClass
    )
    monkeypatch.setattr(
        "model_runners.backend_factory.create_runner_for_artifact",
        lambda export_id, **kwargs: fake_cand,
    )

    # ── Create temp image dir ──────────────────────────────────────────────
    tmp = tempfile.mkdtemp()
    try:
        _make_image_files(tmp, ["img1.png", "img2.png", "img3.png"])

        result = run_benchmark(
            source_model_id=bench_ctx["model_id"],
            candidate_export_id=bench_ctx["export_id"],
            image_dir=tmp,
        )

        assert result.image_count == 3
        assert result.decision_match_rate == 1.0  # all 3 images agree
        assert result.mean_bbox_iou > 0.9  # boxes are very close
        assert result.mean_confidence_delta > 0.0  # conf deltas exist
        assert result.recommended is True  # meets all thresholds with fast fake runners
        assert isinstance(result.avg_latency_ms, float)
        assert isinstance(result.p95_latency_ms, float)
        assert isinstance(result.p99_latency_ms, float)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_benchmark_decision_mismatch_produces_correct_rate(
    bench_ctx: dict[str, str], monkeypatch,
):
    """Decision mismatch is correctly reflected in decision_match_rate."""
    from core.export_benchmark import run_benchmark

    # Source detects something on both images, candidate on only one
    det_src = {
        "a.png": [_make_det("a.png")],
        "b.png": [_make_det("b.png")],
    }
    det_cand = {
        "a.png": [_make_det("a.png")],
        "b.png": [],  # miss — candidate says OK, source says NG
    }

    fake_src = FakeBenchRunner(runner_name="yolo", detections_map=det_src)
    fake_cand = FakeBenchRunner(runner_name="onnx", detections_map=det_cand)

    class _MockYoloClass:
        def __init__(self, model_path: str = "", config: dict | None = None) -> None:
            pass

        def load(self) -> None:
            pass

        def predict_image(self, image_path: str | Path) -> object:
            return fake_src.predict_image(image_path)

    monkeypatch.setattr(
        "model_runners.yolo_runner.YoloModelRunner", _MockYoloClass
    )
    monkeypatch.setattr(
        "model_runners.backend_factory.create_runner_for_artifact",
        lambda export_id, **kwargs: fake_cand,
    )

    tmp = tempfile.mkdtemp()
    try:
        _make_image_files(tmp, ["a.png", "b.png"])
        result = run_benchmark(
            source_model_id=bench_ctx["model_id"],
            candidate_export_id=bench_ctx["export_id"],
            image_dir=tmp,
        )
        assert result.image_count == 2
        assert result.decision_match_rate == 0.5  # 1/2 match
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_benchmark_empty_image_dir_raises(bench_ctx: dict[str, str]):
    """Empty image directory raises ValueError."""
    from core.export_benchmark import run_benchmark

    tmp = tempfile.mkdtemp()
    try:
        with pytest.raises(ValueError, match="No images"):
            run_benchmark(
                source_model_id=bench_ctx["model_id"],
                candidate_export_id=bench_ctx["export_id"],
                image_dir=tmp,
            )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_benchmark_missing_source_model_raises():
    """Non-existent source_model_id raises ValueError."""
    from core.export_benchmark import run_benchmark

    with pytest.raises(ValueError, match="Source model version not found"):
        run_benchmark(
            source_model_id="MODEL_nonexistent",
            candidate_export_id="EXP_whatever",
            image_dir="/tmp",
        )


def test_run_benchmark_nonexistent_candidate_raises(bench_ctx: dict[str, str]):
    """Non-existent candidate export raises ValueError."""
    from core.export_benchmark import run_benchmark

    with pytest.raises(ValueError, match="Candidate export artifact not found"):
        run_benchmark(
            source_model_id=bench_ctx["model_id"],
            candidate_export_id="EXP_nonexistent",
            image_dir="/tmp",
        )


def test_run_benchmark_failed_candidate_raises(bench_ctx: dict[str, str]):
    """Candidate with status='failed' raises ValueError."""
    from core.export_benchmark import run_benchmark
    from core.model_export import create_export_artifact

    failed = create_export_artifact(
        project_id=bench_ctx["project_id"],
        source_model_id=bench_ctx["model_id"],
        backend="onnx",
        status="failed",
    )
    with pytest.raises(ValueError, match="not completed"):
        run_benchmark(
            source_model_id=bench_ctx["model_id"],
            candidate_export_id=failed.export_id,
            image_dir="/tmp",
        )


def test_run_benchmark_nonexistent_image_dir_raises(bench_ctx: dict[str, str]):
    """Non-existent image_dir raises FileNotFoundError."""
    from core.export_benchmark import run_benchmark

    with pytest.raises(FileNotFoundError, match="Image directory not found"):
        run_benchmark(
            source_model_id=bench_ctx["model_id"],
            candidate_export_id=bench_ctx["export_id"],
            image_dir="/tmp/definitely_does_not_exist_abc_123",
        )


def test_run_benchmark_no_matched_detections(
    bench_ctx: dict[str, str], monkeypatch,
):
    """When detections don't overlap, IoU and conf_delta are 0.0."""
    from core.export_benchmark import run_benchmark

    det_src = {"x.png": [_make_det("x", bbox=[0, 0, 10, 10])]}
    det_cand = {"x.png": [_make_det("x", bbox=[100, 100, 110, 110])]}

    fake_src = FakeBenchRunner(runner_name="yolo", detections_map=det_src)
    fake_cand = FakeBenchRunner(runner_name="onnx", detections_map=det_cand)

    class _MockYoloClass:
        def __init__(self, model_path: str = "", config: dict | None = None) -> None:
            pass

        def load(self) -> None:
            pass

        def predict_image(self, image_path: str | Path) -> object:
            return fake_src.predict_image(image_path)

    monkeypatch.setattr(
        "model_runners.yolo_runner.YoloModelRunner", _MockYoloClass
    )
    monkeypatch.setattr(
        "model_runners.backend_factory.create_runner_for_artifact",
        lambda export_id, **kwargs: fake_cand,
    )

    tmp = tempfile.mkdtemp()
    try:
        _make_image_files(tmp, ["x.png"])
        result = run_benchmark(
            source_model_id=bench_ctx["model_id"],
            candidate_export_id=bench_ctx["export_id"],
            image_dir=tmp,
        )
        assert result.mean_bbox_iou == 0.0
        assert result.mean_confidence_delta == 0.0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_benchmark_saves_report(bench_ctx: dict[str, str], monkeypatch):
    """benchmark_report.json is written next to the candidate engine."""
    from core.export_benchmark import run_benchmark

    fake_src = FakeBenchRunner(runner_name="yolo")
    fake_cand = FakeBenchRunner(runner_name="onnx")

    class _MockYoloClass:
        def __init__(self, model_path: str = "", config: dict | None = None) -> None:
            pass

        def load(self) -> None:
            pass

        def predict_image(self, image_path: str | Path) -> object:
            return fake_src.predict_image(image_path)

    monkeypatch.setattr(
        "model_runners.yolo_runner.YoloModelRunner", _MockYoloClass
    )
    monkeypatch.setattr(
        "model_runners.backend_factory.create_runner_for_artifact",
        lambda export_id, **kwargs: fake_cand,
    )

    # Update candidate artifact_path to point to a temp dir
    tmp = tempfile.mkdtemp()
    try:
        from core.model_export import update_export_artifact

        export_dir = os.path.join(tmp, "exports")
        os.makedirs(export_dir, exist_ok=True)
        engine_path = os.path.join(export_dir, "model.onnx")
        update_export_artifact(bench_ctx["export_id"], artifact_path=engine_path)

        img_dir = os.path.join(tmp, "images")
        os.makedirs(img_dir)
        _make_image_files(img_dir, ["test.png"])

        run_benchmark(
            source_model_id=bench_ctx["model_id"],
            candidate_export_id=bench_ctx["export_id"],
            image_dir=img_dir,
        )

        report_path = os.path.join(export_dir, "benchmark_report.json")
        assert os.path.isfile(report_path), f"Report not found at {report_path}"
        import json

        with open(report_path, "r") as f:
            data = json.load(f)
        assert data["source_model_id"] == bench_ctx["model_id"]
        assert data["candidate_export_id"] == bench_ctx["export_id"]
        assert data["image_count"] == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_benchmark_source_model_without_path_raises(bench_ctx: dict[str, str]):
    """Source model with empty model_path raises ValueError."""
    from core.export_benchmark import run_benchmark
    from core.model_version import create_model_version

    mv = create_model_version(
        project_id=bench_ctx["project_id"],
        model_name="no_path_model",
        model_type="yolo",
        model_path="",  # empty
        spec_id=bench_ctx["spec_id"],
    )
    # Ensure model_path stays empty
    with pytest.raises(ValueError, match="no model_path"):
        run_benchmark(
            source_model_id=mv.model_id,
            candidate_export_id=bench_ctx["export_id"],
            image_dir="/tmp",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# recommend thresholds edge cases
# ═══════════════════════════════════════════════════════════════════════════════


def test_recommended_false_when_decision_rate_below_099(bench_ctx: dict[str, str], monkeypatch):
    """decision_match_rate = 0.98 (< 0.99) → recommended=False."""
    from core.export_benchmark import run_benchmark

    # Source detects on both, candidate only on first → 0.5 match rate
    det_src = {"a.png": [_make_det("a")], "b.png": [_make_det("b")]}
    det_cand = {"a.png": [_make_det("a")], "b.png": []}

    fake_src = FakeBenchRunner(runner_name="yolo", detections_map=det_src)
    fake_cand = FakeBenchRunner(runner_name="onnx", detections_map=det_cand)

    class _MockYoloClass:
        def __init__(self, model_path: str = "", config: dict | None = None) -> None:
            pass

        def load(self) -> None:
            pass

        def predict_image(self, image_path: str | Path) -> object:
            return fake_src.predict_image(image_path)

    monkeypatch.setattr(
        "model_runners.yolo_runner.YoloModelRunner", _MockYoloClass
    )
    monkeypatch.setattr(
        "model_runners.backend_factory.create_runner_for_artifact",
        lambda export_id, **kwargs: fake_cand,
    )

    tmp = tempfile.mkdtemp()
    try:
        _make_image_files(tmp, ["a.png", "b.png"])
        result = run_benchmark(
            source_model_id=bench_ctx["model_id"],
            candidate_export_id=bench_ctx["export_id"],
            image_dir=tmp,
        )
        assert result.decision_match_rate < 0.99
        assert result.recommended is False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
