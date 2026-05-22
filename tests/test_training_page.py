"""Tests for training page guardrails."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any, Generator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _setup_db() -> Generator[None, None, None]:
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    os.environ["COPPER_VISION_DB_PATH"] = db_path
    import importlib
    import core.storage

    importlib.reload(core.storage)
    core.storage.init_db()
    yield
    shutil.rmtree(tmp, ignore_errors=True)


def test_missing_bbox_guard_message_blocks_yolo_training():
    from desktop_app.pages.training_page import yolo_missing_bbox_message

    message = yolo_missing_bbox_message(75)

    assert "75 张 NG 图片缺少 YOLO bbox 标注" in message
    assert "已停止训练" in message
    assert "背景样本" in message


def test_field_dataset_version_starts_training_with_dataset_metadata(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from core.customer import create_customer
    from core.dataset_version import create_dataset_version
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.training_job import list_training_jobs
    from desktop_app.app_context import AppContext
    import desktop_app.pages.training_page as training_page
    from desktop_app.pages.training_page import TrainingPage

    customer = create_customer("Training Page Test Co", "TPT")
    project = create_project(customer.customer_id, "Training Page Test Project")
    spec = create_product_spec(
        project.project_id,
        "Training Page Test Spec",
        material="copper",
        geometry_type="strip",
    )
    AppContext.instance().set_current_customer(customer.customer_id, customer.customer_name)
    AppContext.instance().set_current_project(project.project_id, project.project_name)
    AppContext.instance().set_current_spec(spec.spec_id, spec.product_name)

    dataset_dir = tmp_path / "field_dataset"
    dataset_dir.mkdir()
    yaml_path = dataset_dir / "data.yaml"
    yaml_path.write_text("path: .\nnames: [SCRATCH, PIT]\n", encoding="utf-8")
    dataset_version = create_dataset_version(
        project_id=project.project_id,
        spec_id=spec.spec_id,
        version_name="field first training",
        source_type="field_reviews",
        dataset_path=str(dataset_dir),
        yaml_path=str(yaml_path),
        image_count=2,
        class_names=json.dumps(["SCRATCH", "PIT"]),
    )

    captured: dict[str, Any] = {}

    class _Signal:
        def connect(self, _slot) -> None:
            return None

    class _FakeWorker:
        message = _Signal()
        progress = _Signal()
        log_line = _Signal()
        finished = _Signal()
        error = _Signal()

        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def start(self) -> None:
            captured["started"] = True

    monkeypatch.setattr(training_page, "TrainingWorker", _FakeWorker)

    page = TrainingPage()
    page._refresh_sessions()
    idx = page._session_combo.findData(dataset_version.version_id)
    assert idx >= 0
    page._session_combo.setCurrentIndex(idx)

    page._start_training()

    jobs = list_training_jobs(project.project_id)
    assert len(jobs) == 1
    assert jobs[0].dataset_path == str(dataset_dir)
    assert captured["started"] is True
    assert captured["dataset_yaml"] == str(yaml_path)
    assert captured["dataset_version_id"] == dataset_version.version_id
    assert captured["class_mapping"] == {"SCRATCH": 0, "PIT": 1}
    assert captured["spec_id"] == spec.spec_id
    page.close()
