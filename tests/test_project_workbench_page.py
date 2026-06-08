"""Tests for desktop_app/pages/project_workbench_page.py and Phase G navigation."""

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
    """Create parent rows: customer -> project -> spec."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec

    c = create_customer("WB Test Co", "WBT")
    p = create_project(c.customer_id, "WB Test Proj")
    s = create_product_spec(p.project_id, "WB Spec", material="铜", geometry_type="管")
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
    }


def _set_app_context(ctx_data: dict[str, str]) -> None:
    """Set AppContext to the given project/spec."""
    from desktop_app.app_context import AppContext

    app_ctx = AppContext.instance()
    app_ctx.set_current_customer(ctx_data["customer_id"], "WB Test Co")
    app_ctx.set_current_project(ctx_data["project_id"], "WB Test Proj")
    app_ctx.set_current_spec(ctx_data["spec_id"], "WB Spec")


def _tab_texts(tab_widget) -> list[str]:
    return [tab_widget.tabText(i) for i in range(tab_widget.count())]


# ── Widget creation ───────────────────────────────────────────────────


def test_create_workbench_page(qapp: QApplication):
    """Workbench page widget can be instantiated."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    w = ProjectWorkbenchPage()
    assert w is not None
    assert len(w._step_frames) == 8
    assert w._overview_frame is not None
    assert w._detail_frame is not None
    assert w._hint_frame is not None
    w.close()


def test_workbench_has_8_step_frames(qapp: QApplication):
    """8 step frames replace the old 4 summary cards."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    w = ProjectWorkbenchPage()
    assert len(w._step_frames) == 8
    assert len(w._step_icon_labels) == 8
    assert len(w._step_name_labels) == 8
    assert len(w._step_state_labels) == 8
    w.close()


# ── Empty state (no project) ──────────────────────────────────────────


def test_workbench_empty_state_no_project(qapp: QApplication):
    """Step 0 is current, all others pending when no project selected."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage
    from desktop_app.i18n import tr

    w = ProjectWorkbenchPage()
    w.refresh()

    # Step 0 should be current
    assert tr("workbench.status_current") in w._step_state_labels[0].text()
    # Steps 1-7 should be pending
    for i in range(1, 8):
        assert tr("workbench.status_pending") in w._step_state_labels[i].text()
    # Overview shows 0/8
    assert w._overview_progress.text() == "0/8"
    w.close()


def test_workbench_empty_state_overview_placeholder(qapp: QApplication):
    """Overview shows placeholder when no project."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    w = ProjectWorkbenchPage()
    w.refresh()
    assert w._overview_customer.text() == "—"
    assert w._overview_project.text() == "—"
    assert w._overview_spec.text() == "—"
    w.close()


def test_workbench_no_quick_action_buttons(qapp: QApplication, ctx: dict[str, str]):
    """Workbench no longer has quick action buttons."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    w = ProjectWorkbenchPage()
    assert not hasattr(w, "_action_buttons")

    _set_app_context(ctx)
    w.refresh()
    assert not hasattr(w, "_action_buttons")
    w.close()


# ── With project ──────────────────────────────────────────────────────


def test_workbench_with_project_shows_name(qapp: QApplication, ctx: dict[str, str]):
    """Overview bar shows project name from DB when project is selected."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    _set_app_context(ctx)
    w = ProjectWorkbenchPage()
    w.refresh()
    assert "WB Test Proj" in w._overview_project.text()
    w.close()


def test_workbench_detail_panel_populated(qapp: QApplication, ctx: dict[str, str]):
    """Detail panel shows purpose, steps, criteria for selected step."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    _set_app_context(ctx)
    w = ProjectWorkbenchPage()
    w.refresh()
    # Detail panel should have content
    assert len(w._detail_title.text()) > 0
    assert len(w._detail_purpose.text()) > 0
    assert len(w._detail_ops.text()) > 0
    assert len(w._detail_criteria.text()) > 0
    assert len(w._detail_enter_btn.text()) > 0
    w.close()


