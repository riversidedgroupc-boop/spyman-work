"""Build feature-enriched defect candidates from model outputs."""

from __future__ import annotations

from src.fusion.decision_types import DefectCandidate, ModelSource, UnifiedPrediction
from src.postprocess.defect_candidate import (
    candidates_from_anomaly,
    candidates_from_opencv,
    candidates_from_yolo,
)
from src.postprocess.feature_extractor import FeatureExtractor


def build_defect_candidates(
    yolo_result: UnifiedPrediction | None = None,
    patchcore_result: UnifiedPrediction | None = None,
    efficientad_result: UnifiedPrediction | None = None,
    fastflow_result: UnifiedPrediction | None = None,
    opencv_result: UnifiedPrediction | None = None,
    image_width: int = 640,
    image_height: int = 640,
    pixel_size_mm: tuple[float, float] = (0.01, 0.01),
) -> list[DefectCandidate]:
    """Collect and enrich defect candidates from all available model outputs."""
    candidates: list[DefectCandidate] = []

    if yolo_result is not None:
        candidates.extend(candidates_from_yolo(yolo_result))
    if patchcore_result is not None:
        candidates.extend(
            candidates_from_anomaly(
                patchcore_result,
                ModelSource.PATCHCORE,
                image_width=image_width,
                image_height=image_height,
            )
        )
    if efficientad_result is not None:
        candidates.extend(
            candidates_from_anomaly(
                efficientad_result,
                ModelSource.EFFICIENTAD,
                image_width=image_width,
                image_height=image_height,
            )
        )
    if fastflow_result is not None:
        candidates.extend(
            candidates_from_anomaly(
                fastflow_result,
                ModelSource.FASTFLOW,
                image_width=image_width,
                image_height=image_height,
            )
        )
    if opencv_result is not None:
        candidates.extend(candidates_from_opencv(opencv_result))

    return FeatureExtractor().extract_all(candidates, pixel_size_mm)
