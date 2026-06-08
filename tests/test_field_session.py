"""Tests for core.field_session — FieldSession CRUD operations."""
from __future__ import annotations

import pytest


@pytest.fixture
def ctx():
    from core.customer import create_customer
    from core.product_spec import create_product_spec
    from core.project import create_project
    c = create_customer("FS Test Co", "FST")
    p = create_project(c.customer_id, "FS Test Proj")
    s = create_product_spec(p.project_id, "FS Spec", material="铜", geometry_type="管")
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
    }

from core.field_session import (  # noqa: E402
    FieldSession,
    create_field_session,
    delete_field_session,
    delete_field_session_cascade,
    get_field_session,
    list_field_sessions,
    update_field_session,
)

# ── Dataclass ──────────────────────────────────────────────────────

def test_field_session_requires_project_id():
    with pytest.raises(ValueError, match="project_id"):
        FieldSession(
            field_session_id="FLD_test",
            project_id="  ",
            spec_id="SPEC_01",
        )

def test_field_session_rejects_invalid_type(ctx):
    with pytest.raises(ValueError, match="session_type"):
        FieldSession(
            field_session_id="FLD_test",
            project_id=ctx["project_id"],
            spec_id=ctx["spec_id"],
            session_type="invalid_type",
        )

def test_field_session_defaults(ctx):
    s = FieldSession(
        field_session_id="FLD_001",
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
    )
    assert s.session_type == "baseline_collection"
    assert s.status == "created"
    assert s.hardware_snapshot == "{}"
    assert s.acquisition_config_snapshot == "{}"
    assert s.notes == ""

def test_field_session_to_dict_round_trip(ctx):
    s = FieldSession(
        field_session_id="FLD_001",
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        session_type="anomaly_exploration",
        status="in_progress",
        notes="test session",
    )
    d = s.to_dict()
    s2 = FieldSession.from_dict(d)
    assert s2.field_session_id == s.field_session_id
    assert s2.project_id == ctx["project_id"]
    assert s2.session_type == "anomaly_exploration"
    assert s2.status == "in_progress"
    assert s2.notes == "test session"

# ── CRUD ───────────────────────────────────────────────────────────

def test_create_and_get(ctx):
    s = create_field_session(
        project_id=ctx["project_id"], spec_id=ctx["spec_id"]
    )
    assert s.field_session_id.startswith("FLD_")

    fetched = get_field_session(s.field_session_id)
    assert fetched is not None
    assert fetched.project_id == ctx["project_id"]
    assert fetched.spec_id == ctx["spec_id"]

def test_create_with_session_type(ctx):
    s = create_field_session(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        session_type="anomaly_exploration",
        notes="finding unknown defects",
    )
    assert s.session_type == "anomaly_exploration"
    assert s.notes == "finding unknown defects"

def test_list_sessions(ctx):
    from core.product_spec import create_product_spec
    from core.project import create_project
    p2 = create_project(ctx["customer_id"], "FS Proj B")
    s2 = create_product_spec(p2.project_id, "FS Spec B", material="铜", geometry_type="板")
    s3 = create_product_spec(p2.project_id, "FS Spec C", material="铜", geometry_type="棒")

    create_field_session(project_id=ctx["project_id"], spec_id=ctx["spec_id"])
    create_field_session(project_id=p2.project_id, spec_id=s2.spec_id)
    create_field_session(project_id=p2.project_id, spec_id=s3.spec_id)

    all_sessions = list_field_sessions()
    assert len(all_sessions) >= 3

    proj_b = list_field_sessions(project_id=p2.project_id)
    assert len(proj_b) >= 2
    assert all(s.project_id == p2.project_id for s in proj_b)

def test_list_sessions_filters_by_spec(ctx):
    from core.product_spec import create_product_spec

    other_spec = create_product_spec(
        ctx["project_id"],
        "FS Other Spec",
        material="copper",
        geometry_type="tube",
    )

    keep = create_field_session(project_id=ctx["project_id"], spec_id=ctx["spec_id"])
    create_field_session(project_id=ctx["project_id"], spec_id=other_spec.spec_id)

    sessions = list_field_sessions(project_id=ctx["project_id"], spec_id=ctx["spec_id"])

    assert [s.field_session_id for s in sessions] == [keep.field_session_id]

def test_update_status(ctx):
    s = create_field_session(
        project_id=ctx["project_id"], spec_id=ctx["spec_id"]
    )
    updated = update_field_session(s.field_session_id, status="completed", notes="done")
    assert updated is not None
    assert updated.status == "completed"
    assert updated.notes == "done"

    fetched = get_field_session(s.field_session_id)
    assert fetched.status == "completed"

def test_update_nonexistent():
    result = update_field_session("FLD_NOPE", status="completed")
    assert result is None

def test_delete(ctx):
    s = create_field_session(
        project_id=ctx["project_id"], spec_id=ctx["spec_id"]
    )
    delete_field_session(s.field_session_id)
    assert get_field_session(s.field_session_id) is None

def test_delete_nonexistent_does_not_crash():
    delete_field_session("FLD_NOPE")

def test_delete_field_session_cascade_removes_reviews(ctx):
    from core.anomaly_review import create_anomaly_review, get_anomaly_review

    s = create_field_session(project_id=ctx["project_id"], spec_id=ctx["spec_id"])
    review = create_anomaly_review(field_session_id=s.field_session_id, anomaly_score=0.8)

    delete_field_session_cascade(s.field_session_id)

    assert get_anomaly_review(review.review_id) is None
    assert get_field_session(s.field_session_id) is None

def test_delete_field_session_cascade_removes_hybrid_retest_rows(ctx):
    from core.storage import fetch_all, insert

    s = create_field_session(project_id=ctx["project_id"], spec_id=ctx["spec_id"])
    insert(
        "hybrid_retest_runs",
        {
            "run_id": "HRR_test",
            "project_id": ctx["project_id"],
            "spec_id": ctx["spec_id"],
            "field_session_id": s.field_session_id,
            "image_dir": "images",
            "status": "completed",
        },
    )
    insert(
        "hybrid_retest_items",
        {
            "item_id": "HRI_test",
            "run_id": "HRR_test",
            "image_path": "image.png",
            "final_decision": "UNKNOWN",
        },
    )

    delete_field_session_cascade(s.field_session_id)

    assert fetch_all("hybrid_retest_items", where="run_id = ?", params=("HRR_test",)) == []
    assert fetch_all("hybrid_retest_runs", where="run_id = ?", params=("HRR_test",)) == []
    assert get_field_session(s.field_session_id) is None

def test_update_rejects_invalid_session_type(ctx):
    """P1.2: update must re-validate and reject illegal values."""
    s = create_field_session(
        project_id=ctx["project_id"], spec_id=ctx["spec_id"]
    )
    with pytest.raises(ValueError, match="session_type"):
        update_field_session(s.field_session_id, session_type="invalid_type")

# ── All valid session types ─────────────────────────────────────────

@pytest.mark.parametrize("stype", [
    "baseline_collection",
    "anomaly_exploration",
    "first_training",
    "production_retest",
    "deployment",
])
def test_all_valid_session_types(ctx, stype):
    s = FieldSession(
        field_session_id="FLD_VALID",
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        session_type=stype,
    )
    assert s.session_type == stype
