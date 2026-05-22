"""Tests for PriorityRouter."""
import numpy as np
from gpu_scheduler.priority_router import PriorityRouter, RoutingDecision, RoutingStrategy
from runtime.unified_image_pool import TileEntry


def make_tile() -> TileEntry:
    return TileEntry(
        tile_id="T_001",
        run_id="run_test",
        customer_id="test",
        product_id="test",
        camera_id="Cam_01",
        block_id="BLK_001",
        tile_index=0,
        tile_x=0,
        tile_y=0,
        meter_start=100.0,
        meter_end=100.5,
        encoder_count_start=1000,
        encoder_count_end=1005,
        timestamp="2026-05-20T20:30:00",
        image=np.ones((3, 320, 320), dtype=np.uint8) * 128,
    )


def test_cold_start_routes_to_patchcore():
    router = PriorityRouter(RoutingStrategy.COLD_START)
    tile = make_tile()
    decision = router.route_initial(tile)
    assert decision.action == "patchcore"
    assert decision.priority == 0


def test_hybrid_yolo_first_routes_to_yolo():
    router = PriorityRouter(RoutingStrategy.HYBRID_YOLO_FIRST)
    decision = router.route_initial(make_tile())
    assert decision.action == "yolo"


def test_patchcore_first_routes_to_patchcore():
    router = PriorityRouter(RoutingStrategy.PATCHCORE_FIRST)
    decision = router.route_initial(make_tile())
    assert decision.action == "patchcore"


def test_cold_start_ng_goes_to_human_review():
    router = PriorityRouter(RoutingStrategy.COLD_START)
    tile = make_tile()
    decision = router.route_after_result(tile, "patchcore", {"result_type": "NG", "confidence": 0.8})
    assert decision.action == "human_review"


def test_cold_start_ok_releases():
    router = PriorityRouter(RoutingStrategy.COLD_START)
    decision = router.route_after_result(make_tile(), "patchcore", {"result_type": "OK", "confidence": 0.9})
    assert decision.action == "release"


def test_hybrid_yolo_high_conf_ng_saves():
    router = PriorityRouter(RoutingStrategy.HYBRID_YOLO_FIRST)
    decision = router.route_after_result(make_tile(), "yolo", {"result_type": "NG", "confidence": 0.95})
    assert decision.action == "save"


def test_hybrid_yolo_uncertain_routes_to_patchcore():
    router = PriorityRouter(RoutingStrategy.HYBRID_YOLO_FIRST)
    decision = router.route_after_result(make_tile(), "yolo", {"result_type": "UNKNOWN", "confidence": 0.3})
    assert decision.action == "patchcore"


def test_hybrid_yolo_ok_high_conf_releases():
    router = PriorityRouter(RoutingStrategy.HYBRID_YOLO_FIRST)
    decision = router.route_after_result(make_tile(), "yolo", {"result_type": "OK", "confidence": 0.95})
    assert decision.action == "release"


def test_switch_strategy():
    router = PriorityRouter(RoutingStrategy.HYBRID_YOLO_FIRST)
    router.switch_strategy(RoutingStrategy.COLD_START)
    assert router.strategy == RoutingStrategy.COLD_START
    decision = router.route_initial(make_tile())
    assert decision.action == "patchcore"
