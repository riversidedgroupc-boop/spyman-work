"""Field review workspace — anomaly review, defect dictionary, and YOLO dataset preparation.

This page is scoped to the "样本复核" stage of the main workbench flow.
It does NOT cover baseline capture, model training, hybrid detection, or
deployment — those belong to their respective top-level modules.
"""

from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.anomaly_review import (
    list_anomaly_reviews,
    update_anomaly_review,
)
from core.defect_dictionary import (
    create_defect_type,
    list_defect_types,
)
from core.field_session import (
    create_field_session,
    delete_field_session_cascade,
    list_field_sessions,
)
from core.field_training_dataset import build_yolo_dataset_from_field_reviews
from desktop_app.app_context import AppContext
from desktop_app.i18n import I18nManager, tr


_SEVERITY_OPTIONS = [
    ("field_workflow.severity_critical", "critical"),
    ("field_workflow.severity_high", "high"),
    ("field_workflow.severity_medium", "medium"),
    ("field_workflow.severity_low", "low"),
    ("field_workflow.severity_info", "info"),
]


def _replace_combo_options(combo: QComboBox, options: list[tuple[str, str]]) -> None:
    current = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    for label_key, value in options:
        combo.addItem(tr(label_key), value)
    if current is not None:
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    combo.blockSignals(False)


