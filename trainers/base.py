"""Base trainer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.training_job import TrainingJob
from core.training_result import TrainingResult


class BaseTrainer(ABC):
    trainer_name: str = "base"
    supported_tasks: tuple[str, ...] = ()

    def __init__(self, job: TrainingJob):
        self.job = job

    @abstractmethod
    def prepare(self) -> None:
        """Prepare for training — validate data, setup config."""

    @abstractmethod
    def train(self, progress_callback=None) -> None:
        """Execute training."""

    @abstractmethod
    def collect_results(self) -> TrainingResult:
        """Collect training output (model paths, metrics)."""
