"""Autofocus structured logging — console + file handlers with rotation."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_autofocus_logger(
    log_dir: str | Path = "logs",
    level: int = logging.DEBUG,
    console_level: int = logging.INFO,
) -> logging.Logger:
    """Configure and return the autofocus root logger.

    Creates:
    - Console handler (INFO+)
    - File handler (DEBUG+, with timestamp in filename)
    - Run-specific log file

    Args:
        log_dir: Directory for log files.
        level: File log level.
        console_level: Console log level.

    Returns:
        Root autofocus logger.
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("autofocus")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # Format
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_handler = logging.FileHandler(
        log_dir / f"autofocus_{timestamp}.log", encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module."""
    return logging.getLogger(f"autofocus.{name}")
