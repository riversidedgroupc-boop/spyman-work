"""YOLO trainer using ultralytics."""

from __future__ import annotations

import json
import os
from pathlib import Path

from core.training_job import TrainingJob
from core.training_result import TrainingResult
from trainers.base import BaseTrainer
from trainers.registry import register


def _ensure_ultralytics_config_dir() -> None:
    """Keep Ultralytics settings inside the project when the user dir is locked."""
    config_dir = Path("outputs/ultralytics").resolve()
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(config_dir))


@register("yolo")
class YOLOTrainer(BaseTrainer):
    trainer_name = "yolo"
    supported_tasks = ("detection_yolo",)

    def __init__(self, job: TrainingJob):
        super().__init__(job)
        self._result: TrainingResult | None = None

    def prepare(self) -> None:
        _ensure_ultralytics_config_dir()
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "ultralytics 未安装。请执行: pip install ultralytics"
            )

    def train(self, progress_callback=None) -> None:
        _ensure_ultralytics_config_dir()
        from ultralytics import YOLO

        # training_config is stored as JSON string in TrainingJob
        cfg_raw = self.job.training_config or "{}"
        cfg: dict = json.loads(cfg_raw) if isinstance(cfg_raw, str) else (cfg_raw or {})

        base_model = cfg.get("base_model", self.job.base_model or "yolov8n.pt")
        epochs = cfg.get("epochs", 100)
        imgsz = cfg.get("imgsz", 640)
        batch = cfg.get("batch", 8)
        device = cfg.get("device", "cpu")
        workers = cfg.get("workers", 4)
        patience = cfg.get("patience", 30)

        # Find dataset.yaml
        dataset_yaml = self._find_dataset_yaml()

        model = YOLO(base_model)
        results = model.train(
            data=dataset_yaml,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device=device,
            workers=workers,
            patience=patience,
            verbose=True,
        )

        run_dir = getattr(results, "save_dir", None) or ""
        self._result = TrainingResult.from_yolo_output(self.job.job_id, str(run_dir))

    def collect_results(self) -> TrainingResult:
        if self._result:
            return self._result
        return TrainingResult.empty(self.job.job_id)

    def _find_dataset_yaml(self) -> str:
        """Locate data.yaml from dataset_path on the TrainingJob."""
        dataset_path = self.job.dataset_path

        # Direct match: dataset_path is a data.yaml file
        if dataset_path.endswith(".yaml") or dataset_path.endswith(".yml"):
            if os.path.isfile(dataset_path):
                return dataset_path
            raise FileNotFoundError(f"data.yaml 不存在: {dataset_path}")

        # Dataset directory: look for data.yaml inside
        if os.path.isdir(dataset_path):
            yaml_path = os.path.join(dataset_path, "data.yaml")
            if os.path.isfile(yaml_path):
                return yaml_path

            # Fallback: search for any dataset.yaml
            for root, _, files in os.walk(dataset_path):
                if "data.yaml" in files:
                    return os.path.join(root, "data.yaml")
                if "dataset.yaml" in files:
                    return os.path.join(root, "dataset.yaml")

        raise FileNotFoundError(
            f"未找到 data.yaml。请确认 dataset_path 指向有效的 YOLO 数据集目录: {dataset_path}"
        )
