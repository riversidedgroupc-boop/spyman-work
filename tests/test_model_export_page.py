"""Tests for desktop_app/pages/model_export_page.py — Phase E."""
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
    """Temp SQLite DB with Phase E tables."""
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

    c = create_customer("MEP Test Co", "MEPC")
    p = create_project(c.customer_id, "MEP Test Proj")
    s = create_product_spec(p.project_id, "MEP Spec", material="铜", geometry_type="管")
    return {
        "customer_id": c.customer_id,
        "project_id": p.project_id,
        "spec_id": s.spec_id,
    }


def _set_app_context(ctx: dict[str, str]) -> None:
    """Set AppContext to the given project/spec."""
    from desktop_app.app_context import AppContext

    app_ctx = AppContext.instance()
    app_ctx.set_current_customer(ctx["customer_id"], "MEP Test Co")
    app_ctx.set_current_project(ctx["project_id"], "MEP Test Proj")
    app_ctx.set_current_spec(ctx["spec_id"], "MEP Spec")


def _register_yolo_model(project_id: str) -> str:
    """Register a dummy YOLO model version and return its model_id."""
    from core.model_version import create_model_version

    mv = create_model_version(
        project_id=project_id,
        model_name="mep-yolo",
        model_type="yolo",
        model_path="/fake/yolo.pt",
    )
    return mv.model_id


def _patch_env(monkeypatch: pytest.MonkeyPatch,
               tensorrt_available: bool = False) -> None:
    """Patch detect_export_environment to return controlled environment."""
    from core.export_environment import ExportEnvironment

    env = ExportEnvironment(
        gpu_name="NVIDIA GTX 1080",
        cuda_available=True,
        cuda_version="11.8",
        torch_version="2.2.0",
        ultralytics_version="8.1.0",
        tensorrt_available=tensorrt_available,
        tensorrt_version="10.0.1" if tensorrt_available else "",
    )
    import desktop_app.pages.model_export_page as mep_mod

    monkeypatch.setattr(mep_mod, "detect_export_environment", lambda: env)
    return env


