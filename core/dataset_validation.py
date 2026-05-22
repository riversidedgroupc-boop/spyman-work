"""Unified dataset validation for YOLO detection / classification / anomaly detection."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from core.capture_session import list_captured_images, get_capture_session
from core.label_policy import is_background_label, is_defect_label, is_review_label


@dataclass
class DatasetValidationResult:
    """Result of validating a capture session for a given task type."""

    task_type: str = ""  # yolo_detection / image_classification / anomaly_detection
    total_images: int = 0
    ok_images: int = 0
    ng_images: int = 0
    unlabeled_images: int = 0
    review_images: int = 0
    missing_bbox_ng_images: int = 0  # YOLO only
    missing_bbox_paths: list[str] = field(default_factory=list)  # YOLO only
    class_distribution: dict[str, int] = field(default_factory=dict)
    can_train: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines: list[str] = []
        lines.append(f"Task: {self.task_type}")
        lines.append(f"Total images: {self.total_images}")
        lines.append(
            f"OK: {self.ok_images}  NG: {self.ng_images}  "
            f"Review: {self.review_images}  Unlabeled: {self.unlabeled_images}"
        )
        if self.missing_bbox_ng_images:
            lines.append(f"NG images missing bbox: {self.missing_bbox_ng_images}")
        if self.class_distribution:
            dist = ", ".join(f"{k}={v}" for k, v in sorted(self.class_distribution.items()))
            lines.append(f"Classes: {dist}")
        lines.append(f"Can train: {'YES' if self.can_train else 'NO'}")
        if self.errors:
            lines.append("Errors: " + "; ".join(self.errors))
        if self.warnings:
            lines.append("Warnings: " + "; ".join(self.warnings))
        return "\n".join(lines)


def _is_ng_label(label: str) -> bool:
    """Check if a classification label indicates a defect (not background)."""
    return is_defect_label(label)


def _is_ok_label(label: str) -> bool:
    """Check if a classification label indicates OK/background."""
    return is_background_label(label)


def _find_sidecar_txt(image_path: str) -> str:
    """Find the YOLO .txt sidecar file for an image. Returns path or empty string."""
    stem, _ = os.path.splitext(image_path)
    txt_path = stem + ".txt"
    if os.path.isfile(txt_path):
        return txt_path
    return ""


def _has_bboxes(image_path: str) -> bool:
    """Check if a YOLO .txt sidecar exists and contains at least one bbox."""
    txt_path = _find_sidecar_txt(image_path)
    if not txt_path:
        return False
    try:
        text = open(txt_path, encoding="utf-8").read().strip()
        if not text:
            return False
        for line in text.splitlines():
            line = line.strip()
            if line and len(line.split()) >= 5:
                return True
    except Exception:
        return False
    return False


def validate_yolo_detection(session_id: str) -> DatasetValidationResult:
    """Validate a session for YOLO detection training.

    Rules:
    - NG images must have at least one bbox in the sidecar .txt
    - OK images without bbox are fine (background samples)
    - Can train only if no NG image is missing its bbox
    """
    result = DatasetValidationResult(task_type="yolo_detection")
    session = get_capture_session(session_id)
    if session is None:
        result.errors.append(f"Session not found: {session_id}")
        return result

    rows = list_captured_images(session_id)
    result.total_images = len(rows)

    for r in rows:
        label = r.get("classification_label", "").strip()
        path = r.get("image_path", "")

        # Count distribution
        key = label or "(unlabeled)"
        result.class_distribution[key] = result.class_distribution.get(key, 0) + 1

        if not label:
            result.unlabeled_images += 1
            continue

        if is_review_label(label):
            result.review_images += 1
        elif _is_ok_label(label):
            result.ok_images += 1
        elif _is_ng_label(label):
            result.ng_images += 1
            # Check bbox for NG image
            if not _has_bboxes(path):
                result.missing_bbox_ng_images += 1
                result.missing_bbox_paths.append(path)

    # Assessment
    if result.total_images == 0:
        result.can_train = False
        result.errors.append("No images in session")
    elif result.review_images > 0:
        result.can_train = False
        result.errors.append(
            f"{result.review_images} review image(s) require classification before YOLO training"
        )
    elif result.missing_bbox_ng_images > 0:
        result.can_train = False
        result.errors.append(
            f"{result.missing_bbox_ng_images} NG image(s) missing bbox annotations"
        )
    elif result.ng_images == 0:
        result.can_train = False
        result.errors.append("No NG images available for YOLO detection training")
    elif result.ok_images == 0:
        result.warnings.append("No OK/background images — training may be biased")
        result.can_train = True
    else:
        result.can_train = True

    if result.unlabeled_images > 0:
        result.warnings.append(
            f"{result.unlabeled_images} unlabeled images — will be treated as background"
        )

    return result


def validate_image_classification(session_id: str) -> DatasetValidationResult:
    """Validate a session for image classification training.

    Rules:
    - All images must have a label
    - Must have at least 2 classes
    - Each class must have at least 1 image
    """
    result = DatasetValidationResult(task_type="image_classification")
    session = get_capture_session(session_id)
    if session is None:
        result.errors.append(f"Session not found: {session_id}")
        return result

    rows = list_captured_images(session_id)
    result.total_images = len(rows)

    for r in rows:
        label = r.get("classification_label", "").strip()

        key = label or "(unlabeled)"
        result.class_distribution[key] = result.class_distribution.get(key, 0) + 1

        if not label:
            result.unlabeled_images += 1
        elif is_review_label(label):
            result.review_images += 1
        elif _is_ok_label(label):
            result.ok_images += 1
        elif _is_ng_label(label):
            result.ng_images += 1

    # Assessment
    if result.total_images == 0:
        result.can_train = False
        result.errors.append("No images in session")
    elif result.review_images > 0:
        result.can_train = False
        result.errors.append(
            f"{result.review_images} review image(s) require final labels"
        )
    elif result.unlabeled_images > 0:
        result.can_train = False
        result.errors.append(
            f"{result.unlabeled_images} unlabeled image(s) — all images must have labels"
        )
    else:
        class_count = len([k for k in result.class_distribution if k != "(unlabeled)"])
        if class_count < 2:
            result.can_train = False
            result.errors.append("Need at least 2 classes for classification training")
        else:
            result.can_train = True

    return result


def validate_anomaly_detection(session_id: str) -> DatasetValidationResult:
    """Validate a session for anomaly detection (PatchCore) training.

    Rules:
    - Training uses OK images only
    - Need at least 10 OK images for training
    - NG images go to validation/test (warning if missing, not a blocker)
    """
    result = DatasetValidationResult(task_type="anomaly_detection")
    session = get_capture_session(session_id)
    if session is None:
        result.errors.append(f"Session not found: {session_id}")
        return result

    rows = list_captured_images(session_id)
    result.total_images = len(rows)

    for r in rows:
        label = r.get("classification_label", "").strip()
        key = label or "(unlabeled)"
        result.class_distribution[key] = result.class_distribution.get(key, 0) + 1

        if not label:
            result.unlabeled_images += 1
        elif is_review_label(label):
            result.review_images += 1
        elif _is_ok_label(label):
            result.ok_images += 1
        elif _is_ng_label(label):
            result.ng_images += 1

    # Assessment
    if result.total_images == 0:
        result.can_train = False
        result.errors.append("No images in session")
    elif result.review_images > 0:
        result.can_train = False
        result.errors.append(
            f"{result.review_images} review image(s) require final labels before anomaly training"
        )
    elif result.ok_images < 10:
        result.can_train = False
        result.errors.append(
            f"Only {result.ok_images} OK images — need at least 10 for anomaly detection training"
        )
    elif result.ng_images == 0:
        result.warnings.append("No NG images for validation — anomaly detection will have no defect test set")
        result.can_train = True
    else:
        result.can_train = True

    if result.unlabeled_images > 0:
        result.warnings.append(
            f"{result.unlabeled_images} unlabeled images — will be excluded from training"
        )

    return result


def validate_dataset(session_id: str, task_type: str | None = None) -> DatasetValidationResult:
    """Dispatch to the correct validator based on session's task type.

    If task_type is not provided, reads it from the session's dataset_task_type field.
    """
    if task_type is None:
        session = get_capture_session(session_id)
        if session is None:
            result = DatasetValidationResult()
            result.errors.append(f"Session not found: {session_id}")
            return result
        task_type = session.dataset_task_type or ""

    validators = {
        "yolo_detection": validate_yolo_detection,
        "image_classification": validate_image_classification,
        "anomaly_detection": validate_anomaly_detection,
    }
    validator = validators.get(task_type or "", validate_image_classification)
    result = validator(session_id)
    if task_type:
        result.task_type = task_type
    return result
