"""Tests for core.field_session — FieldSession CRUD operations."""
from __future__ import annotations

import os
import shutil
import tempfile

import pytest


@pytest.fixture(autouse=True)
def setup_db():
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
def ctx():
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
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
    get_field_session,
    list_field_sessions,
    update_field_session,
    delete_field_session,
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
