"""YOLO-format annotation parsing for copper tube defect labels.

Each image has a corresponding .txt file with one line per bounding box:
    class_id x_center y_center width height

All coordinates are normalized to [0, 1].
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def _read_lines(label_path: Path) -> list[str]:
    """Read non-empty lines from a label file, returning [] if missing."""
    try:
        text = label_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return []
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_yolo_annotation(
    label_path: str | Path,
    image_width: int,
    image_height: int,
) -> list[dict]:
    """Parse a YOLO-format label file and convert to pixel-space bounding boxes.

    Args:
        label_path: Path to the .txt label file.
        image_width: Image width in pixels.
        image_height: Image height in pixels.

    Returns:
        List of dicts with keys: class_id, class_name, x_center, y_center,
        width, height, bbox_xyxy (in pixels), confidence (1.0 for GT).
        Returns empty list if the label file does not exist or is unreadable.
    """
    from src.dataset.label_schema import class_id_to_name

    path = Path(label_path)
    lines = _read_lines(path)
    results: list[dict] = []

    for line in lines:
        parts = line.split()
        if len(parts) < 5:
            continue

        try:
            class_id = int(parts[0])
            x_center_n = float(parts[1])
            y_center_n = float(parts[2])
            width_n = float(parts[3])
            height_n = float(parts[4])
        except (ValueError, IndexError):
            continue

        # Convert normalized coordinates to pixel space
        x_center_px = x_center_n * image_width
        y_center_px = y_center_n * image_height
        width_px = width_n * image_width
        height_px = height_n * image_height

        x1 = x_center_px - width_px / 2.0
        y1 = y_center_px - height_px / 2.0
        x2 = x_center_px + width_px / 2.0
        y2 = y_center_px + height_px / 2.0

        results.append(
            {
                "class_id": class_id,
                "class_name": class_id_to_name(class_id),
                "x_center": x_center_n,
                "y_center": y_center_n,
                "width": width_n,
                "height": height_n,
                "bbox_xyxy": [x1, y1, x2, y2],
                "confidence": 1.0,
            }
        )

    return results


def parse_yolo_annotation_normalized(
    label_path: str | Path,
) -> list[dict]:
    """Parse YOLO-format label file returning normalized [0,1] coordinates.

    Unlike parse_yolo_annotation, this does not require image dimensions and
    returns coordinates in their original normalized form.

    Args:
        label_path: Path to the .txt label file.

    Returns:
        List of dicts with keys: class_id, class_name, x_center, y_center,
        width, height, bbox_xyxy (normalized), confidence (1.0 for GT).
    """
    from src.dataset.label_schema import class_id_to_name

    path = Path(label_path)
    lines = _read_lines(path)
    results: list[dict] = []

    for line in lines:
        parts = line.split()
        if len(parts) < 5:
            continue

        try:
            class_id = int(parts[0])
            x_center = float(parts[1])
            y_center = float(parts[2])
            width = float(parts[3])
            height = float(parts[4])
        except (ValueError, IndexError):
            continue

        x1 = x_center - width / 2.0
        y1 = y_center - height / 2.0
        x2 = x_center + width / 2.0
        y2 = y_center + height / 2.0

        results.append(
            {
                "class_id": class_id,
                "class_name": class_id_to_name(class_id),
                "x_center": x_center,
                "y_center": y_center,
                "width": width,
                "height": height,
                "bbox_xyxy": [x1, y1, x2, y2],
                "confidence": 1.0,
            }
        )

    return results


def find_label_file(
    image_path: str | Path,
    label_dir: str | Path,
) -> Optional[Path]:
    """Find the matching .txt label file for an image.

    Searches by replacing the image extension with .txt in the label_dir.

    Args:
        image_path: Path to the image file.
        label_dir: Directory containing YOLO-format .txt label files.

    Returns:
        Path to the label file if it exists, None otherwise.
    """
    image_path = Path(image_path)
    label_dir = Path(label_dir)

    stem = image_path.stem
    label_path = label_dir / f"{stem}.txt"

    if label_path.exists():
        return label_path
    return None


def has_label(
    image_path: str | Path,
    label_dir: str | Path,
) -> bool:
    """Check if a label file exists for the given image.

    Args:
        image_path: Path to the image file.
        label_dir: Directory containing YOLO-format .txt label files.

    Returns:
        True if a matching label file exists.
    """
    return find_label_file(image_path, label_dir) is not None
