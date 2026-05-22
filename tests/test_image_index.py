"""Tests for ImageIndexDB."""
import os
import tempfile
from storage_v8.image_index import ImageIndexDB


def test_init_creates_tables():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = ImageIndexDB(db_path)
        conn = db._get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        conn.close()
        table_names = [t["name"] for t in tables]
        assert "image_index" in table_names
        assert "bucket_registry" in table_names
    finally:
        os.unlink(db_path)


def test_insert_and_query_image():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = ImageIndexDB(db_path)
        db.insert_image({
            "image_id": "IMG_001",
            "run_id": "run_001",
            "customer_id": "cust_a",
            "product_id": "prod_01",
            "camera_id": "Cam_01",
            "bucket_id": "bucket_000001",
            "file_path": "/data/run_001/Cam_01/bucket_000001/img.png",
            "result_type": "NG",
            "defect_type": "scratch",
            "model_version": "v003",
            "model_type": "yolo",
            "tile_id": "T_001",
            "block_id": "BLK_001",
            "meter_start": 100.0,
            "meter_end": 100.5,
            "meter_center": 100.25,
            "tile_x": 0,
            "tile_y": 320,
            "confidence": 0.92,
            "created_at": "2026-05-20T20:30:00",
        })
        results = db.query_by_run("run_001")
        assert len(results) == 1
        assert results[0]["result_type"] == "NG"
        assert results[0]["defect_type"] == "scratch"
    finally:
        os.unlink(db_path)


def test_query_filter_by_result_type():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = ImageIndexDB(db_path)
        for i, rt in enumerate(["OK", "NG", "UNKNOWN"]):
            db.insert_image({
                "image_id": f"IMG_{i:03d}",
                "run_id": "run_001",
                "customer_id": "cust_a",
                "product_id": "prod_01",
                "camera_id": "Cam_01",
                "bucket_id": "bucket_000001",
                "file_path": f"/data/img_{i}.png",
                "result_type": rt,
                "defect_type": "",
                "model_version": "v1",
                "model_type": "yolo",
                "tile_id": f"T_{i:03d}",
                "block_id": "BLK_001",
                "meter_start": 100.0 + i,
                "meter_end": 100.5 + i,
                "meter_center": 100.25 + i,
                "tile_x": 0,
                "tile_y": i * 320,
                "confidence": 0.9,
                "created_at": "2026-05-20T20:30:00",
            })
        ng_results = db.query_by_run("run_001", result_type="NG")
        assert len(ng_results) == 1
    finally:
        os.unlink(db_path)


def test_create_and_close_bucket():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = ImageIndexDB(db_path)
        db.create_bucket({
            "bucket_id": "bucket_000001",
            "run_id": "run_001",
            "camera_id": "Cam_01",
            "bucket_type": "ng",
            "bucket_path": "/data/run_001/Cam_01/bucket_000001",
            "max_image_count": 3000,
            "max_size_mb": 500,
            "created_at": "2026-05-20T20:30:00",
        })
        open_bucket = db.get_open_bucket("run_001", "Cam_01")
        assert open_bucket is not None
        assert open_bucket["status"] == "open"

        db.close_bucket("bucket_000001", 1000, 150.0)
        open_bucket2 = db.get_open_bucket("run_001", "Cam_01")
        assert open_bucket2 is None
    finally:
        os.unlink(db_path)
