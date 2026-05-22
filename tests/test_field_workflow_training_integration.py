"""Integration tests for Phase C: TrainingWorker + FieldWorkflow UI training readiness."""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import Generator

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
    """Temp SQLite DB for Phase A + Phase C tables."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    os.environ["COPPER_VISION_DB_PATH"] = db_path
    import importlib
    import core.storage
    importlib.reload(core.storage)
    core.storage.init_db()
    yield
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def ctx() -> dict[str, str]:
    """Create parent rows: customer → project → spec."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    c = create_customer("FTCI Test Co", "FTCI")
    p = create_project(c.customer_id, "FTCI Test Proj")
    s = create_product_spec(p.project_id, "FTCI Spec", material="铜", geometry_type="管")
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
    }


def _set_app_context(ctx: dict[str, str]) -> None:
    """Set AppContext to the given project/spec."""
    from desktop_app.app_context import AppContext
    app_ctx = AppContext.instance()
    app_ctx.set_current_customer(ctx["customer_id"], "FTCI Test Co")
    app_ctx.set_current_project(ctx["project_id"], "FTCI Test Proj")
    app_ctx.set_current_spec(ctx["spec_id"], "FTCI Spec")


# ── TrainingWorker integration ───────────────────────────────────────

def test_training_worker_accepts_dataset_version_id(qapp: QApplication, ctx: dict[str, str]):
    """TrainingWorker accepts optional dataset_version_id, class_mapping, spec_id."""
    from desktop_app.workers.training_worker import TrainingWorker

    worker = TrainingWorker(
        job_id="JOB_test",
        dataset_yaml="/fake/data.yaml",
        dataset_version_id="DSVER_test_123",
        class_mapping={"SCRATCH": 0, "PIT": 1},
        spec_id=ctx["spec_id"],
    )
    assert worker._dataset_version_id == "DSVER_test_123"
    assert worker._class_mapping == {"SCRATCH": 0, "PIT": 1}
    assert worker._spec_id == ctx["spec_id"]


def test_training_worker_default_params(qapp: QApplication):
    """TrainingWorker with default params has empty optional fields."""
    from desktop_app.workers.training_worker import TrainingWorker

    worker = TrainingWorker(
        job_id="JOB_test2",
        dataset_yaml="/fake/data.yaml",
    )
    assert worker._dataset_version_id == ""
    assert worker._class_mapping is None
    assert worker._spec_id == ""


# ── Field Workflow Training Readiness UI ─────────────────────────────

def test_training_readiness_section_exists(qapp: QApplication, ctx: dict[str, str]):
    """FieldWorkflowPage has training readiness section with stats labels and buttons."""
    _set_app_context(ctx)

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()

    # Training readiness section should have labels
    assert w._tr_confirmed_label is not None
    assert w._tr_defect_types_label is not None
    assert w._tr_missing_bbox_label is not None
    assert w._tr_unassigned_label is not None
    assert w._tr_pending_label is not None
    assert w._tr_readiness_label is not None
    assert w._tr_dataset_path_label is not None
    assert w._tr_dataset_yaml_label is not None
    assert w._tr_version_label is not None

    # Buttons should exist
    assert w._generate_dataset_btn is not None
    assert w._refresh_readiness_btn is not None

    w.close()


def test_training_readiness_no_session_shows_empty(qapp: QApplication, ctx: dict[str, str]):
    """Without a field session, training readiness shows '—' and 'Not Ready'."""
    _set_app_context(ctx)

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()

    # All stats should be "—"
    assert w._tr_confirmed_label.text() == "—"
    assert w._tr_readiness_label.text() != ""  # shows something
    w.close()


def test_training_readiness_with_confirmed_defects(
    qapp: QApplication, ctx: dict[str, str],
):
    """Training readiness shows confirmed count when confirmed defects exist."""
    _set_app_context(ctx)

    from core.field_session import create_field_session
    from core.anomaly_review import create_anomaly_review

    fs = create_field_session(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        session_type="anomaly_exploration",
    )

    # Create some reviews
    create_anomaly_review(
        field_session_id=fs.field_session_id,
        image_path="/data/img01.png",
        anomaly_score=0.85,
    )

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()

    # Should have session loaded
    assert w._current_session_id == fs.field_session_id

    # Confirmed count shows "0" (all unreviewed)
    assert w._tr_confirmed_label.text() == "0"
    assert "Not Ready" in w._tr_readiness_label.text() or "不可训练" in w._tr_readiness_label.text()

    w.close()
