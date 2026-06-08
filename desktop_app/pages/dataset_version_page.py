"""Dataset Version page — session list, version history, quality panel."""

from __future__ import annotations

import json
import os
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QMessageBox,
    QLabel,
    QGroupBox,
    QProgressBar,
    QSplitter,
    QTextEdit,
)

from core.capture_session import (
    list_capture_sessions,
    get_classification_counts,
    session_output_root,
    get_capture_session,
)
from core.dataset_builder import build_yolo_dataset_from_session
from core.anomaly_dataset_builder import build_anomaly_dataset_from_session
from core.dataset_version import list_dataset_versions, delete_dataset_version, get_dataset_version
from core.project import get_project_data_dir
from desktop_app.display import session_status_label
from desktop_app.app_context import AppContext
from desktop_app.workers.dataset_worker import DatasetBuildWorker
from desktop_app.i18n import tr, bind, I18nManager


class DatasetVersionPage(QWidget):
    """Replaces old DatasetPage with version management + quality panel."""

    data_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._worker: DatasetBuildWorker | None = None
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ---- Top: session list ----
        session_grp = QGroupBox()
        bind(session_grp, "dataset.available_sessions", setter="setTitle")
        sv = QVBoxLayout(session_grp)

        self._session_table = QTableWidget(0, 5)
        self._session_table.setHorizontalHeaderLabels(
            [
                tr("dataset.col_id"),
                tr("dataset.col_name"),
                tr("app.status"),
                tr("capture.col_captured"),
                tr("dataset.col_distribution"),
            ]
        )
        self._session_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._session_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._session_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._session_table.setMaximumHeight(180)
        sv.addWidget(self._session_table)

        # Buttons
        btn_row = QHBoxLayout()
        self._gen_yolo_btn = QPushButton()
        bind(self._gen_yolo_btn, "dataset_version.generate_yolo")
        self._gen_yolo_btn.setObjectName("primaryBtn")
        self._gen_yolo_btn.clicked.connect(lambda: self._generate("yolo"))
        btn_row.addWidget(self._gen_yolo_btn)

        self._gen_anom_btn = QPushButton()
        bind(self._gen_anom_btn, "dataset_version.generate_anomaly")
        self._gen_anom_btn.clicked.connect(lambda: self._generate("anomaly"))
        btn_row.addWidget(self._gen_anom_btn)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        btn_row.addWidget(self._progress_bar)

        btn_row.addStretch()
        sv.addLayout(btn_row)
        layout.addWidget(session_grp)

        # ---- Middle: version history ----
        hist_grp = QGroupBox()
        bind(hist_grp, "dataset_version.history", setter="setTitle")
        hv = QVBoxLayout(hist_grp)

        self._version_table = QTableWidget(0, 7)
        self._version_table.setHorizontalHeaderLabels(
            [
                tr("dataset_version.col_version"),
                tr("dataset_version.col_source"),
                tr("dataset_version.col_images"),
                tr("dataset_version.col_classes"),
                tr("dataset_version.col_quality"),
                tr("dataset_version.col_date"),
                "",
            ]
        )
        self._version_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._version_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._version_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._version_table.itemSelectionChanged.connect(self._on_version_selected)
        hv.addWidget(self._version_table)

        # Version action buttons
        vbtn_row = QHBoxLayout()
        self._delete_ver_btn = QPushButton()
        bind(self._delete_ver_btn, "app.delete")
        self._delete_ver_btn.setObjectName("dangerBtn")
        self._delete_ver_btn.clicked.connect(self._delete_selected_version)
        vbtn_row.addWidget(self._delete_ver_btn)
        vbtn_row.addStretch()
        hv.addLayout(vbtn_row)

        layout.addWidget(hist_grp)

        # ---- Bottom: quality panel ----
        quality_grp = QGroupBox()
        bind(quality_grp, "dataset_version.quality_score", setter="setTitle")
        qv = QVBoxLayout(quality_grp)

        self._quality_text = QTextEdit()
        self._quality_text.setReadOnly(True)
        self._quality_text.setMaximumHeight(160)
        self._quality_text.setPlaceholderText(tr("dataset_version.no_versions"))
        qv.addWidget(self._quality_text)
        layout.addWidget(quality_grp)

    # ------------------------------------------------------------------
    # Show / refresh
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_all()

    def _refresh_all(self) -> None:
        self._refresh_sessions()
        self._refresh_versions()

    def _refresh_sessions(self) -> None:
        pid = self._ctx.current_project_id
        sessions = list_capture_sessions(pid) if pid else []
        self._session_table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            self._session_table.setItem(row, 0, QTableWidgetItem(s.session_id))
            self._session_table.setItem(row, 1, QTableWidgetItem(s.session_name))
            self._session_table.setItem(row, 2, QTableWidgetItem(session_status_label(s.status)))
            self._session_table.setItem(row, 3, QTableWidgetItem(str(s.captured_image_count)))
            counts = get_classification_counts(s.session_id)
            dist = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
            self._session_table.setItem(row, 4, QTableWidgetItem(dist[:60]))

    def _refresh_versions(self) -> None:
        pid = self._ctx.current_project_id
        versions = list_dataset_versions(project_id=pid) if pid else []
        self._version_table.setRowCount(len(versions))
        for row, dv in enumerate(versions):
            self._version_table.setItem(
                row, 0, QTableWidgetItem(dv.version_name or dv.version_id[:20])
            )
            self._version_table.setItem(row, 1, QTableWidgetItem(dv.source_type))
            self._version_table.setItem(row, 2, QTableWidgetItem(str(dv.image_count)))
            try:
                classes = json.loads(dv.class_names)
                cls_text = ", ".join(classes[:5])
            except (json.JSONDecodeError, TypeError):
                cls_text = dv.class_names[:40]
            self._version_table.setItem(row, 3, QTableWidgetItem(cls_text))
            qs = dv.quality_score
            qs_item = QTableWidgetItem(f"{qs:.0f}/100" if qs is not None else "—")
            if qs is not None:
                if qs >= 80:
                    qs_item.setForeground(Qt.GlobalColor.green)
                elif qs >= 60:
                    qs_item.setForeground(Qt.GlobalColor.yellow)
                else:
                    qs_item.setForeground(Qt.GlobalColor.red)
            self._version_table.setItem(row, 4, qs_item)
            self._version_table.setItem(
                row, 5, QTableWidgetItem(dv.created_at[:16] if dv.created_at else "")
            )
            # Hidden: version_id
            self._version_table.setItem(row, 6, QTableWidgetItem(dv.version_id))

    def _on_version_selected(self) -> None:
        """Display quality report for selected version."""
        row = self._version_table.currentRow()
        if row < 0:
            self._quality_text.clear()
            return
        vid = self._version_table.item(row, 6)
        if vid is None:
            return
        dv = get_dataset_version(vid.text())
        if dv is None:
            return

        lines = [
            f"Version: {dv.version_name}",
            f"Source: {dv.source_type}",
            f"Images: {dv.image_count}",
            f"Val split: {dv.val_split_ratio}",
        ]
        if dv.quality_score is not None:
            lines.append(f"Quality Score: {dv.quality_score:.0f}/100")
        lines.append("")

        # Parse quality report
        if dv.quality_report:
            try:
                report = json.loads(dv.quality_report)
                lines.append(f"Issues: {len(report.get('issues', []))}")
                lines.append(f"Corrupt images: {report.get('corrupt_images', 0)}")
                lines.append(f"Missing labels: {report.get('missing_labels', 0)}")
                lines.append(f"Orphan labels: {report.get('orphan_labels', 0)}")
                lines.append(f"Total classes: {report.get('total_classes', 0)}")
                cc = report.get("class_counts", {})
                if cc:
                    lines.append("Class distribution:")
                    for cls_name, cnt in sorted(cc.items()):
                        lines.append(f"  {cls_name}: {cnt}")
                issues = report.get("issues", [])[:15]
                if issues:
                    lines.append("")
                    lines.append("Issues:")
                    for issue in issues:
                        lines.append(f"  - {issue}")
            except (json.JSONDecodeError, TypeError):
                lines.append(dv.quality_report[:500])

        self._quality_text.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    # Dataset generation
    # ------------------------------------------------------------------

    def _generate(self, kind: str) -> None:
        """Start YOLO or anomaly dataset build in background."""
        row = self._session_table.currentRow()
        if row < 0:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_session"))
            return

        sid_item = self._session_table.item(row, 0)
        if sid_item is None:
            return
        sid = sid_item.text()
        sess = get_capture_session(sid)
        if not sess:
            return

        pid = self._ctx.current_project_id or sess.project_id
        spec_id = self._ctx.current_spec_id or sess.spec_id
        proj_data_dir = get_project_data_dir(pid)

        if kind == "yolo":
            version_name = datetime.now().strftime("v%Y%m%d_%H%M%S")
            dataset_dir = os.path.join(proj_data_dir, "datasets", version_name)
            os.makedirs(dataset_dir, exist_ok=True)
            fn = build_yolo_dataset_from_session
            kwargs = {
                "session_id": sid,
                "dataset_dir": dataset_dir,
                "val_ratio": 0.2,
                "project_id": pid,
                "spec_id": spec_id,
                "version_name": version_name,
            }
        else:
            version_name = datetime.now().strftime("anom_v%Y%m%d_%H%M%S")
            dataset_dir = os.path.join(proj_data_dir, "datasets", version_name)
            os.makedirs(dataset_dir, exist_ok=True)
            fn = build_anomaly_dataset_from_session
            kwargs = {
                "session_id": sid,
                "dataset_dir": dataset_dir,
                "train_ratio": 0.8,
                "project_id": pid,
                "spec_id": spec_id,
                "version_name": version_name,
            }

        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._gen_yolo_btn.setEnabled(False)
        self._gen_anom_btn.setEnabled(False)

        self._worker = DatasetBuildWorker(fn, kwargs, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_build_finished)
        self._worker.error.connect(self._on_build_error)
        self._worker.start()

    def _on_progress(self, msg: str, pct: float) -> None:
        self._progress_bar.setValue(int(pct * 100))
        self._progress_bar.setFormat(f"{msg}  %p%")

    def _on_build_finished(self, result) -> None:
        self._progress_bar.setVisible(False)
        self._gen_yolo_btn.setEnabled(True)
        self._gen_anom_btn.setEnabled(True)

        qs = getattr(result, "quality_score", 0)
        msg = tr(
            "dataset_version.build_complete",
            path=result.dataset_dir,
            images=result.image_count,
            score=qs,
        )
        QMessageBox.information(self, tr("app.completed"), msg)
        self._refresh_versions()
        self.data_changed.emit()

    def _on_build_error(self, err: str) -> None:
        self._progress_bar.setVisible(False)
        self._gen_yolo_btn.setEnabled(True)
        self._gen_anom_btn.setEnabled(True)
        QMessageBox.warning(self, tr("app.error"), err)

    def _delete_selected_version(self) -> None:
        row = self._version_table.currentRow()
        if row < 0:
            return
        vid_item = self._version_table.item(row, 6)
        name_item = self._version_table.item(row, 0)
        if vid_item is None:
            return
        name = name_item.text() if name_item else vid_item.text()
        reply = QMessageBox.question(
            self,
            tr("app.confirm"),
            tr("dataset_version.delete_confirm", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_dataset_version(vid_item.text())
            self._refresh_versions()
            self._quality_text.clear()

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------

    def _refresh_text(self, lang: str = "") -> None:
        self._session_table.setHorizontalHeaderLabels(
            [
                tr("dataset.col_id"),
                tr("dataset.col_name"),
                tr("app.status"),
                tr("capture.col_captured"),
                tr("dataset.col_distribution"),
            ]
        )
        self._version_table.setHorizontalHeaderLabels(
            [
                tr("dataset_version.col_version"),
                tr("dataset_version.col_source"),
                tr("dataset_version.col_images"),
                tr("dataset_version.col_classes"),
                tr("dataset_version.col_quality"),
                tr("dataset_version.col_date"),
                "",
            ]
        )
