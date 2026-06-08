"""Cascade delete operations for customer/project/spec hierarchies.

All deletes run inside a single DB transaction per top-level call.
Leaf-to-root order ensures FK constraints are never violated.
Only deletes database rows — never touches disk files or model artifacts.
"""

from __future__ import annotations

import sqlite3

from core.storage import get_connection


def delete_spec_cascade(spec_id: str) -> None:
    """Delete a product spec and all its child data.

    Deletes: camera_configs, capture_sessions/captured_images,
    field_sessions/anomaly_reviews, hybrid_retest_runs/items,
    training_jobs/model_versions/model_export_artifacts,
    dataset_versions, production_defect_events, defect_types,
    then the spec itself.
    """
    conn = get_connection()
    try:
        _delete_spec_cascade(conn, spec_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _delete_spec_cascade(conn: sqlite3.Connection, spec_id: str) -> None:
    # 1 — Leaf: captured_images → capture_sessions
    session_rows = conn.execute(
        "SELECT session_id FROM capture_sessions WHERE spec_id = ?", (spec_id,)
    ).fetchall()
    for (sid,) in session_rows:
        conn.execute("DELETE FROM captured_images WHERE session_id = ?", (sid,))
    conn.execute("DELETE FROM capture_sessions WHERE spec_id = ?", (spec_id,))

    # 2 — Leaf: anomaly_reviews → field_sessions
    field_rows = conn.execute(
        "SELECT field_session_id FROM field_sessions WHERE spec_id = ?", (spec_id,)
    ).fetchall()
    for (fid,) in field_rows:
        conn.execute("DELETE FROM anomaly_reviews WHERE field_session_id = ?", (fid,))
    conn.execute("DELETE FROM field_sessions WHERE spec_id = ?", (spec_id,))

    # 3 — Leaf: hybrid_retest_items → hybrid_retest_runs
    run_rows = conn.execute(
        "SELECT run_id FROM hybrid_retest_runs WHERE spec_id = ?", (spec_id,)
    ).fetchall()
    for (rid,) in run_rows:
        conn.execute("DELETE FROM hybrid_retest_items WHERE run_id = ?", (rid,))
    conn.execute("DELETE FROM hybrid_retest_runs WHERE spec_id = ?", (spec_id,))

    # 4 — Leaf: model_export_artifacts → model_versions → training_jobs
    job_rows = conn.execute(
        "SELECT job_id FROM training_jobs WHERE spec_id = ?", (spec_id,)
    ).fetchall()
    job_ids = [r[0] for r in job_rows]
    if job_ids:
        placeholders = ",".join("?" * len(job_ids))
        model_rows = conn.execute(
            f"SELECT model_id FROM model_versions WHERE training_job_id IN ({placeholders})",
            job_ids,
        ).fetchall()
        for (mid,) in model_rows:
            conn.execute("DELETE FROM model_export_artifacts WHERE source_model_id = ?", (mid,))
        conn.execute(
            f"DELETE FROM model_versions WHERE training_job_id IN ({placeholders})", job_ids
        )
    conn.execute("DELETE FROM training_jobs WHERE spec_id = ?", (spec_id,))

    # 5 — Standalone spec-level tables
    conn.execute("DELETE FROM dataset_versions WHERE spec_id = ?", (spec_id,))
    conn.execute("DELETE FROM production_defect_events WHERE spec_id = ?", (spec_id,))
    conn.execute("DELETE FROM defect_types WHERE spec_id = ?", (spec_id,))
    conn.execute("DELETE FROM camera_configs WHERE spec_id = ?", (spec_id,))

    # 6 — The spec itself
    conn.execute("DELETE FROM product_specs WHERE spec_id = ?", (spec_id,))


def delete_project_cascade(project_id: str) -> None:
    """Delete a project, all its specs, and all project-level data.

    Deletes every spec under the project (each with full spec cascade),
    then project-scoped rows: remaining model_versions, model_export_artifacts,
    hybrid_retest_runs/items, sample_library_entries, captured_images,
    capture_sessions, dataset_versions, production_defect_events,
    field_sessions, defect_types, training_jobs, then the project itself.
    """
    conn = get_connection()
    try:
        _delete_project_cascade(conn, project_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _delete_project_cascade(conn: sqlite3.Connection, project_id: str) -> None:
    # 1 — Cascade-delete every spec under this project
    spec_rows = conn.execute(
        "SELECT spec_id FROM product_specs WHERE project_id = ?", (project_id,)
    ).fetchall()
    for (sid,) in spec_rows:
        _delete_spec_cascade(conn, sid)

    # 2 — Remaining project-level children (not already deleted via spec cascade)
    # hybrid_retest_runs / items
    run_rows = conn.execute(
        "SELECT run_id FROM hybrid_retest_runs WHERE project_id = ?", (project_id,)
    ).fetchall()
    for (rid,) in run_rows:
        conn.execute("DELETE FROM hybrid_retest_items WHERE run_id = ?", (rid,))
    conn.execute("DELETE FROM hybrid_retest_runs WHERE project_id = ?", (project_id,))

    # model_export_artifacts (project-level, possibly no model FK set)
    conn.execute("DELETE FROM model_export_artifacts WHERE project_id = ?", (project_id,))

    # model_versions not tied to a training job
    conn.execute("DELETE FROM model_versions WHERE project_id = ?", (project_id,))

    # sample_library_entries
    conn.execute("DELETE FROM sample_library_entries WHERE current_project_id = ?", (project_id,))

    # Remaining project-level tables (in case not already swept by spec cascade)
    conn.execute("DELETE FROM captured_images WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM capture_sessions WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM dataset_versions WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM production_defect_events WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM field_sessions WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM defect_types WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM training_jobs WHERE project_id = ?", (project_id,))

    # 3 — The project itself
    conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))


def delete_customer_cascade(customer_id: str) -> None:
    """Delete a customer, all its projects, and all cascaded data.

    Finds all projects under the customer, runs project-level cascade
    for each, then deletes the customer row.  Wrapped in a single
    transaction so a failure at any point rolls back fully.
    """
    conn = get_connection()
    try:
        project_rows = conn.execute(
            "SELECT project_id FROM projects WHERE customer_id = ?", (customer_id,)
        ).fetchall()
        for (pid,) in project_rows:
            _delete_project_cascade(conn, pid)
        conn.execute("DELETE FROM customers WHERE customer_id = ?", (customer_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
