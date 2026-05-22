"""CaptureSession data model and operations."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from core.id_utils import generate_id
from core.storage import delete, fetch_all, fetch_one, insert, update


@dataclass
class CaptureSession:
    session_id: str
    project_id: str
    spec_id: str
    session_name: str
    source_type: str = "directory_watch"
    watch_dirs: str = "{}"
    camera_count: int = 3
    target_image_count: int = 100
    captured_image_count: int = 0
    line_speed_mpm: float = 80.0
    sampling_mode: str = "directory_watch"
    dataset_task_type: str = ""
    status: str = "created"
    output_dir: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "spec_id": self.spec_id,
            "session_name": self.session_name,
            "source_type": self.source_type,
            "watch_dirs": self.watch_dirs,
            "camera_count": self.camera_count,
            "target_image_count": self.target_image_count,
            "captured_image_count": self.captured_image_count,
            "line_speed_mpm": self.line_speed_mpm,
            "sampling_mode": self.sampling_mode,
            "dataset_task_type": self.dataset_task_type,
            "status": self.status,
            "output_dir": self.output_dir,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> CaptureSession:
        return cls(
            session_id=d["session_id"],
            project_id=d["project_id"],
            spec_id=d["spec_id"],
            session_name=d["session_name"],
            source_type=d.get("source_type", "directory_watch"),
            watch_dirs=d.get("watch_dirs", "{}"),
            camera_count=d.get("camera_count", 3),
            target_image_count=d.get("target_image_count", 100),
            captured_image_count=d.get("captured_image_count", 0),
            line_speed_mpm=d.get("line_speed_mpm", 80.0),
            sampling_mode=d.get("sampling_mode", "directory_watch"),
            dataset_task_type=d.get("dataset_task_type", ""),
            status=d.get("status", "created"),
            output_dir=d.get("output_dir"),
            started_at=d.get("started_at"),
            ended_at=d.get("ended_at"),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


def _gen_id() -> str:
    return generate_id("SESS")


def create_capture_session(
    project_id: str,
    spec_id: str,
    session_name: str,
    source_type: str = "directory_watch",
    watch_dirs: str = "{}",
    camera_count: int = 3,
    target_image_count: int = 100,
    line_speed_mpm: float = 80.0,
    sampling_mode: str = "directory_watch",
    dataset_task_type: str = "",
    output_dir: str | None = None,
) -> CaptureSession:
    s = CaptureSession(
        session_id=_gen_id(),
        project_id=project_id,
        spec_id=spec_id,
        session_name=session_name,
        source_type=source_type,
        watch_dirs=watch_dirs,
        camera_count=camera_count,
        target_image_count=target_image_count,
        line_speed_mpm=line_speed_mpm,
        sampling_mode=sampling_mode,
        dataset_task_type=dataset_task_type,
        output_dir=output_dir,
    )
    insert("capture_sessions", s.to_dict())
    return s


def get_capture_session(session_id: str) -> CaptureSession | None:
    row = fetch_one("capture_sessions", session_id, "session_id")
    return CaptureSession.from_dict(row) if row else None


def list_capture_sessions(project_id: str | None = None) -> list[CaptureSession]:
    if project_id:
        rows = fetch_all(
            "capture_sessions",
            where="project_id = ? ORDER BY created_at DESC",
            params=(project_id,),
        )
    else:
        rows = fetch_all("capture_sessions", where="1 ORDER BY created_at DESC")
    return [CaptureSession.from_dict(r) for r in rows]


def update_capture_session(session_id: str, **kwargs) -> CaptureSession | None:
    existing = get_capture_session(session_id)
    if not existing:
        return None
    for k, v in kwargs.items():
        if hasattr(existing, k) and v is not None:
            setattr(existing, k, v)
    update("capture_sessions", session_id, existing.to_dict(), "session_id")
    return existing


def delete_capture_session(session_id: str) -> None:
    delete("capture_sessions", session_id, "session_id")


def add_captured_image(session_id: str, project_id: str, image_path: str,
                       image_name: str, camera_id: str = "", frame_index: int = 0,
                       width: int = 0, height: int = 0) -> str:
    existing = fetch_all(
        "captured_images",
        where=(
            "session_id = ? AND (image_path = ? OR "
            "(image_name = ? AND camera_id = ?)) LIMIT 1"
        ),
        params=(session_id, image_path, image_name, camera_id),
    )
    if existing:
        return existing[0]["image_id"]

    img_id = generate_id("IMG")
    insert("captured_images", {
        "image_id": img_id,
        "session_id": session_id,
        "project_id": project_id,
        "image_path": image_path,
        "image_name": image_name,
        "camera_id": camera_id,
        "frame_index": frame_index,
        "width": width,
        "height": height,
    })
    refresh_capture_session_count(session_id)
    return img_id


def refresh_capture_session_count(session_id: str) -> int:
    count = len(list_captured_images(session_id))
    update("capture_sessions", session_id, {"captured_image_count": count}, "session_id")
    return count


def list_captured_images(session_id: str, camera_id: str | None = None,
                         label: str | None = None) -> list[dict]:
    conditions = ["session_id = ?"]
    params: list = [session_id]
    if camera_id:
        conditions.append("camera_id = ?")
        params.append(camera_id)
    if label is not None:
        if label == "":
            conditions.append("(classification_label = '' OR classification_label IS NULL)")
        else:
            conditions.append("classification_label = ?")
            params.append(label)
    where = " AND ".join(conditions)
    return fetch_all("captured_images", where=where, params=tuple(params))


def get_classification_counts(session_id: str) -> dict[str, int]:
    rows = fetch_all(
        "captured_images",
        where="session_id = ? AND classification_label != '' AND classification_label IS NOT NULL",
        params=(session_id,),
    )
    counts: dict[str, int] = {}
    for r in rows:
        lbl = r.get("classification_label", "")
        if lbl:
            counts[lbl] = counts.get(lbl, 0) + 1
    return counts


def set_image_classification(image_id: str, label: str) -> None:
    update("captured_images", image_id, {"classification_label": label}, "image_id")


def set_session_task_type(session_id: str, task_type: str) -> bool:
    """Set the dataset_task_type on a capture session. Returns True if updated."""
    existing = get_capture_session(session_id)
    if existing is None:
        return False
    update("capture_sessions", session_id, {"dataset_task_type": task_type}, "session_id")
    return True


def get_session_task_type(session_id: str) -> str:
    """Get the dataset_task_type for a session, or empty string."""
    session = get_capture_session(session_id)
    return session.dataset_task_type if session else ""


def session_output_root(project_id: str) -> str:
    from core.project import PROJECT_DATA_ROOT, get_project
    p = get_project(project_id)
    customer_id = p.customer_id if p else "unknown"
    return os.path.join(
        PROJECT_DATA_ROOT, f"customer_{customer_id}",
        f"project_{project_id}", "sample_sessions"
    )
