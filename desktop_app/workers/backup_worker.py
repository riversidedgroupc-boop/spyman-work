"""Background worker for backup creation and restore operations."""
from __future__ import annotations

from desktop_app.workers.base_worker import BaseWorker


class BackupWorker(BaseWorker):
    """Runs backup create/restore in background thread.

    Set *operation* to "create" or "restore".
    """

    def __init__(
        self,
        operation: str,
        kwargs: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._operation = operation
        self._kwargs = kwargs or {}
        self._result = None

    def _run_impl(self) -> None:
        if self._operation == "create":
            from core.config_backup import create_backup
            self.message.emit("Creating backup...")
            meta = create_backup(**self._kwargs)
            self._result = meta
            self.message.emit(f"Backup created: {meta.backup_name} ({meta.size_bytes} bytes)")
        elif self._operation == "restore":
            from core.config_backup import restore_backup
            backup_id = self._kwargs.get("backup_id", "")
            backup_dir = self._kwargs.get("backup_dir")
            self.message.emit(f"Restoring backup: {backup_id}")
            files = restore_backup(backup_id, backup_dir=backup_dir)
            self._result = files
            self.message.emit(f"Restored {len(files)} files")
        else:
            raise ValueError(f"Unknown backup operation: {self._operation}")

    def get_result(self):
        return self._result
