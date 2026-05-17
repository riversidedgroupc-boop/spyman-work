"""Tests for capture session model."""
import os
import tempfile
import pytest


@pytest.fixture(autouse=True)
def setup_db():
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    os.environ["COPPER_VISION_DB_PATH"] = db_path
    import core.storage, importlib
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
    c = create_customer("Sess Test Co", "STC")
    p = create_project(c.customer_id, "Sess Test Proj")
    s = create_product_spec(p.project_id, "Spec1", material="铜", geometry_type="管")
    return {"project_id": p.project_id, "spec_id": s.spec_id}


def test_create_session(ctx):
    from core.capture_session import create_capture_session, get_capture_session
    sess = create_capture_session(ctx["project_id"], ctx["spec_id"], "Test Session")
    assert sess.session_id.startswith("SESS_")
    assert sess.status == "created"
    fetched = get_capture_session(sess.session_id)
    assert fetched is not None


def test_list_sessions(ctx):
    from core.capture_session import create_capture_session, list_capture_sessions
    create_capture_session(ctx["project_id"], ctx["spec_id"], "Session A")
    create_capture_session(ctx["project_id"], ctx["spec_id"], "Session B")
    sessions = list_capture_sessions(ctx["project_id"])
    assert len(sessions) == 2


def test_update_session_status(ctx):
    from core.capture_session import create_capture_session, update_capture_session
    s = create_capture_session(ctx["project_id"], ctx["spec_id"], "Status Test")
    updated = update_capture_session(s.session_id, status="running")
    assert updated.status == "running"


def test_add_and_list_images(ctx):
    from core.capture_session import (
        create_capture_session, add_captured_image, list_captured_images,
    )
    s = create_capture_session(ctx["project_id"], ctx["spec_id"], "Image Test")
    add_captured_image(s.session_id, ctx["project_id"], "/tmp/a.jpg", "a.jpg", camera_id="cam1")
    add_captured_image(s.session_id, ctx["project_id"], "/tmp/b.jpg", "b.jpg", camera_id="cam2")
    all_imgs = list_captured_images(s.session_id)
    assert len(all_imgs) == 2
    cam1_imgs = list_captured_images(s.session_id, camera_id="cam1")
    assert len(cam1_imgs) == 1


def test_classification_counts(ctx):
    from core.capture_session import (
        create_capture_session, add_captured_image, set_image_classification,
        get_classification_counts,
    )
    s = create_capture_session(ctx["project_id"], ctx["spec_id"], "Class Test")
    iid = add_captured_image(s.session_id, ctx["project_id"], "/tmp/a.jpg", "a.jpg")
    set_image_classification(iid, "OK")
    iid2 = add_captured_image(s.session_id, ctx["project_id"], "/tmp/b.jpg", "b.jpg")
    set_image_classification(iid2, "NG_A")
    counts = get_classification_counts(s.session_id)
    assert counts.get("OK") == 1
    assert counts.get("NG_A") == 1
