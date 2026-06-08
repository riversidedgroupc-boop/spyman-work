"""Tests for production runtime mode routing (Round 2 navigation convergence)."""

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


# -- mode_targets_site_capture -------------------------------------------------


def test_mode_targets_site_capture_constant():
    """All 6 RuntimeMode values are covered by the routing helper."""
    from core.runtime_mode import RuntimeMode, mode_targets_site_capture

    site_capture_modes = {RuntimeMode.SETUP_CAPTURE, RuntimeMode.BASELINE_CAPTURE}
    hybrid_modes = {
        RuntimeMode.ANOMALY_ASSISTED_CAPTURE,
        RuntimeMode.HYBRID_CAPTURE,
        RuntimeMode.STABLE_PRODUCTION,
        RuntimeMode.BENCHMARK_REPLAY,
    }

    for mode in site_capture_modes:
        assert mode_targets_site_capture(mode), (
            f"{mode} should route to site_capture"
        )

    for mode in hybrid_modes:
        assert not mode_targets_site_capture(mode), (
            f"{mode} should route to hybrid_runtime"
        )

    # Verify all 6 modes are covered
    all_modes = set(RuntimeMode)
    assert site_capture_modes | hybrid_modes == all_modes, (
        "All RuntimeMode values must be explicitly assigned to a container"
    )


# -- _open_runtime_page routing ------------------------------------------------


@pytest.mark.parametrize(
    "mode_value, expected_container_attr, expected_tab_index",
    [
        ("baseline_capture", "_site_capture_container", 1),
        ("setup_capture", "_site_capture_container", 1),
        ("stable_production", "_hybrid_runtime_container", 0),
        ("hybrid_capture", "_hybrid_runtime_container", 0),
        ("anomaly_assisted_capture", "_hybrid_runtime_container", 0),
        ("benchmark_replay", "_hybrid_runtime_container", 0),
    ],
)
def test_open_runtime_page_route_to_correct_container(
    qapp: QApplication,
    mode_value: str,
    expected_container_attr: str,
    expected_tab_index: int,
):
    """Each runtime mode routes to the correct container and tab."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    w._open_runtime_page(mode_value, "")

    expected_container = getattr(w, expected_container_attr)
    assert w._pages.currentWidget() is expected_container

    if expected_container_attr == "_site_capture_container":
        assert w._site_capture_tabs.currentIndex() == expected_tab_index
    else:
        assert w._hybrid_runtime_tabs.currentIndex() == expected_tab_index

    w.close()


def test_baseline_capture_sets_runtime_mode(qapp: QApplication):
    """BASELINE_CAPTURE sets the correct mode on site_production_page."""
    from core.runtime_mode import RuntimeMode
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    w._open_runtime_page("baseline_capture", "")

    assert w._site_production_page._runtime_mode == RuntimeMode.BASELINE_CAPTURE
    w.close()


def test_stable_production_sets_runtime_mode(qapp: QApplication):
    """STABLE_PRODUCTION sets the correct mode on hybrid_production_page."""
    from core.runtime_mode import RuntimeMode
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    w._open_runtime_page("stable_production", "")

    assert w._hybrid_production_page._runtime_mode == RuntimeMode.STABLE_PRODUCTION
    w.close()


def test_invalid_mode_falls_back_to_stable_production(qapp: QApplication):
    """Unknown mode_value defaults to STABLE_PRODUCTION -> hybrid_runtime."""
    from core.runtime_mode import RuntimeMode
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    w._open_runtime_page("nonexistent_mode", "")

    assert w._pages.currentWidget() is w._hybrid_runtime_container
    assert w._hybrid_runtime_tabs.currentIndex() == 0
    assert w._hybrid_production_page._runtime_mode == RuntimeMode.STABLE_PRODUCTION
    w.close()


# -- session_id linking --------------------------------------------------------


def test_session_id_links_to_site_production_page(qapp: QApplication):
    """Non-empty session_id calls link_capture_session on the right page."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    w._open_runtime_page("baseline_capture", "SESS_001")

    assert w._site_production_page._linked_session_id == "SESS_001"
    w.close()


