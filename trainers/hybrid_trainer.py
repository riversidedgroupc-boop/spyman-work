"""Hybrid trainer — YOLO (detection) + PatchCore (anomaly) composite.

V6: Reserved interface and pipeline skeleton.
V7: Full implementation with integrated training orchestration.

V7 Implementation Plan
-----------------------
1. Load YOLO and PatchCore trainers independently
2. Run YOLO detection training on full dataset (all classes)
3. Build anomaly dataset from OK-only samples (via core/anomaly_dataset_builder)
4. Run PatchCore coreset construction on OK features
5. Merge class_mapping from both trainers
6. Output composite model manifest with both model paths

V6 provides:
- Trainer registration ("hybrid" in registry)
- Job validation (requires both yolo_base_model and patchcore_backbone)
- Placeholder prepare/train/collect_results that document the V7 plan
"""
from __future__ import annotations

from core.training_job import TrainingJob
from core.training_result import TrainingResult
from trainers.base import BaseTrainer
from trainers.registry import register


@register("hybrid")
class HybridTrainer(BaseTrainer):
    """Composite trainer combining YOLO detection and PatchCore anomaly detection.

    V6: Stub — registered but not implemented.
    V7: Full orchestration of dual-model training pipeline.
    """

    trainer_name = "hybrid"
    supported_tasks = ("detection_yolo", "anomaly_patchcore")

    _V7_ROADMAP = """
    V7 HybridTrainer Implementation Plan:

    1. prepare():
       - Validate training_config contains both yolo and patchcore sections
       - Check that dataset_path has both detection labels and OK samples
       - Initialize YOLOTrainer and PatchCoreTrainer sub-trainers
       - Create merged output directory structure

    2. train(progress_callback):
       - Phase 1 (40%): Train YOLO on detection dataset
         - delegate to YOLOTrainer.train()
         - save best.pt to output/hybrid/yolo/
       - Phase 2 (30%): Build anomaly dataset from OK-only samples
         - use core/anomaly_dataset_builder.build_anomaly_dataset_from_session()
       - Phase 3 (30%): Train PatchCore on anomaly dataset
         - delegate to PatchCoreTrainer.train()
         - save coreset to output/hybrid/patchcore/

    3. collect_results():
       - Merge metrics from both trainers
       - Create composite TrainingResult with:
         - model_path: output/hybrid/manifest.json
         - metrics: {yolo: {...}, patchcore: {...}}
         - class_mapping: merged from both trainers
       - Write manifest.json with both model paths
    """

    def __init__(self, job: TrainingJob):
        super().__init__(job)
        self._result: TrainingResult | None = None

    def prepare(self) -> None:
        """V6: Validate job config structure. V7: Full dual-trainer preparation.

        Raises:
            NotImplementedError: V6 stub — full implementation in V7.
        """
        import json

        cfg_raw = self.job.training_config or "{}"
        cfg: dict = json.loads(cfg_raw) if isinstance(cfg_raw, str) else (cfg_raw or {})

        # Validate that the config has both sections
        yolo_cfg = cfg.get("yolo", {})
        patchcore_cfg = cfg.get("patchcore", {})

        if not yolo_cfg and not patchcore_cfg:
            raise ValueError(
                "HybridTrainer requires training_config with 'yolo' and/or 'patchcore' sections. "
                "Example: {\"yolo\": {\"base_model\": \"yolov8n.pt\", \"epochs\": 100}, "
                "\"patchcore\": {\"backbone\": \"wide_resnet50_2\"}}"
            )

        raise NotImplementedError(
            "HybridTrainer (YOLO + PatchCore) will be implemented in V7. "
            "Use YOLOTrainer or PatchCoreTrainer separately in V6. "
            f"Config sections present: {list(cfg.keys())}"
        )

    def train(self, progress_callback=None) -> None:
        """V6: Stub. V7: See _V7_ROADMAP for full implementation plan."""
        raise NotImplementedError(
            "HybridTrainer.train() will be implemented in V7. "
            "See HybridTrainer._V7_ROADMAP for the planned pipeline."
        )

    def collect_results(self) -> TrainingResult:
        """V6: Stub. Returns empty result."""
        if self._result:
            return self._result
        return TrainingResult.empty(self.job.job_id)
