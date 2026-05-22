"""Tests for desktop_app/pages/field_workflow_page.py."""
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
    """Temp SQLite DB for Phase A tables."""
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
    c = create_customer("FW Test Co", "FWT")
    p = create_project(c.customer_id, "FW Test Proj")
    s = create_product_spec(p.project_id, "FW Spec", material="铜", geometry_type="管")
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
    }


def _set_app_context(ctx: dict[str, str]) -> None:
    """Set AppContext to the given project/spec."""
    from desktop_app.app_context import AppContext
    app_ctx = AppContext.instance()
    app_ctx.set_current_customer(ctx["customer_id"], "FW Test Co")
    app_ctx.set_current_project(ctx["project_id"], "FW Test Proj")
    app_ctx.set_current_spec(ctx["spec_id"], "FW Spec")


# ── Construction ────────────────────────────────────────────────────

def test_page_constructs(qapp: QApplication):
    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    assert w is not None
    w.close()


def test_page_has_stepper_and_review_table(qapp: QApplication):
    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    # Should have 7 step widgets
    assert len(w._step_widgets) == 7
    # Should have review table
    assert w._review_table is not None
    w.close()


# ── Blocked state ──────────────────────────────────────────────────

def test_no_context_shows_empty_state(qapp: QApplication):
    """No project/spec selected → blocked state without crashing."""
    from desktop_app.app_context import AppContext
    app_ctx = AppContext.instance()
    # Clear context
    app_ctx.clear_all()

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()  # Force refresh with no context

    # All steps should be blocked
    for sw in w._step_widgets:
        assert sw._badge.text() != ""

    # Tables and combos should be empty
    assert w._review_table.rowCount() == 0
    assert w._defect_table.rowCount() == 0
    assert w._session_combo.count() == 0
    assert w._defect_combo.count() == 0
    w.close()


def test_no_session_shows_pending_step3(qapp: QApplication, ctx: dict[str, str]):
    """With context but no session, step 3 should be pending."""
    _set_app_context(ctx)

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()

    # Steps 0-1 blocked (hardware/baseline), step 2 pending
    assert w._step_widgets[2]._badge.text() != ""
    # Step 3-6 blocked
    for i in range(3, 7):
        assert w._step_widgets[i]._badge.text() != ""
    w.close()


# ── Session CRUD ───────────────────────────────────────────────────

def test_create_session(qapp: QApplication, ctx: dict[str, str]):
    _set_app_context(ctx)

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()

    # Session combo should be empty initially
    assert w._session_combo.count() == 0

    # Create a session button is present
    assert w._create_session_btn is not None

    from core.field_session import create_field_session
    s = create_field_session(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        session_type="anomaly_exploration",
    )
    assert s.field_session_id.startswith("FLD_")

    # Refresh should now show the session
    w._on_refresh()
    assert w._session_combo.count() == 1

    w.close()


def test_list_sessions(qapp: QApplication, ctx: dict[str, str]):
    _set_app_context(ctx)

    from core.field_session import create_field_session
    create_field_session(project_id=ctx["project_id"], spec_id=ctx["spec_id"])
    create_field_session(project_id=ctx["project_id"], spec_id=ctx["spec_id"])

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()
    assert w._session_combo.count() == 2

    w.close()


# ── Defect dictionary ──────────────────────────────────────────────

def test_defect_list_shows_in_table(qapp: QApplication, ctx: dict[str, str]):
    _set_app_context(ctx)

    from core.defect_dictionary import create_defect_type
    create_defect_type(project_id=ctx["project_id"], code="S01", display_name_zh="划痕")
    create_defect_type(project_id=ctx["project_id"], code="S02", display_name_zh="点伤", is_ng=False)

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()

    assert w._defect_table.rowCount() == 2
    # Defect combo populated
    assert w._defect_combo.count() == 2

    w.close()


def test_create_defect_updates_table(qapp: QApplication, ctx: dict[str, str]):
    _set_app_context(ctx)

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()

    assert w._defect_table.rowCount() == 0

    # Fill form and create
    w._new_code.setText("PIT")
    w._new_name_zh.setText("点状缺陷")
    w._new_severity.setCurrentText("high")
    w._new_is_ng.setChecked(True)
    w._on_create_defect()

    assert w._defect_table.rowCount() == 1
    assert w._defect_table.item(0, 0).text() == "PIT"
    assert w._defect_table.item(0, 1).text() == "点状缺陷"

    w.close()


