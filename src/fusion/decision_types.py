"""Core decision types shared across modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FinalDecision(str, Enum):
    OK = "OK"
    ACCEPTABLE_MICRO_DEFECT = "ACCEPTABLE_MICRO_DEFECT"
    SUSPECT = "SUSPECT"
    NG = "NG"
    UNKNOWN = "UNKNOWN"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class DefectClass(str, Enum):
    OK_CLEAN = "OK_clean"
    OK_MICRO_DEFECT = "OK_micro_defect"
    OK_OIL_STAIN = "OK_oil_stain"
    NG_SCRATCH = "NG_scratch"
    NG_PIT = "NG_pit"
    NG_DENT = "NG_dent"
    NG_DENSE_MICRO_DEFECT = "NG_dense_micro_defect"
    NG_STAIN = "NG_stain"
    NG_UNKNOWN = "NG_unknown"
    BORDERLINE = "Borderline"


class ModelSource(str, Enum):
    YOLO = "yolo"
    PATCHCORE = "patchcore"
    EFFICIENTAD = "efficientad"
    FASTFLOW = "fastflow"
    OPENCV = "opencv"
    FUSION = "fusion"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    CONFIRMED_DEFECT = "confirmed_defect"
    ACCEPTABLE_TEXTURE = "acceptable_texture"
    NOISE_OR_REFLECTION = "noise_or_reflection"
    NORMAL = "normal"
    UNKNOWN_PENDING = "unknown_pending"


class ReasonCode(str, Enum):
    YOLO_KNOWN_DEFECT = "yolo_known_defect"
    ANOMALY_UNKNOWN = "anomaly_unknown"
    YOLO_UNCERTAIN_ANOMALY_CONFIRMED = "yolo_uncertain_anomaly_confirmed"
    CLEAN_BY_BOTH = "clean_by_both"
    POSSIBLE_FALSE_POSITIVE = "possible_false_positive"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


class FusionStrategy(str, Enum):
    YOLO_ONLY = "yolo_only"
    ANOMALY_ONLY = "anomaly_only"
    YOLO_PRIORITY = "yolo_priority"
    ANOMALY_PRIORITY = "anomaly_priority"
    RULE_BASED = "rule_based"
    DOUBLE_CONFIRM = "double_confirm"
    EXPLORATION_FIRST = "exploration_first"
    FEW_SHOT = "few_shot"
    PRODUCTION_RETEST = "production_retest"
    STABLE_PRODUCTION = "stable_production"


@dataclass
class BBoxPrediction:
    type: str = "bbox"
    class_name: str = ""
    confidence: float = 0.0
    bbox_xyxy: list[float] = field(default_factory=lambda: [0, 0, 0, 0])
    mask: Optional[list[list[float]]] = None
    score: Optional[float] = None


@dataclass
class AnomalyResult:
    image_score: float = 0.0
    pixel_score_map: Optional[list] = None
    binary_mask: Optional[list] = None
    heatmap_path: Optional[str] = None
    mask_path: Optional[str] = None
    threshold: float = 0.5


@dataclass
class UnifiedPrediction:
    image_path: str = ""
    model_name: str = ""
    predictions: list[BBoxPrediction] = field(default_factory=list)
    anomaly: AnomalyResult = field(default_factory=AnomalyResult)
    runtime_ms: float = 0.0
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class DefectCandidate:
    image_path: str = ""
    candidate_id: int = 0
    source_model: ModelSource = ModelSource.YOLO
    class_name: str = ""
    confidence: float = 0.0
    bbox_xyxy: list[float] = field(default_factory=lambda: [0, 0, 0, 0])
    area_px: float = 0.0
    area_mm2: Optional[float] = None
    length_px: float = 0.0
    length_mm: Optional[float] = None
    width_px: float = 0.0
    width_mm: Optional[float] = None
    aspect_ratio: float = 0.0
    bbox_width: float = 0.0
    bbox_height: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0
    max_anomaly_score: float = 0.0
    mean_anomaly_score: float = 0.0
    yolo_confidence: float = 0.0
    is_long_scratch_like: bool = False
    is_point_like: bool = False
    is_dense_region: bool = False
    gray_contrast: Optional[float] = None
    defect_density_per_meter: Optional[float] = None
    distance_to_edge: Optional[float] = None


@dataclass
class FusionDecision:
    image_path: str = ""
    strategy: FusionStrategy = FusionStrategy.RULE_BASED
    final_decision: FinalDecision = FinalDecision.OK
    reason: str = ""
    candidates: list[DefectCandidate] = field(default_factory=list)
    yolo_result: Optional[UnifiedPrediction] = None
    patchcore_result: Optional[UnifiedPrediction] = None
    efficientad_result: Optional[UnifiedPrediction] = None
    fastflow_result: Optional[UnifiedPrediction] = None
    opencv_result: Optional[UnifiedPrediction] = None
    runtime_ms: float = 0.0
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class ImageRecord:
    image_path: str = ""
    true_label: str = ""
    has_annotation: bool = False
    annotations: list[BBoxPrediction] = field(default_factory=list)
    yolo_result: Optional[UnifiedPrediction] = None
    patchcore_result: Optional[UnifiedPrediction] = None
    efficientad_result: Optional[UnifiedPrediction] = None
    fastflow_result: Optional[UnifiedPrediction] = None
    opencv_result: Optional[UnifiedPrediction] = None
    fusion_decision: Optional[FusionDecision] = None
    is_misclassified: bool = False
    error_type: str = ""
