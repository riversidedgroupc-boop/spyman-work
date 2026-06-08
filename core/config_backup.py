"""Configuration backup and restore (zip-based)."""
from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BackupMeta:
    backup_id: str
    backup_name: str
    backup_path: str
    size_bytes: int
    included_items: list[str]
    created_at: str


def _default_backup_dir() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backup_dir = os.path.join(base, "data", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_backup(
    name: str = "",
    include_db: bool = True,
    include_configs: bool = True,
    include_models: bool = False,
    backup_dir: str | None = None,
) -> BackupMeta:
    root = _project_root()
    dest_dir = backup_dir or _default_backup_dir()
    os.makedirs(dest_dir, exist_ok=True)

    now = datetime.now()
    backup_id = now.strftime("BACKUP_%Y%m%d_%H%M%S_%f")
    backup_name = name or backup_id
    zip_path = os.path.join(dest_dir, f"{backup_id}.zip")

    included: list[str] = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if include_db:
            db_path = os.path.join(root, "data", "app.db")
            if os.path.isfile(db_path):
                zf.write(db_path, "data/app.db")
                included.append("database")

        if include_configs:
            for config_dir in ("config", "configs"):
                cdir = os.path.join(root, config_dir)
                if os.path.isdir(cdir):
                    for fname in os.listdir(cdir):
                        fpath = os.path.join(cdir, fname)
                        if os.path.isfile(fpath):
                            zf.write(fpath, os.path.join(config_dir, fname))
            included.append("configs")

        if include_models:
            models_dir = os.path.join(root, "models")
            if os.path.isdir(models_dir):
                for dirpath, _, filenames in os.walk(models_dir):
                    for fname in filenames:
                        fpath = os.path.join(dirpath, fname)
                        arcname = os.path.relpath(fpath, root)
                        zf.write(fpath, arcname)
            included.append("models")

    size = os.path.getsize(zip_path)
    meta = BackupMeta(
        backup_id=backup_id,
        backup_name=backup_name,
        backup_path=zip_path,
        size_bytes=size,
        included_items=included,
        created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
    )
    _save_meta(meta, dest_dir)
    return meta


def list_backups(backup_dir: str | None = None) -> list[BackupMeta]:
    dest_dir = backup_dir or _default_backup_dir()
    if not os.path.isdir(dest_dir):
        return []
    backups: list[BackupMeta] = []
    for fname in sorted(os.listdir(dest_dir), reverse=True):
        if fname.endswith(".zip"):
            backup_id = fname.replace(".zip", "")
            meta_path = os.path.join(dest_dir, f"{backup_id}.json")
            if os.path.isfile(meta_path):
                meta = _load_meta(meta_path)
                if meta:
                    backups.append(meta)
                    continue
            fpath = os.path.join(dest_dir, fname)
            backups.append(BackupMeta(
                backup_id=backup_id,
                backup_name=backup_id,
                backup_path=fpath,
                size_bytes=os.path.getsize(fpath),
                included_items=[],
                created_at="",
            ))
    return backups


def restore_backup(
    backup_id: str,
    backup_dir: str | None = None,
    restore_root: str | None = None,
) -> list[str]:
    dest_dir = backup_dir or _default_backup_dir()
    zip_path = os.path.join(dest_dir, f"{backup_id}.zip")
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"Backup not found: {zip_path}")

    root = restore_root or _project_root()
    root_abs = os.path.abspath(root)
    restored: list[str] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            target = _safe_restore_target(root_abs, member)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            zf.extract(member, root_abs)
            restored.append(member)
    return restored


def _safe_restore_target(root_abs: str, member: str) -> str:
    normalized_member = member.replace("\\", "/")
    if (
        normalized_member.startswith("/")
        or normalized_member.startswith("../")
        or "/../" in normalized_member
        or normalized_member.endswith("/..")
        or os.path.isabs(member)
        or os.path.splitdrive(member)[0]
    ):
        raise ValueError(f"Unsafe backup member path: {member}")
    target = os.path.abspath(os.path.join(root_abs, normalized_member))
    if os.path.commonpath([root_abs, target]) != root_abs:
        raise ValueError(f"Unsafe backup member path: {member}")
    return target


def delete_backup(backup_id: str, backup_dir: str | None = None) -> None:
    dest_dir = backup_dir or _default_backup_dir()
    zip_path = os.path.join(dest_dir, f"{backup_id}.zip")
    meta_path = os.path.join(dest_dir, f"{backup_id}.json")
    if os.path.isfile(zip_path):
        os.remove(zip_path)
    if os.path.isfile(meta_path):
        os.remove(meta_path)


def export_project_config_package(project_id: str, backup_dir: str | None = None) -> str:
    """Export one customer project as a portable V6 config package.

    The package contains normalized JSON for the project, its customer, product
    specs, and camera configs. It intentionally does not restore anything by
    itself; import conflict handling belongs in a separate explicit workflow.
    """
    from core.customer import get_customer
    from core.project import get_project
    from core.product_spec import list_product_specs
    from core.camera_config import list_camera_configs

    project = get_project(project_id)
    if project is None:
        raise ValueError(f"Project not found: {project_id}")
    customer = get_customer(project.customer_id)
    specs = list_product_specs(project_id)
    camera_configs = []
    for spec in specs:
        camera_configs.extend(cfg.to_dict() for cfg in list_camera_configs(spec.spec_id))

    dest_dir = backup_dir or _default_backup_dir()
    os.makedirs(dest_dir, exist_ok=True)
    now = datetime.now()
    package_id = now.strftime("PROJECT_CONFIG_%Y%m%d_%H%M%S_%f")
    zip_path = os.path.join(dest_dir, f"{package_id}.zip")
    manifest = {
        "package_id": package_id,
        "package_type": "project_config",
        "project_id": project_id,
        "customer_id": project.customer_id,
        "product_spec_count": len(specs),
        "camera_config_count": len(camera_configs),
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        _write_json(zf, "project_config/manifest.json", manifest)
        _write_json(zf, "project_config/customer.json", customer.to_dict() if customer else None)
        _write_json(zf, "project_config/project.json", project.to_dict())
        _write_json(zf, "project_config/product_specs.json", [s.to_dict() for s in specs])
        _write_json(zf, "project_config/camera_configs.json", camera_configs)
    _audit("project_config_export", f"{project_id} -> {zip_path}")
    return zip_path


def _save_meta(meta: BackupMeta, dest_dir: str) -> None:
    meta_path = os.path.join(dest_dir, f"{meta.backup_id}.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "backup_id": meta.backup_id,
            "backup_name": meta.backup_name,
            "backup_path": meta.backup_path,
            "size_bytes": meta.size_bytes,
            "included_items": meta.included_items,
            "created_at": meta.created_at,
        }, f, ensure_ascii=False, indent=2)


def _load_meta(meta_path: str) -> BackupMeta | None:
    try:
        with open(meta_path, encoding="utf-8") as f:
            data = json.load(f)
        return BackupMeta(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def _write_json(zf: zipfile.ZipFile, name: str, data) -> None:
    zf.writestr(name, json.dumps(data, ensure_ascii=False, indent=2))


def _audit(action: str, detail: str) -> None:
    try:
        from core.log_manager import LogManager

        LogManager.instance().log_audit(action, detail)
    except ImportError:
        pass
