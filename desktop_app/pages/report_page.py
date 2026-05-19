"""Report page — generate project/batch/system reports in multiple formats."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QPushButton, QProgressBar, QTextEdit, QMessageBox,
)

from core.product_spec import list_product_specs
from runtime.health_monitor import HealthMonitor
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.workers.report_worker import ReportWorker, SUPPORTED_FORMATS
from desktop_app.constants import APP_VERSION


class ReportPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._worker: ReportWorker | None = None
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        report_type_label = QLabel()
        bind(report_type_label, "report.type")
        top.addWidget(report_type_label)
        self._type_combo = QComboBox()
        self._type_combo.addItem(tr("report.project"), "project")
        self._type_combo.addItem(tr("report.batch"), "batch")
        self._type_combo.addItem(tr("report.system"), "system")
        top.addWidget(self._type_combo)

        format_label = QLabel()
        bind(format_label, "report.format_type")
        top.addWidget(format_label)
        self._format_combo = QComboBox()
        self._format_combo.addItem(tr("report.format_markdown"), "md")
        self._format_combo.addItem(tr("report.format_html"), "html")
        self._format_combo.addItem(tr("report.format_pdf"), "pdf")
        self._format_combo.addItem(tr("report.format_csv"), "csv")
        self._format_combo.addItem(tr("report.format_json"), "json")
        top.addWidget(self._format_combo)

        gen_btn = QPushButton()
        bind(gen_btn, "report.generate")
        gen_btn.clicked.connect(self._generate)
        top.addWidget(gen_btn)
        top.addStretch()
        layout.addLayout(top)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setStyleSheet(
            "background-color: #1E1E1E; color: #D4D4D4; font-family: Consolas; font-size: 12px;"
        )
        layout.addWidget(self._preview, 1)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set combo items on language change."""
        self._type_combo.clear()
        self._type_combo.addItem(tr("report.project"), "project")
        self._type_combo.addItem(tr("report.batch"), "batch")
        self._type_combo.addItem(tr("report.system"), "system")
        self._format_combo.clear()
        self._format_combo.addItem(tr("report.format_markdown"), "md")
        self._format_combo.addItem(tr("report.format_html"), "html")
        self._format_combo.addItem(tr("report.format_pdf"), "pdf")
        self._format_combo.addItem(tr("report.format_csv"), "csv")
        self._format_combo.addItem(tr("report.format_json"), "json")

    def _generate(self):
        rt = self._type_combo.currentData()
        pid = self._ctx.current_project_id

        context: dict = {"version": APP_VERSION}

        if rt == "project":
            context["customer"] = self._ctx.current_customer_name
            context["spec"] = self._ctx.current_spec_name
            # Gather more context from DB
            if pid:
                specs = list_product_specs(pid)
                if specs:
                    s = specs[0]
                    context["material"] = s.material
                    context["morphology"] = s.geometry_type
                    context["line_speed"] = str(s.target_speed_mpm)
                    context["camera_count"] = str(s.camera_count)
        elif rt == "system":
            context["health"] = HealthMonitor().get_health()

        export_fmt = self._format_combo.currentData() or "md"
        self._worker = ReportWorker(
            report_type=rt,
            project_name=self._ctx.current_project_name,
            context=context,
            export_format=export_fmt,
        )
        self._worker.message.connect(self._on_message)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._progress.setVisible(True)
        self._progress.setMaximum(0)
        self._worker.start()

    def _on_message(self, msg):
        self._preview.append(msg)

    def _on_finished(self):
        self._progress.setVisible(False)
        if self._worker:
            path = self._worker.get_output_path()
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._preview.setPlainText(f.read())
            except Exception:
                pass
            QMessageBox.information(self, tr("app.completed"), tr("report.saved_to", path=path))
        self.data_changed.emit()

    def _on_error(self, err):
        self._progress.setVisible(False)
        QMessageBox.critical(self, tr("report.error_title"), err)
