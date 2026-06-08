"""Regression tests for Phase 5 desktop workflow closure."""
from __future__ import annotations

import os

import pytest

from tests import wait_for_condition

@pytest.fixture
def ctx():
    from core.customer import create_customer
    from core.product_spec import create_product_spec
    from core.project import create_project

    c = create_customer("Phase5 Co", "P5")
    p = create_project(c.customer_id, "Phase5 Project")
    s = create_product_spec(p.project_id, "Tube", material="copper", geometry_type="tube")
    return {"project_id": p.project_id, "spec_id": s.spec_id}

def test_add_captured_image_is_idempotent_and_updates_session_count(ctx):
    from core.capture_session import (
        add_captured_image,
        create_capture_session,
        get_capture_session,
        list_captured_images,
    )

    session = create_capture_session(ctx["project_id"], ctx["spec_id"], "Capture")

    first_id = add_captured_image(
        session.session_id,
        ctx["project_id"],
        "C:/images/a.jpg",
        "a.jpg",
        camera_id="cam1",
    )
    second_id = add_captured_image(
        session.session_id,
        ctx["project_id"],
        "C:/images/a.jpg",
        "a.jpg",
        camera_id="cam1",
    )

    assert second_id == first_id
    assert len(list_captured_images(session.session_id)) == 1
    assert get_capture_session(session.session_id).captured_image_count == 1

def test_build_yolo_dataset_from_session_writes_yaml_images_and_labels(ctx, tmp_path):
    from PIL import Image

    from core.capture_session import (
        add_captured_image,
        create_capture_session,
        set_image_classification,
    )
    from core.dataset_builder import build_yolo_dataset_from_session

    raw_dir = tmp_path / "raw" / "cam1"
    raw_dir.mkdir(parents=True)
    image_path = raw_dir / "defect_001.jpg"
    Image.new("RGB", (32, 24), "white").save(image_path)
    image_path.with_suffix(".txt").write_text("0 0.5 0.5 0.25 0.25\n", encoding="utf-8")

    session = create_capture_session(ctx["project_id"], ctx["spec_id"], "Dataset")
    image_id = add_captured_image(
        session.session_id,
        ctx["project_id"],
        str(image_path),
        image_path.name,
        camera_id="cam1",
    )
    set_image_classification(image_id, "NG_A")

    result = build_yolo_dataset_from_session(session.session_id, str(tmp_path / "dataset"))

    assert os.path.isfile(result.yaml_path)
    assert os.path.isfile(tmp_path / "dataset" / "images" / "train" / image_path.name)
    assert os.path.isfile(tmp_path / "dataset" / "labels" / "train" / "defect_001.txt")
    yaml_text = open(result.yaml_path, encoding="utf-8").read()
    assert "path:" in yaml_text
    assert "names:" in yaml_text
    assert result.image_count == 1
    assert result.label_file_count == 1

def test_record_ng_event_saves_image_and_persists_event(ctx, tmp_path):
    import numpy as np

    from core.production_event import list_defect_events, record_ng_event
    from core.schema import DetectionBox, ImagePrediction

    pred = ImagePrediction(
        image_name="frame.jpg",
        detections=[
            DetectionBox(
                image_name="frame.jpg",
                class_id=0,
                class_name="scratch",
                confidence=0.9,
                bbox=[1, 2, 10, 12],
            )
        ],
    )
    image = np.zeros((20, 30, 3), dtype=np.uint8)

    event = record_ng_event(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        batch_id="BATCH_001",
        camera_id="cam1",
        image=image,
        prediction=pred,
        output_root=str(tmp_path),
    )

    assert os.path.isfile(event.ng_image_path)
    events = list_defect_events(project_id=ctx["project_id"])
    assert len(events) == 1
    assert events[0].detection_count == 1
    assert events[0].ng_image_path == event.ng_image_path

def test_inference_pipeline_records_runner_errors():
    import numpy as np

    from runtime.frame_buffer import FrameBuffer
    from runtime.inference_pipeline import InferencePipeline

    class FailingRunner:
        runner_name = "failing"

        def predict_image(self, image_path):
            raise RuntimeError("boom")

    buffer = FrameBuffer()
    buffer.put({"camera_id": "cam1", "image": np.zeros((8, 8, 3), dtype=np.uint8)})
    pipeline = InferencePipeline(buffer)
    pipeline.set_runner(FailingRunner())
    pipeline.start()
    try:
        wait_for_condition(lambda: pipeline.get_status()["error_count"] > 0, timeout=2.0)
    finally:
        pipeline.stop()

    status = pipeline.get_status()
    assert status["error_count"] == 1
    assert "boom" in status["last_error"]
