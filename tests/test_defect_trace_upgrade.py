"""Tests for defect trace upgrade (Phase 4) — production_defect_events queries."""
import os
import tempfile
import shutil

import pytest


@pytest.fixture
def tmp_output():
    """Create a temp output root so record_ng_event doesn't write to real project dir."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def ctx():
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    c = create_customer("Trace Test Co", "TTC")
    p = create_project(c.customer_id, "Trace Proj")
    s = create_product_spec(p.project_id, "Trace Spec", "铜", "管")
    return {"project_id": p.project_id, "spec_id": s.spec_id}


def test_record_ng_event_with_v6_fields(ctx, tmp_output):
    from core.production_event import record_ng_event, list_defect_events
    import numpy as np

    fake_img = np.zeros((64, 64, 3), dtype=np.uint8)

    evt = record_ng_event(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        camera_id="cam1",
        image=fake_img,
        model_version="MODEL_test_001",
        defect_type="NG_A",
        position_meter=12.345,
        output_root=tmp_output,
    )
    assert evt.event_id.startswith("EVT_")
    assert evt.model_version == "MODEL_test_001"
    assert evt.defect_type == "NG_A"
    assert evt.position_meter == pytest.approx(12.345)

    # Verify it's queryable
    events = list_defect_events(project_id=ctx["project_id"])
    assert len(events) == 1
    assert events[0].event_id == evt.event_id

def test_list_defect_events_filters_by_project(ctx, tmp_output):
    from core.production_event import record_ng_event, list_defect_events
    import numpy as np

    fake_img = np.zeros((64, 64, 3), dtype=np.uint8)
    record_ng_event(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        camera_id="cam1",
        image=fake_img,
        model_version="M1",
        output_root=tmp_output,
    )
    record_ng_event(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        camera_id="cam2",
        image=fake_img,
        model_version="M2",
        output_root=tmp_output,
    )
    events = list_defect_events(project_id=ctx["project_id"])
    assert len(events) == 2

def test_list_defect_events_filters_by_spec(ctx, tmp_output):
    from core.production_event import record_ng_event, list_defect_events
    import numpy as np

    fake_img = np.zeros((64, 64, 3), dtype=np.uint8)
    record_ng_event(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        camera_id="cam1",
        image=fake_img,
        output_root=tmp_output,
    )
    events = list_defect_events(spec_id=ctx["spec_id"])
    assert len(events) >= 1

def test_ng_event_auto_derives_defect_type_from_prediction(ctx, tmp_output):
    """When defect_type is empty but prediction has detections, auto-derive from best detection."""
    from core.production_event import record_ng_event
    import numpy as np

    fake_img = np.zeros((64, 64, 3), dtype=np.uint8)

    class FakeDetection:
        def __init__(self, class_name, confidence):
            self.class_name = class_name
            self.confidence = confidence

        def to_dict(self):
            return {"class_name": self.class_name, "confidence": self.confidence}

    class FakePrediction:
        image_name = "test.jpg"
        detections = [FakeDetection("scratch", 0.85), FakeDetection("dent", 0.60)]

    evt = record_ng_event(
        project_id=ctx["project_id"],
        camera_id="cam1",
        image=fake_img,
        prediction=FakePrediction(),
        output_root=tmp_output,
    )
    assert evt.defect_type == "scratch"  # Highest confidence
    assert evt.max_confidence == pytest.approx(0.85)
    assert evt.detection_count == 2

def test_ng_event_defaults_when_no_prediction(ctx, tmp_output):
    from core.production_event import record_ng_event
    import numpy as np

    fake_img = np.zeros((64, 64, 3), dtype=np.uint8)
    evt = record_ng_event(
        project_id=ctx["project_id"],
        camera_id="cam1",
        image=fake_img,
        output_root=tmp_output,
    )
    assert evt.defect_type == ""
    assert evt.max_confidence == 0.0
    assert evt.detection_count == 0
    assert evt.position_meter is None

def test_list_defect_events_returns_empty_for_unknown_project():
    from core.production_event import list_defect_events
    events = list_defect_events(project_id="UNKNOWN_PROJECT")
    assert events == []
