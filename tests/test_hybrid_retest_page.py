"""Tests for desktop_app/pages/hybrid_retest_page.py — Phase D."""
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
    """Temp SQLite DB with Phase D tables (schema v7)."""
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
    c = create_customer("HRP Test Co", "HRPT")
    p = create_project(c.customer_id, "HRP Test Proj")
    s = create_product_spec(p.project_id, "HRP Spec", material="铜", geometry_type="管")
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
    }


def _set_app_context(ctx: dict[str, str]) -> None:
    """Set AppContext to the given project/spec."""
    from desktop_app.app_context import AppContext
    app_ctx = AppContext.instance()
    app_ctx.set_current_customer(ctx["customer_id"], "HRP Test Co")
    app_ctx.set_current_project(ctx["project_id"], "HRP Test Proj")
    app_ctx.set_current_spec(ctx["spec_id"], "HRP Spec")


def _make_temp_image_dir(n_images: int = 3) -> str:
    """Create a temp directory with dummy PNG files."""
    d = tempfile.mkdtemp()
    for i in range(n_images):
        path = os.path.join(d, f"img_{i:03d}.png")
        with open(path, "wb") as f:
            f.write(b"fake_png")
    return d


def _register_yolo_model(project_id: str) -> str:
    """Register a dummy YOLO model version and return its version_id."""
    from core.model_version import create_model_version
    mv = create_model_version(
        project_id=project_id,
        model_name="test-yolo",
        model_type="yolo",
        model_path="/fake/yolo.pt",
    )
    return mv.model_id


