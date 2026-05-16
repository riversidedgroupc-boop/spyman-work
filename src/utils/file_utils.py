"""File system utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path

VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def collect_images(
    image_dir: str | Path,
    valid_extensions: set[str] | None = None,
) -> list[Path]:
    """Collect all image files from a directory (non-recursive)."""
    if valid_extensions is None:
        valid_extensions = VALID_IMAGE_EXTENSIONS

    image_dir = Path(image_dir)
    if not image_dir.exists():
        return []

    images: list[Path] = []
    for ext in valid_extensions:
        images.extend(image_dir.glob(f"*{ext}"))
        images.extend(image_dir.glob(f"*{ext.upper()}"))

    return sorted(set(images))


def collect_images_recursive(
    image_dir: str | Path,
    valid_extensions: set[str] | None = None,
) -> list[Path]:
    """Collect all image files from a directory recursively."""
    if valid_extensions is None:
        valid_extensions = VALID_IMAGE_EXTENSIONS

    image_dir = Path(image_dir)
    if not image_dir.exists():
        return []

    images: list[Path] = []
    for ext in valid_extensions:
        images.extend(image_dir.rglob(f"*{ext}"))
        images.extend(image_dir.rglob(f"*{ext.upper()}"))

    return sorted(set(images))


def ensure_dir(path: str | Path) -> Path:
    """Ensure a directory exists, create if needed."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_relative_path(file_path: str | Path, base_dir: str | Path) -> str:
    """Get a relative path string, falling back to absolute."""
    try:
        return str(Path(file_path).relative_to(base_dir))
    except ValueError:
        return str(file_path)


def file_checksum(file_path: str | Path, algorithm: str = "md5") -> str:
    """Compute file checksum."""
    h = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
