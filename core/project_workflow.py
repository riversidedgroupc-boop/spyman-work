"""Project workflow state derivation.

Derives the current workflow state from existing database records rather than
storing fragile manual flags. Used by project center, field workflow page, and
navigation gating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class WorkflowState(Enum):
    NEW_PROJECT = "new_project"
    DEVICE_CONFIG_REQUIRED = "device_config_required"
    DEVICE_CONFIGURED = "device_configured"
    INITIAL_CAPTURE_READY = "initial_capture_ready"
    INITIAL_CAPTURE_DONE = "initial_capture_done"
    MANUAL_TRIAGE_DONE = "manual_triage_done"
    UNSUPERVISED_READY = "unsupervised_ready"
    UNSUPERVISED_TRAINED = "unsupervised_trained"
    ASSISTED_CAPTURE_READY = "assisted_capture_ready"
    ANOMALY_REVIEW_PENDING = "anomaly_review_pending"
    YOLO_ANNOTATION_READY = "yolo_annotation_ready"
    YOLO_TRAINING_READY = "yolo_training_ready"
    YOLO_TRAINED = "yolo_trained"
    HYBRID_CAPTURE_READY = "hybrid_capture_ready"
    ITERATION_ACTIVE = "iteration_active"
    BENCHMARK_READY = "benchmark_ready"
    ACCEPTANCE_READY = "acceptance_ready"


@dataclass
class WorkflowStatus:
    state: WorkflowState
    display_key: str  # i18n key
    next_action: str  # human-readable next step
    available_actions: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    @property
    def is_blocked(self) -> bool:
        return self.state in (
            WorkflowState.NEW_PROJECT,
            WorkflowState.DEVICE_CONFIG_REQUIRED,
        )


_STATE_DISPLAY: dict[WorkflowState, str] = {
    WorkflowState.NEW_PROJECT: "workflow.state_new_project",
    WorkflowState.DEVICE_CONFIG_REQUIRED: "workflow.state_device_config_required",
    WorkflowState.DEVICE_CONFIGURED: "workflow.state_device_configured",
    WorkflowState.INITIAL_CAPTURE_READY: "workflow.state_initial_capture_ready",
    WorkflowState.INITIAL_CAPTURE_DONE: "workflow.state_initial_capture_done",
    WorkflowState.MANUAL_TRIAGE_DONE: "workflow.state_manual_triage_done",
    WorkflowState.UNSUPERVISED_READY: "workflow.state_unsupervised_ready",
    WorkflowState.UNSUPERVISED_TRAINED: "workflow.state_unsupervised_trained",
    WorkflowState.ASSISTED_CAPTURE_READY: "workflow.state_assisted_capture_ready",
    WorkflowState.ANOMALY_REVIEW_PENDING: "workflow.state_anomaly_review_pending",
    WorkflowState.YOLO_ANNOTATION_READY: "workflow.state_yolo_annotation_ready",
    WorkflowState.YOLO_TRAINING_READY: "workflow.state_yolo_training_ready",
    WorkflowState.YOLO_TRAINED: "workflow.state_yolo_trained",
    WorkflowState.HYBRID_CAPTURE_READY: "workflow.state_hybrid_capture_ready",
    WorkflowState.ITERATION_ACTIVE: "workflow.state_iteration_active",
    WorkflowState.BENCHMARK_READY: "workflow.state_benchmark_ready",
    WorkflowState.ACCEPTANCE_READY: "workflow.state_acceptance_ready",
}


def derive_workflow_status(project_id: str) -> WorkflowStatus:
    """Derive the current workflow state for a project from existing data."""

    if not project_id:
        return WorkflowStatus(
            state=WorkflowState.NEW_PROJECT,
            display_key=_STATE_DISPLAY[WorkflowState.NEW_PROJECT],
            next_action="Create or select a project",
            blocked_actions=["start_capture", "train_model"],
        )

    # Collect evidence
    has_spec = _has_product_spec(project_id)
    has_device_config = _has_device_config(project_id)
    has_capture = _has_capture_session(project_id)
    has_ok_samples = _has_ok_samples(project_id)
    has_ng_samples = _has_ng_samples(project_id)
    has_classifications = _has_classifications(project_id)
    has_unsupervised_model = _has_model_of_type(project_id, "patchcore")
    has_field_session = _has_field_session(project_id)
    has_anomaly_reviews = _has_anomaly_reviews(project_id)
    has_confirmed_defects = _has_confirmed_defects(project_id)
    has_yolo_model = _has_model_of_type(project_id, "yolo")
    has_defect_types = _has_defect_types(project_id)
    has_hybrid_detection = _has_hybrid_detection_records(project_id)

    details = {
        "has_spec": has_spec,
        "has_device_config": has_device_config,
        "has_capture": has_capture,
        "has_ok_samples": has_ok_samples,
        "has_ng_samples": has_ng_samples,
        "has_classifications": has_classifications,
        "has_unsupervised_model": has_unsupervised_model,
        "has_field_session": has_field_session,
        "has_anomaly_reviews": has_anomaly_reviews,
        "has_confirmed_defects": has_confirmed_defects,
        "has_yolo_model": has_yolo_model,
        "has_defect_types": has_defect_types,
        "has_hybrid_detection": has_hybrid_detection,
    }

    # --- Derive state ---

    # Base: need product spec
    if not has_spec:
        return WorkflowStatus(
            state=WorkflowState.NEW_PROJECT,
            display_key=_STATE_DISPLAY[WorkflowState.NEW_PROJECT],
            next_action="Create a product specification (material, geometry, line speed)",
            available_actions=["create_spec"],
            blocked_actions=["start_capture", "train_model"],
            details=details,
        )

    # Device config
    if not has_device_config:
        return WorkflowStatus(
            state=WorkflowState.DEVICE_CONFIG_REQUIRED,
            display_key=_STATE_DISPLAY[WorkflowState.DEVICE_CONFIG_REQUIRED],
            next_action="Configure device and camera settings for this product spec",
            available_actions=["configure_device"],
            blocked_actions=["start_capture"],
            details=details,
        )

    # Device configured but no capture yet
    if not has_capture:
        return WorkflowStatus(
            state=WorkflowState.DEVICE_CONFIGURED,
            display_key=_STATE_DISPLAY[WorkflowState.DEVICE_CONFIGURED],
            next_action="Start a baseline image capture session",
            available_actions=["start_capture"],
            blocked_actions=["train_model"],
            details=details,
        )

    # Has capture but no human classification yet
    if has_capture and not has_classifications:
        return WorkflowStatus(
            state=WorkflowState.INITIAL_CAPTURE_READY,
            display_key=_STATE_DISPLAY[WorkflowState.INITIAL_CAPTURE_READY],
            next_action="Capture complete — classify samples as OK / NG / Uncertain",
            available_actions=["classify_samples"],
            blocked_actions=["train_unsupervised"],
            details=details,
        )

    # Has capture + classifications
    if has_capture and has_classifications:
        # Without OK samples, can't train unsupervised
        if not has_ok_samples:
            return WorkflowStatus(
                state=WorkflowState.INITIAL_CAPTURE_DONE,
                display_key=_STATE_DISPLAY[WorkflowState.INITIAL_CAPTURE_DONE],
                next_action="Mark at least some samples as OK to enable training",
                available_actions=["classify_samples"],
                blocked_actions=["train_unsupervised"],
                details=details,
            )

        # Have OK samples — check unsupervised
        if has_ok_samples and not has_unsupervised_model:
            return WorkflowStatus(
                state=WorkflowState.MANUAL_TRIAGE_DONE,
                display_key=_STATE_DISPLAY[WorkflowState.MANUAL_TRIAGE_DONE],
                next_action="Train unsupervised (PatchCore) model using OK baseline samples",
                available_actions=["train_unsupervised", "start_field_session"],
                blocked_actions=["assisted_capture"],
                details=details,
            )

        # Unsupervised model exists
        if has_unsupervised_model:
            if not has_field_session:
                return WorkflowStatus(
                    state=WorkflowState.UNSUPERVISED_TRAINED,
                    display_key=_STATE_DISPLAY[WorkflowState.UNSUPERVISED_TRAINED],
                    next_action="Start a field session for anomaly-assisted capture",
                    available_actions=["start_field_session", "assisted_capture"],
                    blocked_actions=["train_yolo"],
                    details=details,
                )

            # Field session exists but no reviews
            if has_field_session and not has_anomaly_reviews:
                return WorkflowStatus(
                    state=WorkflowState.ASSISTED_CAPTURE_READY,
                    display_key=_STATE_DISPLAY[WorkflowState.ASSISTED_CAPTURE_READY],
                    next_action="Run anomaly-assisted capture to find suspicious samples",
                    available_actions=["assisted_capture", "review_anomalies"],
                    blocked_actions=["train_yolo"],
                    details=details,
                )

            # Reviews exist but no confirmed defects
            if has_anomaly_reviews and not has_confirmed_defects:
                return WorkflowStatus(
                    state=WorkflowState.ANOMALY_REVIEW_PENDING,
                    display_key=_STATE_DISPLAY[WorkflowState.ANOMALY_REVIEW_PENDING],
                    next_action="Review anomaly candidates — confirm real defects",
                    available_actions=["review_anomalies", "create_defect_types"],
                    blocked_actions=["train_yolo"],
                    details=details,
                )

            # Confirmed defects but no defect types
            if has_confirmed_defects and not has_defect_types:
                return WorkflowStatus(
                    state=WorkflowState.YOLO_ANNOTATION_READY,
                    display_key=_STATE_DISPLAY[WorkflowState.YOLO_ANNOTATION_READY],
                    next_action="Define defect types and annotate bounding boxes on confirmed defects",
                    available_actions=["create_defect_types", "annotate_bbox"],
                    blocked_actions=["train_yolo"],
                    details=details,
                )

            # Defect types exist but no YOLO model yet
            if has_defect_types and not has_yolo_model:
                return WorkflowStatus(
                    state=WorkflowState.YOLO_TRAINING_READY,
                    display_key=_STATE_DISPLAY[WorkflowState.YOLO_TRAINING_READY],
                    next_action="Generate YOLO dataset from reviewed defects and train YOLO model",
                    available_actions=["generate_dataset", "train_yolo"],
                    blocked_actions=["hybrid_capture"],
                    details=details,
                )

            # YOLO model exists
            if has_yolo_model:
                return WorkflowStatus(
                    state=WorkflowState.YOLO_TRAINED,
                    display_key=_STATE_DISPLAY[WorkflowState.YOLO_TRAINED],
                    next_action="Start hybrid capture with YOLO + unsupervised detection",
                    available_actions=["hybrid_capture", "benchmark", "export_model"],
                    blocked_actions=[],
                    details=details,
                )

    # Catch-all: if we get here, iteration is active
    return WorkflowStatus(
        state=WorkflowState.ITERATION_ACTIVE,
        display_key=_STATE_DISPLAY[WorkflowState.ITERATION_ACTIVE],
        next_action="Continue model iteration — collect more samples, retrain, benchmark",
        available_actions=["capture", "train", "benchmark", "export"],
        blocked_actions=[],
        details=details,
    )


# ── Evidence helpers ──────────────────────────────────────────────────

def _has_product_spec(project_id: str) -> bool:
    from core.storage import fetch_all
    rows = fetch_all("product_specs", where="project_id = ?", params=(project_id,))
    return len(rows) > 0


def _has_device_config(project_id: str) -> bool:
    from core.storage import fetch_all
    specs = fetch_all("product_specs", where="project_id = ?", params=(project_id,))
    if not specs:
        return False
    for spec in specs:
        rows = fetch_all("camera_configs", where="spec_id = ?", params=(spec["spec_id"],))
        if rows:
            return True
    return False


def _has_capture_session(project_id: str) -> bool:
    from core.storage import fetch_all
    rows = fetch_all("capture_sessions", where="project_id = ?", params=(project_id,))
    return len(rows) > 0


def _has_classifications(project_id: str) -> bool:
    from core.storage import fetch_all
    rows = fetch_all(
        "captured_images",
        where="project_id = ? AND classification_label != '' AND classification_label IS NOT NULL",
        params=(project_id,),
    )
    return len(rows) > 0


def _has_ok_samples(project_id: str) -> bool:
    from core.storage import fetch_all
    from core.label_policy import is_background_label
    rows = fetch_all(
        "captured_images",
        where="project_id = ? AND classification_label != '' AND classification_label IS NOT NULL",
        params=(project_id,),
    )
    return any(is_background_label(r.get("classification_label", "")) for r in rows)


def _has_ng_samples(project_id: str) -> bool:
    from core.storage import fetch_all
    from core.label_policy import is_background_label
    rows = fetch_all(
        "captured_images",
        where="project_id = ? AND classification_label != '' AND classification_label IS NOT NULL",
        params=(project_id,),
    )
    return any(not is_background_label(r.get("classification_label", "")) for r in rows)


def _has_model_of_type(project_id: str, model_type: str) -> bool:
    from core.storage import fetch_all
    rows = fetch_all(
        "model_versions",
        where="project_id = ? AND model_type = ? AND status IN ('completed', 'candidate', 'active')",
        params=(project_id, model_type),
    )
    return len(rows) > 0


def _has_field_session(project_id: str) -> bool:
    from core.storage import fetch_all
    rows = fetch_all("field_sessions", where="project_id = ?", params=(project_id,))
    return len(rows) > 0


def _has_anomaly_reviews(project_id: str) -> bool:
    from core.storage import get_connection
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM anomaly_reviews ar "
        "JOIN field_sessions fs ON ar.field_session_id = fs.field_session_id "
        "WHERE fs.project_id = ?",
        (project_id,),
    ).fetchone()
    conn.close()
    return row["cnt"] > 0 if row else False


def _has_confirmed_defects(project_id: str) -> bool:
    from core.storage import get_connection
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM anomaly_reviews ar "
        "JOIN field_sessions fs ON ar.field_session_id = fs.field_session_id "
        "WHERE fs.project_id = ? AND ar.review_status = 'confirmed_defect'",
        (project_id,),
    ).fetchone()
    conn.close()
    return row["cnt"] > 0 if row else False


def _has_defect_types(project_id: str) -> bool:
    from core.storage import fetch_all
    rows = fetch_all("defect_types", where="project_id = ?", params=(project_id,))
    return len(rows) > 0


def _has_hybrid_detection_records(project_id: str) -> bool:
    """Check whether real detection or retest results exist (not just field sessions)."""
    from core.storage import fetch_all
    rows = fetch_all(
        "production_defect_events", where="project_id = ?", params=(project_id,)
    )
    if len(rows) > 0:
        return True
    rows = fetch_all(
        "hybrid_retest_runs", where="project_id = ?", params=(project_id,)
    )
    return len(rows) > 0
