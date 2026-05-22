"""Tests for core.dataset_validation — YOLO detection / classification / anomaly validation."""
from __future__ import annotations

from unittest.mock import MagicMock

from core.dataset_validation import (
    DatasetValidationResult,
    _is_ng_label,
    _is_ok_label,
    _find_sidecar_txt,
    _has_bboxes,
    validate_yolo_detection,
    validate_image_classification,
    validate_anomaly_detection,
    validate_dataset,
)


# ── Label helpers ──────────────────────────────────────────────────

def test_is_ng_label():
    assert _is_ng_label("裂纹") is True
    assert _is_ng_label("油污") is True
    assert _is_ng_label("NG-点伤") is True
    assert _is_ng_label("OK") is False
    assert _is_ng_label("UNKNOWN") is False
    assert _is_ng_label("INTERFERENCE") is False
    assert _is_ng_label("UNCERTAIN") is False
    assert _is_ng_label("IGNORE") is False
    assert _is_ng_label("") is False
    assert _is_ng_label("  ") is False


def test_is_ok_label():
    assert _is_ok_label("OK") is True
    assert _is_ok_label("unknown") is False
    assert _is_ok_label("INTERFERENCE") is True
    assert _is_ok_label("裂纹") is False
    assert _is_ok_label("") is True


# ── Sidecar .txt helpers ───────────────────────────────────────────

def test_find_sidecar_txt(tmp_path):
    img = tmp_path / "test.jpg"
    img.write_text("")
    assert _find_sidecar_txt(str(img)) == ""

    txt = tmp_path / "test.txt"
    txt.write_text("0 0.5 0.5 0.1 0.1\n")
    assert _find_sidecar_txt(str(img)) == str(txt)


def test_has_bboxes_positive(tmp_path):
    img = tmp_path / "img.png"
    img.write_text("")
    (tmp_path / "img.txt").write_text("0 0.5 0.5 0.2 0.2\n")
    assert _has_bboxes(str(img)) is True


def test_has_bboxes_no_file(tmp_path):
    img = tmp_path / "img.png"
    img.write_text("")
    assert _has_bboxes(str(img)) is False


def test_has_bboxes_empty_file(tmp_path):
    img = tmp_path / "img.png"
    img.write_text("")
    (tmp_path / "img.txt").write_text("")
    assert _has_bboxes(str(img)) is False


def test_has_bboxes_invalid_lines(tmp_path):
    img = tmp_path / "img.png"
    img.write_text("")
    (tmp_path / "img.txt").write_text("0 0.5 0.5\n")  # only 3 tokens
    assert _has_bboxes(str(img)) is False


# ── DatasetValidationResult dataclass ──────────────────────────────

def test_result_defaults():
    r = DatasetValidationResult()
    assert r.task_type == ""
    assert r.total_images == 0
    assert r.can_train is False
    assert r.warnings == []
    assert r.errors == []


def test_result_summary():
    r = DatasetValidationResult(
        task_type="yolo_detection",
        total_images=100,
        ok_images=80,
        ng_images=15,
        unlabeled_images=5,
        missing_bbox_ng_images=3,
        class_distribution={"OK": 80, "裂纹": 10, "油污": 5},
        can_train=False,
        errors=["3 NG image(s) missing bbox annotations"],
    )
    s = r.summary()
    assert "yolo_detection" in s
    assert "Total images: 100" in s
    assert "NG images missing bbox: 3" in s
    assert "Can train: NO" in s


# ── validate_yolo_detection ────────────────────────────────────────

def _mock_session(rows):
    """Create a mock session + list_captured_images return."""
    return [
        MagicMock(
            __class__=dict,
            dataset_task_type="yolo_detection",
            output_dir="/fake/output",
        ),
        rows,
    ]


def _img_row(label, path):
    return {"classification_label": label, "image_path": path}


def test_yolo_validation_all_ok_no_ng(
    tmp_path, monkeypatch
):
    """OK images without bbox are fine; no NG means can't train."""
    img = tmp_path / "ok_img.png"
    img.write_text("")
    rows = [_img_row("OK", str(img))]

    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="yolo_detection"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: rows,
    )

    result = validate_yolo_detection("SESS_TEST")
    assert result.total_images == 1
    assert result.ok_images == 1
    assert result.ng_images == 0
    assert result.can_train is False
    assert any("No NG images" in e for e in result.errors)


def test_yolo_validation_ng_missing_bbox(
    tmp_path, monkeypatch
):
    """NG image without .txt sidecar → can_train=False."""
    img_ok = tmp_path / "ok.png"
    img_ok.write_text("")
    img_ng = tmp_path / "ng.png"
    img_ng.write_text("")

    rows = [
        _img_row("OK", str(img_ok)),
        _img_row("裂纹", str(img_ng)),
    ]
    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="yolo_detection"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: rows,
    )

    result = validate_yolo_detection("SESS_TEST")
    assert result.total_images == 2
    assert result.ng_images == 1
    assert result.missing_bbox_ng_images == 1
    assert result.can_train is False
    assert any("missing bbox" in e for e in result.errors)


def test_yolo_validation_ng_has_bbox(
    tmp_path, monkeypatch
):
    """NG image with valid .txt sidecar → can_train=True."""
    img_ok = tmp_path / "ok.png"
    img_ok.write_text("")
    img_ng = tmp_path / "ng.png"
    img_ng.write_text("")
    (tmp_path / "ng.txt").write_text("0 0.5 0.5 0.2 0.2\n")

    rows = [
        _img_row("OK", str(img_ok)),
        _img_row("裂纹", str(img_ng)),
    ]
    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="yolo_detection"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: rows,
    )

    result = validate_yolo_detection("SESS_TEST")
    assert result.ng_images == 1
    assert result.missing_bbox_ng_images == 0
    assert result.can_train is True


