"""Image index database — image_index.db schema and CRUD."""
from __future__ import annotations

import os
import sqlite3


def _index_db_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_dir = os.path.join(base, "data")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "image_index.db")


class ImageIndexDB:
    """SQLite index for saved images with traceability metadata."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or _index_db_path()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS image_index (
                image_id       TEXT PRIMARY KEY,
                run_id         TEXT NOT NULL,
                customer_id    TEXT NOT NULL,
                product_id     TEXT NOT NULL,
                camera_id      TEXT NOT NULL,
                bucket_id      TEXT NOT NULL,
                file_path      TEXT NOT NULL,
                result_type    TEXT NOT NULL,
                defect_type    TEXT DEFAULT '',
                model_version  TEXT NOT NULL,
                model_type     TEXT NOT NULL,
                tile_id        TEXT NOT NULL,
                block_id       TEXT NOT NULL,
                meter_start    REAL,
                meter_end      REAL,
                meter_center   REAL,
                tile_x         INTEGER,
                tile_y         INTEGER,
                confidence     REAL DEFAULT 0.0,
                created_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bucket_registry (
                bucket_id       TEXT PRIMARY KEY,
                run_id          TEXT NOT NULL,
                camera_id       TEXT NOT NULL,
                bucket_type     TEXT NOT NULL,
                bucket_path     TEXT NOT NULL,
                image_count     INTEGER DEFAULT 0,
                total_size_mb   REAL DEFAULT 0.0,
                max_image_count INTEGER,
                max_size_mb     REAL,
                created_at      TEXT NOT NULL,
                closed_at       TEXT,
                status          TEXT DEFAULT 'open'
            );

            CREATE INDEX IF NOT EXISTS idx_img_run_camera ON image_index(run_id, camera_id);
            CREATE INDEX IF NOT EXISTS idx_img_defect ON image_index(defect_type);
            CREATE INDEX IF NOT EXISTS idx_img_meter ON image_index(run_id, meter_center);
            CREATE INDEX IF NOT EXISTS idx_img_result ON image_index(result_type);
            CREATE INDEX IF NOT EXISTS idx_img_bucket ON image_index(bucket_id);
        """)
        conn.commit()
        conn.close()

    def insert_image(self, data: dict) -> None:
        conn = self._get_conn()
        try:
            cols = [
                "image_id", "run_id", "customer_id", "product_id", "camera_id",
                "bucket_id", "file_path", "result_type", "defect_type",
                "model_version", "model_type", "tile_id", "block_id",
                "meter_start", "meter_end", "meter_center", "tile_x", "tile_y",
                "confidence", "created_at",
            ]
            placeholders = ", ".join("?" for _ in cols)
            conn.execute(
                f"INSERT INTO image_index ({', '.join(cols)}) VALUES ({placeholders})",
                [data.get(c, None) for c in cols],
            )
            conn.commit()
        finally:
            conn.close()

    def query_by_run(
        self, run_id: str, result_type: str | None = None, camera_id: str | None = None,
        meter_min: float | None = None, meter_max: float | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[dict]:
        conn = self._get_conn()
        where = ["run_id = ?"]
        params: list = [run_id]
        if result_type:
            where.append("result_type = ?")
            params.append(result_type)
        if camera_id:
            where.append("camera_id = ?")
            params.append(camera_id)
        if meter_min is not None:
            where.append("meter_center >= ?")
            params.append(meter_min)
        if meter_max is not None:
            where.append("meter_center <= ?")
            params.append(meter_max)
        sql = f"SELECT * FROM image_index WHERE {' AND '.join(where)} ORDER BY meter_center LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Bucket registry ──

    def create_bucket(self, data: dict) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO bucket_registry (bucket_id, run_id, camera_id, bucket_type, "
                "bucket_path, max_image_count, max_size_mb, created_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')",
                (data["bucket_id"], data["run_id"], data["camera_id"],
                 data["bucket_type"], data["bucket_path"],
                 data.get("max_image_count"), data.get("max_size_mb"),
                 data["created_at"]),
            )
            conn.commit()
        finally:
            conn.close()

    def close_bucket(self, bucket_id: str, image_count: int, total_size_mb: float) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE bucket_registry SET status='closed', closed_at=datetime('now','localtime'), "
                "image_count=?, total_size_mb=? WHERE bucket_id=?",
                (image_count, total_size_mb, bucket_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_open_bucket(self, run_id: str, camera_id: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM bucket_registry WHERE run_id=? AND camera_id=? AND status='open' ORDER BY created_at DESC LIMIT 1",
            (run_id, camera_id),
        ).fetchone()
        conn.close()
        return dict(row) if row else None
