"""Unified label classification policy.

Single source of truth for:
- Which labels are background (OK/IGNORE/INTERFERENCE)
- Which labels need human review (UNKNOWN/UNCERTAIN)
- Which labels are defects (everything else, needs bbox for YOLO)
"""

from __future__ import annotations

# Labels that represent acceptable / non-defect images.
# These images go into background / OK category and do NOT need bbox annotation.
BACKGROUND_LABELS: frozenset[str] = frozenset({"", "OK", "IGNORE", "INTERFERENCE"})

# Labels that need human review before they can be confidently classified.
REVIEW_LABELS: frozenset[str] = frozenset({"UNKNOWN", "UNCERTAIN"})

# ── Classification helpers ────────────────────────────────────────────


def normalize_label(label: str) -> str:
    """Normalize a label string to uppercase with whitespace stripped."""
    return label.strip().upper()


def is_background_label(label: str) -> bool:
    """True if the label is an acceptable background / non-defect tag."""
    return normalize_label(label) in BACKGROUND_LABELS


def is_review_label(label: str) -> bool:
    """True if the label needs human review (UNKNOWN / UNCERTAIN)."""
    return normalize_label(label) in REVIEW_LABELS


def is_defect_label(label: str) -> bool:
    """True if the label represents a confirmed defect (not background, not review).

    Only labels that are explicitly neither background nor review are defects.
    """
    normalized = normalize_label(label)
    if not normalized:
        return False
    return normalized not in BACKGROUND_LABELS and normalized not in REVIEW_LABELS


def needs_bbox(label: str) -> bool:
    """True if images with this label need bbox annotation for YOLO training."""
    return is_defect_label(label)


# ── Legacy-compatible sets (mutable, for code that iterates/checks) ──


def background_label_set() -> set[str]:
    """Return a mutable copy of background labels (for legacy compat)."""
    return set(BACKGROUND_LABELS)


def review_label_set() -> set[str]:
    """Return a mutable copy of review labels (for legacy compat)."""
    return set(REVIEW_LABELS)
