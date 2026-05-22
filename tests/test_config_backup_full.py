"""Tests for config backup and restore (extended)."""
import json
import os
import tempfile

from core.config_backup import create_backup, list_backups, restore_backup, delete_backup


def _reset_backup_state():
    """No-op since backup functions are stateless, but keep for clarity."""
    pass


def test_create_and_restore_roundtrip(tmp_path):
    """Create a backup and restore it, verifying extracted files."""
    meta = create_backup(name="roundtrip_test", backup_dir=str(tmp_path))
    assert meta.backup_id.startswith("BACKUP_")
    assert meta.size_bytes > 0
    assert "database" in meta.included_items

    # Restore into a temp directory
    restore_dir = tmp_path / "restore_target"
    restore_dir.mkdir()
    # restore_backup extracts to project root, so we test with a different dir
    # by directly using zipfile
    import zipfile
    with zipfile.ZipFile(meta.backup_path, "r") as zf:
        zf.extractall(str(restore_dir))

    # Check extracted contents
    extracted = os.listdir(str(restore_dir))
    assert "data" in extracted or "config" in extracted or "configs" in extracted


def test_backup_with_custom_name(tmp_path):
    meta = create_backup(name="CustomBackupName", backup_dir=str(tmp_path))
    assert meta.backup_name == "CustomBackupName"


def test_backup_meta_json_exists(tmp_path):
    meta = create_backup(name="meta_test", backup_dir=str(tmp_path))
    meta_path = os.path.join(str(tmp_path), f"{meta.backup_id}.json")
    assert os.path.isfile(meta_path)
    with open(meta_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["backup_id"] == meta.backup_id
    assert data["backup_name"] == "meta_test"


def test_list_backups_sorted_by_recent(tmp_path):
    b1 = create_backup(name="oldest", backup_dir=str(tmp_path))
    import time
    time.sleep(0.1)
    b2 = create_backup(name="newest", backup_dir=str(tmp_path))
    backups = list_backups(str(tmp_path))
    # Most recent first
    assert backups[0].backup_name == "newest"


def test_delete_backup_removes_both_files(tmp_path):
    meta = create_backup(name="delete_me", backup_dir=str(tmp_path))
    assert os.path.isfile(meta.backup_path)
    meta_path = os.path.join(str(tmp_path), f"{meta.backup_id}.json")
    assert os.path.isfile(meta_path)

    delete_backup(meta.backup_id, str(tmp_path))
    assert not os.path.isfile(meta.backup_path)
    assert not os.path.isfile(meta_path)


def test_restore_nonexistent_raises(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        restore_backup("NONEXISTENT_BACKUP", backup_dir=str(tmp_path))


def test_create_backup_db_only(tmp_path):
    meta = create_backup(name="db_only", include_configs=False, backup_dir=str(tmp_path))
    assert "database" in meta.included_items
    assert "configs" not in meta.included_items
    assert "models" not in meta.included_items


def test_export_project_config_package_contains_project_manifest(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("COPPER_VISION_DB_PATH", str(db_path))
    import importlib
    import core.storage
    importlib.reload(core.storage)
    core.storage.init_db()

    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.camera_config import create_camera_config
    from core.config_backup import export_project_config_package

    customer = create_customer("Package Co", "PKG")
    project = create_project(customer.customer_id, "Package Project")
    spec = create_product_spec(project.project_id, "Tube", "copper", "tube", camera_count=2)
    create_camera_config(spec.spec_id, camera_index=1, camera_id="CAM_01")
    create_camera_config(spec.spec_id, camera_index=2, camera_id="CAM_02")

    package_path = export_project_config_package(project.project_id, backup_dir=str(tmp_path))

    import zipfile
    with zipfile.ZipFile(package_path, "r") as zf:
        names = set(zf.namelist())
        manifest = json.loads(zf.read("project_config/manifest.json").decode("utf-8"))

    assert "project_config/customer.json" in names
    assert "project_config/project.json" in names
    assert "project_config/product_specs.json" in names
    assert "project_config/camera_configs.json" in names
    assert manifest["project_id"] == project.project_id
    assert manifest["camera_config_count"] == 2
