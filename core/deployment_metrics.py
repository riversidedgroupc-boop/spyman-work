"""Deployment-oriented metrics for copper tube online inspection.

Answers: is this model ready for production deployment?
Reuses ``core.matcher.match_detections`` and ``core.schema.DetectionBox``.
"""

from __future__ import annotations

from core.schema import DetectionBox
from core.matcher import match_detections


def compute_detection_counts(
    ground_truths_by_image: dict[str, list[DetectionBox]],
    predictions_by_image: dict[str, list[DetectionBox]],
    iou_threshold: float = 0.5,
    class_aware: bool = True,
) -> dict:
    """Count true positives, false positives, false negatives across all images.

    Deployment readiness must be class-aware by default: a box on the right
    location but with the wrong defect class is still a miss plus a false alarm.
    """
    tp = 0
    fp = 0
    fn = 0
    num_gt = 0
    num_pred = 0

    all_images = set(ground_truths_by_image.keys()) | set(predictions_by_image.keys())

    for img_name in all_images:
        gts = ground_truths_by_image.get(img_name, [])
        preds = predictions_by_image.get(img_name, [])
        num_gt += len(gts)
        num_pred += len(preds)

        result = match_detections(
            gts,
            preds,
            iou_threshold=iou_threshold,
            class_aware=class_aware,
        )
        tp += len(result["matches"])
        fp += len(result["false_positives"])
        fn += len(result["false_negatives"])

    return {
        "num_images": len(all_images),
        "num_gt": num_gt,
        "num_predictions": num_pred,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
    }


def compute_miss_rate(
    ground_truths_by_image: dict[str, list[DetectionBox]],
    predictions_by_image: dict[str, list[DetectionBox]],
    iou_threshold: float = 0.5,
    class_aware: bool = True,
) -> float:
    """Fraction of ground-truth defects that were not detected."""
    counts = compute_detection_counts(
        ground_truths_by_image, predictions_by_image, iou_threshold, class_aware
    )
    total_gt = counts["true_positives"] + counts["false_negatives"]
    if total_gt == 0:
        return 0.0
    return counts["false_negatives"] / total_gt


def compute_false_alarm_rate(
    ground_truths_by_image: dict[str, list[DetectionBox]],
    predictions_by_image: dict[str, list[DetectionBox]],
    iou_threshold: float = 0.5,
    class_aware: bool = True,
) -> float:
    """Fraction of predictions that are false positives."""
    counts = compute_detection_counts(
        ground_truths_by_image, predictions_by_image, iou_threshold, class_aware
    )
    total_preds = counts["true_positives"] + counts["false_positives"]
    if total_preds == 0:
        return 0.0
    return counts["false_positives"] / total_preds


def compute_false_alarms_per_meter(
    ground_truths_by_image: dict[str, list[DetectionBox]],
    predictions_by_image: dict[str, list[DetectionBox]],
    image_meter_length_map: dict[str, float] | None = None,
    iou_threshold: float = 0.5,
    class_aware: bool = True,
) -> float | None:
    """False alarms per meter of inspected tube.

    Returns None if meter-length data is unavailable.
    """
    if image_meter_length_map is None:
        return None

    counts = compute_detection_counts(
        ground_truths_by_image, predictions_by_image, iou_threshold, class_aware
    )

    total_meters = sum(image_meter_length_map.values())
    if total_meters <= 0:
        return None

    return counts["false_positives"] / total_meters


def compute_review_load(
    ground_truths_by_image: dict[str, list[DetectionBox]],
    predictions_by_image: dict[str, list[DetectionBox]],
    iou_threshold: float = 0.5,
    class_aware: bool = True,
) -> dict:
    """Estimate how many images would need human review.

    An image needs review if it has any prediction.
    """
    _ = iou_threshold, class_aware
    all_images = set(ground_truths_by_image.keys()) | set(predictions_by_image.keys())
    review_images = 0

    for img_name in all_images:
        preds = predictions_by_image.get(img_name, [])
        if len(preds) > 0:
            review_images += 1

    return {
        "review_load_images": review_images,
        "total_images": len(all_images),
        "review_load_ratio": review_images / max(len(all_images), 1),
    }


def compute_average_inference_time(
    timing_by_image: dict[str, float] | None = None,
    timing_list: list[float] | None = None,
) -> dict:
    """Compute average and max inference time from timing data."""
    times: list[float] = []
    if timing_by_image:
        times.extend(timing_by_image.values())
    if timing_list:
        times.extend(timing_list)

    if not times:
        return {"avg_inference_ms": 0.0, "max_inference_ms": 0.0}

    return {
        "avg_inference_ms": sum(times) / len(times),
        "max_inference_ms": max(times),
    }


def compute_deployment_summary(
    ground_truths_by_image: dict[str, list[DetectionBox]],
    predictions_by_image: dict[str, list[DetectionBox]],
    image_meter_length_map: dict[str, float] | None = None,
    timing_list: list[float] | None = None,
    iou_threshold: float = 0.5,
    class_aware: bool = True,
) -> dict:
    """Produce a comprehensive deployment-readiness summary."""
    counts = compute_detection_counts(
        ground_truths_by_image, predictions_by_image, iou_threshold, class_aware
    )
    miss_rate = compute_miss_rate(
        ground_truths_by_image, predictions_by_image, iou_threshold, class_aware
    )
    false_alarm_rate = compute_false_alarm_rate(
        ground_truths_by_image, predictions_by_image, iou_threshold, class_aware
    )
    false_alarms_per_meter = compute_false_alarms_per_meter(
        ground_truths_by_image,
        predictions_by_image,
        image_meter_length_map,
        iou_threshold,
        class_aware,
    )
    review_load = compute_review_load(
        ground_truths_by_image, predictions_by_image, iou_threshold, class_aware
    )
    timing = compute_average_inference_time(timing_list=timing_list)

    return {
        **counts,
        "miss_rate": miss_rate,
        "false_alarm_rate": false_alarm_rate,
        "false_alarms_per_meter": false_alarms_per_meter,
        **review_load,
        **timing,
    }
