"""Production defect event persistence and NG image storage."""
from __future__ import annotations

import json
import os
import csv
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from core.storage import fetch_all, insert


@dataclass
class DefectEvent:
    event_id: str
    project_id: str
    spec_id: str
    batch_id: str
    camera_id: str
    event_time: str
    ng_image_path: str
    detection_count: int
    prediction_json: str
    model_version: str = ""
    defect_type: str = ""
    max_confidence: float = 0.0
    position_meter: float | None = None
    status: str = "ng"

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "DefectEvent":
        return cls(
            event_id=row["event_id"],
            project_id=row["project_id"],
            spec_id=row.get("spec_id", ""),
            batch_id=row.get("batch_id", ""),
            camera_id=row.get("camera_id", ""),
            event_time=row.get("event_time", ""),
            ng_image_path=row.get("ng_image_path", ""),
            detection_count=row.get("detection_count", 0),
            prediction_json=row.get("prediction_json", "{}"),
            model_version=row.get("model_version", ""),
            defect_type=row.get("defect_type", ""),
            max_confidence=float(row.get("max_confidence", 0.0)),
            position_meter=row.get("position_meter"),
            status=row.get("status", "ng"),
        )


def record_ng_event(
    project_id: str,
    spec_id: str = "",
    batch_id: str = "",
    camera_id: str = "",
    image=None,
    prediction=None,
    output_root: str = "",
    model_version: str = "",
    defect_type: str = "",
    position_meter: float | None = None,
    block_id: str = "",
    tile_id: str = "",
) -> DefectEvent:
    now = datetime.now()
    event_time = now.strftime("%Y-%m-%d %H:%M:%S.%f")
    event_id = f"{now.strftime('EVT_%Y%m%d_%H%M%S_%f')}_{uuid4().hex[:8]}"
    ng_image_path = ""

    if image is not None:
        import cv2

        root = output_root or "outputs"
        camera_dir = _camera_dir_name(camera_id)
        if os.path.basename(os.path.normpath(root)).lower() == "ng_images":
            base_dir = os.path.join(root, camera_dir)
        else:
            base_dir = os.path.join(root, "ng_images", camera_dir)
        os.makedirs(base_dir, exist_ok=True)
        ng_image_path = os.path.join(base_dir, f"{event_id}.jpg")
        if not cv2.imwrite(ng_image_path, image):
            raise RuntimeError(f"failed to save NG image: {ng_image_path}")

    detections = getattr(prediction, "detections", []) if prediction is not None else []
    max_conf = max((d.confidence for d in detections), default=0.0)
    prediction_json = json.dumps(
        {
            "image_name": getattr(prediction, "image_name", ""),
            "detections": [
                _detection_to_dict(d)
                for d in detections
            ],
            "block_id": block_id,
            "tile_id": tile_id,
        },
        ensure_ascii=False,
    )

    # Auto-derive defect_type from top confidence detection if not provided
    if not defect_type and detections:
        best = max(detections, key=lambda d: d.confidence if hasattr(d, "confidence") else 0)
        defect_type = getattr(best, "class_name", "")

    row = {
        "event_id": event_id,
        "project_id": project_id,
        "spec_id": spec_id,
        "batch_id": batch_id,
        "camera_id": camera_id,
        "event_time": event_time,
        "ng_image_path": ng_image_path,
        "detection_count": len(detections),
        "prediction_json": prediction_json,
        "model_version": model_version,
        "defect_type": defect_type,
        "max_confidence": max_conf,
        "position_meter": position_meter,
        "status": "ng",
    }
    insert("production_defect_events", row)
    _append_defect_files(
        output_root=output_root,
        row=row,
        block_id=block_id,
        tile_id=tile_id,
        image_path=ng_image_path,
    )
    _audit("production_ng_event", f"{event_id} camera={camera_id} model={model_version}")
    return DefectEvent.from_dict(row)


def list_defect_events(
    project_id: str | None = None,
    spec_id: str | None = None,
    batch_id: str | None = None,
) -> list[DefectEvent]:
    conditions: list[str] = []
    params: list[str] = []
    if project_id:
        conditions.append("project_id = ?")
        params.append(project_id)
    if spec_id:
        conditions.append("spec_id = ?")
        params.append(spec_id)
    if batch_id:
        conditions.append("batch_id = ?")
        params.append(batch_id)
    where = " AND ".join(conditions) if conditions else "1"
    where += " ORDER BY event_time DESC"
    return [
        DefectEvent.from_dict(row)
        for row in fetch_all("production_defect_events", where=where, params=tuple(params))
    ]


def _camera_dir_name(camera_id: str) -> str:
    if not camera_id:
        return "CAM_UNKNOWN"
    upper = camera_id.upper()
    if upper.startswith("CAM_"):
        return upper
    if upper.startswith("CAM") and upper[3:].isdigit():
        return f"CAM_{int(upper[3:]):02d}"
    if upper.startswith("CAMERA") and upper[6:].isdigit():
        return f"CAM_{int(upper[6:]):02d}"
    return upper


def _detection_to_dict(det: Any) -> dict[str, Any]:
    if hasattr(det, "to_dict"):
        data = det.to_dict()
    elif isinstance(det, dict):
        data = dict(det)
    else:
        data = {
            "class_name": getattr(det, "class_name", ""),
            "confidence": getattr(det, "confidence", 0.0),
            "bbox": getattr(det, "bbox", []),
        }
    for attr in ("block_x", "block_y", "tile_id", "meter_start", "meter_end"):
        if hasattr(det, attr):
            data[attr] = getattr(det, attr)
    return data


def _append_defect_files(
    output_root: str,
    row: dict[str, Any],
    block_id: str,
    tile_id: str,
    image_path: str,
) -> None:
    if not output_root:
        return
    results_dir = os.path.join(output_root, "results")
    os.makedirs(results_dir, exist_ok=True)
    csv_path = os.path.join(results_dir, "defects.csv")
    jsonl_path = os.path.join(results_dir, "defects.jsonl")
    fields = [
        "time", "camera_id", "block_id", "tile_id", "defect_type", "score",
        "x", "y", "w", "h", "meter_position", "model_version", "image_path",
    ]
    pred = json.loads(row["prediction_json"])
    detections = pred.get("detections", [])
    if detections:
        rows = [
            _defect_file_row(row, det, block_id, tile_id, image_path)
            for det in detections
        ]
    else:
        rows = [_defect_file_row(row, {}, block_id, tile_id, image_path)]

    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    with open(jsonl_path, "a", encoding="utf-8") as f:
        for item in rows:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _defect_file_row(
    event_row: dict[str, Any],
    det: dict[str, Any],
    block_id: str,
    tile_id: str,
    image_path: str,
) -> dict[str, Any]:
    bbox = det.get("bbox") or [0, 0, 0, 0]
    x, y, w, h = (list(bbox) + [0, 0, 0, 0])[:4]
    return {
        "time": event_row["event_time"],
        "camera_id": event_row["camera_id"],
        "block_id": block_id or det.get("block_id", ""),
        "tile_id": tile_id or det.get("tile_id", ""),
        "defect_type": event_row["defect_type"] or det.get("class_name", ""),
        "score": det.get("confidence", event_row["max_confidence"]),
        "x": det.get("block_x", x),
        "y": det.get("block_y", y),
        "w": w,
        "h": h,
        "meter_position": event_row["position_meter"],
        "model_version": event_row["model_version"],
        "image_path": image_path,
    }


def _audit(action: str, detail: str) -> None:
    try:
        from core.log_manager import LogManager

        LogManager.instance().log_audit(action, detail)
    except Exception:
        pass
