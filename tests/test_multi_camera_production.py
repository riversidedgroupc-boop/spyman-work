"""Tests for multi-camera acquisition and inference pipelines."""
import time
import threading
from pathlib import Path

import pytest

from runtime.frame_buffer import FrameBuffer
from runtime.acquisition_pipeline import AcquisitionPipeline
from runtime.inference_pipeline import InferencePipeline


class StubCameraAdapter:
    """Minimal stub that returns incrementing frames for testing."""

    def __init__(self):
        self._count = 0
        self._running = False
        self._connected = False

    def connect(self, params=None):
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def start_acquisition(self):
        self._running = True

    def stop_acquisition(self):
        self._running = False

    def get_frame(self):
        if not self._running:
            return None
        import numpy as np
        self._count += 1
        return (np.random.rand(60, 80, 3) * 255).astype("uint8")

    def get_status(self) -> dict:
        return {"connected": self._connected, "frame_count": self._count}


class StubModelRunner:
    """Stub that returns an empty prediction (no detections)."""

    def __init__(self, name="stub_runner"):
        self.runner_name = name
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def predict_image(self, image_path):
        with self._lock:
            self.calls.append(image_path)
        # Return a simple prediction object
        from core.schema import ImagePrediction
        return ImagePrediction(image_name=image_path, detections=[])

    def load(self):
        pass


def test_acquisition_pipeline_multi_camera():
    """Acquisition pipeline starts and stops with multiple cameras."""
    acq = AcquisitionPipeline(buffer_size=50)
    acq.add_camera("cam1", StubCameraAdapter())
    acq.add_camera("cam2", StubCameraAdapter())
    acq.add_camera("cam3", StubCameraAdapter())

    acq.start()
    time.sleep(0.3)  # Let frames accumulate
    acq.stop()

    buf = acq.get_buffer()
    assert buf.size() > 0
    assert buf.dropped_count() >= 0  # Some drops may happen under load


def test_acquisition_pipeline_remove_camera():
    """Removing a camera stops its acquisition."""
    acq = AcquisitionPipeline(buffer_size=50)
    adapter = StubCameraAdapter()
    acq.add_camera("cam_temp", adapter)
    assert adapter._running is False  # not started yet

    acq.start()
    time.sleep(0.1)
    assert adapter._running is True

    acq.stop()
    acq.remove_camera("cam_temp")

    # After removal, status should not include the removed camera
    statuses = acq.get_status()
    assert not any(s["camera_id"] == "cam_temp" for s in statuses)


def test_inference_pipeline_per_camera_runner():
    """InferencePipeline dispatches frames to the correct per-camera runner."""
    buf = FrameBuffer(max_size=50)
    pipeline = InferencePipeline(buf)

    runner_a = StubModelRunner("runner_A")
    runner_b = StubModelRunner("runner_B")

    pipeline.set_runner(runner_a, camera_id="cam1")
    pipeline.set_runner(runner_b, camera_id="cam2")

    # Put test frames
    import numpy as np
    img = (np.random.rand(60, 80, 3) * 255).astype("uint8")
    buf.put({"camera_id": "cam1", "image": img, "timestamp": time.time()})
    buf.put({"camera_id": "cam2", "image": img, "timestamp": time.time()})

    pipeline.start()
    time.sleep(0.1)
    pipeline.stop()

    statuses = pipeline.get_all_statuses()
    cam_ids = {s["camera_id"] for s in statuses}
    assert "cam1" in cam_ids
    assert "cam2" in cam_ids

    total = pipeline.total_inference_count
    assert total >= 2, f"Expected at least 2 inferences, got {total}"


def test_inference_pipeline_ng_callback():
    """NG callback is invoked when detections are present."""
    buf = FrameBuffer(max_size=50)
    pipeline = InferencePipeline(buf)

    class NgRunner:
        runner_name = "ng_runner"

        def predict_image(self, path):
            from core.schema import DetectionBox, ImagePrediction
            det = DetectionBox(
                image_name="test.jpg", class_id=0, class_name="scratch",
                confidence=0.92, bbox=[10, 10, 50, 50],
            )
            return ImagePrediction(image_name="test.jpg", detections=[det])

    pipeline.set_runner(NgRunner(), camera_id="cam1")

    ng_results: list[dict] = []
    pipeline.set_on_ng(lambda r: ng_results.append(r))

    import numpy as np
    img = (np.random.rand(60, 80, 3) * 255).astype("uint8")
    buf.put({"camera_id": "cam1", "image": img, "timestamp": time.time()})

    pipeline.start()
    time.sleep(0.1)
    pipeline.stop()

    assert len(ng_results) >= 1
    assert ng_results[0]["is_ng"] is True
    assert ng_results[0]["camera_id"] == "cam1"


def test_inference_pipeline_default_runner_fallback():
    """If no per-camera runner is set, the default runner is used."""
    buf = FrameBuffer(max_size=50)
    pipeline = InferencePipeline(buf)

    default_runner = StubModelRunner("default")
    pipeline.set_runner(default_runner)  # no camera_id -> default

    import numpy as np
    img = (np.random.rand(60, 80, 3) * 255).astype("uint8")
    buf.put({"camera_id": "cam_unknown", "image": img, "timestamp": time.time()})

    pipeline.start()
    time.sleep(0.1)
    pipeline.stop()

    # The default runner should have been used for cam_unknown
    assert pipeline.total_inference_count >= 1


def test_inference_pipeline_removes_temp_file_after_runner_error(monkeypatch):
    buf = FrameBuffer(max_size=50)
    pipeline = InferencePipeline(buf)

    class FailingRunner:
        runner_name = "failing"
        seen_path = ""

        def predict_image(self, path):
            self.seen_path = path
            raise RuntimeError("boom")

    runner = FailingRunner()
    pipeline.set_runner(runner, camera_id="cam1")

    import numpy as np
    img = (np.random.rand(60, 80, 3) * 255).astype("uint8")
    buf.put({"camera_id": "cam1", "image": img, "timestamp": time.time()})

    pipeline.start()
    time.sleep(0.1)
    pipeline.stop()

    assert runner.seen_path
    assert not Path(runner.seen_path).exists()
