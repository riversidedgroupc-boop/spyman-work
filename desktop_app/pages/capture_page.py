"""Capture page — create and manage sample capture sessions."""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import Qt, Signal

from desktop_app.i18n import tr, bind, I18nManager
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QDialog, QFormLayout,
    QLineEdit, QSpinBox, QDialogButtonBox, QLabel, QProgressBar, QFileDialog,
    QComboBox,
)

from core.capture_session import (
    create_capture_session, list_capture_sessions, update_capture_session,
    delete_capture_session, session_output_root, add_captured_image,
    refresh_capture_session_count, get_capture_session,
)
from desktop_app.display import SESSION_STATUS_OPTIONS, session_status_label
from desktop_app.app_context import AppContext
from desktop_app.workers.folder_watch_worker import FolderWatchWorker


class CapturePage(QWidget):
    data_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._worker: FolderWatchWorker | None = None
        self._active_session_id = ""
        self._active_project_id = ""
        self._build_ui()
        self._refresh()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Button bar
        btn_layout = QHBoxLayout()
        add_btn = QPushButton()
        bind(add_btn, "capture.new_session")
        add_btn.clicked.connect(self._add_session)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton()
        bind(edit_btn, "app.edit")
        edit_btn.setObjectName("secondaryBtn")
        edit_btn.clicked.connect(self._edit_session)
        btn_layout.addWidget(edit_btn)
        del_btn = QPushButton()
        bind(del_btn, "app.delete")
        del_btn.setObjectName("dangerBtn")
        del_btn.clicked.connect(self._delete_session)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Session table
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            tr("capture.col_id"), tr("capture.col_name"), tr("capture.col_status"),
            tr("capture.col_cameras"), tr("capture.col_target"), tr("capture.col_captured"),
            tr("project.col_created"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemDoubleClicked.connect(lambda _item: self._edit_session())
        layout.addWidget(self._table, 1)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888;")
        layout.addWidget(self._status_label)

        # Control buttons
        ctrl_layout = QHBoxLayout()
        self._start_btn = QPushButton()
        bind(self._start_btn, "capture.start")
        self._start_btn.clicked.connect(self._start_capture)
        ctrl_layout.addWidget(self._start_btn)
        self._stop_btn = QPushButton()
        bind(self._stop_btn, "capture.stop")
        self._stop_btn.setObjectName("dangerBtn")
        self._stop_btn.clicked.connect(self._stop_capture)
        self._stop_btn.setEnabled(False)
        ctrl_layout.addWidget(self._stop_btn)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set table headers on language change."""
        self._table.setHorizontalHeaderLabels([
            tr("capture.col_id"), tr("capture.col_name"), tr("capture.col_status"),
            tr("capture.col_cameras"), tr("capture.col_target"), tr("capture.col_captured"),
            tr("project.col_created"),
        ])

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        pid = self._ctx.current_project_id
        sessions = list_capture_sessions(pid) if pid else []
        self._table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            self._table.setItem(row, 0, QTableWidgetItem(s.session_id))
            self._table.setItem(row, 1, QTableWidgetItem(s.session_name))
            status_item = QTableWidgetItem(session_status_label(s.status))
            status_item.setData(Qt.ItemDataRole.UserRole, s.status)
            self._table.setItem(row, 2, status_item)
            self._table.setItem(row, 3, QTableWidgetItem(str(s.camera_count)))
            self._table.setItem(row, 4, QTableWidgetItem(str(s.target_image_count)))
            self._table.setItem(row, 5, QTableWidgetItem(str(s.captured_image_count)))
            self._table.setItem(row, 6, QTableWidgetItem(s.created_at or ""))

    def _add_session(self) -> None:
        pid = self._ctx.current_project_id
        sid = self._ctx.current_spec_id
        if not pid:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_project_first"))
            return
        dlg = CreateSessionDialog(self, project_id=pid, spec_id=sid)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            data["project_id"] = pid
            data["spec_id"] = sid or ""
            data["output_dir"] = session_output_root(pid)
            create_capture_session(**data)
            self._refresh()
            self.data_changed.emit()

    def _edit_session(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_session"))
            return
        sid = self._table.item(row, 0).text()
        sess = get_capture_session(sid)
        if not sess:
            return
        if self._worker and self._worker.isRunning() and sid == self._active_session_id:
            QMessageBox.warning(self, tr("app.warning"), "采集运行中，请先停止再编辑。")
            return
        dlg = CreateSessionDialog(self, project_id=sess.project_id, spec_id=sess.spec_id, session=sess)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            update_capture_session(sid, **dlg.get_data())
            self._refresh()
            self.data_changed.emit()

    def _delete_session(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        sid = self._table.item(row, 0).text()
        delete_capture_session(sid)
        self._refresh()

    def _start_capture(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_session"))
            return
        sid = self._table.item(row, 0).text()
        import json
        from core.capture_session import get_capture_session
        sess = get_capture_session(sid)
        if not sess:
            return

        watch_dirs = json.loads(sess.watch_dirs)
        output_root = os.path.join(
            sess.output_dir or session_output_root(sess.project_id),
            sess.session_id, "raw"
        )
        self._active_session_id = sess.session_id
        self._active_project_id = sess.project_id

        self._worker = FolderWatchWorker(
            watch_dirs=watch_dirs,
            output_root=output_root,
            camera_count=sess.camera_count,
            target_count=sess.target_image_count,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.message.connect(self._on_message)
        self._worker.image_captured.connect(self._on_image_captured)
        self._worker.finished.connect(self._on_capture_finished)
        self._worker.error.connect(self._on_capture_error)

        update_capture_session(
            sid,
            status="running",
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        )
        self._worker.start()

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress.setVisible(True)
        self._progress.setMaximum(sess.target_image_count)

    def _stop_capture(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)

    def _on_progress(self, current: int, total: int) -> None:
        self._progress.setValue(current)

    def _on_message(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _on_image_captured(self, path: str, camera_id: str, name: str) -> None:
        if self._active_session_id and self._active_project_id:
            add_captured_image(
                self._active_session_id,
                self._active_project_id,
                path,
                name,
                camera_id=camera_id,
            )
        row = self._table.currentRow()
        if row >= 0:
            item = self._table.item(row, 5)
            if item:
                item.setText(str(int(item.text() or 0) + 1))

    def _on_capture_finished(self) -> None:
        if self._active_session_id:
            count = refresh_capture_session_count(self._active_session_id)
            status = "cancelled" if self._worker and self._worker.is_cancelled() else "completed"
            update_capture_session(
                self._active_session_id,
                captured_image_count=count,
                status=status,
                ended_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            )
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._refresh()
        self.data_changed.emit()

    def _on_capture_error(self, err: str) -> None:
        QMessageBox.critical(self, tr("capture.capture_error"), err)
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)


class CreateSessionDialog(QDialog):
    def __init__(self, parent=None, project_id: str = "", spec_id: str = "", session=None) -> None:
        super().__init__(parent)
        self._project_id = project_id
        self._spec_id = spec_id
        self._session = session
        if session:
            self.setWindowTitle("编辑采集会话")
        else:
            bind(self, "session.title", setter="setWindowTitle")
        self.setMinimumWidth(550)
        self._build_ui()
        if session:
            self._load_session(session)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(tr("session.name_placeholder"))
        name_label = QLabel()
        bind(name_label, "session.name")
        form.addRow(name_label, self._name_edit)

        self._camera_count = QSpinBox()
        self._camera_count.setRange(1, 6)
        self._camera_count.setValue(3)
        cam_label = QLabel()
        bind(cam_label, "session.camera_count")
        form.addRow(cam_label, self._camera_count)

        self._target_count = QSpinBox()
        self._target_count.setRange(1, 10000)
        self._target_count.setValue(100)
        target_label = QLabel()
        bind(target_label, "session.target_count")
        form.addRow(target_label, self._target_count)

        self._status_combo = QComboBox()
        for value, label in SESSION_STATUS_OPTIONS:
            self._status_combo.addItem(label, value)
        status_label = QLabel(tr("app.status"))
        form.addRow(status_label, self._status_combo)
        self._status_combo.setVisible(self._session is not None)
        status_label.setVisible(self._session is not None)

        layout.addLayout(form)

        watch_dir_label = QLabel()
        bind(watch_dir_label, "session.watch_dir_label")
        layout.addWidget(watch_dir_label)
        self._watch_edits: dict[str, QLineEdit] = {}
        for i in range(1, 7):
            row = QHBoxLayout()
            cam_lbl = QLabel()
            bind(cam_lbl, "session.camera_label", cam=i)
            row.addWidget(cam_lbl)
            edit = QLineEdit()
            edit.setPlaceholderText(tr("session.watch_dir_placeholder", cam=i))
            row.addWidget(edit)
            browse_btn = QPushButton()
            bind(browse_btn, "app.browse")
            browse_btn.setFixedWidth(36)
            browse_btn.clicked.connect(lambda checked, e=edit: self._browse_dir(e))
            row.addWidget(browse_btn)
            self._watch_edits[f"cam{i}"] = edit
            layout.addLayout(row)

        layout.addSpacing(10)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_dir(self, edit: QLineEdit) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, tr("app.browse"))
        if dir_path:
            edit.setText(dir_path)

    def _load_session(self, session) -> None:
        import json

        self._name_edit.setText(session.session_name)
        self._camera_count.setValue(session.camera_count)
        self._target_count.setValue(session.target_image_count)
        status_index = self._status_combo.findData(session.status)
        if status_index >= 0:
            self._status_combo.setCurrentIndex(status_index)
        try:
            watch_dirs = json.loads(session.watch_dirs or "{}")
        except json.JSONDecodeError:
            watch_dirs = {}
        for cam_id, path in watch_dirs.items():
            edit = self._watch_edits.get(cam_id)
            if edit:
                edit.setText(path)

    def get_data(self) -> dict:
        import json
        watch_dirs: dict[str, str] = {}
        for cam_id, edit in self._watch_edits.items():
            val = edit.text().strip()
            if val:
                watch_dirs[cam_id] = val
        data = {
            "session_name": self._name_edit.text().strip() or tr("session.default_name"),
            "camera_count": self._camera_count.value(),
            "target_image_count": self._target_count.value(),
            "watch_dirs": json.dumps(watch_dirs, ensure_ascii=False),
        }
        if self._session is not None:
            data["status"] = self._status_combo.currentData()
        return data
