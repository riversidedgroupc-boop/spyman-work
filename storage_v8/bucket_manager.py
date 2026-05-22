"""Storage bucket manager with automatic bucket rotation."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime

from storage_v8.image_index import ImageIndexDB


@dataclass
class BucketConfig:
    max_images: int = 3000
    max_size_mb: int = 500
    max_duration_min: int = 60


@dataclass
class Bucket:
    bucket_id: str
    run_id: str
    camera_id: str
    bucket_type: str
    bucket_path: str
    max_images: int = 3000
    max_size_mb: int = 500
    max_duration_min: int = 60
    image_count: int = 0
    total_size_bytes: int = 0
    created_time: float = field(default_factory=time.time)

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 * 1024)

    def should_rotate(self) -> bool:
        if self.image_count >= self.max_images:
            return True
        if self.total_size_mb >= self.max_size_mb:
            return True
        elapsed_min = (time.time() - self.created_time) / 60
        return elapsed_min >= self.max_duration_min


class StorageBucketManager:
    """Manages bucket rotation for disk storage."""

    def __init__(self, base_dir: str, index_db: ImageIndexDB | None = None):
        self._base_dir = base_dir
        self._index_db = index_db or ImageIndexDB(os.path.join(base_dir, "image_index.db"))
        self._active_buckets: dict[tuple[str, str, str], Bucket] = {}

    def get_or_create_bucket(
        self,
        run_id: str,
        camera_id: str,
        bucket_type: str = "ng",
        config: BucketConfig | None = None,
    ) -> Bucket:
        cfg = config or BucketConfig()
        key = (run_id, camera_id, bucket_type)

        bucket = self._active_buckets.get(key)
        if bucket is not None and not bucket.should_rotate():
            return bucket

        if bucket is not None:
            self._index_db.close_bucket(
                bucket.bucket_id, bucket.image_count, bucket.total_size_mb
            )

        next_idx = 1
        cam_dir = os.path.join(self._base_dir, run_id, camera_id, bucket_type)
        if os.path.isdir(cam_dir):
            indices = []
            for dirname in os.listdir(cam_dir):
                marker = "_bucket_"
                if marker not in dirname:
                    continue
                suffix = dirname.rsplit(marker, 1)[-1]
                if suffix.isdigit():
                    indices.append(int(suffix))
            if indices:
                next_idx = max(indices) + 1

        bucket_id = f"{run_id}_{camera_id}_{bucket_type}_bucket_{next_idx:06d}"
        bucket_path = os.path.join(cam_dir, bucket_id)
        os.makedirs(bucket_path, exist_ok=True)

        bucket = Bucket(
            bucket_id=bucket_id,
            run_id=run_id,
            camera_id=camera_id,
            bucket_type=bucket_type,
            bucket_path=bucket_path,
            max_images=cfg.max_images,
            max_size_mb=cfg.max_size_mb,
            max_duration_min=cfg.max_duration_min,
        )

        self._index_db.create_bucket({
            "bucket_id": bucket_id,
            "run_id": run_id,
            "camera_id": camera_id,
            "bucket_type": bucket_type,
            "bucket_path": bucket_path,
            "max_image_count": cfg.max_images,
            "max_size_mb": cfg.max_size_mb,
            "created_at": datetime.now().isoformat(),
        })

        self._active_buckets[key] = bucket
        return bucket

    def record_save(self, bucket: Bucket, file_size_bytes: int) -> None:
        bucket.image_count += 1
        bucket.total_size_bytes += file_size_bytes

    def close_all(self) -> None:
        for bucket in self._active_buckets.values():
            self._index_db.close_bucket(
                bucket.bucket_id, bucket.image_count, bucket.total_size_mb
            )
        self._active_buckets.clear()
