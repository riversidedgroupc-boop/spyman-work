"""Tests for model version model."""
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
    c = create_customer("Model Test Co", "MTC")
    p = create_project(c.customer_id, "Model Proj")
    return {"project_id": p.project_id}


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
