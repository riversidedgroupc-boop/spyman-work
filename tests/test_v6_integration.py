"""V6 end-to-end integration test.

Full pipeline:
  customer → project → spec → camera configs → capture session →
  add images → classify → dataset version → model version →
  activate model → production NG event → query & verify
"""
import json
import os
import tempfile

import numpy as np
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


# ── Step 1: Create customer → project → spec ──────────────────────────

def test_v6_pipeline_create_project_spec():
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec, get_product_spec

    cust = create_customer("Integration Test Co", "ITC")
    proj = create_project(cust.customer_id, "V6 Pipeline Project")
    spec = create_product_spec(proj.project_id, "Copper Tube 25mm", "铜", "管",
                               camera_count=3, target_speed_mpm=80.0)

    assert spec.spec_id.startswith("SPEC_")
    assert spec.camera_count == 3
    assert get_product_spec(spec.spec_id).camera_count == 3


# ── Step 2: Create camera configs ─────────────────────────────────────

def test_v6_pipeline_camera_configs():
    # Setup project context
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.camera_config import create_camera_config, list_camera_configs

    cust = create_customer("CamConfig Co", "CCC")
    proj = create_project(cust.customer_id, "CamConfig Project")
    spec = create_product_spec(proj.project_id, "CC Spec", "铜", "管", camera_count=3)

    # Create 3 camera configs
    for i in range(1, 4):
        cfg = create_camera_config(
            spec_id=spec.spec_id,
            camera_index=i,
            adapter_type="folder_watcher",
            connection_params=json.dumps({"watch_dir": f"C:/cam{i}"}),
            enabled=True,
        )
        assert cfg.config_id.startswith("CAMCONF_")

    cfgs = list_camera_configs(spec.spec_id)
    assert len(cfgs) == 3
    indices = sorted(c.camera_index for c in cfgs)
    assert indices == [1, 2, 3]


# ── Step 3: Capture session + add images + classify ───────────────────

def test_v6_pipeline_capture_and_classify():
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.capture_session import (
        create_capture_session, add_captured_image,
        list_captured_images, get_classification_counts,
        set_image_classification,
    )

    cust = create_customer("Capture Co", "CAP")
    proj = create_project(cust.customer_id, "Capture Project")
    spec = create_product_spec(proj.project_id, "Capture Spec", "铜", "管")

    # Create session with sampling_mode
    sess = create_capture_session(
        project_id=proj.project_id,
        spec_id=spec.spec_id,
        session_name="V6 Integration Session",
        sampling_mode="by_time",
    )
    assert sess.sampling_mode == "by_time"

    # Add images
    img_ids = []
    for i in range(5):
        img_id = add_captured_image(
            session_id=sess.session_id,
            project_id=proj.project_id,
            image_path=f"/fake/path/img_{i:03d}.jpg",
            image_name=f"img_{i:03d}.jpg",
            camera_id=f"cam{(i % 3) + 1}",
            width=640, height=480,
        )
        img_ids.append(img_id)
    assert len(img_ids) == 5

    # Classify
    set_image_classification(img_ids[0], "OK")
    set_image_classification(img_ids[1], "NG_A")
    set_image_classification(img_ids[2], "OK")
    set_image_classification(img_ids[3], "NG_B")
    set_image_classification(img_ids[4], "OK")

    # Verify
    images = list_captured_images(sess.session_id)
    assert len(images) == 5

    counts = get_classification_counts(sess.session_id)
    assert counts.get("OK") == 3
    assert counts.get("NG_A") == 1
    assert counts.get("NG_B") == 1


# ── Step 4: Dataset version ───────────────────────────────────────────

def test_v6_pipeline_dataset_version():
    from core.customer import create_customer
    from core.project import create_project
    from core.dataset_version import create_dataset_version, list_dataset_versions

    cust = create_customer("Dataset Co", "DS")
    proj = create_project(cust.customer_id, "Dataset Project")

    dv = create_dataset_version(
        project_id=proj.project_id,
        version_name="V6 Integration Dataset",
        dataset_path="/fake/dataset/v1",
        yaml_path="/fake/dataset/v1/data.yaml",
        image_count=120,
        class_names=json.dumps(["OK", "NG_A", "NG_B"]),
        quality_score=90.0,
        quality_report=json.dumps({"missing_labels": 0, "corrupt_images": 0}),
    )
    assert dv.version_id.startswith("DSVER_")
    assert dv.quality_score == 90.0

    versions = list_dataset_versions(proj.project_id)
    assert len(versions) == 1


# ── Step 5: Model version + activate / rollback ───────────────────────

def test_v6_pipeline_model_lifecycle():
    from core.customer import create_customer
    from core.project import create_project
    from core.model_version import (
        create_model_version, activate_model, rollback_model,
        get_active_model, list_model_versions,
    )

    cust = create_customer("Model Co", "MOD")
    proj = create_project(cust.customer_id, "Model Project")

    m1 = create_model_version(proj.project_id, "V6 Model A", model_path="/m/a.pt")
    m2 = create_model_version(proj.project_id, "V6 Model B", model_path="/m/b.pt")

    # Neither active initially
    assert get_active_model(proj.project_id) is None

    # Activate Model A
    result = activate_model(m1.model_id)
    assert result.is_active is True
    assert result.status == "active"
    assert result.deployed_at is not None

    active = get_active_model(proj.project_id)
    assert active.model_id == m1.model_id

    # Activate Model B — should deactivate Model A
    activate_model(m2.model_id)
    active2 = get_active_model(proj.project_id)
    assert active2.model_id == m2.model_id

    # Model A should be archived
    from core.model_version import get_model_version
    assert get_model_version(m1.model_id).is_active is False
    assert get_model_version(m1.model_id).status == "archived"

    # Rollback Model B
    rollback_model(m2.model_id)
    assert get_active_model(proj.project_id) is None

    # Re-activate A
    activate_model(m1.model_id)
    assert get_active_model(proj.project_id).model_id == m1.model_id


