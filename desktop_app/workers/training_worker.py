"""Training worker — runs YOLO training in background thread."""
from __future__ import annotations

import io
import json
import os
import sys

from PySide6.QtCore import Signal

from desktop_app.i18n import tr
from desktop_app.workers.base_worker import BaseWorker


class TrainingWorker(BaseWorker):
    """Runs YOLO training via ultralytics in a QThread."""
    log_line = Signal(str)

    def __init__(
        self,
        job_id: str,
        dataset_yaml: str,
        base_model: str = "yolov8n.pt",
        epochs: int = 100,
        imgsz: int = 640,
        batch: int = 8,
        device: str = "cpu",
        output_dir: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._job_id = job_id
        self._dataset_yaml = dataset_yaml
        self._base_model = base_model
        self._epochs = epochs
        self._imgsz = imgsz
        self._batch = batch
        self._device = device
        self._output_dir = output_dir or os.path.join("outputs", "train", job_id)
        self._best_model_path = ""

    def _run_impl(self) -> None:
        from core.training_job import update_training_job
        from datetime import datetime

        update_training_job(
            self._job_id,
            status="running",
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            output_dir=self._output_dir,
        )

        os.makedirs(self._output_dir, exist_ok=True)

        # Capture ultralytics stdout
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured = io.StringIO()

        class TeeOutput:
            def __init__(self, old, tee):
                self.old = old
                self.tee = tee

            def write(self, s):
                self.old.write(s)
                self.tee.write(s)
                if s.strip():
                    self.tee.flush()

            def flush(self):
                self.old.flush()

        sys.stdout = TeeOutput(old_stdout, captured)
        sys.stderr = TeeOutput(old_stderr, captured)

        try:
            from ultralytics import YOLO

            self.message.emit(tr("training.loading_base", model=self._base_model))
            model = YOLO(self._base_model)

            self.message.emit(tr("training.starting", epochs=self._epochs, imgsz=self._imgsz, batch=self._batch))
            results = model.train(
                data=self._dataset_yaml,
                epochs=self._epochs,
                imgsz=self._imgsz,
                batch=self._batch,
                device=self._device,
                project=self._output_dir,
                name="train",
                exist_ok=True,
                verbose=True,
            )

            # Find best.pt
            best_path = ""
            for root, dirs, files in os.walk(os.path.join(self._output_dir, "train")):
                for f in files:
                    if f == "best.pt":
                        best_path = os.path.join(root, f)
                        break
            if not best_path:
                # Check weights/ subdirectory
                weights_dir = os.path.join(self._output_dir, "train", "weights")
                if os.path.isdir(weights_dir):
                    best_path = os.path.join(weights_dir, "best.pt")

            self._best_model_path = best_path

            metrics = {}
            try:
                metrics["mAP50"] = float(results.results_dict.get("metrics/mAP50(B)", 0))
                metrics["mAP50-95"] = float(results.results_dict.get("metrics/mAP50-95(B)", 0))
            except Exception:
                pass

            self.message.emit(tr("training.completed", path=best_path))

            # Update job
            update_training_job(
                self._job_id,
                status="completed",
                end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                best_model_path=best_path,
                last_model_path=os.path.join(self._output_dir, "train", "weights", "last.pt"),
                metrics=json.dumps(metrics),
            )

            # Register model version
            if best_path:
                from core.model_version import create_model_version
                from core.training_job import get_training_job
                job = get_training_job(self._job_id)
                if job:
                    create_model_version(
                        project_id=job.project_id,
                        model_name=f"{job.job_name} (trained)",
                        training_job_id=self._job_id,
                        model_type="yolo",
                        model_path=best_path,
                        base_model=self._base_model,
                        metrics=json.dumps(metrics),
                        status="completed",
                    )

        except Exception as e:
            self.message.emit(tr("training.failed", error=str(e)))
            from core.training_job import update_training_job
            update_training_job(self._job_id, status="failed", notes=str(e))
            raise
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def get_best_model_path(self) -> str:
        return self._best_model_path