def test_workbench_hint_bar_populated(qapp: QApplication, ctx: dict[str, str]):
    """Hint bar shows blocker and recommended next step."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    _set_app_context(ctx)
    w = ProjectWorkbenchPage()
    w.refresh()
    assert len(w._hint_blocker.text()) > 0
    assert len(w._hint_next.text()) > 0
    w.close()


# ── Step click → detail panel, no navigation ──────────────────────────


def test_workbench_step_click_updates_detail(qapp: QApplication, ctx: dict[str, str]):
    """Clicking a step updates the detail panel without navigating."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    _set_app_context(ctx)
    w = ProjectWorkbenchPage()
    w.refresh()

    # Click step 1 (device config)
    w._on_step_clicked(1)
    assert w._selected_step_idx == 1
    from desktop_app.i18n import tr

    assert tr("workbench.step_device_config") in w._detail_title.text()
    assert len(w._detail_purpose.text()) > 0
    w.close()


def test_workbench_step_click_does_not_navigate(qapp: QApplication, ctx: dict[str, str]):
    """Clicking a step does not emit navigate_to_page."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage
    from desktop_app.app_context import AppContext

    _set_app_context(ctx)
    w = ProjectWorkbenchPage()
    w.refresh()

    navigated: list[str] = []
    app_ctx = AppContext.instance()
    app_ctx.navigate_to_page.connect(lambda pid: navigated.append(pid))

    w._on_step_clicked(3)
    assert len(navigated) == 0  # no navigation on step click
    w.close()


def test_workbench_enter_button_navigates(qapp: QApplication, ctx: dict[str, str]):
    """Clicking the enter button emits navigate_to_page."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage
    from desktop_app.app_context import AppContext

    _set_app_context(ctx)
    w = ProjectWorkbenchPage()
    w.refresh()

    navigated: list[str] = []
    app_ctx = AppContext.instance()
    app_ctx.navigate_to_page.connect(lambda pid: navigated.append(pid))

    # Select a step and click enter
    w._on_step_clicked(1)  # device_setup
    w._on_enter_clicked()
    assert len(navigated) == 1
    assert navigated[0] == "device_setup"
    w.close()


def test_workbench_enter_project_config_emits_special_signal(
    qapp: QApplication, ctx: dict[str, str],
):
    """Enter button for step 0 emits navigate_to_project_center."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage
    from desktop_app.app_context import AppContext

    _set_app_context(ctx)
    w = ProjectWorkbenchPage()
    w.refresh()

    project_center_calls: list[None] = []
    app_ctx = AppContext.instance()
    app_ctx.navigate_to_project_center.connect(lambda: project_center_calls.append(None))

    w._on_step_clicked(0)  # project config
    w._on_enter_clicked()
    assert len(project_center_calls) == 1
    w.close()


# ── Context change refreshes ──────────────────────────────────────────


def test_workbench_refresh_on_project_changed(qapp: QApplication, ctx: dict[str, str]):
    """Workbench refreshes when project_changed signal fires."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    w = ProjectWorkbenchPage()
    w.refresh()
    assert w._overview_project.text() == "—"

    _set_app_context(ctx)
    w.refresh()
    assert "WB Test Proj" in w._overview_project.text()
    w.close()


def test_workbench_refresh_via_signal(qapp: QApplication, ctx: dict[str, str]):
    """Workbench.refresh() is callable and updates UI."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    _set_app_context(ctx)
    w = ProjectWorkbenchPage()
    w.refresh()

    # After refresh with project set, overview should be populated
    assert w._overview_customer.text() != "—"
    assert w._overview_project.text() != "—"
    w.close()


# ── Step state derivation ─────────────────────────────────────────────


def test_workbench_step_states_new_project(qapp: QApplication, ctx: dict[str, str]):
    """With project + spec but no device config, step 1 is current."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage
    from desktop_app.i18n import tr

    _set_app_context(ctx)
    w = ProjectWorkbenchPage()
    w.refresh()

    # New project with spec but no device → step 1 (device config) is current
    states = [w._step_state_labels[i].text() for i in range(8)]
    assert tr("workbench.status_done") in states[0]  # project config done
    assert tr("workbench.status_current") in states[1]  # device config current
    w.close()