def test_yolo_validation_review_label_blocks_training(tmp_path, monkeypatch):
    """UNKNOWN/UNCERTAIN must be reviewed before YOLO training."""
    img_ok = tmp_path / "ok.png"
    img_ok.write_text("")
    img_review = tmp_path / "unknown.png"
    img_review.write_text("")
    img_ng = tmp_path / "ng.png"
    img_ng.write_text("")
    (tmp_path / "ng.txt").write_text("0 0.5 0.5 0.2 0.2\n")

    rows = [
        _img_row("OK", str(img_ok)),
        _img_row("UNKNOWN", str(img_review)),
        _img_row("裂纹", str(img_ng)),
    ]
    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="yolo_detection"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: rows,
    )

    result = validate_yolo_detection("SESS_TEST")
    assert result.review_images == 1
    assert result.can_train is False
    assert any("review image" in e for e in result.errors)


def test_yolo_validation_no_ok_warns(tmp_path, monkeypatch):
    """All NG with bbox but no OK → can train but warns."""
    img_ng = tmp_path / "ng.png"
    img_ng.write_text("")
    (tmp_path / "ng.txt").write_text("0 0.5 0.5 0.2 0.2\n")

    rows = [_img_row("裂纹", str(img_ng))]
    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="yolo_detection"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: rows,
    )

    result = validate_yolo_detection("SESS_TEST")
    assert result.can_train is True
    assert any("No OK" in w for w in result.warnings)


def test_yolo_validation_session_not_found(monkeypatch):
    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: None,
    )
    result = validate_yolo_detection("SESS_MISSING")
    assert result.can_train is False
    assert any("Session not found" in e for e in result.errors)


# ── validate_image_classification ──────────────────────────────────

def test_cls_validation_all_labeled_two_classes(tmp_path, monkeypatch):
    img1 = tmp_path / "a.png"
    img1.write_text("")
    img2 = tmp_path / "b.png"
    img2.write_text("")
    rows = [
        _img_row("裂纹", str(img1)),
        _img_row("OK", str(img2)),
    ]
    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="image_classification"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: rows,
    )

    result = validate_image_classification("SESS_TEST")
    assert result.can_train is True
    assert result.unlabeled_images == 0


def test_cls_validation_unlabeled_blocks(tmp_path, monkeypatch):
    img1 = tmp_path / "a.png"
    img1.write_text("")
    img2 = tmp_path / "b.png"
    img2.write_text("")
    rows = [
        _img_row("裂纹", str(img1)),
        _img_row("", str(img2)),
    ]
    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="image_classification"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: rows,
    )

    result = validate_image_classification("SESS_TEST")
    assert result.can_train is False
    assert result.unlabeled_images == 1


def test_cls_validation_single_class_blocks(tmp_path, monkeypatch):
    img1 = tmp_path / "a.png"
    img1.write_text("")
    img2 = tmp_path / "b.png"
    img2.write_text("")
    rows = [
        _img_row("OK", str(img1)),
        _img_row("OK", str(img2)),
    ]
    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="image_classification"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: rows,
    )

    result = validate_image_classification("SESS_TEST")
    assert result.can_train is False
    assert any("at least 2" in e for e in result.errors)


# ── validate_anomaly_detection ─────────────────────────────────────

def test_anomaly_validation_enough_ok(tmp_path, monkeypatch):
    images = []
    for i in range(12):
        img = tmp_path / f"ok_{i}.png"
        img.write_text("")
        images.append(_img_row("OK", str(img)))
    # add a few NG
    for i in range(3):
        img = tmp_path / f"ng_{i}.png"
        img.write_text("")
        images.append(_img_row("裂纹", str(img)))

    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="anomaly_detection"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: images,
    )

    result = validate_anomaly_detection("SESS_TEST")
    assert result.ok_images == 12
    assert result.ng_images == 3
    assert result.can_train is True


def test_anomaly_validation_too_few_ok(tmp_path, monkeypatch):
    images = []
    for i in range(5):
        img = tmp_path / f"ok_{i}.png"
        img.write_text("")
        images.append(_img_row("OK", str(img)))

    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="anomaly_detection"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: images,
    )

    result = validate_anomaly_detection("SESS_TEST")
    assert result.can_train is False
    assert any("at least 10" in e for e in result.errors)


def test_anomaly_validation_no_ng_warns(tmp_path, monkeypatch):
    images = []
    for i in range(15):
        img = tmp_path / f"ok_{i}.png"
        img.write_text("")
        images.append(_img_row("OK", str(img)))

    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="anomaly_detection"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: images,
    )

    result = validate_anomaly_detection("SESS_TEST")
    assert result.can_train is True
    assert any("No NG" in w for w in result.warnings)


# ── validate_dataset dispatcher ────────────────────────────────────

def test_validate_dataset_dispatches_by_session_task_type(tmp_path, monkeypatch):
    """validate_dataset reads task_type from session if not provided."""
    img = tmp_path / "img.png"
    img.write_text("")
    rows = [_img_row("OK", str(img))]

    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="image_classification"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: rows,
    )

    result = validate_dataset("SESS_TEST")
    assert result.task_type == "image_classification"


def test_validate_dataset_explicit_task_type(tmp_path, monkeypatch):
    img = tmp_path / "img.png"
    img.write_text("")
    rows = [_img_row("OK", str(img))]

    monkeypatch.setattr(
        "core.dataset_validation.get_capture_session",
        lambda sid: MagicMock(dataset_task_type="yolo_detection"),
    )
    monkeypatch.setattr(
        "core.dataset_validation.list_captured_images",
        lambda sid: rows,
    )

    result = validate_dataset("SESS_TEST", task_type="anomaly_detection")
    assert result.task_type == "anomaly_detection"
