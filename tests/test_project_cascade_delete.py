"""Tests for cascade delete operations (customer → project → spec)."""

import pytest

# ── helpers ──

def _make_customer(name="Test Corp"):
    from core.customer import create_customer

    return create_customer(name, name[:3].upper())

def _make_project(customer_id):
    from core.project import create_project

    return create_project(customer_id, "Test Project")

def _make_spec(project_id):
    from core.product_spec import create_product_spec

    return create_product_spec(
        project_id, "Tube-25mm", material="铜", geometry_type="管",
        target_speed_mpm=80.0, camera_count=3,
    )

def _add_capture_session(project_id, spec_id):
    from core.capture_session import create_capture_session

    return create_capture_session(project_id, spec_id, "Test Session")

def _add_camera_config(spec_id):
    from core.id_utils import generate_id
    from core.storage import insert

    cid = generate_id("CAM")
    insert("camera_configs", {
        "config_id": cid, "spec_id": spec_id,
        "camera_index": 1, "camera_name": "TestCam",
        "camera_type": "area", "brand": "TestBrand",
        "adapter_type": "folder_watcher",
        "connection_params": "{}",
    })
    return cid

def _add_training_job(project_id, spec_id):
    from core.id_utils import generate_id
    from core.storage import insert

    jid = generate_id("JOB")
    insert("training_jobs", {
        "job_id": jid, "project_id": project_id, "spec_id": spec_id,
        "job_name": "Test Job", "model_family": "yolo",
        "task_type": "detection", "training_config": "{}",
    })
    return jid

# ── spec cascade ──

def test_delete_spec_removes_spec():
    c = _make_customer()
    p = _make_project(c.customer_id)
    s = _make_spec(p.project_id)
    from core.product_spec import delete_product_spec, get_product_spec

    delete_product_spec(s.spec_id)
    assert get_product_spec(s.spec_id) is None

def test_delete_spec_cascades_camera_configs():
    c = _make_customer()
    p = _make_project(c.customer_id)
    s = _make_spec(p.project_id)
    cid = _add_camera_config(s.spec_id)
    from core.product_spec import delete_product_spec
    from core.storage import fetch_one

    delete_product_spec(s.spec_id)
    assert fetch_one("camera_configs", cid, "config_id") is None

def test_delete_spec_cascades_capture_sessions():
    c = _make_customer()
    p = _make_project(c.customer_id)
    s = _make_spec(p.project_id)
    from core.capture_session import create_capture_session
    from core.product_spec import delete_product_spec
    from core.storage import fetch_one

    sess = create_capture_session(p.project_id, s.spec_id, "Test Session")
    delete_product_spec(s.spec_id)
    assert fetch_one("capture_sessions", sess.session_id, "session_id") is None

def test_delete_spec_cascades_training_jobs_and_models():
    c = _make_customer()
    p = _make_project(c.customer_id)
    s = _make_spec(p.project_id)
    jid = _add_training_job(p.project_id, s.spec_id)
    from core.id_utils import generate_id
    from core.storage import insert, fetch_one
    from core.product_spec import delete_product_spec

    mid = generate_id("MODEL")
    insert("model_versions", {
        "model_id": mid, "project_id": p.project_id, "spec_id": s.spec_id,
        "training_job_id": jid, "model_name": "TestModel", "model_type": "yolo",
        "model_path": "/tmp/test.pt", "class_mapping": "{}",
    })
    eid = generate_id("EXPORT")
    insert("model_export_artifacts", {
        "export_id": eid, "project_id": p.project_id, "spec_id": s.spec_id,
        "source_model_id": mid, "backend": "onnx", "precision": "fp32",
    })

    delete_product_spec(s.spec_id)
    assert fetch_one("model_export_artifacts", eid, "export_id") is None
    assert fetch_one("model_versions", mid, "model_id") is None
    assert fetch_one("training_jobs", jid, "job_id") is None

def test_delete_spec_cascades_field_sessions_and_reviews():
    c = _make_customer()
    p = _make_project(c.customer_id)
    s = _make_spec(p.project_id)
    from core.id_utils import generate_id
    from core.storage import insert, fetch_one
    from core.product_spec import delete_product_spec

    fid = generate_id("FIELD")
    insert("field_sessions", {
        "field_session_id": fid, "project_id": p.project_id, "spec_id": s.spec_id,
        "hardware_snapshot": "{}", "acquisition_config_snapshot": "{}",
    })
    rid = generate_id("REVIEW")
    insert("anomaly_reviews", {
        "review_id": rid, "field_session_id": fid,
        "anomaly_score": 0.85,
    })

    delete_product_spec(s.spec_id)
    assert fetch_one("anomaly_reviews", rid, "review_id") is None
    assert fetch_one("field_sessions", fid, "field_session_id") is None

def test_delete_spec_preserves_other_specs():
    c = _make_customer()
    p = _make_project(c.customer_id)
    s1 = _make_spec(p.project_id)
    s2 = _make_spec(p.project_id)
    from core.product_spec import delete_product_spec, get_product_spec

    delete_product_spec(s1.spec_id)
    assert get_product_spec(s1.spec_id) is None
    assert get_product_spec(s2.spec_id) is not None

