"""Folder watcher camera adapter — reads images from directory as simulated camera feed."""
from __future__ import annotations

import os
import time
from collections import deque
from threading import Lock

from camera_adapters.base import BaseCameraAdapter


class FolderWatcherCameraAdapter(BaseCameraAdapter):
    adapter_name = "folder_watcher"

    def __init__(self):
        self._watch_dir = ""
        self._connected = False
        self._acquiring = False
        self._frame_buffer: deque = deque(maxlen=100)
        self._image_files: list[str] = []
        self._current_index = 0
        self._fps = 0.0
        self._frame_count = 0
        self._start_time = 0.0
        self._lock = Lock()
        self._loop_count = 0

    def list_devices(self) -> list[dict]:
        return [{"id": "folder_watcher_0", "name": "目录监听相机 (Folder Watcher)"}]

    def connect(self, config: dict) -> bool:
        self._watch_dir = config.get("watch_dir", "")
        if self._watch_dir and not os.path.isdir(self._watch_dir):
            os.makedirs(self._watch_dir, exist_ok=True)
        self._connected = True
        return True

    def disconnect(self) -> None:
        self.stop_acquisition()
        self._connected = False

    def start_acquisition(self) -> None:
        self._acquiring = True
        self._current_index = 0
        self._frame_count = 0
        self._start_time = time.time()
        self._refresh_file_list()

    def stop_acquisition(self) -> None:
        self._acquiring = False

    def _refresh_file_list(self) -> None:
        if not self._watch_dir or not os.path.isdir(self._watch_dir):
            self._image_files = []
            return
        exts = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        self._image_files = sorted([
            os.path.join(self._watch_dir, f)
            for f in os.listdir(self._watch_dir)
            if os.path.splitext(f)[1].lower() in exts
        ])

    def get_frame(self):
        import cv2
        with self._lock:
            if not self._acquiring:
                return None
            if not self._image_files:
                self._refresh_file_list()
            if not self._image_files:
                return None

            path = self._image_files[self._current_index % len(self._image_files)]
            self._current_index += 1
            if self._current_index >= len(self._image_files):
                self._current_index = 0
                self._loop_count += 1
                self._refresh_file_list()  # Check for new files each loop

            img = cv2.imread(path)
            if img is not None:
                self._frame_count += 1
                elapsed = time.time() - self._start_time
                if elapsed > 0:
                    self._fps = self._frame_count / elapsed
            return img

    def get_status(self) -> dict:
        return {
            "connected": self._connected,
            "acquiring": self._acquiring,
            "fps": round(self._fps, 1),
            "frame_count": self._frame_count,
            "watch_dir": self._watch_dir,
            "image_count": len(self._image_files),
            "loop_count": self._loop_count,
        }

    def set_exposure(self, exposure_us: float) -> None:
        pass  # Folder watcher is simulated — no hardware exposure control

    def set_gain(self, gain_db: float) -> None:
        pass  # Folder watcher is simulated — no hardware gain control

    def set_trigger_mode(self, mode: str) -> None:
        pass  # Folder watcher is simulated — no hardware trigger

    def set_roi(self, x: int, y: int, w: int, h: int) -> None:
        pass  # Folder watcher is simulated — no hardware ROI
