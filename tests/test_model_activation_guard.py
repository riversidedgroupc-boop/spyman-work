"""Tests for model activation / rollback guards (Phase 4)."""
import os

import pytest

@pytest.fixture
def ctx():
    from core.customer import create_customer
    from core.project import create_project
    c = create_customer("Activation Co", "AC")
    p = create_project(c.customer_id, "Activation Proj")
    return {"project_id": p.project_id}

def test_activate_model_sets_is_active(ctx):
    from core.model_version import (
        create_model_version, get_model_version, activate_model,
    )
    m = create_model_version(ctx["project_id"], "Model X", model_path="/m/x.pt")
    assert m.is_active is False

    result = activate_model(m.model_id)
    assert result is not None
    assert result.is_active is True
    assert result.status == "active"
    assert result.deployed_at is not None

    fetched = get_model_version(m.model_id)
    assert fetched.is_active is True

def test_activate_model_deactivates_previous(ctx):
    from core.model_version import (
        create_model_version, get_model_version, activate_model,
    )
    m1 = create_model_version(ctx["project_id"], "Model A", model_path="/m/a.pt")
    m2 = create_model_version(ctx["project_id"], "Model B", model_path="/m/b.pt")

    # Activate first model
    activate_model(m1.model_id)
    assert get_model_version(m1.model_id).is_active is True

    # Activate second model — should deactivate first
    activate_model(m2.model_id)
    assert get_model_version(m1.model_id).is_active is False
    assert get_model_version(m1.model_id).status == "archived"
    assert get_model_version(m2.model_id).is_active is True

def test_activate_nonexistent_returns_none():
    from core.model_version import activate_model
    assert activate_model("NONEXISTENT_ID") is None

def test_rollback_model_clears_active(ctx):
    from core.model_version import (
        create_model_version, get_model_version, activate_model, rollback_model,
    )
    m = create_model_version(ctx["project_id"], "Rollback Me", model_path="/m/r.pt")
    activate_model(m.model_id)
    assert get_model_version(m.model_id).is_active is True

    result = rollback_model(m.model_id)
    assert result is not None
    assert result.is_active is False
    assert result.status == "rolled_back"
    assert result.deployed_at is None

    fetched = get_model_version(m.model_id)
    assert fetched.is_active is False
    assert fetched.status == "rolled_back"

def test_rollback_nonexistent_returns_none():
    from core.model_version import rollback_model
    assert rollback_model("NONEXISTENT_ID") is None

def test_get_active_model_returns_none_when_no_active(ctx):
    from core.model_version import create_model_version, get_active_model
    create_model_version(ctx["project_id"], "Inactive", model_path="/m/i.pt")
    assert get_active_model(ctx["project_id"]) is None

def test_get_active_model_returns_active(ctx):
    from core.model_version import (
        create_model_version, activate_model, get_active_model,
    )
    m = create_model_version(ctx["project_id"], "Active One", model_path="/m/a.pt")
    activate_model(m.model_id)
    active = get_active_model(ctx["project_id"])
    assert active is not None
    assert active.model_id == m.model_id
    assert active.is_active is True

def test_activate_then_rollback_then_reactivate(ctx):
    from core.model_version import (
        create_model_version, get_model_version,
        activate_model, rollback_model, get_active_model,
    )
    m = create_model_version(ctx["project_id"], "Cycle", model_path="/m/c.pt")

    # Activate
    activate_model(m.model_id)
    assert get_active_model(ctx["project_id"]).model_id == m.model_id

    # Rollback
    rollback_model(m.model_id)
    assert get_active_model(ctx["project_id"]) is None

    # Re-activate
    activate_model(m.model_id)
    assert get_active_model(ctx["project_id"]).model_id == m.model_id
    assert get_model_version(m.model_id).status == "active"

def test_is_active_in_list(ctx):
    from core.model_version import (
        create_model_version, activate_model, list_model_versions,
    )
    m1 = create_model_version(ctx["project_id"], "Inactive", model_path="/m/i.pt")
    m2 = create_model_version(ctx["project_id"], "Active", model_path="/m/a.pt")
    activate_model(m2.model_id)

    models = list_model_versions(ctx["project_id"])
    by_id = {m.model_id: m for m in models}
    assert by_id[m1.model_id].is_active is False
    assert by_id[m2.model_id].is_active is True

def test_active_model_is_unique_per_spec_not_whole_project(ctx):
    from core.product_spec import create_product_spec
    from core.model_version import (
        activate_model,
        create_model_version,
        get_active_model,
        get_model_version,
    )

    spec_a = create_product_spec(ctx["project_id"], "Spec A", "copper", "tube", camera_count=1)
    spec_b = create_product_spec(ctx["project_id"], "Spec B", "copper", "tube", camera_count=6)
    model_a = create_model_version(
        ctx["project_id"], "Model A", spec_id=spec_a.spec_id, model_path="/m/a.pt"
    )
    model_b = create_model_version(
        ctx["project_id"], "Model B", spec_id=spec_b.spec_id, model_path="/m/b.pt"
    )

    activate_model(model_a.model_id)
    activate_model(model_b.model_id)

    assert get_model_version(model_a.model_id).is_active is True
    assert get_model_version(model_b.model_id).is_active is True
    assert get_active_model(ctx["project_id"], spec_id=spec_a.spec_id).model_id == model_a.model_id
    assert get_active_model(ctx["project_id"], spec_id=spec_b.spec_id).model_id == model_b.model_id

def test_model_activation_and_rollback_write_audit_log(ctx, tmp_path):
    from core.log_manager import LogManager
    from core.model_version import activate_model, create_model_version, rollback_model

    LogManager._instance = None
    LogManager(log_dir=str(tmp_path))
    model = create_model_version(ctx["project_id"], "Audited", model_path="/m/a.pt")

    activate_model(model.model_id)
    rollback_model(model.model_id)

    text = (tmp_path / "audit.log").read_text(encoding="utf-8")
    assert "model_activate" in text
    assert "model_rollback" in text
    assert model.model_id in text
