"""Shared test helpers — importable as `from tests import make_detection_box, wait_for_condition`."""

from __future__ import annotations

import time
from collections.abc import Callable

from core.schema import DetectionBox


def make_detection_box(
    img: str = "img.jpg",
    cid: int = 0,
    cls_id: int | None = None,
    cname: str = "defect",
    cls_name: str | None = None,
    conf: float = 0.9,
    bbox: list[float] | None = None,
) -> DetectionBox:
    """Factory for DetectionBox instances, accepting both `cid`/`cname` and `cls_id`/`cls_name`."""
    if bbox is None:
        bbox = [0, 0, 100, 100]
    class_id = cls_id if cls_id is not None else cid
    class_name_val = cls_name if cls_name is not None else cname
    return DetectionBox(img, class_id, class_name_val, conf, bbox)


def wait_for_condition(
    condition_fn: Callable[[], bool],
    timeout: float = 2.0,
    interval: float = 0.01,
) -> None:
    """Poll `condition_fn` until it returns truthy or `timeout` expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition_fn():
            return
        time.sleep(interval)
