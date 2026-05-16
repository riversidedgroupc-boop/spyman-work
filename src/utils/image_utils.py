"""Image loading and preprocessing utilities."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def load_image(image_path: str | Path, grayscale: bool = False) -> np.ndarray:
    """Load an image from path. Returns BGR (default) or grayscale array."""
    path = str(image_path)
    if grayscale:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    else:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    return img


def load_image_rgb(image_path: str | Path) -> np.ndarray:
    """Load image as RGB."""
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def get_image_size(image_path: str | Path) -> tuple[int, int]:
    """Get image (width, height) without fully decoding."""
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    h, w = img.shape[:2]
    return w, h


def resize_image(
    image: np.ndarray,
    target_size: tuple[int, int],
    keep_aspect: bool = True,
) -> np.ndarray:
    """Resize image to target (width, height)."""
    if keep_aspect:
        h, w = image.shape[:2]
        tw, th = target_size
        scale = min(tw / w, th / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((th, tw, 3) if image.ndim == 3 else (th, tw), dtype=image.dtype)
        y_off = (th - new_h) // 2
        x_off = (tw - new_w) // 2
        if image.ndim == 3:
            canvas[y_off : y_off + new_h, x_off : x_off + new_w] = resized
        else:
            canvas[y_off : y_off + new_h, x_off : x_off + new_w] = resized
        return canvas
    return cv2.resize(image, target_size, interpolation=cv2.INTER_LINEAR)


def normalize_image(image: np.ndarray) -> np.ndarray:
    """Normalize image to [0, 1] float32."""
    return image.astype(np.float32) / 255.0


def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    """Convert BGR to RGB."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(image: np.ndarray) -> np.ndarray:
    """Convert RGB to BGR."""
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
