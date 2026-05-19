"""Trainer registry — maps model_family strings to trainer classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trainers.base import BaseTrainer

_registry: dict[str, type[BaseTrainer]] = {}


def register(name: str):
    """Decorator to register a trainer class."""
    def decorator(cls):
        _registry[name] = cls
        return cls
    return decorator


def get_trainer(name: str) -> type[BaseTrainer] | None:
    return _registry.get(name)


def list_trainers() -> list[dict]:
    """Return registered trainers with metadata."""
    return [{"name": name, "class": cls} for name, cls in _registry.items()]
