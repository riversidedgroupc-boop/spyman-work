"""Tests for storage layer."""
import os
import tempfile

import pytest


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    os.environ["COPPER_VISION_DB_PATH"] = db_path
    import core.storage
    import importlib
    importlib.reload(core.storage)
    core.storage.init_db()
    yield db_path
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


def test_init_db_creates_tables(temp_db):
    from core.storage import get_connection
    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [t[0] for t in tables]
    assert "customers" in table_names
    assert "projects" in table_names
    assert "product_specs" in table_names
    conn.close()


def test_insert_and_fetch_one(temp_db):
    from core.storage import insert, fetch_one
    insert("customers", {
        "customer_id": "CUST_001",
        "customer_name": "Test Corp",
        "short_name": "TC",
    })
    row = fetch_one("customers", "CUST_001")
    assert row is not None
    assert row["customer_name"] == "Test Corp"


def test_fetch_all(temp_db):
    from core.storage import insert, fetch_all
    insert("customers", {"customer_id": "C_1", "customer_name": "A", "short_name": "A"})
    insert("customers", {"customer_id": "C_2", "customer_name": "B", "short_name": "B"})
    rows = fetch_all("customers")
    assert len(rows) == 2


def test_update(temp_db):
    from core.storage import insert, update, fetch_one
    insert("customers", {"customer_id": "C_1", "customer_name": "A", "short_name": "A"})
    update("customers", "C_1", {"customer_name": "Updated"})
    row = fetch_one("customers", "C_1")
    assert row["customer_name"] == "Updated"


def test_delete(temp_db):
    from core.storage import insert, delete, fetch_one
    insert("customers", {"customer_id": "C_1", "customer_name": "A", "short_name": "A"})
    delete("customers", "C_1")
    row = fetch_one("customers", "C_1")
    assert row is None