def test_workbench_all_steps_have_names(qapp: QApplication):
    """All 8 steps have non-empty display names."""
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    w = ProjectWorkbenchPage()
    for i in range(8):
        name = w._step_name_labels[i].text()
        assert len(name) > 0, f"Step {i} has empty name"
    w.close()


# ── Navigation structure (Phase G) ────────────────────────────────────


def test_nav_items_9_entries(qapp: QApplication):
    """Phase G: NAV_ITEMS has at least 9 entries."""
    from desktop_app.constants import NAV_ITEMS

    assert len(NAV_ITEMS) >= 9


def test_nav_items_all_ids(qapp: QApplication):
    """Phase G: All expected nav IDs are present (subset check)."""
    from desktop_app.constants import NAV_ITEMS

    ids = [item["id"] for item in NAV_ITEMS]
    expected = [
        "workbench",
        "device_setup",
        "site_capture",
        "sample_review",
        "model_iteration",
        "hybrid_runtime",
        "performance",
        "delivery",
        "maintenance",
    ]
    for eid in expected:
        assert eid in ids, f"Expected nav id '{eid}' not found in NAV_ITEMS"


def test_old_nav_entries_not_in_nav_items(qapp: QApplication):
    """Phase G: Old flat-menu entries are NOT in NAV_ITEMS."""
    from desktop_app.constants import NAV_ITEMS

    ids = [item["id"] for item in NAV_ITEMS]
    old_entries = [
        "project_center",
        "capture",
        "training",
        "evaluation",
        "production",
        "device_config",
        "reports",
        "settings",
        "field_workflow",
        "hybrid_retest",
    ]
    for old_id in old_entries:
        assert old_id not in ids, f"Old nav entry '{old_id}' should not be in NAV_ITEMS"


def test_nav_items_have_labels_and_icons(qapp: QApplication):
    """Every NAV_ITEM has id, label, and a QtAwesome icon name."""
    from desktop_app.constants import NAV_ITEMS

    for item in NAV_ITEMS:
        assert "id" in item
        assert "label" in item
        assert "icon" in item
        assert len(item["id"]) > 0
        assert len(item["label"]) > 0
        assert item["icon"].startswith("fa5s.")


# ── Container mapping (Phase G) ───────────────────────────────────────


def test_main_window_page_ids_routed(qapp: QApplication):
    """MainWindow._on_page_selected routes all 9 page_ids."""
    from desktop_app.constants import NAV_ITEMS
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    page_ids = [item["id"] for item in NAV_ITEMS]
    for pid in page_ids:
        # Should not raise
        w._on_page_selected(pid)
    w.close()


def test_main_window_has_9_containers(qapp: QApplication):
    """MainWindow._pages has at least 9 containers."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    assert w._pages.count() >= 9
    w.close()


def test_main_window_container_objects(qapp: QApplication):
    """All container references are set after _build_ui."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    assert w._workbench_container is not None
    assert w._device_container is not None
    assert w._site_capture_container is not None
    assert w._sample_review_container is not None
    assert w._training_container is not None
    assert w._hybrid_runtime_container is not None
    assert w._performance_container is not None
    assert w._delivery_container is not None
    assert w._maintenance_container is not None
    assert w._af_container is not None
    w.close()


def test_main_window_site_capture_tabs_exclude_review_pages(qapp: QApplication):
    """site_capture keeps capture + live runtime only."""
    from desktop_app.i18n import tr
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    assert w._site_capture_tabs.count() == 2
    assert _tab_texts(w._site_capture_tabs) == [
        tr("capture.title"),
        tr("production.title"),
    ]
    assert not hasattr(w, "_site_classify_page")
    assert not hasattr(w, "_site_dataset_page")
    w.close()