def test_session_id_links_to_hybrid_production_page(qapp: QApplication):
    """Non-empty session_id links on hybrid page for production modes."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    w._open_runtime_page("stable_production", "SESS_002")

    assert w._hybrid_production_page._linked_session_id == "SESS_002"
    w.close()


def test_empty_session_id_does_not_alter_link(qapp: QApplication):
    """Empty session_id leaves the previous link intact."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    # Set an existing link
    w._hybrid_production_page._linked_session_id = "EXISTING"
    w._open_runtime_page("stable_production", "")

    assert w._hybrid_production_page._linked_session_id == "EXISTING"
    w.close()


# -- backward-compat signal wrappers -------------------------------------------


def test_navigate_to_production_signal_wrapper(qapp: QApplication):
    """The old navigate_to_production signal still works via thin wrapper."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    w._on_navigate_to_production("hybrid_capture", "SESS_003")

    assert w._pages.currentWidget() is w._hybrid_runtime_container
    assert w._hybrid_runtime_tabs.currentIndex() == 0
    assert w._hybrid_production_page._linked_session_id == "SESS_003"
    w.close()


def test_navigate_to_site_production_signal_wrapper(qapp: QApplication):
    """The old navigate_to_site_production signal still works via thin wrapper."""
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    w._on_navigate_to_site_production("setup_capture", "SESS_004")

    assert w._pages.currentWidget() is w._site_capture_container
    assert w._site_capture_tabs.currentIndex() == 1
    assert w._site_production_page._linked_session_id == "SESS_004"
    w.close()


# -- AppContext signals wired to MainWindow ------------------------------------


def test_app_context_navigate_to_production_connected(qapp: QApplication):
    """navigate_to_production signal is wired to the MainWindow handler."""
    from desktop_app.app_context import AppContext
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    app_ctx = AppContext.instance()

    # Emit the signal -- should NOT raise
    app_ctx.navigate_to_production.emit("stable_production", "")
    w.close()


def test_app_context_navigate_to_site_production_connected(qapp: QApplication):
    """navigate_to_site_production signal is wired to the MainWindow handler."""
    from desktop_app.app_context import AppContext
    from desktop_app.main_window import MainWindow

    w = MainWindow()
    app_ctx = AppContext.instance()

    # Emit the signal -- should NOT raise
    app_ctx.navigate_to_site_production.emit("baseline_capture", "")
    w.close()


# -- cpp_runtime_paths ---------------------------------------------------------


def test_cpp_runtime_paths_are_run_scoped(tmp_path):
    from core.runtime_mode import cpp_runtime_paths

    state_path, config_path = cpp_runtime_paths(tmp_path, "run_001")

    assert state_path == tmp_path / "runtime" / "run_001" / "state.json"
    assert config_path == tmp_path / "runtime" / "run_001" / "config.json"


def test_cpp_runtime_paths_unique_per_run(tmp_path):
    from core.runtime_mode import cpp_runtime_paths

    s1, c1 = cpp_runtime_paths(tmp_path, "run_A")
    s2, c2 = cpp_runtime_paths(tmp_path, "run_B")

    assert s1 != s2
    assert c1 != c2


# -- ProductionRunPage runtime backend selection ---------------------------------


def test_production_run_page_defaults_to_python_runtime_backend(qapp):
    """By default (no env var), backend_name is 'python_runtime'."""
    from core.runtime_mode import RuntimeMode
    from desktop_app.pages.production_run_page import ProductionRunPage

    page = ProductionRunPage(runtime_mode=RuntimeMode.STABLE_PRODUCTION)
    assert page._runtime_backend_name == "python_runtime"
    assert page._runtime_backend is None
    page.close()


def test_production_run_page_backend_name_from_env(qapp):
    """CX_RUNTIME_BACKEND env var is read at init time."""
    from core.runtime_mode import RuntimeMode
    from desktop_app.pages.production_run_page import ProductionRunPage

    os.environ["CX_RUNTIME_BACKEND"] = "fake_cpp_runtime"
    try:
        page = ProductionRunPage(runtime_mode=RuntimeMode.STABLE_PRODUCTION)
        assert page._runtime_backend_name == "fake_cpp_runtime"
        assert page._runtime_backend is None  # backend instantiated lazily in _start
        page.close()
    finally:
        os.environ.pop("CX_RUNTIME_BACKEND", None)


def test_production_run_page_backend_error_blocks_pipeline_start(qapp, monkeypatch):
    """Runtime backend error must stop startup before acquisition/timer starts."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.runtime_contracts import RuntimeStatus
    from core.runtime_mode import RuntimeMode
    from desktop_app.app_context import AppContext
    import desktop_app.pages.production_run_page as page_mod
    from desktop_app.pages.production_run_page import ProductionRunPage

    customer = create_customer("Runtime Backend Error Co", "RBE")
    project = create_project(customer.customer_id, "Runtime Backend Error Project")
    spec = create_product_spec(
        project.project_id,
        "Runtime Backend Error Spec",
        material="copper",
        geometry_type="tube",
        camera_count=1,
    )
    ctx = AppContext.instance()
    ctx.set_current_customer(customer.customer_id, customer.customer_name)
    ctx.set_current_project(project.project_id, project.project_name)
    ctx.set_current_spec(spec.spec_id, spec.product_name)

    class ErrorBackend:
        start_called = False

        def start(self, config):
            self.start_called = True
            return RuntimeStatus(
                state="error",
                error_code="BACKEND_START_FAILED",
                error_message="blocked",
            )

        def stop(self):
            return RuntimeStatus(state="stopped")

        def status(self):
            return RuntimeStatus(state="stopped")

    backend = ErrorBackend()

    def fake_create_backend(*args, **kwargs):
        return backend

    class SpyAcquisition:
        start_called = False

        def set_encoder(self, encoder):
            self.encoder = encoder

        def set_sampling_controller(self, sampling_controller):
            self.sampling_controller = sampling_controller

        def start(self):
            self.start_called = True

        def stop(self):
            pass

        def get_status(self):
            return []

    monkeypatch.setattr(page_mod, "create_backend", fake_create_backend)
    monkeypatch.setattr(
        page_mod.QMessageBox,
        "warning",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        page_mod.QMessageBox,
        "critical",
        lambda *args, **kwargs: None,
    )

    os.environ["CX_RUNTIME_BACKEND"] = "fake_cpp_runtime"
    try:
        page = ProductionRunPage(runtime_mode=RuntimeMode.BASELINE_CAPTURE)
        spy_acq = SpyAcquisition()
        page._acq = spy_acq
        page._inference.stop = lambda: None
        page._connect_area_scan = lambda camera_id, cfg: None

        page._start()

        assert backend.start_called
        assert not spy_acq.start_called
        assert not page._timer.isActive()
        page.close()
    finally:
        os.environ.pop("CX_RUNTIME_BACKEND", None)