def _patch_yolo_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid real Ultralytics/model loading in UI worker tests."""
    import desktop_app.workers.hybrid_retest_worker as worker_mod
    from core.hybrid_retest import FakeYoloRunner

    monkeypatch.setattr(
        worker_mod,
        "_build_yolo_runner",
        lambda model_id, confidence=0.01: FakeYoloRunner(),
    )


# ── Construction ────────────────────────────────────────────────────

def test_page_constructs(qapp: QApplication):
    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    assert w is not None
    w.close()


def test_page_has_config_controls(qapp: QApplication):
    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    assert w._yolo_combo is not None
    assert w._anomaly_combo is not None
    assert w._image_dir_edit is not None
    assert w._browse_dir_btn is not None
    assert w._yolo_thresh_spin is not None
    assert w._anomaly_thresh_spin is not None
    assert w._anomaly_high_spin is not None
    w.close()


def test_page_has_summary_labels(qapp: QApplication):
    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    assert w._total_label is not None
    assert w._ok_label is not None
    assert w._ng_label is not None
    assert w._suspect_label is not None
    assert w._unknown_label is not None
    assert w._needs_review_label is not None
    assert w._routed_label is not None
    w.close()


def test_page_has_results_table(qapp: QApplication):
    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    assert w._results_table is not None
    assert w._results_table.columnCount() == 7
    w.close()


def test_page_has_buttons_and_progress(qapp: QApplication):
    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    assert w._start_btn is not None
    assert w._stop_btn is not None
    assert w._refresh_models_btn is not None
    assert w._progress_bar is not None
    assert w._progress_label is not None
    assert w._log_view is not None
    w.close()


# ── Model combo ─────────────────────────────────────────────────────

def test_model_combo_empty_without_context(qapp: QApplication):
    """Without project context, model combo only has placeholder after refresh."""
    from desktop_app.app_context import AppContext
    AppContext.instance().clear_all()

    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    w._refresh_models()
    # Only placeholder item (select model + empty data)
    assert w._yolo_combo.count() == 1
    assert w._yolo_combo.currentData() == ""
    w.close()


def test_model_combo_populated_with_yolo_models(
    qapp: QApplication, ctx: dict[str, str],
):
    """With context and registered YOLO model, combo shows it."""
    _set_app_context(ctx)
    _register_yolo_model(ctx["project_id"])

    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    w._refresh_models()

    # Should have placeholder + 1 model
    assert w._yolo_combo.count() >= 2
    # Find the model entry
    found = False
    for i in range(w._yolo_combo.count()):
        if w._yolo_combo.itemData(i):
            found = True
            break
    assert found, "No YOLO model found in combo"
    w.close()


def test_anomaly_combo_has_no_model_placeholder(qapp: QApplication):
    """Anomaly model combo has '(No anomaly model)' placeholder."""
    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    assert w._anomaly_combo.count() >= 1
    assert w._anomaly_combo.itemData(0) == ""
    w.close()


def test_model_combo_populated_with_patchcore_models(
    qapp: QApplication, ctx: dict[str, str],
):
    """With context and registered PatchCore model, anomaly combo shows it."""
    from core.model_version import create_model_version

    _set_app_context(ctx)
    create_model_version(
        project_id=ctx["project_id"],
        model_name="PatchCore model",
        model_type="patchcore",
        model_path="D:/fake/patchcore_model.json",
    )

    from desktop_app.pages.hybrid_retest_page import HybridRetestPage

    w = HybridRetestPage()
    w._refresh_models()

    found = False
    for i in range(w._anomaly_combo.count()):
        if w._anomaly_combo.itemData(i):
            found = True
            break
    assert found, "No PatchCore model found in anomaly combo"
    w.close()


# ── Guard conditions ────────────────────────────────────────────────

def test_start_without_project_shows_info(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch,
):
    """Clicking Start without project shows info dialog."""
    from desktop_app.app_context import AppContext
    AppContext.instance().clear_all()

    import desktop_app.pages.hybrid_retest_page as hrp
    infos: list[str] = []
    monkeypatch.setattr(hrp.QMessageBox, "information", lambda *a, **kw: infos.append("info"))

    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    w._on_start()
    assert len(infos) >= 1
    w.close()


def test_start_without_yolo_model_shows_warning(
    qapp: QApplication, ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    """Clicking Start without YOLO model shows warning."""
    _set_app_context(ctx)

    import desktop_app.pages.hybrid_retest_page as hrp
    warns: list[str] = []
    monkeypatch.setattr(hrp.QMessageBox, "warning", lambda *a, **kw: warns.append("warn"))

    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    w._on_start()
    assert len(warns) >= 1
    w.close()


def test_start_with_invalid_dir_shows_warning(
    qapp: QApplication, ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    """Clicking Start with invalid image dir shows warning."""
    _set_app_context(ctx)
    _register_yolo_model(ctx["project_id"])

    import desktop_app.pages.hybrid_retest_page as hrp
    warns: list[str] = []
    monkeypatch.setattr(hrp.QMessageBox, "warning", lambda *a, **kw: warns.append("warn"))

    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    w._refresh_models()
    # Select the YOLO model
    for i in range(w._yolo_combo.count()):
        if w._yolo_combo.itemData(i):
            w._yolo_combo.setCurrentIndex(i)
            break
    w._image_dir_edit.setText("/nonexistent/dir")
    w._on_start()
    assert len(warns) >= 1
    w.close()


# ── Worker launch ───────────────────────────────────────────────────

def test_start_launches_worker(
    qapp: QApplication, ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    """With valid config, _on_start creates a worker."""
    _set_app_context(ctx)
    _register_yolo_model(ctx["project_id"])
    _patch_yolo_loader(monkeypatch)
    img_dir = _make_temp_image_dir(2)

    try:
        from desktop_app.pages.hybrid_retest_page import HybridRetestPage
        w = HybridRetestPage()
        w._refresh_models()
        # Select the YOLO model
        for i in range(w._yolo_combo.count()):
            if w._yolo_combo.itemData(i):
                w._yolo_combo.setCurrentIndex(i)
                break
        w._image_dir_edit.setText(img_dir)

        w._on_start()
        assert w._worker is not None
        assert w._worker.isRunning()

        # Wait for worker to finish
        w._worker.wait(10000)
        assert not w._worker.isRunning()
        w.close()
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


def test_start_disables_inputs(
    qapp: QApplication, ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    """After _on_start, inputs are disabled."""
    _set_app_context(ctx)
    _register_yolo_model(ctx["project_id"])
    _patch_yolo_loader(monkeypatch)
    img_dir = _make_temp_image_dir(1)

    try:
        from desktop_app.pages.hybrid_retest_page import HybridRetestPage
        w = HybridRetestPage()
        w._refresh_models()
        for i in range(w._yolo_combo.count()):
            if w._yolo_combo.itemData(i):
                w._yolo_combo.setCurrentIndex(i)
                break
        w._image_dir_edit.setText(img_dir)

        w._on_start()
        assert not w._start_btn.isEnabled()
        assert w._stop_btn.isEnabled()
        assert not w._yolo_combo.isEnabled()
        assert not w._image_dir_edit.isEnabled()

        w._worker.wait(10000)
        w.close()
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


def test_stop_button_disabled_initially(qapp: QApplication):
    """Stop button is disabled when page first created."""
    from desktop_app.pages.hybrid_retest_page import HybridRetestPage
    w = HybridRetestPage()
    assert not w._stop_btn.isEnabled()
    assert w._start_btn.isEnabled()
    w.close()


# ── Results table and summary ──────────────────────────────────────

def test_results_populated_after_run(
    qapp: QApplication, ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    """After a retest run, results table and summary are populated."""
    _set_app_context(ctx)
    _register_yolo_model(ctx["project_id"])
    _patch_yolo_loader(monkeypatch)
    img_dir = _make_temp_image_dir(2)

    try:
        from desktop_app.pages.hybrid_retest_page import HybridRetestPage
        w = HybridRetestPage()
        w._refresh_models()
        for i in range(w._yolo_combo.count()):
            if w._yolo_combo.itemData(i):
                w._yolo_combo.setCurrentIndex(i)
                break
        w._image_dir_edit.setText(img_dir)

        w._on_start()
        w._worker.wait(10000)
        # Process queued signal delivery
        qapp.processEvents()

        # Results table populated
        assert w._results_table.rowCount() == 2

        # Summary labels updated
        assert int(w._total_label.text()) == 2
        # At minimum we should have some non-zero values
        assert w._ok_label.text() != "" or w._ng_label.text() != "" or w._unknown_label.text() != ""

        w.close()
    finally:
        shutil.rmtree(img_dir, ignore_errors=True)


# ── Navigation ─────────────────────────────────────────────────────

def test_nav_item_registered(qapp: QApplication):
    from desktop_app.constants import NAV_ITEMS
    ids = [item["id"] for item in NAV_ITEMS]
    assert "hybrid_runtime" in ids
    hr_item = next(item for item in NAV_ITEMS if item["id"] == "hybrid_runtime")
    assert "label" in hr_item
    assert hr_item["icon"]


# ── i18n keys ──────────────────────────────────────────────────────

def test_i18n_keys_exist(qapp: QApplication):
    """All hybrid_retest i18n keys resolve."""
    from desktop_app.i18n import tr
    keys = [
        "hybrid_retest.config",
        "hybrid_retest.yolo_model",
        "hybrid_retest.anomaly_model",
        "hybrid_retest.no_anomaly_model",
        "hybrid_retest.image_dir",
        "hybrid_retest.image_dir_placeholder",
        "hybrid_retest.browse",
        "hybrid_retest.select_image_dir",
        "hybrid_retest.yolo_threshold",
        "hybrid_retest.anomaly_threshold",
        "hybrid_retest.anomaly_high_threshold",
        "hybrid_retest.start",
        "hybrid_retest.stop",
        "hybrid_retest.refresh_models",
        "hybrid_retest.idle",
        "hybrid_retest.stopping",
        "hybrid_retest.complete",
        "hybrid_retest.failed",
        "hybrid_retest.summary",
        "hybrid_retest.total",
        "hybrid_retest.ok",
        "hybrid_retest.ng",
        "hybrid_retest.suspect",
        "hybrid_retest.unknown",
        "hybrid_retest.needs_review",
        "hybrid_retest.routed",
        "hybrid_retest.col_image",
        "hybrid_retest.col_decision",
        "hybrid_retest.col_reason",
        "hybrid_retest.col_yolo_count",
        "hybrid_retest.col_anomaly_score",
        "hybrid_retest.col_runtime",
        "hybrid_retest.col_review_id",
        "hybrid_retest.log_placeholder",
        "hybrid_retest.select_model",
        "hybrid_retest.no_yolo_model",
        "hybrid_retest.invalid_image_dir",
        "nav.hybrid_retest",
    ]
    for key in keys:
        text = tr(key)
        assert text != key, f"Key '{key}' not translated: got '{text}'"


def test_i18n_keys_exist_in_chinese(qapp: QApplication):
    """All hybrid_retest keys have Chinese translations."""
    from desktop_app.i18n import I18nManager
    mgr = I18nManager.instance()
    current = mgr.language
    mgr.set_language("zh")
    try:
        from desktop_app.i18n import tr
        keys = ["hybrid_retest.start", "hybrid_retest.complete", "nav.hybrid_retest"]
        for key in keys:
            text = tr(key)
            assert text != key
            assert any('一' <= c <= '鿿' or c in '▶■（）' for c in text), (
                f"Key '{key}' has no Chinese chars: '{text}'"
            )
    finally:
        mgr.set_language(current)
