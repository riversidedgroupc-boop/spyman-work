"""Tests for dataset_version model and CRUD."""

import pytest


@pytest.fixture
def ctx():
    """Create prerequisite customer -> project."""
    from core.customer import create_customer
    from core.project import create_project
    c = create_customer("TestCorp", "TC")
    p = create_project(c.customer_id, "TestProject")
    return {"customer": c, "project": p}


def test_create_dataset_version(ctx):
    from core.dataset_version import create_dataset_version, get_dataset_version
    p = ctx["project"]
    dv = create_dataset_version(
        project_id=p.project_id, version_name="Dataset_v001",
        dataset_path="/tmp/ds1", image_count=500,
    )
    assert dv.version_id.startswith("DSVER_")
    assert dv.version_name == "Dataset_v001"
    assert dv.image_count == 500
    fetched = get_dataset_version(dv.version_id)
    assert fetched is not None
    assert fetched.project_id == p.project_id


def test_list_dataset_versions(ctx):
    from core.dataset_version import create_dataset_version, list_dataset_versions
    p = ctx["project"]
    create_dataset_version(project_id=p.project_id, version_name="v1", dataset_path="/tmp/d1")
    create_dataset_version(project_id=p.project_id, version_name="v2", dataset_path="/tmp/d2")
    versions = list_dataset_versions(project_id=p.project_id)
    assert len(versions) == 2


def test_update_dataset_version(ctx):
    from core.dataset_version import create_dataset_version, update_dataset_version, get_dataset_version
    p = ctx["project"]
    dv = create_dataset_version(project_id=p.project_id, version_name="v1", dataset_path="/tmp/d1")
    update_dataset_version(dv.version_id, quality_score=85.0, quality_report="Good")
    updated = get_dataset_version(dv.version_id)
    assert updated.quality_score == 85.0
    assert updated.quality_report == "Good"


def test_delete_dataset_version(ctx):
    from core.dataset_version import create_dataset_version, delete_dataset_version, get_dataset_version
    p = ctx["project"]
    dv = create_dataset_version(project_id=p.project_id, version_name="v1", dataset_path="/tmp/d1")
    delete_dataset_version(dv.version_id)
    assert get_dataset_version(dv.version_id) is None


def test_roundtrip_dict(ctx):
    from core.dataset_version import DatasetVersion
    p = ctx["project"]
    dv = DatasetVersion(
        version_id="DSVER_test", project_id=p.project_id,
        version_name="v_test", dataset_path="/tmp/d", yaml_path="/tmp/d.yaml",
        image_count=100, class_names='["OK","NG_A"]', val_split_ratio=0.3,
        quality_score=95.0, quality_report="All good",
    )
    d = dv.to_dict()
    dv2 = DatasetVersion.from_dict(d)
    assert dv2.version_id == "DSVER_test"
    assert dv2.image_count == 100
    assert dv2.class_names == '["OK","NG_A"]'
    assert dv2.val_split_ratio == 0.3
    assert dv2.quality_score == 95.0
