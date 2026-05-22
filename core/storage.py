"""SQLite database layer for desktop application."""
from __future__ import annotations

import os
import sqlite3
from typing import Any


def _db_path() -> str:
    env_path = os.environ.get("COPPER_VISION_DB_PATH", "")
    if env_path:
        return env_path
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_dir = os.path.join(base, "data")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "app.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Current schema version for migration tracking
_SCHEMA_VERSION = 8


def init_db() -> None:
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            short_name TEXT NOT NULL,
            industry TEXT,
            contact TEXT,
            location TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            project_name TEXT NOT NULL,
            project_type TEXT NOT NULL DEFAULT 'surface_inspection',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE IF NOT EXISTS product_specs (
            spec_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            material TEXT NOT NULL DEFAULT '',
            geometry_type TEXT NOT NULL DEFAULT '',
            surface_type TEXT NOT NULL DEFAULT '',
            diameter_mm REAL,
            width_mm REAL,
            thickness_mm REAL,
            length_mm REAL,
            line_speed_min_mpm REAL NOT NULL DEFAULT 10.0,
            line_speed_max_mpm REAL NOT NULL DEFAULT 200.0,
            target_speed_mpm REAL NOT NULL DEFAULT 80.0,
            min_defect_size_mm REAL,
            camera_count INTEGER NOT NULL DEFAULT 3,
            camera_layout TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS capture_sessions (
            session_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            spec_id TEXT NOT NULL,
            session_name TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'directory_watch',
            watch_dirs TEXT NOT NULL DEFAULT '{}',
            camera_count INTEGER NOT NULL DEFAULT 3,
            target_image_count INTEGER NOT NULL DEFAULT 100,
            captured_image_count INTEGER NOT NULL DEFAULT 0,
            line_speed_mpm REAL NOT NULL DEFAULT 80.0,
            sampling_mode TEXT NOT NULL DEFAULT 'directory_watch',
            status TEXT NOT NULL DEFAULT 'created',
            output_dir TEXT,
            started_at TEXT,
            ended_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (spec_id) REFERENCES product_specs(spec_id)
        );

        CREATE TABLE IF NOT EXISTS captured_images (
            image_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            image_path TEXT NOT NULL,
            image_name TEXT NOT NULL,
            camera_id TEXT NOT NULL DEFAULT '',
            frame_index INTEGER NOT NULL DEFAULT 0,
            width INTEGER DEFAULT 0,
            height INTEGER DEFAULT 0,
            classification_label TEXT DEFAULT '',
            position_meter REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (session_id) REFERENCES capture_sessions(session_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS training_jobs (
            job_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            spec_id TEXT NOT NULL,
            dataset_path TEXT NOT NULL DEFAULT '',
            job_name TEXT NOT NULL,
            model_family TEXT NOT NULL DEFAULT 'yolo',
            base_model TEXT NOT NULL DEFAULT 'yolov8n.pt',
            task_type TEXT NOT NULL DEFAULT 'detection',
            training_config TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'created',
            start_time TEXT,
            end_time TEXT,
            output_dir TEXT,
            best_model_path TEXT,
            last_model_path TEXT,
            metrics TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS model_versions (
            model_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            spec_id TEXT NOT NULL DEFAULT '',
            dataset_version_id TEXT,
            training_job_id TEXT,
            model_name TEXT NOT NULL,
            model_type TEXT NOT NULL DEFAULT 'yolo',
            model_path TEXT NOT NULL DEFAULT '',
            base_model TEXT,
            class_mapping TEXT NOT NULL DEFAULT '{}',
            metrics TEXT,
            status TEXT NOT NULL DEFAULT 'created',
            is_active INTEGER NOT NULL DEFAULT 0,
            deployed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            notes TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (training_job_id) REFERENCES training_jobs(job_id)
        );

        CREATE TABLE IF NOT EXISTS production_defect_events (
            event_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            spec_id TEXT NOT NULL DEFAULT '',
            batch_id TEXT NOT NULL DEFAULT '',
            camera_id TEXT NOT NULL DEFAULT '',
            event_time TEXT NOT NULL,
            ng_image_path TEXT NOT NULL DEFAULT '',
            detection_count INTEGER NOT NULL DEFAULT 0,
            prediction_json TEXT NOT NULL DEFAULT '{}',
            model_version TEXT NOT NULL DEFAULT '',
            defect_type TEXT NOT NULL DEFAULT '',
            max_confidence REAL NOT NULL DEFAULT 0.0,
            position_meter REAL,
            status TEXT NOT NULL DEFAULT 'ng',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS camera_configs (
            config_id TEXT PRIMARY KEY,
            spec_id TEXT NOT NULL,
            camera_index INTEGER NOT NULL DEFAULT 1 CHECK(camera_index >= 1 AND camera_index <= 6),
            camera_id TEXT NOT NULL DEFAULT '',
            camera_name TEXT NOT NULL DEFAULT '',
            camera_type TEXT NOT NULL DEFAULT '',
            brand TEXT NOT NULL DEFAULT '',
            serial_number TEXT NOT NULL DEFAULT '',
            ip_address TEXT NOT NULL DEFAULT '',
            adapter_type TEXT NOT NULL DEFAULT 'folder_watcher',
            connection_params TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER NOT NULL DEFAULT 1,
            trigger_mode TEXT NOT NULL DEFAULT 'continuous',
            exposure_us REAL,
            gain_db REAL,
            resolution_width INTEGER,
            resolution_height INTEGER,
            pixel_size_um REAL,
            position_desc TEXT NOT NULL DEFAULT '',
            save_ng_image INTEGER NOT NULL DEFAULT 1,
            roi TEXT NOT NULL DEFAULT '{}',
            model_binding TEXT NOT NULL DEFAULT '',
            line_rate INTEGER,
            image_block_height INTEGER DEFAULT 1024,
            pixel_format TEXT NOT NULL DEFAULT 'Mono8',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (spec_id) REFERENCES product_specs(spec_id)
        );

        CREATE TABLE IF NOT EXISTS dataset_versions (
            version_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            spec_id TEXT NOT NULL DEFAULT '',
            capture_session_id TEXT,
            version_name TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'session',
            dataset_path TEXT NOT NULL,
            yaml_path TEXT NOT NULL DEFAULT '',
            image_count INTEGER NOT NULL DEFAULT 0,
            class_names TEXT NOT NULL DEFAULT '[]',
            val_split_ratio REAL NOT NULL DEFAULT 0.2,
            quality_score REAL,
            quality_report TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS field_sessions (
            field_session_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            spec_id TEXT NOT NULL,
            session_type TEXT NOT NULL DEFAULT 'baseline_collection',
            status TEXT NOT NULL DEFAULT 'created',
            hardware_snapshot TEXT NOT NULL DEFAULT '{}',
            acquisition_config_snapshot TEXT NOT NULL DEFAULT '{}',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (spec_id) REFERENCES product_specs(spec_id)
        );

        CREATE TABLE IF NOT EXISTS defect_types (
            defect_type_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            spec_id TEXT NOT NULL DEFAULT '',
            code TEXT NOT NULL DEFAULT '',
            display_name_zh TEXT NOT NULL DEFAULT '',
            display_name_en TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL DEFAULT 'medium',
            description TEXT NOT NULL DEFAULT '',
            is_ng INTEGER NOT NULL DEFAULT 1,
            sample_image_paths TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS anomaly_reviews (
            review_id TEXT PRIMARY KEY,
            field_session_id TEXT NOT NULL,
            image_path TEXT NOT NULL DEFAULT '',
            crop_path TEXT NOT NULL DEFAULT '',
            heatmap_path TEXT NOT NULL DEFAULT '',
            anomaly_score REAL NOT NULL DEFAULT 0.0,
            cluster_id TEXT NOT NULL DEFAULT '',
            review_status TEXT NOT NULL DEFAULT 'unreviewed',
            assigned_defect_type_id TEXT,
            reviewer TEXT NOT NULL DEFAULT '',
            reviewed_at TEXT,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (field_session_id) REFERENCES field_sessions(field_session_id),
            FOREIGN KEY (assigned_defect_type_id) REFERENCES defect_types(defect_type_id)
        );

        CREATE TABLE IF NOT EXISTS hybrid_retest_runs (
            run_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            spec_id TEXT NOT NULL DEFAULT '',
            field_session_id TEXT NOT NULL DEFAULT '',
            yolo_model_id TEXT NOT NULL DEFAULT '',
            anomaly_model_id TEXT NOT NULL DEFAULT '',
            image_dir TEXT NOT NULL DEFAULT '',
            config_json TEXT NOT NULL DEFAULT '{}',
            summary_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'created',
            started_at TEXT,
            ended_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS hybrid_retest_items (
            item_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            image_path TEXT NOT NULL,
            final_decision TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            yolo_detection_count INTEGER NOT NULL DEFAULT 0,
            anomaly_score REAL NOT NULL DEFAULT 0,
            runtime_ms REAL NOT NULL DEFAULT 0,
            review_id TEXT,
            extra_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (run_id) REFERENCES hybrid_retest_runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS model_export_artifacts (
            export_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            spec_id TEXT NOT NULL DEFAULT '',
            source_model_id TEXT NOT NULL,
            backend TEXT NOT NULL,
            precision TEXT NOT NULL DEFAULT 'fp32',
            artifact_path TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'created',
            device_name TEXT NOT NULL DEFAULT '',
            cuda_version TEXT NOT NULL DEFAULT '',
            tensorrt_version TEXT NOT NULL DEFAULT '',
            input_shape TEXT NOT NULL DEFAULT '',
            export_config_json TEXT NOT NULL DEFAULT '{}',
            metrics_json TEXT NOT NULL DEFAULT '{}',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (source_model_id) REFERENCES model_versions(model_id)
        );

        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        );
    """)
    conn.commit()
    conn.close()

    # Run migrations to add any missing columns/tables
    migrate_v6()
    migrate_v7()
    migrate_v8()


def migrate_v6() -> None:
    """Apply schema v6: add missing columns + Phase A exploration tables.

    This single function handles ALL v6 changes for both fresh installs
    and upgrades from v5.  Existing tables get new columns; new tables
    are created if they don't exist yet.
    """
    conn = get_connection()
    try:
        # Check if migration already applied
        row = conn.execute(
            "SELECT version FROM schema_version WHERE version = ?", (_SCHEMA_VERSION,)
        ).fetchone()
        if row:
            conn.close()
            return
    except Exception:
        pass  # schema_version table may not exist yet

    # Ensure schema_version table exists
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
    )

    # --- model_versions: is_active, deployed_at ---
    mv_cols = {r[1] for r in conn.execute("PRAGMA table_info(model_versions)")}
    if "is_active" not in mv_cols:
        conn.execute("ALTER TABLE model_versions ADD COLUMN is_active INTEGER NOT NULL DEFAULT 0")
    if "deployed_at" not in mv_cols:
        conn.execute("ALTER TABLE model_versions ADD COLUMN deployed_at TEXT")
    if "spec_id" not in mv_cols:
        conn.execute("ALTER TABLE model_versions ADD COLUMN spec_id TEXT NOT NULL DEFAULT ''")
    if "dataset_version_id" not in mv_cols:
        conn.execute("ALTER TABLE model_versions ADD COLUMN dataset_version_id TEXT")

    # --- camera_configs: structured V6 camera fields ---
    cc_cols = {r[1] for r in conn.execute("PRAGMA table_info(camera_configs)")}
    camera_columns = {
        "camera_id": "TEXT NOT NULL DEFAULT ''",
        "camera_name": "TEXT NOT NULL DEFAULT ''",
        "camera_type": "TEXT NOT NULL DEFAULT ''",
        "brand": "TEXT NOT NULL DEFAULT ''",
        "serial_number": "TEXT NOT NULL DEFAULT ''",
        "ip_address": "TEXT NOT NULL DEFAULT ''",
        "resolution_width": "INTEGER",
        "resolution_height": "INTEGER",
        "pixel_size_um": "REAL",
        "position_desc": "TEXT NOT NULL DEFAULT ''",
        "save_ng_image": "INTEGER NOT NULL DEFAULT 1",
        "line_rate": "INTEGER",
        "image_block_height": "INTEGER DEFAULT 1024",
        "pixel_format": "TEXT NOT NULL DEFAULT 'Mono8'",
    }
    for col, decl in camera_columns.items():
        if col not in cc_cols:
            conn.execute(f"ALTER TABLE camera_configs ADD COLUMN {col} {decl}")

    # --- production_defect_events: model_version, defect_type, max_confidence, position_meter ---
    pde_cols = {r[1] for r in conn.execute("PRAGMA table_info(production_defect_events)")}
    if "model_version" not in pde_cols:
        conn.execute("ALTER TABLE production_defect_events ADD COLUMN model_version TEXT NOT NULL DEFAULT ''")
    if "defect_type" not in pde_cols:
        conn.execute("ALTER TABLE production_defect_events ADD COLUMN defect_type TEXT NOT NULL DEFAULT ''")
    if "max_confidence" not in pde_cols:
        conn.execute("ALTER TABLE production_defect_events ADD COLUMN max_confidence REAL NOT NULL DEFAULT 0.0")
    if "position_meter" not in pde_cols:
        conn.execute("ALTER TABLE production_defect_events ADD COLUMN position_meter REAL")

    # --- capture_sessions: sampling_mode, dataset_task_type ---
    cs_cols = {r[1] for r in conn.execute("PRAGMA table_info(capture_sessions)")}
    if "sampling_mode" not in cs_cols:
        conn.execute("ALTER TABLE capture_sessions ADD COLUMN sampling_mode TEXT NOT NULL DEFAULT 'directory_watch'")
    if "dataset_task_type" not in cs_cols:
        conn.execute("ALTER TABLE capture_sessions ADD COLUMN dataset_task_type TEXT NOT NULL DEFAULT ''")

    # --- captured_images: position_meter ---
    ci_cols = {r[1] for r in conn.execute("PRAGMA table_info(captured_images)")}
    if "position_meter" not in ci_cols:
        conn.execute("ALTER TABLE captured_images ADD COLUMN position_meter REAL")

    # --- Phase A exploration tables (schema v6) ---
    existing_tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    if "field_sessions" not in existing_tables:
        conn.execute("""
            CREATE TABLE field_sessions (
                field_session_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                spec_id TEXT NOT NULL,
                session_type TEXT NOT NULL DEFAULT 'baseline_collection',
                status TEXT NOT NULL DEFAULT 'created',
                hardware_snapshot TEXT NOT NULL DEFAULT '{}',
                acquisition_config_snapshot TEXT NOT NULL DEFAULT '{}',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (project_id) REFERENCES projects(project_id),
                FOREIGN KEY (spec_id) REFERENCES product_specs(spec_id)
            )
        """)

    if "defect_types" not in existing_tables:
        conn.execute("""
            CREATE TABLE defect_types (
                defect_type_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                spec_id TEXT NOT NULL DEFAULT '',
                code TEXT NOT NULL DEFAULT '',
                display_name_zh TEXT NOT NULL DEFAULT '',
                display_name_en TEXT NOT NULL DEFAULT '',
                severity TEXT NOT NULL DEFAULT 'medium',
                description TEXT NOT NULL DEFAULT '',
                is_ng INTEGER NOT NULL DEFAULT 1,
                sample_image_paths TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        """)

    if "anomaly_reviews" not in existing_tables:
        conn.execute("""
            CREATE TABLE anomaly_reviews (
                review_id TEXT PRIMARY KEY,
                field_session_id TEXT NOT NULL,
                image_path TEXT NOT NULL DEFAULT '',
                crop_path TEXT NOT NULL DEFAULT '',
                heatmap_path TEXT NOT NULL DEFAULT '',
                anomaly_score REAL NOT NULL DEFAULT 0.0,
                cluster_id TEXT NOT NULL DEFAULT '',
                review_status TEXT NOT NULL DEFAULT 'unreviewed',
                assigned_defect_type_id TEXT,
                reviewer TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (field_session_id) REFERENCES field_sessions(field_session_id),
                FOREIGN KEY (assigned_defect_type_id) REFERENCES defect_types(defect_type_id)
            )
        """)

    # Record schema version
    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (_SCHEMA_VERSION,))
    conn.commit()
    conn.close()


def migrate_v7() -> None:
    """Apply schema v7: add hybrid_retest tables (Phase D)."""
    conn = get_connection()
    try:
        # Check if migration already applied
        row = conn.execute(
            "SELECT version FROM schema_version WHERE version = ?", (_SCHEMA_VERSION,)
        ).fetchone()
        if row:
            conn.close()
            return
    except Exception:
        pass

    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
    )

    existing_tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    if "hybrid_retest_runs" not in existing_tables:
        conn.execute("""
            CREATE TABLE hybrid_retest_runs (
                run_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                spec_id TEXT NOT NULL DEFAULT '',
                field_session_id TEXT NOT NULL DEFAULT '',
                yolo_model_id TEXT NOT NULL DEFAULT '',
                anomaly_model_id TEXT NOT NULL DEFAULT '',
                image_dir TEXT NOT NULL DEFAULT '',
                config_json TEXT NOT NULL DEFAULT '{}',
                summary_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'created',
                started_at TEXT,
                ended_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)

    if "hybrid_retest_items" not in existing_tables:
        conn.execute("""
            CREATE TABLE hybrid_retest_items (
                item_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                image_path TEXT NOT NULL,
                final_decision TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                yolo_detection_count INTEGER NOT NULL DEFAULT 0,
                anomaly_score REAL NOT NULL DEFAULT 0,
                runtime_ms REAL NOT NULL DEFAULT 0,
                review_id TEXT,
                extra_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (run_id) REFERENCES hybrid_retest_runs(run_id)
            )
        """)

    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (_SCHEMA_VERSION,))
    conn.commit()
    conn.close()


def migrate_v8() -> None:
    """Apply schema v8: add model_export_artifacts table."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT version FROM schema_version WHERE version = ?", (_SCHEMA_VERSION,)
        ).fetchone()
        if row:
            conn.close()
            return
    except Exception:
        pass

    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
    )

    existing_tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    if "model_export_artifacts" not in existing_tables:
        conn.execute("""
            CREATE TABLE model_export_artifacts (
                export_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                spec_id TEXT NOT NULL DEFAULT '',
                source_model_id TEXT NOT NULL,
                backend TEXT NOT NULL,
                precision TEXT NOT NULL DEFAULT 'fp32',
                artifact_path TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'created',
                device_name TEXT NOT NULL DEFAULT '',
                cuda_version TEXT NOT NULL DEFAULT '',
                tensorrt_version TEXT NOT NULL DEFAULT '',
                input_shape TEXT NOT NULL DEFAULT '',
                export_config_json TEXT NOT NULL DEFAULT '{}',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (project_id) REFERENCES projects(project_id),
                FOREIGN KEY (source_model_id) REFERENCES model_versions(model_id)
            )
        """)

    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (_SCHEMA_VERSION,))
    conn.commit()
    conn.close()


def insert(table: str, data: dict[str, Any]) -> None:
    columns = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    conn = get_connection()
    conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        list(data.values()),
    )
    conn.commit()
    conn.close()


def fetch_one(table: str, id_value: str, id_column: str = "customer_id") -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        f"SELECT * FROM {table} WHERE {id_column} = ?", (id_value,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def fetch_all(
    table: str, where: str | None = None, params: tuple = ()
) -> list[dict[str, Any]]:
    conn = get_connection()
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update(
    table: str, id_value: str, data: dict[str, Any], id_column: str = "customer_id"
) -> None:
    from datetime import datetime
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    set_clause = ", ".join(f"{k} = ?" for k in data)
    conn = get_connection()
    conn.execute(
        f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?",
        list(data.values()) + [id_value],
    )
    conn.commit()
    conn.close()


def delete(table: str, id_value: str, id_column: str = "customer_id") -> None:
    conn = get_connection()
    conn.execute(f"DELETE FROM {table} WHERE {id_column} = ?", (id_value,))
    conn.commit()
    conn.close()
