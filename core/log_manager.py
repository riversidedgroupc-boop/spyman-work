"""Multi-category rotating log system with audit trail.

Produces 6 log files: app, camera, inference, system, error, audit.
Each rotates at 10 MB with 5 backups kept.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


class LogManager:
    """Singleton managing 6 rotating log categories."""

    _instance: LogManager | None = None
    CATEGORIES = ("app", "camera", "inference", "system", "error", "audit")

    def __init__(self, log_dir: str | None = None):
        if LogManager._instance is not None:
            raise RuntimeError("Use LogManager.instance()")
        self._log_dir = log_dir or self._default_log_dir()
        os.makedirs(self._log_dir, exist_ok=True)
        self._loggers: dict[str, logging.Logger] = {}
        LogManager._instance = self

    @staticmethod
    def _default_log_dir() -> str:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "logs")

    @classmethod
    def instance(cls) -> "LogManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def log_dir(self) -> str:
        return self._log_dir

    def get_logger(self, category: str) -> logging.Logger:
        if category not in self.CATEGORIES:
            raise ValueError(f"Unknown log category: {category}. Use one of {self.CATEGORIES}")
        if category in self._loggers:
            return self._loggers[category]

        logger = logging.getLogger(f"cx_vision.{category}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        log_path = os.path.join(self._log_dir, f"{category}.log")
        handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.info(f"Log started for category: {category}")
        self._loggers[category] = logger
        return logger

    def get_log_path(self, category: str) -> str:
        return os.path.join(self._log_dir, f"{category}.log")

    def log_audit(self, action: str, detail: str = "") -> None:
        audit = self.get_logger("audit")
        audit.info(f"{action} | {detail}")

    def all_log_paths(self) -> dict[str, str]:
        return {cat: self.get_log_path(cat) for cat in self.CATEGORIES}

    def reset(self) -> None:
        for logger in self._loggers.values():
            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)
        self._loggers.clear()
