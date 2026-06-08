"""Tests for DatasetVersion auto-creation from dataset builders."""
import json
import os

import pytest


@pytest.fixture
def ctx():
    """Create prerequisite customer -> project -> spec."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    c = create_customer("DSIntCorp", "DI")
    p = create_project(c.customer_id, "DSIntProject")
    s = create_product_spec(p.project_id, "DSIntSpec", "铝", "板")
    return {"customer": c, "project": p, "spec": s}


def _make_session_with_images(project_id, spec_id, tmp_path, n_ok=5, n_ng=2):
    """Create a session with classified images."""
    import numpy as np
    import cv2
    from core.capture_session import create_capture_session

    sess = create_capture_session(
        project_id=project_id, spec_id=spec_id,
        session_name="IntegrationTest",
    )

    raw_dir = os.path.join(tmp_path, sess.session_id, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    from core.storage import insert
    for i in range(n_ok):
        img_path = os.path.join(raw_dir, f"ok_{i:04d}.jpg")
        cv2.imwrite(img_path, (np.random.rand(60, 80, 3) * 255).astype(np.uint8))
        insert("captured_images", {
            "image_id": f"IMG_OK_{i}",
            "session_id": sess.session_id,
            "project_id": project_id,
            "image_name": f"ok_{i:04d}.jpg",
            "image_path": img_path,
            "classification_label": "OK",
            "created_at": "2025-06-01 10:00:00",
        })

    for i in range(n_ng):
        img_path = os.path.join(raw_dir, f"ng_{i:04d}.jpg")
        cv2.imwrite(img_path, (np.random.rand(60, 80, 3) * 255).astype(np.uint8))
        # Also write a label file for one of the NG images
        label_path = os.path.splitext(img_path)[0] + ".txt"
        with open(label_path, "w") as f:
            f.write("0 0.5 0.5 0.1 0.1\n")
        insert("captured_images", {
            "image_id": f"IMG_NG_{i}",
            "session_id": sess.session_id,
            "project_id": project_id,
            "image_name": f"ng_{i:04d}.jpg",
            "image_path": img_path,
            "classification_label": "scratch",
            "created_at": "2025-06-01 10:01:00",
        })

    from core.storage import update
    update("capture_sessions", sess.session_id, {"captured_image_count": n_ok + n_ng}, "session_id")

    return sess


def test_yolo_build_creates_dataset_version(ctx, tmp_path):
    """build_yolo_dataset_from_session creates a DatasetVersion record."""
    from core.dataset_builder import build_yolo_dataset_from_session
    from core.dataset_version import list_dataset_versions

    sess = _make_session_with_images(
        ctx["project"].project_id,
        ctx["spec"].spec_id,
        str(tmp_path),
    )

    dataset_dir = tmp_path / "yolo_ds"
    result = build_yolo_dataset_from_session(
        sess.session_id, str(dataset_dir),
        project_id=ctx["project"].project_id,
        spec_id=ctx["spec"].spec_id,
        version_name="v1_test",
    )

    versions = list_dataset_versions(project_id=ctx["project"].project_id)
    assert len(versions) == 1

    dv = versions[0]
    assert dv.version_name == "v1_test"
    assert dv.source_type == "session"
    assert dv.image_count == 7
    assert dv.capture_session_id == sess.session_id
    assert dv.quality_score is not None
    assert dv.quality_score >= 0

    # Verify quality_report is valid JSON
    report = json.loads(dv.quality_report)
    assert "quality_score" in report
    assert "class_counts" in report
    assert "issues" in report

    # Verify result also has quality_score
    assert result.quality_score == dv.quality_score


def test_yolo_build_without_project_id_no_version(ctx, tmp_path):
    """Without project_id, no DatasetVersion is created."""
    from core.dataset_builder import build_yolo_dataset_from_session
    from core.dataset_version import list_dataset_versions

    sess = _make_session_with_images(
        ctx["project"].project_id,
        ctx["spec"].spec_id,
        str(tmp_path),
    )

    result = build_yolo_dataset_from_session(
        sess.session_id, str(tmp_path / "yolo_no_version"),
    )

    versions = list_dataset_versions(project_id=ctx["project"].project_id)
    assert len(versions) == 0
    assert result.image_count == 7


def test_yolo_build_blocks_review_labels(ctx, tmp_path):
    """UNKNOWN/UNCERTAIN images must be reviewed before YOLO dataset generation."""
    from core.dataset_builder import build_yolo_dataset_from_session
    from core.storage import insert

    sess = _make_session_with_images(
        ctx["project"].project_id,
        ctx["spec"].spec_id,
        str(tmp_path),
    )
    img_path = os.path.join(tmp_path, sess.session_id, "raw", "unknown.jpg")
    with open(img_path, "wb") as f:
        f.write(b"x")
    insert("captured_images", {
        "image_id": "IMG_UNKNOWN_1",
        "session_id": sess.session_id,
        "project_id": ctx["project"].project_id,
        "image_name": "unknown.jpg",
        "image_path": img_path,
        "classification_label": "UNKNOWN",
        "created_at": "2025-06-01 10:02:00",
    })

    with pytest.raises(ValueError, match="review image"):
        build_yolo_dataset_from_session(sess.session_id, str(tmp_path / "blocked"))


def test_dataset_version_crud(ctx):
    """Basic CRUD for DatasetVersion."""
    from core.dataset_version import (
        create_dataset_version, get_dataset_version,
        list_dataset_versions, update_dataset_version,
        delete_dataset_version,
    )

    dv = create_dataset_version(
        project_id=ctx["project"].project_id,
        spec_id=ctx["spec"].spec_id,
        version_name="crud_test",
        source_type="session",
        image_count=100,
        quality_score=85.0,
    )

    # Read
    fetched = get_dataset_version(dv.version_id)
    assert fetched is not None
    assert fetched.version_name == "crud_test"
    assert fetched.quality_score == 85.0

    # List
    versions = list_dataset_versions(project_id=ctx["project"].project_id)
    assert len(versions) == 1

    # Update
    update_dataset_version(dv.version_id, quality_score=90.0, image_count=200)
    updated = get_dataset_version(dv.version_id)
    assert updated.quality_score == 90.0
    assert updated.image_count == 200

    # Delete
    delete_dataset_version(dv.version_id)
    assert get_dataset_version(dv.version_id) is None
