"""Worker that watches directories for new images and copies them to a capture session."""
from __future__ import annotations

import hashlib
import os
import shutil
import time

from PySide6.QtCore import Signal

from desktop_app.workers.base_worker import BaseWorker

IMAGE_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


class FolderWatchWorker(BaseWorker):
    """Watches camera directories, copies new images to session output."""

    image_captured = Signal(str, str, str)  # image_path, camera_id, image_name

    def __init__(
        self,
        watch_dirs: dict[str, str],
        output_root: str,
        camera_count: int = 3,
        target_count: int = 100,
        poll_interval: float = 0.5,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._watch_dirs = watch_dirs
        self._output_root = output_root
        self._camera_count = camera_count
        self._target_count = target_count
        self._poll_interval = poll_interval
        self._seen_files: set[tuple[str, str]] = set()
        self._total_captured = 0

    def _run_impl(self) -> None:
        for i in range(1, self._camera_count + 1):
            os.makedirs(os.path.join(self._output_root, f"cam{i}"), exist_ok=True)

        while not self._cancelled and self._total_captured < self._target_count:
            found = False
            for cam_id, watch_dir in self._watch_dirs.items():
                if not os.path.isdir(watch_dir):
                    continue
                try:
                    entries = sorted(os.listdir(watch_dir))
                except OSError:
                    continue
                for fname in entries:
                    if self._cancelled:
                        break
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in IMAGE_EXTENSIONS:
                        continue
                    src = os.path.join(watch_dir, fname)
                    if not os.path.isfile(src):
                        continue
                    seen_key = (cam_id, os.path.abspath(src))
                    if seen_key in self._seen_files:
                        continue
                    self._seen_files.add(seen_key)

                    try:
                        from PIL import Image
                        with Image.open(src) as img:
                            img.verify()
                    except Exception:
                        self.message.emit(f"跳过损坏图片: {fname}")
                        continue

                    out_dir = os.path.join(self._output_root, cam_id)
                    os.makedirs(out_dir, exist_ok=True)
                    dst = os.path.join(out_dir, fname)
                    shutil.copy2(src, dst)

                    self._total_captured += 1
                    self.image_captured.emit(dst, cam_id, fname)
                    self.progress.emit(self._total_captured, self._target_count)
                    self.message.emit(
                        f"[{cam_id}] {fname} ({self._total_captured}/{self._target_count})"
                    )
                    found = True

                    if self._total_captured >= self._target_count:
                        break

            if not found:
                time.sleep(self._poll_interval)

        self.message.emit(
            f"采集完成: {self._total_captured} 张"
            if not self._cancelled
            else f"采集已取消: {self._total_captured} 张"
        )

    @staticmethod
    def _file_hash(path: str) -> str:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
