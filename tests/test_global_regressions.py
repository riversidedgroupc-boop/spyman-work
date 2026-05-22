"""Regression tests for global application review findings."""
from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import threading
import time

import cv2
import numpy as np
import pytest


@pytest.fixture
def temp_db():
    tmp = tempfile.mkdtemp()
    os.environ["COPPER_VISION_DB_PATH"] = os.path.join(tmp, "test.db")
    import core.storage

    importlib.reload(core.storage)
    core.storage.init_db()
    yield
    shutil.rmtree(tmp, ignore_errors=True)


def _create_context():
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec

    customer = create_customer("Global Regression", "GR")
    project = create_project(customer.customer_id, "Project")
    spec = create_product_spec(project.project_id, "Spec", material="copper", geometry_type="tube")
    return project, spec


def test_dataset_builder_keeps_same_filename_from_different_cameras(temp_db, tmp_path):
    from core.capture_session import create_capture_session
    from core.dataset_builder import build_yolo_dataset_from_session
    from core.storage import insert

    project, spec = _create_context()
    session = create_capture_session(project.project_id, spec.spec_id, "same filenames")
    raw_root = tmp_path / "raw"
    for camera_id, value in (("cam1", 40), ("cam2", 180)):
        cam_dir = raw_root / camera_id
        cam_dir.mkdir(parents=True)
        image_path = cam_dir / "000001.jpg"
        cv2.imwrite(str(image_path), np.full((20, 20, 3), value, dtype=np.uint8))
        insert("captured_images", {
            "image_id": f"IMG_{camera_id}",
            "session_id": session.session_id,
            "project_id": project.project_id,
            "image_path": str(image_path),
            "image_name": "000001.jpg",
            "camera_id": camera_id,
            "classification_label": "OK",
        })

    result = build_yolo_dataset_from_session(session.session_id, str(tmp_path / "dataset"))
    copied = list((tmp_path / "dataset" / "images").rglob("*.jpg"))

    assert result.image_count == 2
    assert len(copied) == 2
    assert len({p.name for p in copied}) == 2


def test_folder_watch_keeps_same_content_per_camera(tmp_path):
    from desktop_app.workers.folder_watch_worker import FolderWatchWorker

    cam1 = tmp_path / "cam1"
    cam2 = tmp_path / "cam2"
    cam1.mkdir()
    cam2.mkdir()
    image = np.full((20, 20, 3), 128, dtype=np.uint8)
    cv2.imwrite(str(cam1 / "same.jpg"), image)
    cv2.imwrite(str(cam2 / "same.jpg"), image)

    worker = FolderWatchWorker(
        {"cam1": str(cam1), "cam2": str(cam2)},
        str(tmp_path / "out"),
        camera_count=2,
        target_count=2,
        poll_interval=0.01,
    )
    thread = threading.Thread(target=worker._run_impl)
    thread.start()
    time.sleep(0.2)
    worker._cancelled = True
    thread.join(timeout=1)

    assert (tmp_path / "out" / "cam1" / "same.jpg").exists()
    assert (tmp_path / "out" / "cam2" / "same.jpg").exists()
