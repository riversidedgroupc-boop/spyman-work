"""Anomaly detection training worker — PatchCore coreset construction in background."""
from __future__ import annotations

import json
import os
from datetime import datetime

from PySide6.QtCore import Signal

from desktop_app.workers.base_worker import BaseWorker


class AnomalyTrainingWorker(BaseWorker):
    """Runs PatchCore (anomaly detection) training in a background QThread.

    Unlike YOLO training, PatchCore has no epoch loop — it's a one-shot
    coreset construction. Progress is reported in phases:
      - Validating dataset
      - Loading backbone
      - Extracting features
      - Building coreset
      - Saving model
    """

    log_line = Signal(str)

    def __init__(
        self,
        job_id: str,
        dataset_path: str,
        output_dir: str = "",
        device: str = "cpu",
        backbone: str = "wide_resnet50_2",
        image_size: int = 256,
        coreset_sampling_ratio: float = 0.1,
        dataset_version_id: str = "",
        spec_id: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._job_id = job_id
        self._dataset_path = dataset_path
        self._output_dir = output_dir or os.path.join(
            "outputs", "train_anomaly", f"patchcore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self._device = device
        self._backbone = backbone
        self._image_size = image_size
        self._coreset_sampling_ratio = coreset_sampling_ratio
        self._best_model_path = ""
        self._dataset_version_id = dataset_version_id
        self._spec_id = spec_id

    def _run_impl(self) -> None:
        from core.training_job import update_training_job, get_training_job

        update_training_job(
            self._job_id,
            status="running",
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            output_dir=self._output_dir,
        )

        os.makedirs(self._output_dir, exist_ok=True)

        # Phase 1: Validate dataset
        self.message.emit("Validating anomaly detection dataset...")
        self.log_line.emit("Checking dataset structure...")

        train_good_dir = os.path.join(self._dataset_path, "train", "good")
        if not os.path.isdir(train_good_dir):
            raise FileNotFoundError(
                f"Anomaly detection dataset requires train/good/ directory.\n"
                f"Expected: {train_good_dir}\n\n"
                f"Please generate an anomaly detection dataset first via "
                f"the Dataset Version page with task type 'anomaly_detection'."
            )

        ok_images = [
            f for f in os.listdir(train_good_dir)
            if os.path.splitext(f)[1].lower() in {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        ]
        if len(ok_images) < 10:
            raise ValueError(
                f"Need at least 10 OK images for anomaly detection training. "
                f"Found: {len(ok_images)} in {train_good_dir}"
            )

        self.log_line.emit(f"Found {len(ok_images)} OK training images")
        self.progress.emit(10, 100)
        self.message.emit("Dataset validated — starting PatchCore training...")

        # Phase 2: Try PatchCore trainer via registry
        try:
            import trainers.patchcore_trainer  # noqa: F401
            from trainers.registry import get_trainer

            job = get_training_job(self._job_id)
            if job is None:
                raise RuntimeError(f"Training job not found: {self._job_id}")

            config = {
                "backbone": self._backbone,
                "coreset_sampling_ratio": self._coreset_sampling_ratio,
                "device": self._device,
                "image_size": self._image_size,
            }
            # Update job with full config
            update_training_job(self._job_id, training_config=json.dumps(config))

            trainer_cls = get_trainer("patchcore")
            if trainer_cls is None:
                raise NotImplementedError(
                    "PatchCore trainer is not registered.\n\n"
                    "The anomaly detection training backend is not yet available."
                )

            trainer = trainer_cls(job)
            self.log_line.emit("Preparing PatchCore trainer...")
            self.progress.emit(20, 100)
            trainer.prepare()

            self.log_line.emit("Running coreset construction...")
            self.progress.emit(30, 100)
            trainer.train(progress_callback=self._on_trainer_progress)

            self.progress.emit(90, 100)
            result = trainer.collect_results()

            # Find saved model path
            best_path = ""
            for root, dirs, files in os.walk(self._output_dir):
                for f in files:
                    if f in (
                        "coreset.pt",
                        "model.pt",
                        "patchcore_model.pt",
                        "patchcore_model.json",
                    ):
                        best_path = os.path.join(root, f)
                        break
                if best_path:
                    break

            if not best_path:
                # Check if trainer wrote to a specific path
                if hasattr(trainer, "output_path"):
                    best_path = trainer.output_path or ""

            self._best_model_path = best_path
            self.progress.emit(100, 100)

            if not best_path and getattr(result, "best_model_path", ""):
                best_path = result.best_model_path

            metrics = result.metrics if getattr(result, "metrics", None) else {}

            self.message.emit("PatchCore training completed")

            # Update job
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            update_training_job(
                self._job_id,
                status="completed",
                end_time=end_time,
                best_model_path=best_path,
                metrics=json.dumps(metrics),
            )

            # Register model version
            if best_path and job:
                from core.model_version import create_model_version

                create_model_version(
                    project_id=job.project_id,
                    model_name=f"{job.job_name} (PatchCore)",
                    training_job_id=self._job_id,
                    model_type="patchcore",
                    model_path=best_path,
                    base_model=self._backbone,
                    metrics=json.dumps(metrics),
                    status="completed",
                    spec_id=self._spec_id or job.spec_id,
                    dataset_version_id=self._dataset_version_id or "",
                )
                self.log_line.emit(f"Model version registered: {best_path}")

        except NotImplementedError as e:
            # Trainer not implemented yet — this is expected in V6
            self.log_line.emit(f"PatchCore training not available: {e}")
            update_training_job(
                self._job_id,
                status="failed",
                notes=str(e),
            )
            raise

    def _on_trainer_progress(self, percent: float, message: str = "") -> None:
        """Callback from trainer during coreset construction."""
        pct = int(max(30, min(90, 30 + percent * 0.6)))
        self.progress.emit(pct, 100)
        if message:
            self.message.emit(message)
            self.log_line.emit(message)

    def get_best_model_path(self) -> str:
        return self._best_model_path
