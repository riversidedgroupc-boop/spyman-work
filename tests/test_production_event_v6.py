"""Tests for extended V6 DefectEvent fields."""
import json
import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def setup_db():
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    os.environ["COPPER_VISION_DB_PATH"] = db_path
    import core.storage
    import importlib
    importlib.reload(core.storage)
    core.storage.init_db()
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    c = create_customer("TestCorp", "TC")
    p = create_project(c.customer_id, "TestProject")
    s = create_product_spec(p.project_id, "TestSpec", "铜", "管")
    yield {"customer": c, "project": p, "spec": s}
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


def test_record_ng_event_with_v6_fields(setup_db, tmp_path):
    from core.production_event import record_ng_event, list_defect_events
    import numpy as np
    img = (np.random.rand(100, 100, 3) * 255).astype("uint8")

    evt = record_ng_event(
        project_id=setup_db["project"].project_id,
        spec_id=setup_db["spec"].spec_id,
        camera_id="CAM_01",
        image=img,
        output_root=str(tmp_path),
        model_version="model_v001",
        defect_type="scratch",
        position_meter=12.345,
    )
    assert evt.model_version == "model_v001"
    assert evt.defect_type == "scratch"
    assert evt.position_meter == 12.345

    # Verify from DB
    events = list_defect_events(project_id=setup_db["project"].project_id)
    assert len(events) == 1
    assert events[0].model_version == "model_v001"
    assert events[0].defect_type == "scratch"
    assert events[0].position_meter == 12.345


def test_record_ng_event_with_prediction_autofill(setup_db, tmp_path):
    from core.production_event import record_ng_event
    from core.schema import DetectionBox, ImagePrediction
    import numpy as np

    img = (np.random.rand(100, 100, 3) * 255).astype("uint8")
    det = DetectionBox(image_name="test.jpg", class_id=0, class_name="pit", confidence=0.95, bbox=[10, 10, 50, 50])
    pred = ImagePrediction(image_name="test.jpg", detections=[det])

    evt = record_ng_event(
        project_id=setup_db["project"].project_id,
        image=img,
        prediction=pred,
        output_root=str(tmp_path),
    )
    assert evt.detection_count == 1
    assert evt.max_confidence == 0.95
    assert evt.defect_type == "pit"


def test_record_ng_event_saves_under_camera_directory(setup_db, tmp_path):
    from core.production_event import record_ng_event
    import numpy as np

    img = (np.random.rand(16, 16, 3) * 255).astype("uint8")
    evt = record_ng_event(
        project_id=setup_db["project"].project_id,
        spec_id=setup_db["spec"].spec_id,
        batch_id="run_001",
        camera_id="CAM_02",
        image=img,
        output_root=str(tmp_path / "run_001"),
        model_version="model_v001",
        defect_type="scratch",
        position_meter=12.5,
    )

    normalized = evt.ng_image_path.replace("\\", "/")
    assert "/ng_images/CAM_02/" in normalized
    assert os.path.isfile(evt.ng_image_path)


def test_defect_event_from_dict_backward_compat():
    from core.production_event import DefectEvent
    # Simulate a V5 row without new fields
    old_row = {
        "event_id": "EVT_1", "project_id": "p1", "spec_id": "s1",
        "batch_id": "", "camera_id": "cam1", "event_time": "2025-01-01",
        "ng_image_path": "/tmp/x.jpg", "detection_count": 1,
        "prediction_json": "{}", "status": "ng",
        # New fields may be missing
        "model_version": "", "defect_type": "", "max_confidence": 0.0,
        "position_meter": None,
    }
    evt = DefectEvent.from_dict(old_row)
    assert evt.model_version == ""
    assert evt.defect_type == ""
    assert evt.max_confidence == 0.0
    assert evt.position_meter is None
