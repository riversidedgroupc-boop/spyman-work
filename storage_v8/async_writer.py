"""Async disk writer with save policy and bucket management."""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from datetime import datetime
from typing import Callable

import cv2

from gpu_scheduler.stats import TileResult
from runtime.unified_image_pool import TileEntry
from storage_v8.bucket_manager import StorageBucketManager
from storage_v8.disk_monitor import DiskLevel, DiskMonitor
from storage_v8.image_index import ImageIndexDB
from storage_v8.save_policy import SavePolicyManager

logger = logging.getLogger(__name__)


class AsyncDiskWriter:
    """Non-blocking disk writer with save policy and bucket management."""

    def __init__(
        self,
        base_dir: str,
        policy: SavePolicyManager,
        bucket_mgr: StorageBucketManager | None = None,
        index_db: ImageIndexDB | None = None,
        queue_size: int = 500,
        disk_monitor: DiskMonitor | None = None,
    ):
        self._base_dir = base_dir
        self._policy = policy
        self._bucket_mgr = bucket_mgr or StorageBucketManager(base_dir, index_db)
        self._index_db = index_db or ImageIndexDB(os.path.join(base_dir, "image_index.db"))
        self._disk_monitor = disk_monitor or DiskMonitor(base_dir)

        self._queue: queue.Queue[tuple[TileEntry, TileResult, bool]] = queue.Queue(maxsize=queue_size)
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._stats = {
            "written": 0,
            "results_written": 0,
            "skipped": 0,
            "failed": 0,
            "queue_full_drops": 0,
            "disk_degraded_drops": 0,
            "disk_level": "normal",
        }
        self._disk_check_interval = 30.0
        self._last_disk_check = 0.0

        self._on_write_complete: Callable | None = None

    def set_on_write_complete(self, callback: Callable) -> None:
        self._on_write_complete = callback

    def write(self, tile: TileEntry, result: TileResult) -> bool:
        """Queue a write request without blocking the detection loop."""
        save_image = self._policy.should_save_image(result)
        save_result_only = self._policy.should_save_result(result)
        if not save_image and not save_result_only:
            self._stats["skipped"] += 1
            return True

        if self._disk_monitor.level == DiskLevel.CRITICAL and result.result_type == "OK":
            self._stats["disk_degraded_drops"] += 1
            logger.warning("Disk critical, dropping OK tile %s", result.tile_id)
            return True

        try:
            self._queue.put_nowait((tile, result, save_image))
            return True
        except queue.Full:
            self._stats["queue_full_drops"] += 1
            logger.warning("Save queue full, dropping tile %s", result.tile_id)
            return False

    def start(self) -> None:
        self._running.set()
        self._thread = threading.Thread(target=self._write_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        self._drain_queue()
        self._bucket_mgr.close_all()
        if self._thread:
            self._thread.join(timeout=5)

    def _drain_queue(self) -> None:
        count = 0
        while True:
            try:
                item = self._queue.get_nowait()
                self._do_write(*item)
                count += 1
            except queue.Empty:
                break
        if count:
            logger.info("Drained %d pending writes on shutdown", count)

    def _write_loop(self) -> None:
        while self._running.is_set():
            self._maybe_check_disk()
            try:
                item = self._queue.get(timeout=0.5)
                self._do_write(*item)
            except queue.Empty:
                continue

    def _maybe_check_disk(self) -> None:
        now = time.monotonic()
        if now - self._last_disk_check < self._disk_check_interval:
            return
        self._last_disk_check = now
        status = self._disk_monitor.check()
        self._stats["disk_level"] = status.level.value
        if status.level == DiskLevel.WARNING:
            logger.warning(
                "Disk space low: %.1f%% free (%d MB)",
                status.free_pct,
                status.free_bytes // (1024 * 1024),
            )
        elif status.level == DiskLevel.CRITICAL:
            logger.critical(
                "Disk space critically low: %.1f%% free (%d MB); only NG/UNKNOWN images will be saved",
                status.free_pct,
                status.free_bytes // (1024 * 1024),
            )

    def _do_write(self, tile: TileEntry, result: TileResult, save_image: bool) -> None:
        try:
            bucket = self._bucket_mgr.get_or_create_bucket(
                run_id=result.run_id,
                camera_id=result.camera_id,
                bucket_type="ng" if result.result_type in ("NG", "UNKNOWN") else "ok",
            )

            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = (
                f"{result.camera_id}_"
                f"m{result.meter_start:09.3f}_"
                f"tile{tile.tile_index:04d}_"
                f"{result.model_type}_"
                f"model_{result.model_version}_"
                f"{result.result_type}_"
                f"{ts}.png"
            )
            filepath = os.path.join(bucket.bucket_path, filename)

            file_size = 0
            if save_image:
                img = tile.image
                if img.ndim == 3 and img.shape[0] == 3:
                    img = img.transpose(1, 2, 0)
                if not cv2.imwrite(filepath, img):
                    raise OSError(f"cv2.imwrite failed: {filepath}")
                file_size = os.path.getsize(filepath)
            else:
                filepath = ""

            self._bucket_mgr.record_save(bucket, file_size)
            self._index_db.insert_image({
                "image_id": f"{result.tile_id}_{result.model_type}_{result.model_version}_{result.result_type}",
                "run_id": result.run_id,
                "customer_id": tile.customer_id,
                "product_id": result.product_id,
                "camera_id": result.camera_id,
                "bucket_id": bucket.bucket_id,
                "file_path": filepath,
                "result_type": result.result_type,
                "defect_type": result.defect_type,
                "model_version": result.model_version,
                "model_type": result.model_type,
                "tile_id": result.tile_id,
                "block_id": tile.block_id,
                "meter_start": result.meter_start,
                "meter_end": result.meter_end,
                "meter_center": (result.meter_start + result.meter_end) / 2,
                "tile_x": tile.tile_x,
                "tile_y": tile.tile_y,
                "confidence": result.confidence,
                "created_at": result.created_time,
            })

            if save_image:
                self._stats["written"] += 1
            self._stats["results_written"] += 1

            if self._on_write_complete:
                self._on_write_complete(filepath, result)

        except Exception:
            self._stats["failed"] += 1
            logger.exception("Failed to write tile %s", result.tile_id)

    def get_stats(self) -> dict:
        stats = dict(self._stats)
        stats["queue_size"] = self._queue.qsize()
        return stats