# -- RuntimeConfig builder tests ------------------------------------------------


def test_build_runtime_config_maps_camera_configs(qapp, monkeypatch):
    """_build_runtime_config returns RuntimeConfig with proper camera mapping."""
    from core.camera_config import CameraConfig
    from core.runtime_contracts import RuntimeConfig
    from core.runtime_mode import RuntimeMode
    from desktop_app.pages.production_run_page import ProductionRunPage

    page = ProductionRunPage(runtime_mode=RuntimeMode.STABLE_PRODUCTION)

    # Build fake camera configs
    cfgs = {
        "cam1": CameraConfig(
            config_id="c1",
            spec_id="s1",
            camera_index=1,
            adapter_type="line_scan",
            serial_number="SN001",
            resolution_width=2048,
            resolution_height=1,
            image_block_height=2048,
        ),
        "cam2": CameraConfig(
            config_id="c2",
            spec_id="s1",
            camera_index=2,
            adapter_type="hikrobot_area_scan",
            serial_number="SN002",
            ip_address="192.168.1.100",
            resolution_width=1920,
            resolution_height=1080,
        ),
    }

    # Monkeypatch get_model_version to avoid DB dependency
    class _FakeModel:
        model_path = "/models/yolo.pt"

    monkeypatch.setattr(
        "desktop_app.pages.production_run_page.get_model_version",
        lambda model_id: _FakeModel() if model_id else None,
    )

    config = page._build_runtime_config(
        run_id="run_001",
        project_id="proj_001",
        spec_id="spec_001",
        camera_configs=cfgs,
        yolo_model_id="yolo_1",
        anomaly_model_id="",
        output_dir="/tmp/output",
    )

    assert isinstance(config, RuntimeConfig)
    assert config.run_id == "run_001"
    assert config.project_id == "proj_001"
    assert config.spec_id == "spec_001"
    assert config.backend == "python_runtime"
    assert config.output_dir == "/tmp/output"
    assert config.confidence == 0.5
    assert config.iou == 0.45

    assert len(config.cameras) == 2

    cam1 = config.cameras[0]
    assert cam1.camera_id == "cam1"
    assert cam1.camera_type == "line_scan"
    assert cam1.serial_number == "SN001"
    assert cam1.width == 2048
    assert cam1.block_height == 2048

    cam2 = config.cameras[1]
    assert cam2.camera_id == "cam2"
    assert cam2.camera_type == "area_scan"
    assert cam2.ip_address == "192.168.1.100"
    assert cam2.width == 1920
    assert cam2.height == 1080

    assert config.model_artifacts == {"yolo": "/models/yolo.pt"}

    page.close()


