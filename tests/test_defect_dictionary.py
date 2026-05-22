"""Tests for core.defect_dictionary — DefectType CRUD + filtering."""
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
    c = create_customer("DD Test Co", "DDT")
    p = create_project(c.customer_id, "DD Test Proj")
    s = create_product_spec(p.project_id, "DD Spec", material="铜", geometry_type="管")
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
    }


from core.defect_dictionary import (  # noqa: E402
    DefectType,
    create_defect_type,
    get_defect_type,
    list_defect_types,
    get_active_defect_types,
    update_defect_type,
    delete_defect_type,
)


# ── Dataclass ──────────────────────────────────────────────────────

def test_defect_type_requires_project_id():
    with pytest.raises(ValueError, match="project_id"):
        DefectType(
            defect_type_id="DEF_test",
            project_id="  ",
        )


def test_defect_type_rejects_invalid_severity(ctx):
    with pytest.raises(ValueError, match="severity"):
        DefectType(
            defect_type_id="DEF_test",
            project_id=ctx["project_id"],
            severity="unknown_level",
        )


def test_defect_type_defaults(ctx):
    dt = DefectType(defect_type_id="DEF_001", project_id=ctx["project_id"])
    assert dt.spec_id == ""
    assert dt.code == ""
    assert dt.severity == "medium"
    assert dt.is_ng is True
    assert dt.sample_image_paths == "[]"


def test_defect_type_to_dict_round_trip(ctx):
    dt = DefectType(
        defect_type_id="DEF_001",
        project_id=ctx["project_id"],
        code="SCRATCH",
        display_name_zh="划痕",
        display_name_en="Scratch",
        severity="high",
        description="Surface scratch defect",
        is_ng=True,
    )
    d = dt.to_dict()
    dt2 = DefectType.from_dict(d)
    assert dt2.defect_type_id == dt.defect_type_id
    assert dt2.code == "SCRATCH"
    assert dt2.display_name_zh == "划痕"
    assert dt2.severity == "high"
    assert dt2.is_ng is True


def test_is_ng_false_round_trip(ctx):
    dt = DefectType(
        defect_type_id="DEF_002",
        project_id=ctx["project_id"],
        code="TEXTURE",
        is_ng=False,
    )
    d = dt.to_dict()
    assert d["is_ng"] == 0
    dt2 = DefectType.from_dict(d)
    assert dt2.is_ng is False


# ── CRUD ───────────────────────────────────────────────────────────

def test_create_and_get(ctx):
    dt = create_defect_type(
        project_id=ctx["project_id"],
        code="PIT",
        display_name_zh="点伤",
        severity="medium",
    )
    assert dt.defect_type_id.startswith("DEF_")

    fetched = get_defect_type(dt.defect_type_id)
    assert fetched is not None
    assert fetched.code == "PIT"
    assert fetched.display_name_zh == "点伤"


def test_list_defect_types(ctx):
    from core.project import create_project
    p2 = create_project(ctx["customer_id"], "DD Proj B")
    create_defect_type(project_id=ctx["project_id"], code="A1", display_name_zh="缺陷A1")
    create_defect_type(project_id=ctx["project_id"], code="A2", display_name_zh="缺陷A2")
    create_defect_type(project_id=p2.project_id, code="B1", display_name_zh="缺陷B1")

    all_types = list_defect_types()
    assert len(all_types) >= 3

    proj_a = list_defect_types(project_id=ctx["project_id"])
    assert len(proj_a) >= 2
    assert all(dt.project_id == ctx["project_id"] for dt in proj_a)


def test_get_active_defect_types(ctx):
    create_defect_type(project_id=ctx["project_id"], code="NG1", is_ng=True)
    create_defect_type(project_id=ctx["project_id"], code="NG2", is_ng=True)
    create_defect_type(project_id=ctx["project_id"], code="OK_TEXTURE", is_ng=False)

    active = get_active_defect_types(project_id=ctx["project_id"])
    assert len(active) >= 2
    assert all(dt.is_ng for dt in active)


def test_update_defect_type(ctx):
    dt = create_defect_type(project_id=ctx["project_id"], code="OLD", display_name_zh="旧名称")
    updated = update_defect_type(dt.defect_type_id, display_name_zh="新名称", severity="critical")
    assert updated is not None
    assert updated.display_name_zh == "新名称"
    assert updated.severity == "critical"

    fetched = get_defect_type(dt.defect_type_id)
    assert fetched.display_name_zh == "新名称"


def test_update_nonexistent():
    result = update_defect_type("DEF_NOPE", display_name_zh="xxx")
    assert result is None


def test_delete(ctx):
    dt = create_defect_type(project_id=ctx["project_id"], code="DEL", display_name_zh="待删除")
    delete_defect_type(dt.defect_type_id)
    assert get_defect_type(dt.defect_type_id) is None


def test_delete_nonexistent_does_not_crash():
    delete_defect_type("DEF_NOPE")


def test_update_rejects_invalid_severity(ctx):
    """P1.2: update must re-validate and reject illegal severity."""
    dt = create_defect_type(project_id=ctx["project_id"], code="TEST", display_name_zh="测试")
    with pytest.raises(ValueError, match="severity"):
        update_defect_type(dt.defect_type_id, severity="invalid_level")


# ── All valid severities ───────────────────────────────────────────

@pytest.mark.parametrize("sev", ["critical", "high", "medium", "low", "info"])
def test_all_valid_severities(ctx, sev):
    dt = DefectType(
        defect_type_id="DEF_SEV",
        project_id=ctx["project_id"],
        severity=sev,
    )
    assert dt.severity == sev