# ── Step 6: Production NG events with V6 fields ───────────────────────

def test_v6_pipeline_production_ng_events():
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.production_event import record_ng_event, list_defect_events

    cust = create_customer("Production Co", "PRD")
    proj = create_project(cust.customer_id, "Production Project")
    spec = create_product_spec(proj.project_id, "Prod Spec", "铜", "管")

    fake_img = np.zeros((128, 128, 3), dtype=np.uint8)

    # Record NG events with full V6 fields
    for i, (cam, dtype, pos) in enumerate([
        ("cam1", "scratch", 1.234),
        ("cam2", "dent", 5.678),
        ("cam1", "scratch", 2.345),
        ("cam3", "hole", 9.012),
        ("cam2", "dent", 6.789),
    ]):
        evt = record_ng_event(
            project_id=proj.project_id,
            spec_id=spec.spec_id,
            camera_id=cam,
            image=fake_img.copy() if i < 3 else fake_img.copy(),
            model_version="MODEL_v6_active",
            defect_type=dtype,
            position_meter=pos,
        )
        assert evt.event_id.startswith("EVT_")
        assert evt.defect_type == dtype

    # Query all
    events = list_defect_events(project_id=proj.project_id)
    assert len(events) == 5

    # Verify V6 fields
    cameras = set(e.camera_id for e in events)
    assert cameras == {"cam1", "cam2", "cam3"}

    positions = [e.position_meter for e in events]
    assert all(p is not None for p in positions)
    assert min(positions) == pytest.approx(1.234)
    assert max(positions) == pytest.approx(9.012)

    # Verify model_version on all events
    assert all(e.model_version == "MODEL_v6_active" for e in events)


# ── Step 7: Sampling controller integration ───────────────────────────

def test_v6_pipeline_sampling_controller():
    from datetime import datetime, timedelta
    from core.sampling_controller import SamplingController

    ctrl = SamplingController()
    ctrl.configure(mode="by_time", interval_seconds=2.0)
    ctrl.set_enabled(True)

    now = datetime(2026, 1, 1, 12, 0, 0)

    # First capture always fires
    assert ctrl.should_capture(now=now) is True
    assert ctrl.state.capture_count == 1

    # Too soon
    assert ctrl.should_capture(now=now + timedelta(seconds=0.5)) is False

    # After interval
    assert ctrl.should_capture(now=now + timedelta(seconds=2.5)) is True
    assert ctrl.state.capture_count == 2

    # Switch to distance mode
    ctrl.configure(mode="by_distance", distance_meters=0.5)
    ctrl.set_enabled(True)

    assert ctrl.should_capture(position_m=0.0) is True
    assert ctrl.should_capture(position_m=0.3) is False
    assert ctrl.should_capture(position_m=0.6) is True
    assert ctrl.state.capture_count == 2  # Reset by configure

    # Switch to manual
    ctrl.configure(mode="manual")
    ctrl.set_enabled(True)
    assert ctrl.should_capture() is False
    ctrl.trigger_manual()
    assert ctrl.should_capture() is True


# ── Step 8: Config backup roundtrip ───────────────────────────────────

def test_v6_pipeline_backup_roundtrip():
    from core.config_backup import create_backup, list_backups, delete_backup

    backup_dir = tempfile.mkdtemp()
    try:
        # Create backup
        meta = create_backup(name="v6_integration_backup", backup_dir=backup_dir,
                             include_configs=True, include_models=False)
        assert meta.backup_id.startswith("BACKUP_")
        assert meta.size_bytes > 0
        assert "database" in meta.included_items
        assert "configs" in meta.included_items
        assert "models" not in meta.included_items

        # List
        backups = list_backups(backup_dir)
        assert len(backups) == 1
        assert backups[0].backup_name == "v6_integration_backup"

        # Cleanup
        delete_backup(meta.backup_id, backup_dir)
        assert list_backups(backup_dir) == []
    finally:
        import shutil
        shutil.rmtree(backup_dir, ignore_errors=True)


# ── Step 9: Dataset quality check integration ─────────────────────────

def test_v6_pipeline_dataset_quality():
    from core.dataset_quality import DatasetQualityChecker

    tmp = tempfile.mkdtemp()
    try:
        checker = DatasetQualityChecker(str(tmp))
        # Empty directory — should score low
        report = checker.full_report()
        assert isinstance(report["quality_score"], (int, float))
        assert isinstance(report, dict)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ── Step 10: Encoder reader simulated mode ────────────────────────────

def test_v6_pipeline_encoder_simulated():
    import time
    from runtime.encoder_reader import SimulatedEncoderReader

    encoder = SimulatedEncoderReader()
    encoder.connect({"line_speed_mpm": 60.0, "pulses_per_meter": 1000.0})

    p1 = encoder.read_position_meter()
    time.sleep(0.2)
    p2 = encoder.read_position_meter()

    # Position should increase over time (1 m/s at 60 mpm)
    assert p2 >= p1
    assert p2 > 0.0

    status = encoder.get_status()
    assert status["speed_mpm"] == 60.0
    assert status["connected"] is True

    encoder.disconnect()