def test_main_window_sample_review_owns_review_and_dataset_tabs(qapp: QApplication):
    """sample_review is the single entry for classification and dataset review."""
    from desktop_app.i18n import tr
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    assert _tab_texts(w._sample_review_tabs) == [
        tr("classify.title"),
        tr("bbox.page_title"),
        tr("field_workflow.title"),
        tr("nav.sample_library"),
        tr("dataset.title"),
    ]
    w.close()


def test_main_window_model_iteration_excludes_delivery_export(qapp: QApplication):
    """model_iteration keeps training/model history; export belongs to delivery."""
    from desktop_app.i18n import tr
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    assert w._training_tabs.count() == 3
    assert _tab_texts(w._training_tabs) == [
        tr("training.title"),
        tr("jobs.title"),
        tr("model.title"),
    ]
    assert not hasattr(w, "_model_export_page")
    w.close()


def test_main_window_delivery_keeps_model_export(qapp: QApplication):
    """delivery remains the single workflow entry for export."""
    from desktop_app.i18n import tr
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    assert _tab_texts(w._delivery_tabs) == [
        tr("report.title"),
        tr("export.title"),
    ]
    assert w._delivery_export_page is not None
    w.close()


# ── MainWindow refresh wiring ─────────────────────────────────────────


def test_main_window_context_change_refreshes_workbench(
    qapp: QApplication,
):
    """_on_context_changed calls workbench_page.refresh()."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    refresh_called: list[bool] = []

    def _fake_refresh() -> None:
        refresh_called.append(True)

    w._workbench_page.refresh = _fake_refresh
    w._on_context_changed("")
    assert len(refresh_called) == 1
    w.close()


def test_top_refresh_only_refreshes_current_visible_tab(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
):
    """Top refresh should dispatch to the currently visible page/tab only."""
    calls: list[str] = []

    from desktop_app.pages.camera_workbench_page import CameraWorkbenchPage
    from desktop_app.pages.project_center_page import ProjectCenterPage
    from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage

    monkeypatch.setattr(ProjectWorkbenchPage, "refresh", lambda self: calls.append("workbench"))
    monkeypatch.setattr(ProjectCenterPage, "refresh", lambda self: calls.append("project_center"))
    monkeypatch.setattr(CameraWorkbenchPage, "refresh", lambda self: calls.append("camera"), raising=False)

    from desktop_app.main_window import MainWindow

    w = MainWindow()
    w._pages.setCurrentWidget(w._device_container)
    w._device_tabs.setCurrentWidget(w._camera_workbench_page)

    w._selector.refreshed.emit()

    assert calls == ["camera"]
    w.close()


def test_main_window_navigate_to_project_center(
    qapp: QApplication,
):
    """navigate_to_project_center switches to workbench + project-center tab."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    w._workbench_tabs.setCurrentIndex(0)  # start on workbench tab
    w._on_navigate_to_project_center()
    assert w._pages.currentWidget() is w._workbench_container
    assert w._workbench_tabs.currentIndex() == 1  # project-center tab
    w.close()


# ── AppContext signals ────────────────────────────────────────────────


def test_app_context_navigate_to_page_signal(qapp: QApplication):
    """navigate_to_page signal exists and carries page_id string."""
    from desktop_app.app_context import AppContext

    app_ctx = AppContext.instance()
    received: list[str] = []
    app_ctx.navigate_to_page.connect(lambda pid: received.append(pid))
    app_ctx.navigate_to_page.emit("site_capture")
    assert "site_capture" in received


def test_app_context_navigate_to_site_production_signal(qapp: QApplication):
    """navigate_to_site_production signal carries mode and session_id."""
    from desktop_app.app_context import AppContext

    app_ctx = AppContext.instance()
    received: list[tuple[str, str]] = []
    app_ctx.navigate_to_site_production.connect(lambda m, s: received.append((m, s)))
    app_ctx.navigate_to_site_production.emit("baseline_capture", "SESS_001")
    assert ("baseline_capture", "SESS_001") in received


