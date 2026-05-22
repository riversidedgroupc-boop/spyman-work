"""Tests for dataset quality checker."""
import json
import os

from core.dataset_quality import DatasetQualityChecker


def test_empty_dataset_dir(tmp_path):
    checker = DatasetQualityChecker(str(tmp_path))
    report = checker.full_report()
    assert report["quality_score"] < 100
    assert len(report["issues"]) > 0


def test_perfect_dataset(tmp_path):
    # Create minimal YOLO-format dataset
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir()
    labels_dir.mkdir()
    import cv2
    import numpy as np
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    for i in range(5):
        cv2.imwrite(str(images_dir / f"img_{i:04d}.jpg"), img)
        with open(labels_dir / f"img_{i:04d}.txt", "w") as f:
            f.write("0 0.5 0.5 0.1 0.1\n")

    checker = DatasetQualityChecker(str(tmp_path))
    report = checker.full_report()
    assert report["quality_score"] == 100.0
    assert report["class_counts"] == {"0": 5}
    assert report["corrupt_images"] == 0
    assert report["missing_labels"] == 0
    assert report["orphan_labels"] == 0


def test_missing_labels_detected(tmp_path):
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir()
    labels_dir.mkdir()
    import cv2
    import numpy as np
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.imwrite(str(images_dir / "img_0001.jpg"), img)
    cv2.imwrite(str(images_dir / "img_0002.jpg"), img)
    # Only one label file
    with open(labels_dir / "img_0001.txt", "w") as f:
        f.write("0 0.5 0.5 0.1 0.1\n")

    checker = DatasetQualityChecker(str(tmp_path))
    report = checker.full_report()
    assert report["missing_labels"] == 1
    assert report["quality_score"] < 100


def test_orphan_labels_detected(tmp_path):
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir()
    labels_dir.mkdir()
    import cv2
    import numpy as np
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.imwrite(str(images_dir / "img_0001.jpg"), img)
    # Two label files, one orphan
    with open(labels_dir / "img_0001.txt", "w") as f:
        f.write("0 0.5 0.5 0.1 0.1\n")
    with open(labels_dir / "img_0002.txt", "w") as f:
        f.write("1 0.5 0.5 0.1 0.1\n")

    checker = DatasetQualityChecker(str(tmp_path))
    report = checker.full_report()
    assert report["orphan_labels"] == 1


def test_corrupt_images_detected(tmp_path):
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir()
    labels_dir.mkdir()
    # Corrupt image file
    with open(images_dir / "bad.jpg", "w") as f:
        f.write("not an image")
    with open(labels_dir / "bad.txt", "w") as f:
        f.write("0 0.5 0.5 0.1 0.1\n")

    checker = DatasetQualityChecker(str(tmp_path))
    report = checker.full_report()
    assert report["corrupt_images"] == 1
