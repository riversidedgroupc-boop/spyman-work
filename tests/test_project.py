"""Tests for project model and CRUD."""
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
def customer():
    from core.customer import create_customer
    return create_customer("Project Test Corp", "PTC")


def test_create_project(customer):
    from core.project import create_project, get_project
    p = create_project(customer.customer_id, "Test Project")
    assert p.project_id.startswith("PROJ_")
    assert p.customer_id == customer.customer_id
    assert p.status == "active"
    fetched = get_project(p.project_id)
    assert fetched is not None
    assert fetched.project_name == "Test Project"


def test_list_projects_by_customer(customer):
    from core.project import create_project, list_projects
    create_project(customer.customer_id, "Project A")
    create_project(customer.customer_id, "Project B")
    projects = list_projects(customer.customer_id)
    assert len(projects) == 2


def test_update_project_status(customer):
    from core.project import create_project, update_project
    p = create_project(customer.customer_id, "Status Test")
    updated = update_project(p.project_id, status="completed")
    assert updated.status == "completed"


def test_delete_project(customer):
    from core.project import create_project, delete_project, get_project
    p = create_project(customer.customer_id, "Delete Me")
    delete_project(p.project_id)
    assert get_project(p.project_id) is None