def test_app_context_navigate_to_project_center_signal(qapp: QApplication):
    """navigate_to_project_center signal exists."""
    from desktop_app.app_context import AppContext

    app_ctx = AppContext.instance()
    received: list[None] = []
    app_ctx.navigate_to_project_center.connect(lambda: received.append(None))
    app_ctx.navigate_to_project_center.emit()
    assert len(received) == 1


# ── i18n coverage ─────────────────────────────────────────────────────


def test_workbench_i18n_keys_exist(qapp: QApplication):
    """All workbench i18n keys resolve."""
    from desktop_app.i18n import tr

    keys = [
        "nav.workbench",
        "nav.device_setup",
        "nav.site_capture",
        "nav.sample_review",
        "nav.model_iteration",
        "nav.hybrid_runtime",
        "nav.performance",
        "nav.delivery",
        "nav.maintenance",
        "workbench.header",
        "workbench.no_project",
        "workbench.no_project_hint",
        "workbench.card_device",
        "workbench.card_capture",
        "workbench.card_samples",
        "workbench.card_models",
        "workbench.project_missing",
        "workbench.spec_missing",
        "workbench.progress",
        "workbench.current_stage",
        "workbench.status_done",
        "workbench.status_current",
        "workbench.status_blocked",
        "workbench.status_pending",
        "workbench.step_purpose",
        "workbench.completion_criteria",
        "workbench.operation_steps",
        "workbench.missing_items",
        "workbench.enter_step",
        "workbench.blocker_label",
        "workbench.recommended_next",
        "workbench.hint_no_spec",
        "workbench.hint_no_device",
        "workbench.hint_no_capture",
        "workbench.hint_no_model",
    ]
    for key in keys:
        result = tr(key)
        assert result and result != key, f"Missing i18n key: {key}"


def test_workbench_step_i18n_keys_exist(qapp: QApplication):
    """All 8 step name/purpose/criteria/ops i18n keys resolve."""
    from desktop_app.i18n import tr

    steps = [
        "project_config",
        "device_config",
        "site_capture",
        "sample_review",
        "model_training",
        "hybrid_detection",
        "performance",
        "delivery",
    ]
    for step in steps:
        for prefix in ["workbench.step_", "workbench.purpose_", "workbench.criteria_", "workbench.ops_"]:
            key = f"{prefix}{step}"
            result = tr(key)
            assert result and result != key, f"Missing i18n key: {key}"


def test_sample_library_i18n_keys_exist(qapp: QApplication):
    """All sample_library i18n keys resolve."""
    from desktop_app.i18n import tr

    keys = [
        "nav.sample_library",
        "sample_library.search_placeholder",
        "sample_library.source_current",
        "sample_library.source_import",
        "sample_library.source_reference",
        "sample_library.col_image",
        "sample_library.col_label",
        "sample_library.col_source",
        "sample_library.col_source_project",
        "sample_library.col_review",
        "sample_library.counts",
        "sample_library.import_selected",
        "sample_library.reference_selected",
        "sample_library.select_entries",
        "sample_library.select_target_dir",
        "sample_library.import_result",
        "sample_library.reference_result",
    ]
    for key in keys:
        result = tr(key)
        assert result and result != key, f"Missing i18n key: {key}"


def test_defect_trace_i18n_keys_exist(qapp: QApplication):
    """nav.defect_trace i18n key resolves."""
    from desktop_app.i18n import tr

    assert tr("nav.defect_trace") != "nav.defect_trace"