def test_build_runtime_config_includes_model_artifacts(qapp, monkeypatch):
    """_build_runtime_config includes both yolo and anomaly model paths."""
    from core.camera_config import CameraConfig
    from core.runtime_contracts import RuntimeConfig
    from core.runtime_mode import RuntimeMode
    from desktop_app.pages.production_run_page import ProductionRunPage

    page = ProductionRunPage(runtime_mode=RuntimeMode.STABLE_PRODUCTION)

    class _YoloModel:
        model_path = "/models/yolo_v2.pt"

    class _AnomalyModel:
        model_path = "/models/patchcore.pt"

    def fake_get_model_version(model_id):
        if model_id == "yolo_1":
            return _YoloModel()
        if model_id == "anom_1":
            return _AnomalyModel()
        return None

    monkeypatch.setattr(
        "desktop_app.pages.production_run_page.get_model_version",
        fake_get_model_version,
    )

    cfgs = {
        "cam1": CameraConfig(
            config_id="c1",
            spec_id="s1",
            camera_index=1,
            adapter_type="folder_watcher",
        ),
    }

    config = page._build_runtime_config(
        run_id="run_002",
        project_id="proj_002",
        spec_id="spec_002",
        camera_configs=cfgs,
        yolo_model_id="yolo_1",
        anomaly_model_id="anom_1",
        output_dir="/tmp/out2",
    )

    assert config.model_artifacts == {
        "yolo": "/models/yolo_v2.pt",
        "anomaly": "/models/patchcore.pt",
    }

    page.close()


# -- Spy classes for backend/pipeline behavior tests ----------------------------


class _SpyBackend:
    """Test spy: records calls to a RuntimeBackend."""

    def __init__(self, start_status=None):
        from core.runtime_contracts import RuntimeStatus

        self.start_called = False
        self.stop_called = False
        self.started_config = None
        self._start_status = start_status or RuntimeStatus(state="running")

    def start(self, config):
        self.start_called = True
        self.started_config = config
        return self._start_status

    def stop(self):
        self.stop_called = True
        from core.runtime_contracts import RuntimeStatus

        return RuntimeStatus(state="stopped")

    def status(self):
        from core.runtime_contracts import RuntimeStatus

        return RuntimeStatus(state="running")


class _SpyAcquisition:
    """Test spy: records calls to AcquisitionPipeline."""

    def __init__(self):
        self.start_called = False
        self.stop_called = False
        self.encoder_set = False
        self.sampling_set = False

    def start(self):
        self.start_called = True

    def stop(self):
        self.stop_called = True

    def set_encoder(self, encoder):
        self.encoder_set = True

    def set_sampling_controller(self, sc):
        self.sampling_set = True

    def add_camera(self, *args, **kwargs):
        pass

    def add_line_scan_camera(self, *args, **kwargs):
        pass

    def get_buffer(self):
        class _Buf:
            def get_per_camera(self, cid):
                return None
        return _Buf()

    def get_status(self):
        return []


# -- Behavior tests: python vs external backend routing -------------------------


