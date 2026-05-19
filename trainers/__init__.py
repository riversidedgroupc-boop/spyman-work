"""Trainers package — auto-import to populate registry."""

from trainers.registry import get_trainer, list_trainers  # noqa: F401
from trainers.yolo_trainer import YOLOTrainer  # noqa: F401
from trainers.patchcore_trainer import PatchCoreTrainer  # noqa: F401
from trainers.hybrid_trainer import HybridTrainer  # noqa: F401
