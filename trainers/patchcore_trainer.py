"""PatchCore trainer — anomaly detection via coreset construction.

V6: Stub with V7 implementation plan.
V7: Full PatchCore training using anomalib library.

V7 Implementation Plan
-----------------------
1. Load a pre-trained backbone (wide_resnet50_2 default) from torchvision
2. Extract features from all OK (good) training images
3. Build coreset via greedy subsampling (PatchCore algorithm)
4. Save coreset + backbone config to model_path directory
5. Report metrics: coreset_size, feature_dim, coverage

Architecture note:
  PatchCore creates a memory bank of nominal features and uses
  nearest-neighbor distance for anomaly scoring at inference time.
  There is no traditional "training" loop — the coreset construction
  is the training step.
"""
from __future__ import annotations

import json
import os

from core.training_job import TrainingJob
from core.training_result import TrainingResult
from trainers.base import BaseTrainer
from trainers.registry import register


@register("patchcore")
class PatchCoreTrainer(BaseTrainer):
    """PatchCore anomaly detection trainer.

    V6: Reserved interface — raises NotImplementedError with roadmap.
    V7: Full coreset construction pipeline.

    Required training_config keys (V7):
        backbone: str = "wide_resnet50_2"
        coreset_sampling_ratio: float = 0.1
        device: str = "cpu"
        image_size: int = 256
    """

    trainer_name = "patchcore"
    supported_tasks = ("anomaly_patchcore",)

    def __init__(self, job: TrainingJob):
        super().__init__(job)
        self._result: TrainingResult | None = None

    def prepare(self) -> None:
        """V6: Validate config and environment. V7: Load backbone + scan dataset.

        V7 prepare() will:
        1. Parse training_config for backbone/device/image_size
        2. Import anomalib or torchvision for backbone loading
        3. Validate dataset directory structure (train/good/ must exist)
        4. Pre-compute image list and feature extraction plan
        5. Allocate output directory for coreset

        Raises:
            NotImplementedError: V6 stub.
        """
        cfg_raw = self.job.training_config or "{}"
        cfg: dict = json.loads(cfg_raw) if isinstance(cfg_raw, str) else (cfg_raw or {})

        dataset_path = self.job.dataset_path
        if not dataset_path or not os.path.isdir(dataset_path):
            raise FileNotFoundError(
                f"PatchCore requires a valid dataset_path. "
                f"Expected structure: {dataset_path}/train/good/"
            )

        # Check for anomalib availability
        try:
            import anomalib  # noqa: F401
            _anomalib_available = True
        except ImportError:
            _anomalib_available = False

        raise NotImplementedError(
            "PatchCore 训练将在 V7 中实现。\n\n"
            "V7 实现计划:\n"
            "1. 从 torchvision 加载预训练 backbone (默认 wide_resnet50_2)\n"
            "2. 提取所有 OK 训练图像的特征\n"
            "3. 通过贪心降采样构建 coreset (PatchCore 算法核心)\n"
            "4. 保存 coreset + backbone 配置到模型输出目录\n\n"
            f"数据集路径: {dataset_path}\n"
            f"anomalib 可用: {_anomalib_available}\n"
            f"配置: {json.dumps(cfg, ensure_ascii=False)}"
        )

    def train(self, progress_callback=None) -> None:
        """V6: Stub. V7: Execute coreset construction.

        V7 train() will:
        1. Load backbone and freeze weights
        2. Extract features from train/good/ images in batches
        3. Concatenate all nominal features into memory bank
        4. Run greedy coreset subsampling
        5. Save coreset.pt and config.json to output directory
        6. Report progress via progress_callback(percent, message)
        """
        raise NotImplementedError(
            "PatchCore 训练将在 V7 中实现。"
        )

    def collect_results(self) -> TrainingResult:
        """V6: Returns empty result. V7: Returns coreset metrics."""
        if self._result:
            return self._result
        return TrainingResult.empty(self.job.job_id)
