"""Tests for training job model."""
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
    yield
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def ctx():
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    c = create_customer("Job Test Co", "JTC")
    p = create_project(c.customer_id, "Job Proj")
    s = create_product_spec(p.project_id, "Spec", material="铜", geometry_type="管")
    return {"project_id": p.project_id, "spec_id": s.spec_id}


def test_create_job(ctx):
    from core.training_job import create_training_job, get_training_job
    j = create_training_job(ctx["project_id"], ctx["spec_id"], "Test Job")
    assert j.job_id.startswith("JOB_")
    assert j.status == "created"
    fetched = get_training_job(j.job_id)
    assert fetched is not None


def test_list_jobs(ctx):
    from core.training_job import create_training_job, list_training_jobs
    create_training_job(ctx["project_id"], ctx["spec_id"], "A")
    create_training_job(ctx["project_id"], ctx["spec_id"], "B")
    assert len(list_training_jobs(ctx["project_id"])) == 2


def test_update_job_status(ctx):
    from core.training_job import create_training_job, update_training_job
    j = create_training_job(ctx["project_id"], ctx["spec_id"], "Status Test")
    u = update_training_job(j.job_id, status="running")
    assert u.status == "running"
