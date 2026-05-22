"""Tests for StorageBucketManager."""
import tempfile
import time
import os
from storage_v8.bucket_manager import StorageBucketManager, BucketConfig, Bucket


def test_create_first_bucket():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = StorageBucketManager(tmpdir)
        bucket = mgr.get_or_create_bucket("run_001", "Cam_01", "ng")
        assert bucket.bucket_id.endswith("bucket_000001")
        assert "run_001" in bucket.bucket_path
        assert os.path.isdir(bucket.bucket_path)


def test_same_bucket_returned_when_not_full():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = StorageBucketManager(tmpdir)
        b1 = mgr.get_or_create_bucket("run_001", "Cam_01", "ng")
        b2 = mgr.get_or_create_bucket("run_001", "Cam_01", "ng")
        assert b1 is b2
        assert b1.bucket_id == b2.bucket_id


def test_bucket_ids_are_unique_across_cameras():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = StorageBucketManager(tmpdir)
        b1 = mgr.get_or_create_bucket("run_001", "Cam_01", "ng")
        b2 = mgr.get_or_create_bucket("run_001", "Cam_02", "ng")
        assert b1.bucket_id != b2.bucket_id


def test_ok_and_ng_use_separate_active_buckets():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = StorageBucketManager(tmpdir)
        ng = mgr.get_or_create_bucket("run_001", "Cam_01", "ng")
        ok = mgr.get_or_create_bucket("run_001", "Cam_01", "ok")
        assert ng.bucket_type == "ng"
        assert ok.bucket_type == "ok"
        assert ng.bucket_id != ok.bucket_id


def test_rotation_by_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = BucketConfig(max_images=3, max_size_mb=99999, max_duration_min=99999)
        mgr = StorageBucketManager(tmpdir)
        b1 = mgr.get_or_create_bucket("run_001", "Cam_01", "ng", config)
        for _ in range(5):
            mgr.record_save(b1, 1000)
        # After 3 saves → should rotate on next get
        b2 = mgr.get_or_create_bucket("run_001", "Cam_01", "ng", config)
        assert b2.bucket_id != b1.bucket_id
        assert b1.image_count == 5


def test_should_rotate_count():
    b = Bucket(
        bucket_id="b_001", run_id="r", camera_id="c", bucket_type="ok",
        bucket_path="/tmp/b", max_images=3, max_size_mb=500, max_duration_min=9999,
        image_count=3,
    )
    assert b.should_rotate()


def test_should_rotate_size():
    b = Bucket(
        bucket_id="b_001", run_id="r", camera_id="c", bucket_type="ok",
        bucket_path="/tmp/b", max_images=99999, max_size_mb=5, max_duration_min=9999,
        image_count=1, total_size_bytes=6 * 1024 * 1024,
    )
    assert b.should_rotate()