def test_training_i18n_keys_exist(qapp: QApplication):
    """Phase G training i18n keys resolve."""
    from desktop_app.i18n import tr

    keys = [
        "training.task_type_label",
        "training.task_yolo",
        "training.task_anomaly",
        "training.task_classification",
        "training.task_yolo_field",
        "training.anomaly_param_group",
        "training.monitor_group",
        "training.monitor_idle",
        "training.monitor_no_job",
        "training.monitor_state",
        "training.monitor_job",
        "training.monitor_epoch",
        "training.monitor_message",
        "training.log_placeholder",
        "training.cls_placeholder",
        "training.anomaly_placeholder",
        "training.cls_not_implemented",
        "training.starting_anomaly",
        "training.starting_yolo_field",
        "training.starting_yolo",
        "training.training",
        "training.dataset_prefix_field",
        "training.dataset_prefix_anomaly",
        "training.monitor_stopping",
        "training.monitor_stop_requested",
        "training.monitor_completed",
        "training.monitor_stopped",
        "training.monitor_failed",
    ]
    for key in keys:
        result = tr(key)
        assert result and result != key, f"Missing i18n key: {key}"


def test_workflow_state_i18n_keys_exist(qapp: QApplication):
    """All workflow state i18n keys resolve."""
    from desktop_app.i18n import tr

    keys = [
        "workflow.state_new_project",
        "workflow.state_device_config_required",
        "workflow.state_device_configured",
        "workflow.state_initial_capture_ready",
        "workflow.state_initial_capture_done",
        "workflow.state_manual_triage_done",
        "workflow.state_unsupervised_ready",
        "workflow.state_unsupervised_trained",
        "workflow.state_assisted_capture_ready",
        "workflow.state_anomaly_review_pending",
        "workflow.state_yolo_annotation_ready",
        "workflow.state_yolo_training_ready",
        "workflow.state_yolo_trained",
        "workflow.state_hybrid_capture_ready",
        "workflow.state_iteration_active",
        "workflow.state_benchmark_ready",
        "workflow.state_acceptance_ready",
    ]
    for key in keys:
        result = tr(key)
        assert result and result != key, f"Missing i18n key: {key}"


# ── Sample library page ───────────────────────────────────────────────


def test_sample_library_page_creation(qapp: QApplication):
    """SampleLibraryPage can be created."""
    from desktop_app.pages.sample_library_page import SampleLibraryPage

    w = SampleLibraryPage()
    assert w is not None
    assert w._table is not None
    assert w._search_edit is not None
    assert w._source_filter is not None
    assert w._import_btn.text()
    assert w._reference_btn.text()
    w.close()


# ── Defect trace page ─────────────────────────────────────────────────


def test_defect_trace_page_creation(qapp: QApplication):
    """DefectTracePage can be created."""
    from desktop_app.pages.defect_trace_page import DefectTracePage

    w = DefectTracePage()
    assert w is not None
    w.close()


# ── Refresh text safety ─────────────────────────────────────────────────


def test_main_window_refresh_text_no_errors(qapp: QApplication):
    """_refresh_text runs without IndexError after convergence — no stale tab indices."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    # Should not raise IndexError or AttributeError
    w._refresh_text()
    w._refresh_text("zh")
    w.close()


# ── Full tab count structure ────────────────────────────────────────────


def test_main_window_all_container_tab_counts(qapp: QApplication):
    """Verify tab counts for all 9 containers after convergence."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    assert w._workbench_tabs.count() == 2
    assert w._device_tabs.count() == 2
    assert w._site_capture_tabs.count() == 2
    assert w._sample_review_tabs.count() == 5
    assert w._training_tabs.count() == 3
    assert w._hybrid_runtime_tabs.count() == 3
    assert w._performance_tabs.count() == 4
    assert w._delivery_tabs.count() == 2
    assert w._maintenance_tabs.count() == 4
    w.close()


# ── site_capture production tab index ────────────────────────────────────


def test_main_window_navigate_to_site_production_index(qapp: QApplication):
    """_on_navigate_to_site_production targets tab index 1 (still valid after convergence)."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    # Simulate production navigation
    w._on_navigate_to_site_production("baseline_capture", "")
    assert w._site_capture_tabs.currentIndex() == 1
    assert w._pages.currentWidget() is w._site_capture_container
    w.close()
