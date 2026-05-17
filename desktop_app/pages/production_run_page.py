"""Production run page — real-time detection with simulated camera."""
from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QGroupBox, QGridLayout, QMessageBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
)

from camera_adapters.folder_watcher import FolderWatcherCameraAdapter
from runtime.frame_buffer import FrameBuffer
from runtime.acquisition_pipeline import AcquisitionPipeline
from runtime.inference_pipeline import InferencePipeline
from runtime.health_monitor import HealthMonitor
from core.model_version import list_model_versions, get_model_version
from core.production_event import record_ng_event
from desktop_app.display import model_type_label
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, bind, I18nManager


class ProductionRunPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._acq = AcquisitionPipeline(buffer_size=50)
        self._buffer = self._acq.get_buffer()
        self._inference = InferencePipeline(self._buffer)
        self._health = HealthMonitor()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_display)
        self._ng_images: list[str] = []
        self._events: list[dict] = []
        self._watch_dir_path = ""
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Top control bar
        ctrl = QHBoxLayout()
        model_label = QLabel()
        bind(model_label, "production.model")
        ctrl.addWidget(model_label)
        self._model_combo = QComboBox(); self._model_combo.setMinimumWidth(200)
        ctrl.addWidget(self._model_combo)

        watch_label = QLabel()
        bind(watch_label, "production.watch_dir")
        ctrl.addWidget(watch_label)
        self._dir_label = QLabel()
        bind(self._dir_label, "app.not_configured")
        self._dir_label.setStyleSheet("color: #888;")
        ctrl.addWidget(self._dir_label)

        from PySide6.QtWidgets import QFileDialog
        browse_btn = QPushButton()
        bind(browse_btn, "inference.select_dir")
        browse_btn.clicked.connect(self._browse_dir)
        ctrl.addWidget(browse_btn)

        self._start_btn = QPushButton()
        bind(self._start_btn, "production.start")
        self._start_btn.clicked.connect(self._start)
        ctrl.addWidget(self._start_btn)
        self._stop_btn = QPushButton()
        bind(self._stop_btn, "production.stop")
        self._stop_btn.setObjectName("dangerBtn")
        self._stop_btn.setEnabled(False); self._stop_btn.clicked.connect(self._stop)
        ctrl.addWidget(self._stop_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Main area: live image + status
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Live image display
        img_widget = QWidget()
        img_layout = QVBoxLayout(img_widget); img_layout.setContentsMargins(0, 0, 0, 0)
        self._live_label = QLabel()
        bind(self._live_label, "production.live_view")
        self._live_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._live_label.setMinimumSize(400, 300)
        self._live_label.setStyleSheet("background-color: #111; border: 1px solid #3E3E3E; color: #888;")
        img_layout.addWidget(self._live_label, 1)
        self._cam_status_group = QGroupBox()
        bind(self._cam_status_group, "production.cam_status", setter="setTitle")
        cs_layout = QGridLayout(self._cam_status_group)
        self._cam_status_labels: dict[str, QLabel] = {}
        for i in range(1, 5):
            lbl = QLabel()
            bind(lbl, "production.cam_offline", i=i)
            lbl.setStyleSheet("color: #888;")
            cs_layout.addWidget(lbl, (i-1)//2, (i-1)%2)
            self._cam_status_labels[f"cam{i}"] = lbl
        img_layout.addWidget(self._cam_status_group)
        splitter.addWidget(img_widget)

        # Right panel: NG images + events
        right = QWidget()
        right_layout = QVBoxLayout(right); right_layout.setContentsMargins(0, 0, 0, 0)

        ng_group = QGroupBox()
        bind(ng_group, "production.recent_ng", setter="setTitle")
        ng_layout = QVBoxLayout(ng_group)
        self._ng_label = QLabel()
        bind(self._ng_label, "production.no_ng")
        self._ng_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ng_label.setMinimumHeight(200)
        self._ng_label.setStyleSheet("background-color: #111; border: 1px solid #3E3E3E; color: #888;")
        ng_layout.addWidget(self._ng_label)
        right_layout.addWidget(ng_group)

        evt_group = QGroupBox()
        bind(evt_group, "production.defect_events", setter="setTitle")
        evt_layout = QVBoxLayout(evt_group)
        self._event_table = QTableWidget(0, 4)
        self._event_table.setHorizontalHeaderLabels([tr("production.col_time"), tr("production.col_camera"), tr("production.col_dets"), tr("production.col_ng")])
        self._event_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        evt_layout.addWidget(self._event_table)
        right_layout.addWidget(evt_group)

        splitter.addWidget(right)
        splitter.setSizes([500, 300])
        layout.addWidget(splitter, 1)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set combo placeholder, table headers on language change."""
        self._event_table.setHorizontalHeaderLabels([tr("production.col_time"), tr("production.col_camera"), tr("production.col_dets"), tr("production.col_ng")])
        self._model_combo.clear(); self._model_combo.addItem(tr("app.select_model"), "")
        pid = self._ctx.current_project_id
        if pid:
            for m in list_model_versions(pid):
                self._model_combo.addItem(f"{m.model_name} ({model_type_label(m.model_type)})", m.model_id)

    def showEvent(self, event):
        super().showEvent(event)
        self._model_combo.clear(); self._model_combo.addItem(tr("app.select_model"), "")
        pid = self._ctx.current_project_id
        if pid:
            for m in list_model_versions(pid):
                self._model_combo.addItem(f"{m.model_name} ({model_type_label(m.model_type)})", m.model_id)

    def _browse_dir(self):
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, tr("inference.select_dir"))
        if d:
            self._dir_label.setText(d)
            self._watch_dir_path = d

    def _start(self):
        model_id = self._model_combo.currentData()
        watch_dir = self._watch_dir_path
        if not model_id: QMessageBox.information(self, tr("app.tip"), tr("app.select_model")); return
        if not watch_dir: QMessageBox.information(self, tr("app.tip"), tr("production.select_watch_dir")); return

        model = get_model_version(model_id)
        if not model: return

        # Setup camera
        cam = FolderWatcherCameraAdapter()
        cam.connect({"watch_dir": watch_dir})
        self._acq.add_camera("cam1", cam)

        # Setup inference
        try:
            from model_runners.yolo_runner import YoloModelRunner
            runner = YoloModelRunner(model_path=model.model_path, config={"confidence": 0.5, "device": "cpu"})
            runner.load()
            self._inference.set_runner(runner)
            self._inference.set_on_ng(self._on_ng_detected)
        except Exception as e:
            QMessageBox.critical(self, tr("production.model_load_failed"), str(e))
            return

        self._acq.start()
        self._inference.start()
        self._timer.start(200)  # Refresh at 5 FPS

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    def _stop(self):
        self._timer.stop()
        self._inference.stop()
        self._acq.stop()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _on_ng_detected(self, result):
        event = record_ng_event(
            project_id=self._ctx.current_project_id or "unknown",
            spec_id=self._ctx.current_spec_id,
            batch_id="default",
            camera_id=result.get("camera_id", ""),
            image=result.get("image"),
            prediction=result.get("prediction"),
        )
        self._ng_images.append(event.ng_image_path)
        self._events.append({
            "time": event.event_time,
            "camera": event.camera_id,
            "dets": event.detection_count,
            "ng": True,
        })
        if len(self._ng_images) > 20:
            self._ng_images = self._ng_images[-20:]

    def _refresh_display(self):
        # Update camera status
        statuses = self._acq.get_status()
        for st in statuses:
            cid = st.get("camera_id", "")
            lbl = self._cam_status_labels.get(cid)
            if lbl:
                lbl.setText(tr("production.cam_status_fmt", cam=cid, fps=st.get("fps", 0), frames=st.get("frame_count", 0)))

        # Show latest frame
        latest = self._buffer.get_latest()
        if latest is not None:
            img = latest["image"]
            import cv2
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg).scaled(
                self._live_label.width(), self._live_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
            )
            self._live_label.setPixmap(pixmap)

        if self._ng_images:
            ng_path = self._ng_images[-1]
            if os.path.isfile(ng_path):
                self._ng_label.setPixmap(
                    QPixmap(ng_path).scaled(
                        self._ng_label.width(), self._ng_label.height(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

        # Update event table
        recent = self._events[-20:]
        self._event_table.setRowCount(len(recent))
        for row, evt in enumerate(reversed(recent)):
            self._event_table.setItem(row, 0, QTableWidgetItem(str(evt.get("time", ""))[-12:]))
            self._event_table.setItem(row, 1, QTableWidgetItem(evt.get("camera", "")))
            self._event_table.setItem(row, 2, QTableWidgetItem(str(evt.get("dets", 0))))
            self._event_table.setItem(row, 3, QTableWidgetItem("NG" if evt.get("ng") else "OK"))
