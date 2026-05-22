"""TrainingResult — encapsulates training output data."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrainingResult:
    job_id: str
    best_model_path: str = ""
    last_model_path: str = ""
    output_dir: str = ""
    metrics: dict = field(default_factory=dict)

    @classmethod
    def empty(cls, job_id: str) -> TrainingResult:
        return cls(job_id=job_id)

    @classmethod
    def from_yolo_output(cls, job_id: str, run_dir: str) -> TrainingResult:
        """Parse ultralytics YOLO training output directory."""
        import json
        import os

        result = cls(job_id=job_id, output_dir=run_dir)

        best_path = os.path.join(run_dir, "weights", "best.pt")
        last_path = os.path.join(run_dir, "weights", "last.pt")
        if os.path.isfile(best_path):
            result.best_model_path = best_path
        if os.path.isfile(last_path):
            result.last_model_path = last_path

        # Try to read results.csv or results.json
        results_json = os.path.join(run_dir, "results.json")
        if os.path.isfile(results_json):
            with open(results_json) as f:
                result.metrics = json.load(f)
        else:
            results_csv = os.path.join(run_dir, "results.csv")
            if os.path.isfile(results_csv):
                result.metrics = {"results_csv": results_csv}

        return result
