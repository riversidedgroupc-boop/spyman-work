"""Simple logging setup."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logger(
    name: str = "copper_defect_eval",
    level: int = logging.INFO,
    log_file: str | Path | None = None,
) -> logging.Logger:
    """Create a logger with console handler and optional file handler."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    if log_file:
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


_default_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Get the default logger instance."""
    global _default_logger
    if _default_logger is None:
        _default_logger = setup_logger()
    return _default_logger
