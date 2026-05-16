"""Excel report schema definitions.

These field lists define the columns for each sheet in the generated Excel report.
They are shared between excel_report.py and any other report consumers.
"""

SUMMARY_FIELDS: list[str] = [
    "total_images",
    "ok_fpr",
    "ng_miss_rate",
    "acceptable_micro_fpr",
    "unknown_recall",
    "borderline_detection_rate",
    "avg_inference_time_ms",
]

IMAGE_RESULT_FIELDS: list[str] = [
    "image_path",
    "true_label",
    "yolo_result",
    "patchcore_score",
    "efficientad_score",
    "fastflow_score",
    "opencv_result",
    "fusion_strategy",
    "final_decision",
    "reason",
    "is_correct",
    "runtime_ms",
]

DEFECT_CANDIDATE_FIELDS: list[str] = [
    "image_path",
    "candidate_id",
    "source_model",
    "class_name",
    "confidence",
    "bbox",
    "area_px",
    "length_px",
    "width_px",
    "area_mm2",
    "length_mm",
    "width_mm",
    "aspect_ratio",
    "max_anomaly_score",
    "decision",
    "reason",
]

MISCLASSIFIED_FIELDS: list[str] = [
    "image_path",
    "true_label",
    "final_decision",
    "error_type",
    "reason",
]
