"""Tests for config backup and restore."""
import os
import zipfile

from core.config_backup import create_backup, list_backups, restore_backup, delete_backup


def test_create_backup_defaults(tmp_path):
    meta = create_backup(name="test_backup", backup_dir=str(tmp_path))
    assert meta.backup_id.startswith("BACKUP_")
    assert meta.backup_name == "test_backup"
    assert meta.size_bytes > 0
    assert "database" in meta.included_items
    assert "configs" in meta.included_items
    assert os.path.isfile(meta.backup_path)


def test_create_backup_db_only(tmp_path):
    meta = create_backup(name="db_only", include_configs=False, backup_dir=str(tmp_path))
    assert "database" in meta.included_items
    assert "configs" not in meta.included_items


def test_list_backups(tmp_path):
    create_backup(name="b1", backup_dir=str(tmp_path))
    create_backup(name="b2", backup_dir=str(tmp_path))
    backups = list_backups(backup_dir=str(tmp_path))
    assert len(backups) >= 2


def test_restore_backup(tmp_path):
    meta = create_backup(name="restore_test", backup_dir=str(tmp_path))
    restored = restore_backup(meta.backup_id, backup_dir=str(tmp_path))
    assert "data/app.db" in restored or any("data" in r for r in restored)


def test_restore_backup_rejects_path_traversal(tmp_path):
    zip_path = tmp_path / "EVIL.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../outside.txt", "owned")

    try:
        restore_backup("EVIL", backup_dir=str(tmp_path))
    except ValueError as exc:
        assert "unsafe" in str(exc).lower()
    else:
        raise AssertionError("unsafe backup member was restored")


def test_delete_backup(tmp_path):
    meta = create_backup(name="to_delete", backup_dir=str(tmp_path))
    assert os.path.isfile(meta.backup_path)
    delete_backup(meta.backup_id, backup_dir=str(tmp_path))
    assert not os.path.isfile(meta.backup_path)