def test_create_defect_without_code_shows_warning(
    qapp: QApplication, ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    _set_app_context(ctx)

    import desktop_app.pages.field_workflow_page as fwp
    warned: list[str] = []
    monkeypatch.setattr(fwp.QMessageBox, "warning", lambda *a, **kw: warned.append("warn"))

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._new_code.setText("")  # empty code
    w._on_create_defect()
    assert len(warned) >= 1

    w.close()


# ── Anomaly review status update ───────────────────────────────────

def test_review_queue_shows_entries(qapp: QApplication, ctx: dict[str, str]):
    _set_app_context(ctx)

    from core.field_session import create_field_session
    from core.anomaly_review import create_anomaly_review
    fs = create_field_session(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        session_type="anomaly_exploration",
    )
    create_anomaly_review(
        field_session_id=fs.field_session_id,
        image_path="/data/img01.png",
        anomaly_score=0.85,
        cluster_id="c1",
    )

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()
    # Select session explicitly (setCurrentIndex may not fire signal for idx==0)
    idx = w._session_combo.findData(fs.field_session_id)
    assert idx >= 0
    w._session_combo.setCurrentIndex(idx)
    w._on_session_selected()  # Force refresh of review queue

    # Review table should have 1 row
    assert w._review_table.rowCount() == 1
    assert w._review_table.item(0, 0).text().startswith("ARV_")
    assert w._review_table.item(0, 1).text() == "unreviewed"

    w.close()


def test_auto_load_review_queue_on_refresh(qapp: QApplication, ctx: dict[str, str]):
    """P1 regression: _on_refresh with existing session+reviews auto-populates review table."""
    _set_app_context(ctx)

    from core.field_session import create_field_session
    from core.anomaly_review import create_anomaly_review
    fs = create_field_session(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        session_type="anomaly_exploration",
    )
    create_anomaly_review(
        field_session_id=fs.field_session_id,
        anomaly_score=0.78,
    )

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()

    # After refresh, first session should be auto-selected and review queue populated
    assert w._session_combo.count() == 1
    assert w._current_session_id == fs.field_session_id
    assert w._review_table.rowCount() == 1, (
        f"Expected 1 review row after _on_refresh auto-select, "
        f"got {w._review_table.rowCount()} (current_session_id={w._current_session_id!r})"
    )

    w.close()


def test_mark_review_normal(qapp: QApplication, ctx: dict[str, str]):
    _set_app_context(ctx)

    from core.field_session import create_field_session
    from core.anomaly_review import create_anomaly_review
    fs = create_field_session(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        session_type="anomaly_exploration",
    )
    r = create_anomaly_review(
        field_session_id=fs.field_session_id,
        anomaly_score=0.55,
    )

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()
    idx = w._session_combo.findData(fs.field_session_id)
    w._session_combo.setCurrentIndex(idx)
    w._on_session_selected()  # Force refresh of review queue

    # Select row and mark normal
    w._review_table.selectRow(0)
    w._reviewer_input.setText("tester")
    w._on_mark_status("normal")

    # Verify DB update
    from core.anomaly_review import get_anomaly_review
    updated = get_anomaly_review(r.review_id)
    assert updated.review_status == "normal"
    assert updated.reviewer == "tester"
    assert updated.reviewed_at is not None

    w.close()


def test_confirm_defect_assigns_type(qapp: QApplication, ctx: dict[str, str]):
    _set_app_context(ctx)

    from core.field_session import create_field_session
    from core.anomaly_review import create_anomaly_review
    from core.defect_dictionary import create_defect_type

    fs = create_field_session(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        session_type="anomaly_exploration",
    )
    r = create_anomaly_review(
        field_session_id=fs.field_session_id,
        anomaly_score=0.92,
    )
    dt = create_defect_type(
        project_id=ctx["project_id"],
        code="SCRATCH",
        display_name_zh="划痕",
    )

    from desktop_app.pages.field_workflow_page import FieldWorkflowPage
    w = FieldWorkflowPage()
    w._on_refresh()
    idx = w._session_combo.findData(fs.field_session_id)
    w._session_combo.setCurrentIndex(idx)
    w._on_session_selected()  # Force refresh of review queue

    # Select defect type in combo
    dt_idx = w._defect_combo.findData(dt.defect_type_id)
    assert dt_idx >= 0
    w._defect_combo.setCurrentIndex(dt_idx)

    # Select row and confirm defect
    w._review_table.selectRow(0)
    w._reviewer_input.setText("张三")
    w._on_confirm_defect()

    from core.anomaly_review import get_anomaly_review
    updated = get_anomaly_review(r.review_id)
    assert updated.review_status == "confirmed_defect"
    assert updated.assigned_defect_type_id == dt.defect_type_id
    assert updated.reviewer == "张三"

    w.close()


# ── Navigation ─────────────────────────────────────────────────────

def test_nav_item_registered(qapp: QApplication):
    from desktop_app.constants import NAV_ITEMS
    ids = [item["id"] for item in NAV_ITEMS]
    assert "field_workflow" in ids
    fw_item = next(item for item in NAV_ITEMS if item["id"] == "field_workflow")
    assert "label" in fw_item
    assert fw_item["icon"]