def _patch_worker(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Patch ModelExportWorker.run to complete immediately."""
    finished_msgs: list[str] = []

    class _FakeWorker:
        finished = __import__("PySide6.QtCore").Signal(object)
        progress = __import__("PySide6.QtCore").Signal(str)
        error = __import__("PySide6.QtCore").Signal(str)

        def __init__(self, task_type: str, config: dict, parent=None) -> None:
            self.task_type = task_type
            self.config = config

        def start(self) -> None:
            from core.model_export import ModelExportArtifact

            result = ModelExportArtifact(
                export_id="EXP_fake_001",
                project_id=self.config.get("project_id", ""),
                source_model_id=self.config.get("model_id", ""),
                backend=self.config.get("backend", "onnx"),
                precision=self.config.get("precision", "fp32"),
                artifact_path="/tmp/test.onnx",
                status="completed",
            )
            finished_msgs.append("done")
            self.finished.emit(result)

        def cancel(self) -> None:
            pass

        def isRunning(self) -> bool:
            return False

        def wait(self, timeout: int = 0) -> bool:
            return True

    import desktop_app.pages.model_export_page as mep_mod

    monkeypatch.setattr(mep_mod, "ModelExportWorker", _FakeWorker)
    return finished_msgs


# ── Construction ────────────────────────────────────────────────────

def test_page_constructs(qapp: QApplication):
    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    assert w is not None
    w.close()


def test_env_info_displayed(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    _patch_env(monkeypatch, tensorrt_available=False)

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    assert w._gpu_label.text() == "NVIDIA GTX 1080"
    assert w._cuda_label.text() == "11.8"
    assert w._torch_label.text() == "2.2.0"
    assert "8.1.0" in w._ultralytics_label.text()
    assert "Not Available" in w._tensorrt_label.text() or "不可用" in w._tensorrt_label.text()
    w.close()


def test_page_has_config_controls(qapp: QApplication):
    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    assert w._model_combo is not None
    assert w._refresh_model_btn is not None
    assert w._onnx_radio is not None
    assert w._tensorrt_radio is not None
    assert w._fp32_radio is not None
    assert w._fp16_radio is not None
    assert w._int8_radio is not None
    assert w._imgsz_spin is not None
    assert w._workspace_spin is not None
    assert w._calib_dir_edit is not None
    assert w._browse_calib_btn is not None
    w.close()


def test_page_has_action_buttons(qapp: QApplication):
    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    assert w._export_onnx_btn is not None
    assert w._export_trt_btn is not None
    assert w._benchmark_btn is not None
    assert w._deploy_btn is not None
    assert w._stop_btn is not None
    assert w._progress_bar is not None
    assert w._status_label is not None
    w.close()


def test_page_has_artifacts_table(qapp: QApplication):
    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    assert w._artifacts_table is not None
    assert w._artifacts_table.columnCount() == 7
    w.close()


# ── Model combo ─────────────────────────────────────────────────────

def test_model_combo_empty_without_context(qapp: QApplication):
    from desktop_app.app_context import AppContext

    AppContext.instance().clear_all()

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    w._refresh_models()
    assert w._model_combo.count() == 1
    assert w._model_combo.currentData() == ""
    w.close()


def test_model_combo_populated_with_yolo_models(
    qapp: QApplication, ctx: dict[str, str],
):
    _set_app_context(ctx)
    _register_yolo_model(ctx["project_id"])

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    w._refresh_models()
    assert w._model_combo.count() >= 2
    found = False
    for i in range(w._model_combo.count()):
        if w._model_combo.itemData(i):
            found = True
            break
    assert found, "No YOLO model found in combo"
    w.close()


# ── Guard conditions ────────────────────────────────────────────────

def test_buttons_disabled_without_project(qapp: QApplication):
    from desktop_app.app_context import AppContext

    AppContext.instance().clear_all()

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    assert not w._export_onnx_btn.isEnabled()
    assert not w._export_trt_btn.isEnabled()
    assert not w._model_combo.isEnabled()
    w.close()


def test_buttons_disabled_without_model(
    qapp: QApplication, ctx: dict[str, str],
):
    _set_app_context(ctx)

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    w._refresh_models()
    # Config controls enabled, but export buttons disabled (no model selected)
    assert w._model_combo.isEnabled()
    assert not w._export_onnx_btn.isEnabled()
    assert not w._export_trt_btn.isEnabled()
    w.close()


def test_tensorrt_disabled_when_unavailable(
    qapp: QApplication, ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    _patch_env(monkeypatch, tensorrt_available=False)
    _set_app_context(ctx)

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    assert w._onnx_radio.isChecked()
    assert not w._tensorrt_radio.isEnabled()
    w.close()


def test_int8_disabled_without_calibration(
    qapp: QApplication, ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    _patch_env(monkeypatch, tensorrt_available=True)
    _set_app_context(ctx)
    _register_yolo_model(ctx["project_id"])

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    w._refresh_models()
    for i in range(w._model_combo.count()):
        if w._model_combo.itemData(i):
            w._model_combo.setCurrentIndex(i)
            break

    # Select INT8
    w._int8_radio.setChecked(True)
    w._on_precision_changed()
    assert w._calib_dir_edit.isEnabled()
    assert not w._export_onnx_btn.isEnabled()
    assert not w._export_trt_btn.isEnabled()
    w.close()


def test_refresh_models_populates_combo(
    qapp: QApplication, ctx: dict[str, str],
):
    _set_app_context(ctx)
    _register_yolo_model(ctx["project_id"])

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    assert any(
        w._model_combo.itemData(i) for i in range(w._model_combo.count())
    )
    w.close()


# ── Artifact table ─────────────────────────────────────────────────

def test_artifact_table_updated(
    qapp: QApplication, ctx: dict[str, str],
):
    _set_app_context(ctx)
    model_id = _register_yolo_model(ctx["project_id"])

    from core.model_export import create_export_artifact

    create_export_artifact(
        project_id=ctx["project_id"],
        source_model_id=model_id,
        backend="onnx",
        precision="fp32",
    )

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    w._refresh_artifacts()
    assert w._artifacts_table.rowCount() >= 1
    found = False
    for r in range(w._artifacts_table.rowCount()):
        if w._artifacts_table.item(r, 1).text() == "onnx":
            found = True
            break
    assert found
    w.close()


# ── Export action guard dialogs ────────────────────────────────────

def test_export_without_project_shows_info(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch,
):
    from desktop_app.app_context import AppContext

    AppContext.instance().clear_all()

    import desktop_app.pages.model_export_page as mep

    infos: list[str] = []
    monkeypatch.setattr(mep.QMessageBox, "information", lambda *a, **kw: infos.append("info"))

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    w._on_export("export_onnx")
    assert len(infos) == 1
    w.close()


def test_export_without_model_shows_warning(
    qapp: QApplication, ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    _set_app_context(ctx)

    import desktop_app.pages.model_export_page as mep

    warns: list[str] = []
    monkeypatch.setattr(mep.QMessageBox, "warning", lambda *a, **kw: warns.append("warn"))

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    w._refresh_models()
    w._on_export("export_onnx")
    assert len(warns) == 1
    w.close()


# ── Worker launch ──────────────────────────────────────────────────

def test_start_launches_worker(
    qapp: QApplication, ctx: dict[str, str], monkeypatch: pytest.MonkeyPatch,
):
    _patch_env(monkeypatch, tensorrt_available=True)
    _set_app_context(ctx)
    _register_yolo_model(ctx["project_id"])

    import desktop_app.pages.model_export_page as mep

    class _Tracker:
        started = False

    class _FakeSignal:
        """A simple callable that records connections."""
        def connect(self, fn):
            pass

        def emit(self, *args):
            pass

    class _FakeWorker:
        finished = _FakeSignal()
        progress = _FakeSignal()
        error = _FakeSignal()

        def __init__(self, task_type: str, config: dict, parent=None) -> None:
            self.task_type = task_type
            self.config = config

        def start(self) -> None:
            _Tracker.started = True

        def cancel(self) -> None:
            pass

        def isRunning(self) -> bool:
            return not _Tracker.started

        def wait(self, timeout: int = 0) -> bool:
            return True

    monkeypatch.setattr(mep, "ModelExportWorker", _FakeWorker)

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    w._refresh_models()
    for i in range(w._model_combo.count()):
        if w._model_combo.itemData(i):
            w._model_combo.setCurrentIndex(i)
            break
    w._on_export("export_onnx")
    assert _Tracker.started
    w.close()


def test_benchmark_shows_coming_soon(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch,
):
    import desktop_app.pages.model_export_page as mep

    infos: list[str] = []
    monkeypatch.setattr(mep.QMessageBox, "information", lambda *a, **kw: infos.append("info"))

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    w._on_benchmark()
    assert len(infos) == 1
    w.close()


def test_deploy_shows_coming_soon(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch,
):
    import desktop_app.pages.model_export_page as mep

    infos: list[str] = []
    monkeypatch.setattr(mep.QMessageBox, "information", lambda *a, **kw: infos.append("info"))

    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    w._on_deploy()
    assert len(infos) == 1
    w.close()


# ── i18n keys ──────────────────────────────────────────────────────

def test_i18n_keys_exist(qapp: QApplication):
    """All export i18n keys resolve."""
    from desktop_app.i18n import tr

    keys = [
        "export.title",
        "export.environment",
        "export.gpu",
        "export.cuda",
        "export.pytorch",
        "export.ultralytics",
        "export.tensorrt",
        "export.not_available",
        "export.config",
        "export.model_version",
        "export.backend",
        "export.precision",
        "export.image_size",
        "export.workspace_gb",
        "export.calibration_dir",
        "export.browse",
        "export.export_onnx",
        "export.export_tensorrt",
        "export.benchmark",
        "export.generate_package",
        "export.artifacts",
        "export.col_id",
        "export.col_backend",
        "export.col_precision",
        "export.col_status",
        "export.col_path",
        "export.col_error",
        "export.col_device",
        "export.status_created",
        "export.status_running",
        "export.status_completed",
        "export.status_failed",
        "export.status_invalid",
        "export.no_model",
        "export.no_project",
        "export.tensorrt_unavailable",
        "export.int8_needs_calibration",
        "export.refresh",
        "export.coming_soon",
        "export.select_calibration_dir",
        "export.stop",
        "export.browse_calibration",
    ]
    for key in keys:
        text = tr(key)
        assert text != key, f"Key '{key}' not translated: got '{text}'"


def test_i18n_keys_exist_in_chinese(qapp: QApplication):
    """All export keys have Chinese translations with Chinese chars."""
    from desktop_app.i18n import I18nManager, tr

    mgr = I18nManager.instance()
    current = mgr.language
    mgr.set_language("zh")
    try:
        keys = [
            "export.title",
            "export.environment",
            "export.export_onnx",
            "export.export_tensorrt",
            "export.status_completed",
        ]
        for key in keys:
            text = tr(key)
            assert text != key
            assert any("一" <= c <= "鿿" for c in text), (
                f"Key '{key}' has no Chinese chars: '{text}'"
            )
    finally:
        mgr.set_language(current)


def test_status_display_known(qapp: QApplication):
    """_status_display translates known statuses."""
    from desktop_app.pages.model_export_page import ModelExportPage

    w = ModelExportPage()
    assert "completed" not in w._status_display("completed").lower() or (
        "已完成" in w._status_display("completed")
    )

    # Verify known statuses resolve
    for s in ["created", "running", "completed", "failed", "invalid"]:
        result = w._status_display(s)
        assert result != s, f"Status '{s}' not translated"
    w.close()
