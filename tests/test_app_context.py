"""Tests for AppContext."""
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_app_context_singleton(qapp):
    from desktop_app.app_context import AppContext
    ctx1 = AppContext.instance()
    ctx2 = AppContext.instance()
    assert ctx1 is ctx2


def test_app_context_defaults(qapp):
    from desktop_app.app_context import AppContext
    ctx = AppContext.instance()
    assert ctx.current_customer_id == ""
    assert ctx.current_project_id == ""
    assert ctx.current_spec_id == ""


def test_set_customer_emits_signal(qapp):
    from desktop_app.app_context import AppContext
    ctx = AppContext.instance()
    signals_received = []
    ctx.customer_changed.connect(lambda cid: signals_received.append(cid))
    ctx.set_current_customer("CUST_001", "Test Corp")
    assert ctx.current_customer_id == "CUST_001"
    assert len(signals_received) == 1
    assert signals_received[0] == "CUST_001"


def test_set_project_emits_signal(qapp):
    from desktop_app.app_context import AppContext
    ctx = AppContext.instance()
    signals_received = []
    ctx.project_changed.connect(lambda pid: signals_received.append(pid))
    ctx.set_current_project("PROJ_001", "Test Project")
    assert signals_received[0] == "PROJ_001"


def test_clear_context(qapp):
    from desktop_app.app_context import AppContext
    ctx = AppContext.instance()
    ctx.set_current_customer("CUST_X", "X")
    ctx.set_current_project("PROJ_X", "X")
    ctx.clear_all()
    assert ctx.current_customer_id == ""
    assert ctx.current_project_id == ""
