"""Shared test fixtures for copper-defect-eval-tool.

Helper functions (make_detection_box, wait_for_condition) live in tests/__init__.py
so they can be imported as `from tests import make_detection_box, wait_for_condition`.
"""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def setup_db() -> Any:
    """Create a temp SQLite database for every test, auto-cleanup after."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    old_db_path = os.environ.get("COPPER_VISION_DB_PATH")
    os.environ["COPPER_VISION_DB_PATH"] = db_path
    import core.storage

    importlib.reload(core.storage)
    core.storage.init_db()
    from desktop_app.app_context import AppContext

    AppContext.instance().clear_all()
    try:
        yield
    finally:
        AppContext.instance().clear_all()
        if old_db_path is None:
            os.environ.pop("COPPER_VISION_DB_PATH", None)
        else:
            os.environ["COPPER_VISION_DB_PATH"] = old_db_path
        shutil.rmtree(tmp, ignore_errors=True)
