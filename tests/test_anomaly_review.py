"""Tests for core.anomaly_review — AnomalyReview CRUD + status transitions."""
from __future__ import annotations

import pytest


@pytest.fixture
def ctx():
    """Create parent rows needed for FK constraints."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    from core.field_session import create_field_session
    c = create_customer("AR Test Co", "ART")
    p = create_project(c.customer_id, "AR Test Proj")
    s = create_product_spec(p.project_id, "AR Spec", material="铜", geometry_type="管")
    fs = create_field_session(
        project_id=p.project_id,
        spec_id=s.spec_id,
        session_type="anomaly_exploration",
    )
    return {
        "project_id": p.project_id,
        "spec_id": s.spec_id,
        "field_session_id": fs.field_session_id,
    }


from core.anomaly_review import (  # noqa: E402
    AnomalyReview,
    create_anomaly_review,
    get_anomaly_review,
    list_anomaly_reviews,
    update_anomaly_review,
    delete_anomaly_review,
    confirm_as_defect,
)


# ── Dataclass ──────────────────────────────────────────────────────

def test_anomaly_review_requires_field_session_id():
    with pytest.raises(ValueError, match="field_session_id"):
        AnomalyReview(
            review_id="ARV_test",
            field_session_id="  ",
        )


def test_anomaly_review_rejects_invalid_status(ctx):
    with pytest.raises(ValueError, match="review_status"):
        AnomalyReview(
            review_id="ARV_test",
            field_session_id=ctx["field_session_id"],
            review_status="invalid_status",
        )


def test_anomaly_review_defaults(ctx):
    r = AnomalyReview(review_id="ARV_001", field_session_id=ctx["field_session_id"])
    assert r.review_status == "unreviewed"
    assert r.anomaly_score == 0.0
    assert r.cluster_id == ""
    assert r.assigned_defect_type_id is None


def test_anomaly_review_to_dict_round_trip(ctx):
    r = AnomalyReview(
        review_id="ARV_001",
        field_session_id=ctx["field_session_id"],
        image_path="/data/img01.png",
        anomaly_score=0.92,
        cluster_id="cluster_3",
        review_status="confirmed_defect",
        assigned_defect_type_id="DEF_SCRATCH",
        reviewer="张三",
        notes="明显的划痕缺陷",
    )
    d = r.to_dict()
    r2 = AnomalyReview.from_dict(d)
    assert r2.review_id == r.review_id
    assert r2.anomaly_score == 0.92
    assert r2.cluster_id == "cluster_3"
    assert r2.review_status == "confirmed_defect"
    assert r2.assigned_defect_type_id == "DEF_SCRATCH"
    assert r2.reviewer == "张三"


# ── CRUD ───────────────────────────────────────────────────────────

def test_create_and_get(ctx):
    r = create_anomaly_review(
        field_session_id=ctx["field_session_id"],
        image_path="/data/img01.png",
        anomaly_score=0.85,
        cluster_id="c1",
    )
    assert r.review_id.startswith("ARV_")
    assert r.review_status == "unreviewed"

    fetched = get_anomaly_review(r.review_id)
    assert fetched is not None
    assert fetched.anomaly_score == 0.85
    assert fetched.cluster_id == "c1"


def test_list_by_field_session(ctx):
    create_anomaly_review(field_session_id=ctx["field_session_id"], anomaly_score=0.7)
    create_anomaly_review(field_session_id=ctx["field_session_id"], anomaly_score=0.9)

    # Create a second field session for cross-check
    from core.field_session import create_field_session
    fs2 = create_field_session(
        project_id=ctx["project_id"],
        spec_id=ctx["spec_id"],
        session_type="anomaly_exploration",
    )
    create_anomaly_review(field_session_id=fs2.field_session_id, anomaly_score=0.3)

    reviews = list_anomaly_reviews(field_session_id=ctx["field_session_id"])
    assert len(reviews) >= 2


def test_list_by_status(ctx):
    create_anomaly_review(field_session_id=ctx["field_session_id"], anomaly_score=0.8)
    create_anomaly_review(field_session_id=ctx["field_session_id"], anomaly_score=0.9)
    create_anomaly_review(field_session_id=ctx["field_session_id"], anomaly_score=0.6)

    unreviewed = list_anomaly_reviews(
        field_session_id=ctx["field_session_id"], review_status="unreviewed"
    )
    assert len(unreviewed) >= 3


def test_update_review(ctx):
    r = create_anomaly_review(field_session_id=ctx["field_session_id"], anomaly_score=0.5)
    updated = update_anomaly_review(
        r.review_id,
        review_status="confirmed_defect",
        anomaly_score=0.95,
    )
    assert updated is not None
    assert updated.review_status == "confirmed_defect"
    assert updated.anomaly_score == 0.95


def test_update_nonexistent():
    result = update_anomaly_review("ARV_NOPE", review_status="normal")
    assert result is None


def test_update_rejects_invalid_review_status(ctx):
    """P1.2: update must re-validate and reject illegal status."""
    r = create_anomaly_review(field_session_id=ctx["field_session_id"])
    with pytest.raises(ValueError, match="review_status"):
        update_anomaly_review(r.review_id, review_status="invalid_status")


def test_delete(ctx):
    r = create_anomaly_review(field_session_id=ctx["field_session_id"])
    delete_anomaly_review(r.review_id)
    assert get_anomaly_review(r.review_id) is None


# ── Status transitions ─────────────────────────────────────────────

def test_transition_unreviewed_to_confirmed_defect(ctx):
    from core.defect_dictionary import create_defect_type
    dt = create_defect_type(
        project_id=ctx["project_id"], code="DEF01", display_name_zh="缺陷01"
    )
    r = create_anomaly_review(field_session_id=ctx["field_session_id"])
    updated = update_anomaly_review(
        r.review_id,
        review_status="confirmed_defect",
        assigned_defect_type_id=dt.defect_type_id,
        reviewer="李四",
    )
    assert updated.review_status == "confirmed_defect"
    assert updated.assigned_defect_type_id == dt.defect_type_id
    assert updated.reviewer == "李四"


def test_transition_unreviewed_to_noise(ctx):
    r = create_anomaly_review(field_session_id=ctx["field_session_id"])
    updated = update_anomaly_review(r.review_id, review_status="noise_or_reflection")
    assert updated.review_status == "noise_or_reflection"


def test_transition_unreviewed_to_unknown_pending(ctx):
    r = create_anomaly_review(field_session_id=ctx["field_session_id"])
    updated = update_anomaly_review(r.review_id, review_status="unknown_pending")
    assert updated.review_status == "unknown_pending"


def test_transition_unreviewed_to_acceptable_texture(ctx):
    r = create_anomaly_review(field_session_id=ctx["field_session_id"])
    updated = update_anomaly_review(r.review_id, review_status="acceptable_texture")
    assert updated.review_status == "acceptable_texture"


def test_transition_unreviewed_to_normal(ctx):
    r = create_anomaly_review(field_session_id=ctx["field_session_id"])
    updated = update_anomaly_review(r.review_id, review_status="normal")
    assert updated.review_status == "normal"


# ── Convenience: confirm_as_defect ─────────────────────────────────

def test_confirm_as_defect(ctx):
    from core.defect_dictionary import create_defect_type
    dt = create_defect_type(
        project_id=ctx["project_id"], code="SCRATCH", display_name_zh="划痕"
    )
    r = create_anomaly_review(field_session_id=ctx["field_session_id"], anomaly_score=0.88)
    result = confirm_as_defect(r.review_id, defect_type_id=dt.defect_type_id, reviewer="王五")
    assert result is not None
    assert result.review_status == "confirmed_defect"
    assert result.assigned_defect_type_id == dt.defect_type_id
    assert result.reviewer == "王五"
    assert result.reviewed_at is not None


def test_confirm_as_defect_nonexistent():
    result = confirm_as_defect("ARV_NOPE", "DEF_X", "tester")
    assert result is None


# ── All valid review statuses ──────────────────────────────────────

@pytest.mark.parametrize("status", [
    "unreviewed",
    "confirmed_defect",
    "acceptable_texture",
    "noise_or_reflection",
    "normal",
    "unknown_pending",
])
def test_all_valid_review_statuses(ctx, status):
    r = AnomalyReview(
        review_id="ARV_VALID",
        field_session_id=ctx["field_session_id"],
        review_status=status,
    )
    assert r.review_status == status