def test_delete_spec_cascades_hybrid_retest():
    c = _make_customer()
    p = _make_project(c.customer_id)
    s = _make_spec(p.project_id)
    from core.id_utils import generate_id
    from core.storage import insert, fetch_one
    from core.product_spec import delete_product_spec

    rid = generate_id("HRETEST")
    insert("hybrid_retest_runs", {
        "run_id": rid, "project_id": p.project_id, "spec_id": s.spec_id,
        "config_json": "{}", "summary_json": "{}",
    })
    iid = generate_id("HRITEM")
    insert("hybrid_retest_items", {
        "item_id": iid, "run_id": rid, "image_path": "/tmp/test.png",
        "final_decision": "ng",
    })

    delete_product_spec(s.spec_id)
    assert fetch_one("hybrid_retest_items", iid, "item_id") is None
    assert fetch_one("hybrid_retest_runs", rid, "run_id") is None

# ── project cascade ──

def test_delete_project_removes_project():
    c = _make_customer()
    p = _make_project(c.customer_id)
    from core.project import delete_project, get_project

    delete_project(p.project_id)
    assert get_project(p.project_id) is None

def test_delete_project_cascades_all_specs():
    c = _make_customer()
    p = _make_project(c.customer_id)
    s1 = _make_spec(p.project_id)
    s2 = _make_spec(p.project_id)
    from core.project import delete_project
    from core.product_spec import get_product_spec

    delete_project(p.project_id)
    assert get_product_spec(s1.spec_id) is None
    assert get_product_spec(s2.spec_id) is None

def test_delete_project_cascades_child_data():
    c = _make_customer()
    p = _make_project(c.customer_id)
    s = _make_spec(p.project_id)
    cid = _add_camera_config(s.spec_id)
    jid = _add_training_job(p.project_id, s.spec_id)
    from core.project import delete_project
    from core.storage import fetch_one

    delete_project(p.project_id)
    assert fetch_one("camera_configs", cid, "config_id") is None
    assert fetch_one("training_jobs", jid, "job_id") is None
    assert fetch_one("product_specs", s.spec_id, "spec_id") is None
    assert fetch_one("projects", p.project_id, "project_id") is None

def test_delete_project_cascades_sample_library():
    c = _make_customer()
    p = _make_project(c.customer_id)
    from core.id_utils import generate_id
    from core.storage import insert, fetch_one
    from core.project import delete_project

    eid = generate_id("SAMPLE")
    insert("sample_library_entries", {
        "entry_id": eid, "current_project_id": p.project_id,
        "current_image_path": "/tmp/test.png",
        "device_config_snapshot": "{}",
    })

    delete_project(p.project_id)
    assert fetch_one("sample_library_entries", eid, "entry_id") is None

def test_delete_project_preserves_other_projects():
    c = _make_customer()
    p1 = _make_project(c.customer_id)
    p2 = _make_project(c.customer_id)
    from core.project import delete_project, get_project

    delete_project(p1.project_id)
    assert get_project(p1.project_id) is None
    assert get_project(p2.project_id) is not None

# ── customer cascade ──

def test_delete_customer_removes_customer():
    c = _make_customer()
    from core.customer import delete_customer, get_customer

    delete_customer(c.customer_id)
    assert get_customer(c.customer_id) is None

def test_delete_customer_cascades_all_projects_and_specs():
    c = _make_customer()
    p1 = _make_project(c.customer_id)
    p2 = _make_project(c.customer_id)
    s1 = _make_spec(p1.project_id)
    s2 = _make_spec(p2.project_id)
    from core.customer import delete_customer
    from core.project import get_project
    from core.product_spec import get_product_spec

    delete_customer(c.customer_id)
    assert get_project(p1.project_id) is None
    assert get_project(p2.project_id) is None
    assert get_product_spec(s1.spec_id) is None
    assert get_product_spec(s2.spec_id) is None

def test_delete_customer_cascades_deeply():
    c = _make_customer()
    p = _make_project(c.customer_id)
    s = _make_spec(p.project_id)
    cid = _add_camera_config(s.spec_id)
    jid = _add_training_job(p.project_id, s.spec_id)
    from core.id_utils import generate_id
    from core.storage import insert, fetch_one
    from core.customer import delete_customer

    eid = generate_id("SAMPLE")
    insert("sample_library_entries", {
        "entry_id": eid, "current_project_id": p.project_id,
        "current_image_path": "/tmp/test.png",
        "device_config_snapshot": "{}",
    })

    delete_customer(c.customer_id)
    assert fetch_one("customers", c.customer_id) is None
    assert fetch_one("projects", p.project_id, "project_id") is None
    assert fetch_one("product_specs", s.spec_id, "spec_id") is None
    assert fetch_one("camera_configs", cid, "config_id") is None
    assert fetch_one("training_jobs", jid, "job_id") is None
    assert fetch_one("sample_library_entries", eid, "entry_id") is None

def test_delete_customer_preserves_other_customers():
    c1 = _make_customer("Corp A")
    c2 = _make_customer("Corp B")
    p2 = _make_project(c2.customer_id)
    from core.customer import delete_customer, get_customer
    from core.project import get_project

    delete_customer(c1.customer_id)
    assert get_customer(c1.customer_id) is None
    assert get_customer(c2.customer_id) is not None
    assert get_project(p2.project_id) is not None

# ── rollback on failure ──

def test_cascade_transaction_commits_cleanly():
    """A clean customer tree deletes atomically and completely."""
    c = _make_customer()
    p = _make_project(c.customer_id)
    _make_spec(p.project_id)
    from core.customer import delete_customer, get_customer
    from core.project import get_project

    # Normal cascade should succeed without error
    try:
        delete_customer(c.customer_id)
    except Exception:
        pytest.fail("Cascade delete should not raise for a clean customer tree")

    assert get_customer(c.customer_id) is None
    assert get_project(p.project_id) is None