def test_python_runtime_start_uses_python_pipeline(qapp, monkeypatch):
    """Default python_runtime backend starts acquisition pipeline."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.runtime_mode import RuntimeMode
    from desktop_app.app_context import AppContext
    import desktop_app.pages.production_run_page as page_mod
    from desktop_app.pages.production_run_page import ProductionRunPage

    customer = create_customer("Python Start Co", "PSC")
    project = create_project(customer.customer_id, "Python Start Project")
    spec = create_product_spec(
        project.project_id, "Python Start Spec",
        material="copper", geometry_type="tube", camera_count=1,
    )
    ctx = AppContext.instance()
    ctx.set_current_customer(customer.customer_id, customer.customer_name)
    ctx.set_current_project(project.project_id, project.project_name)
    ctx.set_current_spec(spec.spec_id, spec.product_name)

    monkeypatch.setattr(page_mod.QMessageBox, "information", lambda *a, **kw: None)
    monkeypatch.setattr(page_mod.QMessageBox, "warning", lambda *a, **kw: None)
    monkeypatch.setattr(page_mod.QMessageBox, "critical", lambda *a, **kw: None)

    old = os.environ.pop("CX_RUNTIME_BACKEND", None)
    try:
        page = ProductionRunPage(runtime_mode=RuntimeMode.BASELINE_CAPTURE)
        spy_acq = _SpyAcquisition()
        page._acq = spy_acq
        page._inference.stop = lambda: None
        page._connect_area_scan = lambda camera_id, cfg: None

        page._start()

        assert spy_acq.start_called, "python_runtime should start acquisition"
        assert page._runtime_backend is None or not isinstance(page._runtime_backend, _SpyBackend)
        page.close()
    finally:
        if old is not None:
            os.environ["CX_RUNTIME_BACKEND"] = old


def test_external_runtime_start_does_not_start_python_pipeline(qapp, monkeypatch):
    """External backend (fake_cpp_runtime) skips ALL Python hardware/model init."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.runtime_contracts import RuntimeStatus
    from core.runtime_mode import RuntimeMode
    from desktop_app.app_context import AppContext
    import desktop_app.pages.production_run_page as page_mod
    from desktop_app.pages.production_run_page import ProductionRunPage

    customer = create_customer("Ext Start Co", "ESC")
    project = create_project(customer.customer_id, "Ext Start Project")
    spec = create_product_spec(
        project.project_id, "Ext Start Spec",
        material="copper", geometry_type="tube", camera_count=1,
    )
    ctx = AppContext.instance()
    ctx.set_current_customer(customer.customer_id, customer.customer_name)
    ctx.set_current_project(project.project_id, project.project_name)
    ctx.set_current_spec(spec.spec_id, spec.product_name)

    monkeypatch.setattr(page_mod.QMessageBox, "information", lambda *a, **kw: None)
    monkeypatch.setattr(page_mod.QMessageBox, "warning", lambda *a, **kw: None)
    monkeypatch.setattr(page_mod.QMessageBox, "critical", lambda *a, **kw: None)

    spy_backend = _SpyBackend(RuntimeStatus(state="running"))
    monkeypatch.setattr(page_mod, "create_backend", lambda *a, **kw: spy_backend)

    # Track whether _connect_area_scan or _connect_line_scan are called
    connect_area_called = False
    connect_line_called = False

    os.environ["CX_RUNTIME_BACKEND"] = "fake_cpp_runtime"
    try:
        page = ProductionRunPage(runtime_mode=RuntimeMode.BASELINE_CAPTURE)
        spy_acq = _SpyAcquisition()
        page._acq = spy_acq

        # Replace connect methods with spies (NOT no-op lambdas) so we
        # can assert they were never reached.
        def _spy_connect_area(camera_id, cfg):
            nonlocal connect_area_called
            connect_area_called = True
        def _spy_connect_line(camera_id, cfg):
            nonlocal connect_line_called
            connect_line_called = True
        page._connect_area_scan = _spy_connect_area
        page._connect_line_scan = _spy_connect_line

        page._start()

        assert spy_backend.start_called, "external backend should be started"
        assert not spy_acq.start_called, (
            "external backend must NOT start Python acquisition"
        )
        assert not spy_acq.encoder_set, (
            "external backend must NOT set Python encoder"
        )
        assert not spy_acq.sampling_set, (
            "external backend must NOT set Python sampling controller"
        )
        assert not connect_area_called, (
            "external backend must NOT call _connect_area_scan"
        )
        assert not connect_line_called, (
            "external backend must NOT call _connect_line_scan"
        )
        page.close()
    finally:
        os.environ.pop("CX_RUNTIME_BACKEND", None)


