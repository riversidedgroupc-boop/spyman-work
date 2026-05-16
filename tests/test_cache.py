"""Tests for prediction cache invalidation."""

from __future__ import annotations

import os
import time

from core.cache import build_prediction_cache_key


def test_cache_key_changes_when_images_change(tmp_path):
    model_path = tmp_path / "model.pt"
    image_dir = tmp_path / "images"
    model_path.write_bytes(b"model")
    image_dir.mkdir()

    first_image = image_dir / "a.jpg"
    first_image.write_bytes(b"first")
    key_before = build_prediction_cache_key(str(model_path), str(image_dir))

    time.sleep(1.1)
    second_image = image_dir / "b.jpg"
    second_image.write_bytes(b"second")
    os.utime(second_image, None)
    key_after = build_prediction_cache_key(str(model_path), str(image_dir))

    assert key_after != key_before

