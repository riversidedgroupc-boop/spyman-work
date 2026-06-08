"""Tests for model version model."""
import os

import pytest

@pytest.fixture
def ctx():
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    c = create_customer("Model Test Co", "MTC")
    p = create_project(c.customer_id, "Model Proj")
    s = create_product_spec(p.project_id, "ModelSpec", "铜", "管")
    return {"project_id": p.project_id, "spec_id": s.spec_id}

def test_create_model(ctx):
    from core.model_version import create_model_version, get_model_version
    m = create_model_version(ctx["project_id"], "Test Model", model_path="/models/best.pt")
    assert m.model_id.startswith("MODEL_")
    fetched = get_model_version(m.model_id)
    assert fetched is not None
    assert fetched.model_path == "/models/best.pt"

def test_list_models(ctx):
    from core.model_version import create_model_version, list_model_versions
    create_model_version(ctx["project_id"], "Model A")
    create_model_version(ctx["project_id"], "Model B")
    assert len(list_model_versions(ctx["project_id"])) == 2

def test_update_status(ctx):
    from core.model_version import create_model_version, update_model_version
    m = create_model_version(ctx["project_id"], "Status")
    u = update_model_version(m.model_id, status="candidate")
    assert u.status == "candidate"

def test_model_links_to_dataset_training_job_and_class_mapping(ctx):
    """Model version links to dataset_version_id, training_job_id, and class_mapping."""
    from core.model_version import create_model_version, get_model_version
    from core.training_job import create_training_job
    import json

    job = create_training_job(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        job_name="linkage_test_job",
    )

    class_map = {"scratch": 0, "pit": 1}
    m = create_model_version(
        ctx["project_id"],
        "LinkedModel",
        model_path="/models/linked_best.pt",
        dataset_version_id="DSVER_test123",
        training_job_id=job.job_id,
        class_mapping=json.dumps(class_map),
        model_type="yolo",
        spec_id=ctx["spec_id"],
    )

    fetched = get_model_version(m.model_id)
    assert fetched is not None
    assert fetched.dataset_version_id == "DSVER_test123"
    assert fetched.training_job_id == job.job_id
    assert fetched.class_mapping == json.dumps(class_map)
    assert fetched.spec_id == ctx["spec_id"]
    assert fetched.model_type == "yolo"

def test_model_linkage_roundtrip(ctx):
    """Full roundtrip: dataset → training job → model with all linkage fields."""
    import json
    from core.dataset_version import create_dataset_version
    from core.training_job import create_training_job
    from core.model_version import create_model_version, get_model_version

    ds = create_dataset_version(
        project_id=ctx["project_id"],
        version_name="linkage_test_v1",
        source_type="field_reviews",
        dataset_path="/data/linkage_test",
        class_names=json.dumps(["scratch", "dent"]),
    )

    job = create_training_job(
        project_id=ctx["project_id"],
        spec_id="",
        job_name="linkage_job",
        dataset_path=ds.dataset_path,
    )

    class_map = {"scratch": 0, "dent": 1}
    m = create_model_version(
        ctx["project_id"],
        "RoundtripModel",
        model_path="/models/roundtrip.pt",
        dataset_version_id=ds.version_id,
        training_job_id=job.job_id,
        class_mapping=json.dumps(class_map),
        spec_id="",
        model_type="yolo",
    )

    fetched = get_model_version(m.model_id)
    assert fetched.dataset_version_id == ds.version_id
    assert fetched.training_job_id == job.job_id
    loaded_map = json.loads(fetched.class_mapping)
    assert loaded_map == class_map