def test_external_runtime_stop_does_not_stop_python_pipeline(qapp, monkeypatch):
    """External backend stop() does NOT call Python pipeline stop."""
    from core.runtime_contracts import RuntimeStatus
    from core.runtime_mode import RuntimeMode
    import desktop_app.pages.production_run_page as page_mod
    from desktop_app.pages.production_run_page import ProductionRunPage

    monkeypatch.setattr(page_mod.QMessageBox, "warning", lambda *a, **kw: None)
    monkeypatch.setattr(page_mod.QMessageBox, "critical", lambda *a, **kw: None)
    monkeypatch.setattr(page_mod.QMessageBox, "information", lambda *a, **kw: None)

    spy_backend = _SpyBackend(RuntimeStatus(state="running"))
    spy_acq = _SpyAcquisition()

    os.environ["CX_RUNTIME_BACKEND"] = "fake_cpp_runtime"
    try:
        page = ProductionRunPage(runtime_mode=RuntimeMode.STABLE_PRODUCTION)
        page._runtime_backend = spy_backend
        page._acq = spy_acq
        page._inference.stop = lambda: None

        # Simulate external backend stop
        page._stop()

        assert spy_backend.stop_called, "external backend stop() should be called"
        assert not spy_acq.stop_called, (
            "external backend must NOT stop Python acquisition"
        )
        page.close()
    finally:
        os.environ.pop("CX_RUNTIME_BACKEND", None)


def test_external_runtime_refresh_uses_backend_status(qapp, monkeypatch):
    """External runtime _refresh_display() polls backend.status(), not Python pipeline."""
    from core.runtime_contracts import RuntimeStatus
    from core.runtime_mode import RuntimeMode
    from desktop_app.pages.production_run_page import ProductionRunPage

    class _RefreshBackend:
        def __init__(self):
            self.status_called = False

        def start(self, config):
            return RuntimeStatus(state="running")

        def stop(self):
            return RuntimeStatus(state="stopped")

        def status(self):
            self.status_called = True
            return RuntimeStatus(
                state="running",
                uptime_ms=1234,
                fps_by_camera={"cam1": 25.5},
                queue_size=2,
                dropped_frames=1,
                ng_count=3,
            )

    class _RaisingAcq:
        def get_status(self):
            raise AssertionError("external runtime must not call _acq.get_status()")

        def set_encoder(self, *a, **kw):
            pass

        def set_sampling_controller(self, *a, **kw):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def get_buffer(self):
            class _Buf:
                def get_per_camera(self, cid):
                    return None
            return _Buf()

        def add_camera(self, *a, **kw):
            pass

        def add_line_scan_camera(self, *a, **kw):
            pass

    from desktop_app.app_context import AppContext
    AppContext.instance()

    monkeypatch.setattr(
        "desktop_app.pages.production_run_page.QMessageBox",
        lambda *a, **kw: None,
    )

    os.environ["CX_RUNTIME_BACKEND"] = "fake_cpp_runtime"
    try:
        page = ProductionRunPage(runtime_mode=RuntimeMode.BASELINE_CAPTURE)
        backend = _RefreshBackend()
        page._runtime_backend = backend
        page._acq = _RaisingAcq()
        # Fake a camera status label for the status display
        from PySide6.QtWidgets import QLabel as _QLabel
        page._cam_status_labels["cam1"] = _QLabel("")

        page._refresh_display()

        assert backend.status_called, "backend.status() must be called for external runtime refresh"
        assert "cam1" in page._cam_status_labels["cam1"].text()
        assert "25.5" in page._cam_status_labels["cam1"].text()
        page.close()
    finally:
        os.environ.pop("CX_RUNTIME_BACKEND", None)
