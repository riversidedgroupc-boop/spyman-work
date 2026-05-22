"""Tests for core/label_policy.py — unified label classification."""
from __future__ import annotations

import pytest

from core.label_policy import (
    BACKGROUND_LABELS,
    REVIEW_LABELS,
    normalize_label,
    is_background_label,
    is_review_label,
    is_defect_label,
    needs_bbox,
    background_label_set,
    review_label_set,
)


# ── Constants ─────────────────────────────────────────────────────


def test_background_labels_are_frozenset():
    assert isinstance(BACKGROUND_LABELS, frozenset)


def test_review_labels_are_frozenset():
    assert isinstance(REVIEW_LABELS, frozenset)


def test_background_labels_contains_expected():
    assert "" in BACKGROUND_LABELS
    assert "OK" in BACKGROUND_LABELS
    assert "IGNORE" in BACKGROUND_LABELS
    assert "INTERFERENCE" in BACKGROUND_LABELS


def test_review_labels_contains_expected():
    assert "UNKNOWN" in REVIEW_LABELS
    assert "UNCERTAIN" in REVIEW_LABELS


def test_review_labels_not_in_background():
    """Review labels are separate from background labels."""
    for label in REVIEW_LABELS:
        assert label not in BACKGROUND_LABELS


# ── normalize_label ───────────────────────────────────────────────


def test_normalize_label_strips_and_uppercases():
    assert normalize_label(" ok ") == "OK"
    assert normalize_label("Unknown") == "UNKNOWN"
    assert normalize_label("裂纹") == "裂纹"
    assert normalize_label("") == ""


# ── is_background_label ───────────────────────────────────────────


@pytest.mark.parametrize("label", ["OK", "ok", " OK ", "IGNORE", "ignore", "INTERFERENCE", "interference", ""])
def test_is_background_label_true(label: str):
    assert is_background_label(label) is True


@pytest.mark.parametrize("label", ["裂纹", "UNKNOWN", "UNCERTAIN", "NG_A", "油污"])
def test_is_background_label_false(label: str):
    assert is_background_label(label) is False


# ── is_review_label ───────────────────────────────────────────────


@pytest.mark.parametrize("label", ["UNKNOWN", "unknown", " UNKNOWN ", "UNCERTAIN", "uncertain"])
def test_is_review_label_true(label: str):
    assert is_review_label(label) is True


@pytest.mark.parametrize("label", ["OK", "裂纹", "IGNORE", "INTERFERENCE", ""])
def test_is_review_label_false(label: str):
    assert is_review_label(label) is False


# ── is_defect_label ───────────────────────────────────────────────


@pytest.mark.parametrize("label", ["裂纹", "油污", "NG-A", "NG_B", "点伤", "scratch"])
def test_is_defect_label_true(label: str):
    assert is_defect_label(label) is True


@pytest.mark.parametrize("label", ["OK", "ok", "IGNORE", "INTERFERENCE", "UNKNOWN", "UNCERTAIN", ""])
def test_is_defect_label_false(label: str):
    assert is_defect_label(label) is False


# ── needs_bbox ────────────────────────────────────────────────────


def test_needs_bbox_alias():
    """needs_bbox is an alias for is_defect_label."""
    assert needs_bbox("裂纹") is True
    assert needs_bbox("OK") is False
    assert needs_bbox("UNKNOWN") is False


# ── Legacy-compatible sets ────────────────────────────────────────


def test_background_label_set_mutable():
    s = background_label_set()
    assert isinstance(s, set)
    assert "" in s
    assert "OK" in s
    # Can mutate
    s.add("TEST")
    assert "TEST" in s


def test_review_label_set_mutable():
    s = review_label_set()
    assert isinstance(s, set)
    assert "UNKNOWN" in s


# ── Integration: matches existing dataset_validation expectations ──


def test_backward_compat_with_dataset_validation():
    """Verify label_policy matches the old _is_ng_label / _is_ok_label behavior."""
    # Old _is_ng_label: rejects OK, UNKNOWN, INTERFERENCE, UNCERTAIN, IGNORE, ""
    for label in ["OK", "UNKNOWN", "INTERFERENCE", "UNCERTAIN", "IGNORE", ""]:
        assert is_defect_label(label) is False, f"{label} should NOT be defect"

    # Old _is_ng_label: accepts any non-background label
    for label in ["裂纹", "油污", "NG-点伤"]:
        assert is_defect_label(label) is True, f"{label} should be defect"

    # Old _is_ok_label: accepts OK/UNKNOWN/INTERFERENCE/UNCERTAIN/IGNORE/""
    for label in ["OK", "UNKNOWN", "INTERFERENCE", "UNCERTAIN", "IGNORE", ""]:
        assert (is_background_label(label) or is_review_label(label)) is True


# ── Edge cases ────────────────────────────────────────────────────


def test_empty_whitespace_is_background():
    assert is_background_label("   ") is True


def test_none_label_behavior():
    """is_defect_label with None would raise AttributeError — callers must guard."""
    with pytest.raises(AttributeError):
        is_defect_label(None)  # type: ignore[arg-type]


def test_custom_label_is_defect():
    """Any label not in background or review is treated as defect."""
    assert is_defect_label("CUSTOM_DEFECT_TYPE") is True
    assert is_defect_label("scratch") is True
