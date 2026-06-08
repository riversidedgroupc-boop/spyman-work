"""Tests for anomaly dataset builder."""
import os

import pytest


@pytest.fixture
def ctx():
    """Create prerequisite customer -> project -> spec."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    c = create_customer("AnomalyCorp", "AC")
    p = create_project(c.customer_id, "AnomalyProject")
    s = create_product_spec(p.project_id, "AnomalySpec", "铜", "管")
    return {"customer": c, "project": p, "spec": s}


def _make_session_with_images(project_id: str, spec_id: str, tmp_path: str):
    """Create a capture session with some OK and NG images."""
    import numpy as np
    import cv2
    from core.capture_session import create_capture_session

    sess = create_capture_session(
        project_id=project_id, spec_id=spec_id,
        session_name="AnomalyTest",
        source_type="directory_watch",
    )

    raw_dir = os.path.join(tmp_path, sess.session_id, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    # 5 OK images
    for i in range(5):
        img = (np.random.rand(60, 80, 3) * 255).astype(np.uint8)
        img_path = os.path.join(raw_dir, f"ok_{i:04d}.jpg")
        cv2.imwrite(img_path, img)

    # 2 NG images
    for i in range(2):
        img = (np.random.rand(60, 80, 3) * 255).astype(np.uint8)
        img_path = os.path.join(raw_dir, f"ng_{i:04d}.jpg")
        cv2.imwrite(img_path, img)

    # Register captured images
    from core.storage import insert
    for i in range(5):
        insert("captured_images", {
            "image_id": f"IMG_OK_{i}",
            "session_id": sess.session_id,
            "project_id": project_id,
            "image_name": f"ok_{i:04d}.jpg",
            "image_path": os.path.join(raw_dir, f"ok_{i:04d}.jpg"),
            "classification_label": "OK",
            "created_at": "2025-06-01 10:00:00",
        })
    for i in range(2):
        insert("captured_images", {
            "image_id": f"IMG_NG_{i}",
            "session_id": sess.session_id,
            "project_id": project_id,
            "image_name": f"ng_{i:04d}.jpg",
            "image_path": os.path.join(raw_dir, f"ng_{i:04d}.jpg"),
            "classification_label": "scratch",
            "created_at": "2025-06-01 10:01:00",
        })

    # Update session count
    from core.storage import update
    update("capture_sessions", sess.session_id, {"captured_image_count": 7}, "session_id")

    return sess


def test_build_anomaly_dataset_from_session(ctx, tmp_path):
    """Build an anomaly dataset from a session with OK and NG images."""
    from core.anomaly_dataset_builder import build_anomaly_dataset_from_session

    sess = _make_session_with_images(
        ctx["project"].project_id,
        ctx["spec"].spec_id,
        str(tmp_path),
    )

    dataset_dir = tmp_path / "anomaly_dataset"
    result = build_anomaly_dataset_from_session(
        sess.session_id, str(dataset_dir),
        train_ratio=0.8,
        include_ng_test=True,
    )

    assert result.train_count == 4  # 80% of 5 OK
    assert result.test_good_count == 1  # remaining 1 OK
    assert result.test_defect_count == 2  # both NG
    assert os.path.isdir(str(dataset_dir / "train" / "good"))
    assert os.path.isdir(str(dataset_dir / "test" / "good"))
    assert os.path.isdir(str(dataset_dir / "test" / "defect"))
    assert result.quality_score == 80.0  # anomaly datasets lack labels/ dir (expected)


def test_build_anomaly_dataset_no_ng_test(ctx, tmp_path):
    """With include_ng_test=False, NG images are skipped."""
    from core.anomaly_dataset_builder import build_anomaly_dataset_from_session

    sess = _make_session_with_images(
        ctx["project"].project_id,
        ctx["spec"].spec_id,
        str(tmp_path),
    )

    dataset_dir = tmp_path / "anomaly_no_ng"
    result = build_anomaly_dataset_from_session(
        sess.session_id, str(dataset_dir),
        train_ratio=0.8,
        include_ng_test=False,
    )

    assert result.test_defect_count == 0


def test_build_anomaly_dataset_creates_version_record(ctx, tmp_path):
    """DatasetVersion record is auto-created when project_id is given."""
    from core.anomaly_dataset_builder import build_anomaly_dataset_from_session
    from core.dataset_version import list_dataset_versions

    sess = _make_session_with_images(
        ctx["project"].project_id,
        ctx["spec"].spec_id,
        str(tmp_path),
    )

    dataset_dir = tmp_path / "anomaly_versioned"
    result = build_anomaly_dataset_from_session(
        sess.session_id, str(dataset_dir),
        project_id=ctx["project"].project_id,
        spec_id=ctx["spec"].spec_id,
        version_name="test_anomaly_v1",
    )

    assert result.train_count > 0
    versions = list_dataset_versions(project_id=ctx["project"].project_id)
    assert len(versions) == 1
    assert versions[0].version_name == "test_anomaly_v1"
    assert versions[0].source_type == "anomaly"
    assert versions[0].image_count == 7
    assert versions[0].quality_score is not None


def test_build_anomaly_dataset_empty_session_raises(ctx, tmp_path):
    """Raises ValueError if no images in session."""
    from core.anomaly_dataset_builder import build_anomaly_dataset_from_session
    from core.capture_session import create_capture_session

    sess = create_capture_session(
        project_id=ctx["project"].project_id,
        spec_id=ctx["spec"].spec_id,
        session_name="EmptySession",
    )

    with pytest.raises(ValueError, match="no captured images"):
        build_anomaly_dataset_from_session(
            sess.session_id, str(tmp_path / "empty_dataset"),
        )


def test_ng_samples_do_not_pollute_train_good(ctx, tmp_path):
    """NG images must NOT appear in train/good/ — the unsupervised baseline."""
    from core.anomaly_dataset_builder import build_anomaly_dataset_from_session
    from core.label_policy import is_background_label

    sess = _make_session_with_images(
        ctx["project"].project_id,
        ctx["spec"].spec_id,
        str(tmp_path),
    )

    dataset_dir = tmp_path / "anomaly_no_pollute"
    result = build_anomaly_dataset_from_session(
        sess.session_id, str(dataset_dir),
    )

    # Every file in train/good/ must correspond to an OK-classified image
    train_good_dir = str(dataset_dir / "train" / "good")
    train_files = sorted(os.listdir(train_good_dir))
    assert len(train_files) == result.train_count

    ok_images = [
        r for r in _list_session_images(sess.session_id)
        if is_background_label(r.get("classification_label", ""))
    ]
    ok_names = {r["image_name"] for r in ok_images}
    for fname in train_files:
        assert fname in ok_names, (
            f"NG image {fname} leaked into train/good/ — unsupervised baseline contaminated"
        )


def test_uncertain_images_block_anomaly_build(ctx, tmp_path):
    """Images with review labels (Uncertain/Unknown) block anomaly dataset build."""
    import numpy as np
    import cv2
    from core.capture_session import create_capture_session
    from core.storage import insert

    sess = create_capture_session(
        project_id=ctx["project"].project_id,
        spec_id=ctx["spec"].spec_id,
        session_name="UncertainSession",
    )

    raw_dir = os.path.join(str(tmp_path), sess.session_id, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    img = (np.random.rand(60, 80, 3) * 255).astype(np.uint8)
    img_path = os.path.join(raw_dir, "uncertain_0001.jpg")
    cv2.imwrite(img_path, img)

    insert("captured_images", {
        "image_id": "IMG_UNCERTAIN_0",
        "session_id": sess.session_id,
        "project_id": ctx["project"].project_id,
        "image_name": "uncertain_0001.jpg",
        "image_path": img_path,
        "classification_label": "Uncertain",
        "created_at": "2025-06-01 10:00:00",
    })

    from core.storage import update
    update("capture_sessions", sess.session_id, {"captured_image_count": 1}, "session_id")

    from core.anomaly_dataset_builder import build_anomaly_dataset_from_session
    with pytest.raises(ValueError, match="review image"):
        build_anomaly_dataset_from_session(
            sess.session_id, str(tmp_path / "blocked_anomaly"),
        )


def _list_session_images(session_id: str):
    """Helper: list captured_images rows for a session."""
    from core.storage import fetch_all
    return fetch_all("captured_images", where="session_id = ?", params=(session_id,))
