"""Tests for SavePolicyManager."""
from gpu_scheduler.stats import TileResult
from storage_v8.save_policy import SavePolicyManager, SaveMode


def make_result(result_type: str, meter_start: float = 100.0) -> TileResult:
    return TileResult(
        tile_id="T_001",
        camera_id="Cam_01",
        run_id="run_001",
        product_id="prod_01",
        model_type="yolo",
        model_version="v1",
        result_type=result_type,
        defect_type="scratch" if result_type == "NG" else "",
        confidence=0.9,
        bbox=None,
        inference_time_ms=5.0,
        gpu_device_id=0,
        meter_start=meter_start,
        meter_end=meter_start + 0.5,
        created_time="2026-05-20T20:30:00",
    )


def test_save_ng_only_saves_ng():
    pm = SavePolicyManager(SaveMode.SAVE_NG_ONLY)
    assert pm.should_save_image(make_result("NG"))
    assert pm.should_save_image(make_result("UNKNOWN"))
    assert not pm.should_save_image(make_result("OK"))


def test_save_all_saves_everything():
    pm = SavePolicyManager(SaveMode.SAVE_ALL)
    assert pm.should_save_image(make_result("NG"))
    assert pm.should_save_image(make_result("OK"))
    assert pm.should_save_image(make_result("UNKNOWN"))


def test_result_only_saves_nothing():
    pm = SavePolicyManager(SaveMode.RESULT_ONLY)
    assert not pm.should_save_image(make_result("NG"))
    assert not pm.should_save_image(make_result("OK"))


def test_switch_mode():
    pm = SavePolicyManager(SaveMode.SAVE_NG_ONLY)
    assert not pm.should_save_image(make_result("OK"))
    pm.switch_mode(SaveMode.SAVE_ALL)
    assert pm.should_save_image(make_result("OK"))
