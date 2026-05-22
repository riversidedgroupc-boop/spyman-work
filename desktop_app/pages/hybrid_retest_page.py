"""Hybrid retest page — YOLO + anomaly fusion retest for first-delivery verification."""
from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QPushButton, QLabel, QLineEdit, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QFileDialog, QProgressBar, QTextEdit,
)

from core.hybrid_retest import (
    HybridRetestConfig,
)
from core.model_version import list_model_versions
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, I18nManager
from desktop_app.workers.hybrid_retest_worker import HybridRetestWorker


class HybridRetestPage(QWidget):
    """Hybrid retest UI for field-delivery first-model verification."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._worker: HybridRetestWorker | None = None
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    # ── UI Construction ──────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Config section ──────────────────────────────────────
        config_group = QGroupBox(tr("hybrid_retest.config"))
        config_form = QFormLayout(config_group)
        config_form.setSpacing(4)

        # YOLO model combo
        self._yolo_combo = QComboBox()
        self._yolo_combo.setMinimumWidth(300)
        config_form.addRow(tr("hybrid_retest.yolo_model"), self._yolo_combo)

        # Anomaly model combo
        self._anomaly_combo = QComboBox()
        self._anomaly_combo.setMinimumWidth(300)
        self._anomaly_combo.addItem(tr("hybrid_retest.no_anomaly_model"), "")
        config_form.addRow(tr("hybrid_retest.anomaly_model"), self._anomaly_combo)

        # Image directory
        dir_layout = QHBoxLayout()
        self._image_dir_edit = QLineEdit()
        self._image_dir_edit.setPlaceholderText(tr("hybrid_retest.image_dir_placeholder"))
        self._image_dir_edit.setMinimumWidth(260)
        dir_layout.addWidget(self._image_dir_edit)
        self._browse_dir_btn = QPushButton(tr("hybrid_retest.browse"))
        self._browse_dir_btn.clicked.connect(self._on_browse_dir)
        dir_layout.addWidget(self._browse_dir_btn)
        config_form.addRow(tr("hybrid_retest.image_dir"), dir_layout)

        # Thresholds
        self._yolo_thresh_spin = QDoubleSpinBox()
        self._yolo_thresh_spin.setRange(0.1, 0.99)
        self._yolo_thresh_spin.setSingleStep(0.05)
        self._yolo_thresh_spin.setValue(0.5)
        config_form.addRow(tr("hybrid_retest.yolo_threshold"), self._yolo_thresh_spin)

        self._anomaly_thresh_spin = QDoubleSpinBox()
        self._anomaly_thresh_spin.setRange(0.1, 0.99)
        self._anomaly_thresh_spin.setSingleStep(0.05)
        self._anomaly_thresh_spin.setValue(0.65)
        config_form.addRow(tr("hybrid_retest.anomaly_threshold"), self._anomaly_thresh_spin)

        self._anomaly_high_spin = QDoubleSpinBox()
        self._anomaly_high_spin.setRange(0.1, 0.99)
        self._anomaly_high_spin.setSingleStep(0.05)
        self._anomaly_high_spin.setValue(0.85)
        config_form.addRow(tr("hybrid_retest.anomaly_high_threshold"), self._anomaly_high_spin)

        layout.addWidget(config_group)

        # ── Buttons ─────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self._start_btn = QPushButton(tr("hybrid_retest.start"))
        self._start_btn.clicked.connect(self._on_start)
        btn_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton(tr("hybrid_retest.stop"))
        self._stop_btn.setObjectName("dangerBtn")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_layout.addWidget(self._stop_btn)

        self._refresh_models_btn = QPushButton(tr("hybrid_retest.refresh_models"))
        self._refresh_models_btn.clicked.connect(self._refresh_models)
        btn_layout.addWidget(self._refresh_models_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # ── Progress ────────────────────────────────────────────
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel(tr("hybrid_retest.idle"))
        self._progress_label.setStyleSheet("color: #888;")
        layout.addWidget(self._progress_label)

        # ── Summary ─────────────────────────────────────────────
        summary_group = QGroupBox(tr("hybrid_retest.summary"))
        summary_layout = QHBoxLayout(summary_group)
        summary_layout.setSpacing(12)

        self._total_label = QLabel("0")
        self._ok_label = QLabel("0")
        self._ng_label = QLabel("0")
        self._suspect_label = QLabel("0")
        self._unknown_label = QLabel("0")
        self._needs_review_label = QLabel("0")
        self._routed_label = QLabel("0")

        for label_text, value_label in [
            ("hybrid_retest.total", self._total_label),
            ("hybrid_retest.ok", self._ok_label),
            ("hybrid_retest.ng", self._ng_label),
            ("hybrid_retest.suspect", self._suspect_label),
            ("hybrid_retest.unknown", self._unknown_label),
            ("hybrid_retest.needs_review", self._needs_review_label),
            ("hybrid_retest.routed", self._routed_label),
        ]:
            pair = QHBoxLayout()
            pair.setSpacing(4)
            pair.addWidget(QLabel(tr(label_text) + ":"))
            pair.addWidget(value_label)
            summary_layout.addLayout(pair)

        summary_layout.addStretch()
        layout.addWidget(summary_group)

        # ── Results table ───────────────────────────────────────
        self._results_table = QTableWidget(0, 7)
        self._results_table.setHorizontalHeaderLabels([
            tr("hybrid_retest.col_image"),
            tr("hybrid_retest.col_decision"),
            tr("hybrid_retest.col_reason"),
            tr("hybrid_retest.col_yolo_count"),
            tr("hybrid_retest.col_anomaly_score"),
            tr("hybrid_retest.col_runtime"),
            tr("hybrid_retest.col_review_id"),
        ])
        self._results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._results_table, 1)

        # ── Log ─────────────────────────────────────────────────
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumHeight(100)
        self._log_view.setPlaceholderText(tr("hybrid_retest.log_placeholder"))
        layout.addWidget(self._log_view)

    def _refresh_text(self, lang: str = "") -> None:
        pass  # Group box titles bound via tr() at construction; no dynamic rebuild needed

    # ── Events ──────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_models()

    def _get_project_id(self) -> str:
        return self._ctx.current_project_id

    def _get_spec_id(self) -> str:
        return self._ctx.current_spec_id

    # ── Model refresh ───────────────────────────────────────────

    def _refresh_models(self) -> None:
        self._yolo_combo.clear()
        self._yolo_combo.addItem(tr("hybrid_retest.select_model"), "")
        pid = self._get_project_id()
        if not pid:
            return
        models = list_model_versions(project_id=pid)
        for mv in models:
            if mv.model_type == "yolo" and mv.model_path:
                label = f"{mv.model_name} ({mv.model_id})"
                self._yolo_combo.addItem(label, mv.model_id)

    # ── Browse ──────────────────────────────────────────────────

    def _on_browse_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("hybrid_retest.select_image_dir"))
        if d:
            self._image_dir_edit.setText(d)

    # ── Start / Stop ────────────────────────────────────────────

    def _on_start(self) -> None:
        pid = self._get_project_id()
        if not pid:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_project"))
            return
        yolo_id = self._yolo_combo.currentData()
        if not yolo_id:
            QMessageBox.warning(self, tr("app.warning"), tr("hybrid_retest.no_yolo_model"))
            return
        image_dir = self._image_dir_edit.text().strip()
        if not image_dir or not os.path.isdir(image_dir):
            QMessageBox.warning(self, tr("app.warning"), tr("hybrid_retest.invalid_image_dir"))
            return

        config = HybridRetestConfig(
            project_id=pid,
            spec_id=self._get_spec_id(),
            yolo_model_id=yolo_id,
            anomaly_model_id=self._anomaly_combo.currentData() or "",
            image_dir=image_dir,
            yolo_conf_threshold=self._yolo_thresh_spin.value(),
            anomaly_score_threshold=self._anomaly_thresh_spin.value(),
            anomaly_high_threshold=self._anomaly_high_spin.value(),
        )

        self._worker = HybridRetestWorker(config)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._set_running(True)
        self._results_table.setRowCount(0)
        self._log_view.clear()
        self._reset_summary()
        self._worker.start()

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._progress_label.setText(tr("hybrid_retest.stopping"))

    def _set_running(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._yolo_combo.setEnabled(not running)
        self._anomaly_combo.setEnabled(not running)
        self._image_dir_edit.setEnabled(not running)
        self._browse_dir_btn.setEnabled(not running)
        self._yolo_thresh_spin.setEnabled(not running)
        self._anomaly_thresh_spin.setEnabled(not running)
        self._anomaly_high_spin.setEnabled(not running)
        self._refresh_models_btn.setEnabled(not running)

    def _reset_summary(self) -> None:
        for lbl in [self._total_label, self._ok_label, self._ng_label,
                     self._suspect_label, self._unknown_label,
                     self._needs_review_label, self._routed_label]:
            lbl.setText("0")
        self._progress_bar.setValue(0)

    # ── Callbacks ───────────────────────────────────────────────

    def _on_progress(self, current: int, total: int, image_path: str) -> None:
        pct = int(current * 100 / total) if total else 0
        self._progress_bar.setValue(pct)
        self._progress_label.setText(f"{current}/{total}: {os.path.basename(image_path)}")

    def _on_finished(self, result: object) -> None:
        self._set_running(False)
        self._progress_label.setText(tr("hybrid_retest.complete"))
        self._progress_bar.setValue(100)

        # Populate results table
        items = getattr(result, "items", [])
        self._results_table.setRowCount(len(items))
        for i, item in enumerate(items):
            self._results_table.setItem(i, 0, QTableWidgetItem(
                os.path.basename(item.image_path)))
            self._results_table.setItem(i, 1, QTableWidgetItem(item.final_decision))
            self._results_table.setItem(i, 2, QTableWidgetItem(item.reason))
            self._results_table.setItem(i, 3, QTableWidgetItem(str(item.yolo_detection_count)))
            self._results_table.setItem(i, 4, QTableWidgetItem(f"{item.anomaly_score:.3f}"))
            self._results_table.setItem(i, 5, QTableWidgetItem(f"{item.runtime_ms:.1f}"))
            self._results_table.setItem(i, 6, QTableWidgetItem(item.review_id or "—"))

        # Update summary
        self._total_label.setText(str(getattr(result, "total_count", 0)))
        self._ok_label.setText(str(getattr(result, "ok_count", 0)))
        self._ng_label.setText(str(getattr(result, "ng_count", 0)))
        self._suspect_label.setText(str(getattr(result, "suspect_count", 0)))
        self._unknown_label.setText(str(getattr(result, "unknown_count", 0)))
        self._needs_review_label.setText(str(getattr(result, "needs_review_count", 0)))
        routed = (getattr(result, "suspect_count", 0) +
                  getattr(result, "unknown_count", 0) +
                  getattr(result, "needs_review_count", 0))
        self._routed_label.setText(str(routed))

        self._log_view.append(
            f"Run {getattr(result, 'run_id', '?')}: "
            f"{getattr(result, 'total_count', 0)} images, "
            f"OK={getattr(result, 'ok_count', 0)} "
            f"NG={getattr(result, 'ng_count', 0)} "
            f"Suspect={getattr(result, 'suspect_count', 0)} "
            f"Unknown={getattr(result, 'unknown_count', 0)} "
            f"NeedsReview={getattr(result, 'needs_review_count', 0)}"
        )

    def _on_error(self, err: str) -> None:
        self._set_running(False)
        self._progress_label.setText(tr("hybrid_retest.failed"))
        self._log_view.append(f"ERROR: {err}")
        QMessageBox.critical(self, tr("app.error"), err)