class FieldWorkflowPage(QWidget):
    """Anomaly review workspace within the 样本复核 stage.

    Covers: field sessions → anomaly review queue → defect dictionary →
    YOLO dataset preparation.
    """

    data_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._current_session_id = ""
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    # ── UI Construction ──────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(self._build_session_area())
        layout.addWidget(self._build_review_queue())
        layout.addWidget(self._build_review_actions())
        layout.addWidget(self._build_training_readiness())
        layout.addWidget(self._build_defect_dictionary())
        layout.addStretch(1)

        scroll.setWidget(content)

    def _build_session_area(self) -> QGroupBox:
        gb = QGroupBox(tr("field_workflow.session"))
        layout = QHBoxLayout(gb)
        layout.setSpacing(6)

        self._session_combo = QComboBox()
        self._session_combo.setMinimumWidth(200)
        self._session_combo.currentIndexChanged.connect(self._on_session_selected)
        layout.addWidget(self._session_combo, 1)

        self._create_session_btn = QPushButton(tr("field_workflow.create_session"))
        self._create_session_btn.clicked.connect(self._on_create_session)
        layout.addWidget(self._create_session_btn)

        self._delete_session_btn = QPushButton(tr("app.delete"))
        self._delete_session_btn.setObjectName("dangerBtn")
        self._delete_session_btn.setEnabled(False)
        self._delete_session_btn.clicked.connect(self._on_delete_session)
        layout.addWidget(self._delete_session_btn)

        self._refresh_btn = QPushButton(tr("field_workflow.refresh"))
        self._refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(self._refresh_btn)

        self._session_status_label = QLabel("")
        layout.addWidget(self._session_status_label)

        return gb

    def _build_review_queue(self) -> QGroupBox:
        gb = QGroupBox(tr("field_workflow.review_queue"))
        layout = QVBoxLayout(gb)
        layout.setSpacing(4)

        self._review_table = QTableWidget(0, 8)
        self._review_table.setHorizontalHeaderLabels(
            [
                "review_id",
                tr("app.status"),
                tr("field_workflow.score"),
                tr("field_workflow.cluster"),
                tr("field_workflow.image"),
                tr("field_workflow.assigned_defect"),
                tr("field_workflow.reviewer"),
                tr("field_workflow.reviewed_at"),
            ]
        )
        self._review_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._review_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._review_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._review_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._review_table.selectionModel().selectionChanged.connect(self._on_review_selected)
        self._review_table.setMaximumHeight(160)
        layout.addWidget(self._review_table)

        # Candidate detail (read-only form)
        self._detail_form = QFormLayout()
        self._detail_form.setSpacing(2)
        self._detail_image = QLabel("—")
        self._detail_score = QLabel("—")
        self._detail_cluster = QLabel("—")
        self._detail_status = QLabel("—")
        self._detail_notes = QLabel("—")
        self._detail_form.addRow(tr("field_workflow.image"), self._detail_image)
        self._detail_form.addRow(tr("field_workflow.score"), self._detail_score)
        self._detail_form.addRow(tr("field_workflow.cluster"), self._detail_cluster)
        self._detail_form.addRow(tr("app.status"), self._detail_status)
        self._detail_form.addRow(tr("app.notes"), self._detail_notes)
        layout.addLayout(self._detail_form)

        return gb

    def _build_review_actions(self) -> QGroupBox:
        gb = QGroupBox(tr("field_workflow.candidate_detail"))
        layout = QHBoxLayout(gb)
        layout.setSpacing(6)

        self._reviewer_input = QLineEdit()
        self._reviewer_input.setPlaceholderText(tr("field_workflow.reviewer"))
        self._reviewer_input.setMaximumWidth(120)
        layout.addWidget(QLabel(tr("field_workflow.reviewer")))
        layout.addWidget(self._reviewer_input)

        self._defect_combo = QComboBox()
        self._defect_combo.setMinimumWidth(120)
        layout.addWidget(QLabel(tr("field_workflow.assigned_defect")))
        layout.addWidget(self._defect_combo)

        self._confirm_defect_btn = QPushButton(tr("field_workflow.confirm_defect"))
        self._confirm_defect_btn.clicked.connect(self._on_confirm_defect)
        layout.addWidget(self._confirm_defect_btn)

        self._mark_normal_btn = QPushButton(tr("field_workflow.mark_normal"))
        self._mark_normal_btn.clicked.connect(lambda: self._on_mark_status("normal"))
        layout.addWidget(self._mark_normal_btn)

        self._mark_noise_btn = QPushButton(tr("field_workflow.mark_noise"))
        self._mark_noise_btn.clicked.connect(lambda: self._on_mark_status("noise_or_reflection"))
        layout.addWidget(self._mark_noise_btn)

        self._mark_texture_btn = QPushButton(tr("field_workflow.mark_texture"))
        self._mark_texture_btn.clicked.connect(lambda: self._on_mark_status("acceptable_texture"))
        layout.addWidget(self._mark_texture_btn)

        self._mark_unknown_btn = QPushButton(tr("field_workflow.mark_unknown"))
        self._mark_unknown_btn.clicked.connect(lambda: self._on_mark_status("unknown_pending"))
        layout.addWidget(self._mark_unknown_btn)

        return gb

    def _build_training_readiness(self) -> QGroupBox:
        gb = QGroupBox(tr("field_workflow.training_readiness"))
        layout = QVBoxLayout(gb)
        layout.setSpacing(4)

        # Stats form
        self._training_stats_form = QFormLayout()
        self._training_stats_form.setSpacing(2)

        self._tr_confirmed_label = QLabel("—")
        self._tr_defect_types_label = QLabel("—")
        self._tr_missing_bbox_label = QLabel("—")
        self._tr_unassigned_label = QLabel("—")
        self._tr_pending_label = QLabel("—")
        self._tr_readiness_label = QLabel("—")
        self._tr_dataset_path_label = QLabel("—")
        self._tr_dataset_yaml_label = QLabel("—")
        self._tr_version_label = QLabel("—")

        self._training_stats_form.addRow(
            tr("field_workflow.confirmed_defect_count"), self._tr_confirmed_label
        )
        self._training_stats_form.addRow(
            tr("field_workflow.defect_type_count"), self._tr_defect_types_label
        )
        self._training_stats_form.addRow(
            tr("field_workflow.missing_bbox_count"), self._tr_missing_bbox_label
        )
        self._training_stats_form.addRow(
            tr("field_workflow.skipped_unassigned"), self._tr_unassigned_label
        )
        self._training_stats_form.addRow(
            tr("field_workflow.pending_unknown_count"), self._tr_pending_label
        )
        self._training_stats_form.addRow(tr("app.status"), self._tr_readiness_label)
        self._training_stats_form.addRow(
            tr("field_workflow.dataset_path"), self._tr_dataset_path_label
        )
        self._training_stats_form.addRow(
            tr("field_workflow.dataset_yaml"), self._tr_dataset_yaml_label
        )
        self._training_stats_form.addRow(tr("field_workflow.version_label"), self._tr_version_label)
        layout.addLayout(self._training_stats_form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self._generate_dataset_btn = QPushButton(tr("field_workflow.generate_dataset"))
        self._generate_dataset_btn.clicked.connect(self._on_generate_dataset)
        btn_layout.addWidget(self._generate_dataset_btn)

        self._refresh_readiness_btn = QPushButton(tr("field_workflow.refresh_readiness"))
        self._refresh_readiness_btn.clicked.connect(self._refresh_training_readiness)
        btn_layout.addWidget(self._refresh_readiness_btn)

        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        return gb

    def _build_defect_dictionary(self) -> QGroupBox:
        gb = QGroupBox(tr("field_workflow.defect_dictionary"))
        layout = QVBoxLayout(gb)
        layout.setSpacing(4)

        # Table
        self._defect_table = QTableWidget(0, 6)
        self._defect_table.setHorizontalHeaderLabels(
            [
                tr("field_workflow.code"),
                tr("field_workflow.name_zh"),
                tr("field_workflow.name_en"),
                tr("field_workflow.severity"),
                tr("field_workflow.is_ng"),
                tr("field_workflow.description"),
            ]
        )
        self._defect_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._defect_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._defect_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._defect_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._defect_table.setMaximumHeight(160)
        layout.addWidget(self._defect_table)

        # Create form
        form_layout = QHBoxLayout()
        form_layout.setSpacing(4)

        self._new_code = QLineEdit()
        self._new_code.setPlaceholderText(tr("field_workflow.code"))
        self._new_code.setMaximumWidth(80)
        form_layout.addWidget(QLabel(tr("field_workflow.code")))
        form_layout.addWidget(self._new_code)

        self._new_name_zh = QLineEdit()
        self._new_name_zh.setPlaceholderText(tr("field_workflow.name_zh"))
        self._new_name_zh.setMaximumWidth(80)
        form_layout.addWidget(QLabel(tr("field_workflow.name_zh")))
        form_layout.addWidget(self._new_name_zh)

        self._new_name_en = QLineEdit()
        self._new_name_en.setPlaceholderText(tr("field_workflow.name_en"))
        self._new_name_en.setMaximumWidth(80)
        form_layout.addWidget(QLabel(tr("field_workflow.name_en")))
        form_layout.addWidget(self._new_name_en)

        self._new_severity = QComboBox()
        _replace_combo_options(self._new_severity, _SEVERITY_OPTIONS)
        form_layout.addWidget(QLabel(tr("field_workflow.severity")))
        form_layout.addWidget(self._new_severity)

        self._new_is_ng = QCheckBox()
        self._new_is_ng.setChecked(True)
        form_layout.addWidget(QLabel(tr("field_workflow.is_ng")))
        form_layout.addWidget(self._new_is_ng)

        self._new_description = QLineEdit()
        self._new_description.setPlaceholderText(tr("field_workflow.description"))
        self._new_description.setMaximumWidth(120)
        form_layout.addWidget(QLabel(tr("field_workflow.description")))
        form_layout.addWidget(self._new_description)

        self._create_defect_btn = QPushButton(tr("field_workflow.create_defect"))
        self._create_defect_btn.clicked.connect(self._on_create_defect)
        form_layout.addWidget(self._create_defect_btn)

        form_layout.addStretch(1)
        layout.addLayout(form_layout)

        return gb

    # ── Events ───────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._on_refresh()

    def _refresh_text(self, lang: str = "") -> None:
        _replace_combo_options(self._new_severity, _SEVERITY_OPTIONS)

    # ── Logic ────────────────────────────────────────────────────

    def _get_project_id(self) -> str:
        return self._ctx.current_project_id

    def _get_spec_id(self) -> str:
        return self._ctx.current_spec_id

    def _has_context(self) -> bool:
        return bool(self._get_project_id() and self._get_spec_id())

    def _on_refresh(self) -> None:
        if not self._has_context():
            self._session_combo.clear()
            self._session_status_label.setText("")
            self._review_table.setRowCount(0)
            self._defect_table.setRowCount(0)
            self._defect_combo.clear()
            self._current_session_id = ""
            self._delete_session_btn.setEnabled(False)
            return

        # Refresh sessions
        sessions = list_field_sessions(
            project_id=self._get_project_id(),
            spec_id=self._get_spec_id(),
        )
        self._session_combo.blockSignals(True)
        self._session_combo.clear()
        for s in sessions:
            self._session_combo.addItem(
                f"{s.field_session_id} ({s.session_type})", s.field_session_id
            )
        self._session_combo.blockSignals(False)

        if self._current_session_id:
            idx = self._session_combo.findData(self._current_session_id)
            if idx >= 0:
                self._session_combo.setCurrentIndex(idx)
            else:
                self._current_session_id = ""
        elif self._session_combo.count() > 0:
            # Initial load: auto-select the first session
            self._current_session_id = self._session_combo.currentData() or ""
            # Update status label for the auto-selected session
            from core.field_session import get_field_session

            fs = get_field_session(self._current_session_id)
            if fs:
                self._session_status_label.setText(f"{tr('app.status')}: {fs.status}")

        self._delete_session_btn.setEnabled(bool(self._current_session_id))
        self._refresh_review_queue()
        self._refresh_defect_dictionary()
        self._refresh_training_readiness()

    def _on_create_session(self) -> None:
        if not self._has_context():
            QMessageBox.warning(self, tr("app.warning"), tr("field_workflow.no_context"))
            return
        try:
            s = create_field_session(
                project_id=self._get_project_id(),
                spec_id=self._get_spec_id(),
                session_type="anomaly_exploration",
            )
            self._current_session_id = s.field_session_id
            self._on_refresh()
        except Exception as e:
            QMessageBox.critical(self, tr("app.error"), str(e))

    def _on_delete_session(self) -> None:
        if not self._current_session_id:
            QMessageBox.warning(self, tr("app.warning"), tr("field_workflow.no_session"))
            return

        session_id = self._current_session_id
        reply = QMessageBox.question(
            self,
            tr("app.confirm_delete"),
            tr("field_workflow.delete_session_confirm", session_id=session_id),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_field_session_cascade(session_id)
            self._current_session_id = ""
            self._session_status_label.setText("")
            self._tr_dataset_path_label.setText("-")
            self._tr_dataset_yaml_label.setText("-")
            self._tr_version_label.setText("-")
            self._on_refresh()
            QMessageBox.information(
                self,
                tr("app.tip"),
                tr("field_workflow.session_deleted", session_id=session_id),
            )
        except Exception as e:
            QMessageBox.critical(self, tr("app.error"), str(e))

    def _on_session_selected(self) -> None:
        data = self._session_combo.currentData()
        self._current_session_id = data if data else ""
        self._delete_session_btn.setEnabled(bool(self._current_session_id))
        # Clear dataset generation result on session change
        self._tr_dataset_path_label.setText("—")
        self._tr_dataset_yaml_label.setText("—")
        self._tr_version_label.setText("—")
        if self._current_session_id:
            self._refresh_review_queue()
            # Show session status
            from core.field_session import get_field_session

            fs = get_field_session(self._current_session_id)
            if fs:
                self._session_status_label.setText(f"{tr('app.status')}: {fs.status}")

    def _refresh_review_queue(self) -> None:
        self._review_table.setRowCount(0)
        if not self._current_session_id:
            return
        reviews = list_anomaly_reviews(field_session_id=self._current_session_id)
        for i, r in enumerate(reviews):
            self._review_table.insertRow(i)
            self._review_table.setItem(i, 0, QTableWidgetItem(r.review_id))
            self._review_table.setItem(i, 1, QTableWidgetItem(r.review_status))
            self._review_table.setItem(i, 2, QTableWidgetItem(f"{r.anomaly_score:.2f}"))
            self._review_table.setItem(i, 3, QTableWidgetItem(r.cluster_id))
            self._review_table.setItem(i, 4, QTableWidgetItem(r.image_path or "—"))
            self._review_table.setItem(i, 5, QTableWidgetItem(r.assigned_defect_type_id or "—"))
            self._review_table.setItem(i, 6, QTableWidgetItem(r.reviewer or "—"))
            self._review_table.setItem(i, 7, QTableWidgetItem(r.reviewed_at or "—"))

    def _on_review_selected(self) -> None:
        indexes = self._review_table.selectionModel().selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        review_id = self._review_table.item(row, 0).text()
        reviews = list_anomaly_reviews(field_session_id=self._current_session_id)
        matched = [r for r in reviews if r.review_id == review_id]
        if not matched:
            return
        r = matched[0]
        self._detail_image.setText(r.image_path or "—")
        self._detail_score.setText(f"{r.anomaly_score:.3f}")
        self._detail_cluster.setText(r.cluster_id or "—")
        self._detail_status.setText(r.review_status)
        self._detail_notes.setText(r.notes or "—")

    def _on_mark_status(self, status: str) -> None:
        indexes = self._review_table.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.warning(self, tr("app.warning"), tr("app.select_first"))
            return
        review_id = self._review_table.item(indexes[0].row(), 0).text()
        reviewer = self._reviewer_input.text().strip()
        try:
            update_anomaly_review(
                review_id,
                review_status=status,
                reviewer=reviewer,
                reviewed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            self._on_refresh()
        except Exception as e:
            QMessageBox.critical(self, tr("app.error"), str(e))

    def _on_confirm_defect(self) -> None:
        indexes = self._review_table.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.warning(self, tr("app.warning"), tr("app.select_first"))
            return
        defect_id = self._defect_combo.currentData()
        if not defect_id:
            QMessageBox.warning(self, tr("app.warning"), tr("field_workflow.assigned_defect"))
            return
        review_id = self._review_table.item(indexes[0].row(), 0).text()
        reviewer = self._reviewer_input.text().strip()
        try:
            update_anomaly_review(
                review_id,
                review_status="confirmed_defect",
                assigned_defect_type_id=defect_id,
                reviewer=reviewer,
                reviewed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            self._on_refresh()
        except Exception as e:
            QMessageBox.critical(self, tr("app.error"), str(e))

    def _refresh_defect_dictionary(self) -> None:
        self._defect_table.setRowCount(0)
        self._defect_combo.clear()
        if not self._get_project_id():
            return
        defect_types = list_defect_types(project_id=self._get_project_id())
        for i, dt in enumerate(defect_types):
            self._defect_table.insertRow(i)
            self._defect_table.setItem(i, 0, QTableWidgetItem(dt.code))
            self._defect_table.setItem(i, 1, QTableWidgetItem(dt.display_name_zh))
            self._defect_table.setItem(i, 2, QTableWidgetItem(dt.display_name_en))
            self._defect_table.setItem(i, 3, QTableWidgetItem(dt.severity))
            self._defect_table.setItem(i, 4, QTableWidgetItem("NG" if dt.is_ng else "OK"))
            self._defect_table.setItem(i, 5, QTableWidgetItem(dt.description))
            self._defect_combo.addItem(f"{dt.code} — {dt.display_name_zh}", dt.defect_type_id)

    def _on_create_defect(self) -> None:
        if not self._get_project_id():
            QMessageBox.warning(self, tr("app.warning"), tr("field_workflow.no_context"))
            return
        code = self._new_code.text().strip()
        name_zh = self._new_name_zh.text().strip()
        if not code or not name_zh:
            QMessageBox.warning(self, tr("app.warning"), tr("app.validation_failed"))
            return
        try:
            create_defect_type(
                project_id=self._get_project_id(),
                spec_id=self._get_spec_id(),
                code=code,
                display_name_zh=name_zh,
                display_name_en=self._new_name_en.text().strip(),
                severity=self._new_severity.currentData() or "medium",
                description=self._new_description.text().strip(),
                is_ng=self._new_is_ng.isChecked(),
            )
            self._new_code.clear()
            self._new_name_zh.clear()
            self._new_name_en.clear()
            self._new_description.clear()
            self._refresh_defect_dictionary()
        except Exception as e:
            QMessageBox.critical(self, tr("app.error"), str(e))

    # ── Phase C: Training Readiness ────────────────────────────────

    def _refresh_training_readiness(self) -> None:
        """Refresh training readiness stats for the current session."""
        self._tr_confirmed_label.setText("—")
        self._tr_defect_types_label.setText("—")
        self._tr_missing_bbox_label.setText("—")
        self._tr_unassigned_label.setText("—")
        self._tr_pending_label.setText("—")
        self._tr_readiness_label.setText(tr("field_workflow.training_not_ready"))
        # Note: dataset_path/yaml/version labels are NOT reset here —
        # they persist across refreshes so the user can see the last
        # generated dataset. They are only cleared on session change.

        if not self._current_session_id or not self._get_project_id():
            return

        reviews = list_anomaly_reviews(field_session_id=self._current_session_id)
        defect_types = list_defect_types(project_id=self._get_project_id())

        confirmed = [r for r in reviews if r.review_status == "confirmed_defect"]
        unassigned = [r for r in confirmed if not r.assigned_defect_type_id]
        assigned = [r for r in confirmed if r.assigned_defect_type_id]

        # Check bbox presence for assigned confirmed defects
        from core.field_training_dataset import _find_label_path, _has_bbox

        missing_bbox = 0
        for r in assigned:
            if not r.image_path or not os.path.isfile(r.image_path):
                missing_bbox += 1
            else:
                label_path = _find_label_path(r.image_path)
                if not _has_bbox(label_path):
                    missing_bbox += 1

        pending_unknown = [
            r for r in reviews if r.review_status in ("unreviewed", "unknown_pending")
        ]

        self._tr_confirmed_label.setText(str(len(confirmed)))
        self._tr_defect_types_label.setText(str(len(defect_types)))
        self._tr_missing_bbox_label.setText(str(missing_bbox))
        self._tr_unassigned_label.setText(str(len(unassigned)))
        self._tr_pending_label.setText(str(len(pending_unknown)))

        # Readiness: need confirmed + assigned + with bbox
        ready = len(assigned) > 0 and (len(assigned) - missing_bbox) > 0 and len(defect_types) > 0
        self._tr_readiness_label.setText(
            tr("field_workflow.training_ready")
            if ready
            else tr("field_workflow.training_not_ready")
        )

    def _on_generate_dataset(self) -> None:
        """Generate YOLO first-training dataset from confirmed anomaly reviews."""
        if not self._get_project_id() or not self._get_spec_id():
            QMessageBox.warning(self, tr("app.warning"), tr("field_workflow.no_context"))
            return
        if not self._current_session_id:
            QMessageBox.warning(self, tr("app.warning"), tr("field_workflow.no_session"))
            return

        # Confirm confirmed defects exist
        reviews = list_anomaly_reviews(field_session_id=self._current_session_id)
        confirmed = [
            r
            for r in reviews
            if r.review_status == "confirmed_defect" and r.assigned_defect_type_id
        ]
        if not confirmed:
            QMessageBox.warning(self, tr("app.warning"), tr("field_workflow.no_confirmed_defect"))
            return

        from datetime import datetime

        dataset_dir = os.path.join(
            "outputs",
            "datasets",
            f"{self._current_session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )

        try:
            result = build_yolo_dataset_from_field_reviews(
                field_session_id=self._current_session_id,
                dataset_dir=dataset_dir,
                project_id=self._get_project_id(),
                spec_id=self._get_spec_id(),
            )
            self._tr_dataset_path_label.setText(result.dataset_dir)
            self._tr_dataset_yaml_label.setText(result.yaml_path)
            self._tr_version_label.setText(result.dataset_version_id or "—")
            self._tr_readiness_label.setText(tr("field_workflow.dataset_generated"))
            self._refresh_training_readiness()
            QMessageBox.information(
                self,
                tr("app.info"),
                f"{tr('field_workflow.dataset_generated')}\n"
                f"{tr('field_workflow.dataset_path')}: {result.dataset_dir}\n"
                f"{tr('field_workflow.dataset_yaml')}: {result.yaml_path}",
            )
        except Exception as e:
            QMessageBox.critical(self, tr("field_workflow.dataset_build_failed"), str(e))
