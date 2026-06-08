"""Main application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QSplitter,
    QTabWidget,
    QPushButton,
)

from desktop_app.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
)
from desktop_app.theme_manager import ThemeManager
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.navigation import NavigationBar
from desktop_app.widgets.project_selector import ProjectSelector
from desktop_app.widgets.status_bar import AppStatusBar
from desktop_app.pages.project_center_page import ProjectCenterPage
from desktop_app.pages.capture_page import CapturePage
from desktop_app.pages.sample_classification_page import SampleClassificationPage
from desktop_app.pages.bbox_annotation_page import BboxAnnotationPage
from desktop_app.pages.dataset_version_page import DatasetVersionPage
from desktop_app.pages.training_page import TrainingPage
from desktop_app.pages.training_jobs_page import TrainingJobsPage
from desktop_app.pages.model_version_page import ModelVersionPage
from desktop_app.pages.inference_page import InferencePage
from desktop_app.pages.evaluation_page import EvaluationPage
from desktop_app.pages.model_comparison_page import ModelComparisonPage
from desktop_app.app_context import AppContext
from core.runtime_mode import RuntimeMode, mode_targets_site_capture
from desktop_app.pages.production_run_page import ProductionRunPage
from desktop_app.pages.camera_workbench_page import CameraWorkbenchPage
from desktop_app.pages.production_line_com_page import ProductionLineComPage
from desktop_app.pages.report_page import ReportPage
from desktop_app.pages.system_settings_page import SystemSettingsPage
from desktop_app.pages.log_center_page import LogCenterPage
from desktop_app.pages.backup_restore_page import BackupRestorePage
from desktop_app.pages.help_page import HelpPage
from desktop_app.pages.benchmark_page import BenchmarkPage
from desktop_app.pages.project_workbench_page import ProjectWorkbenchPage
from desktop_app.pages.field_workflow_page import FieldWorkflowPage
from desktop_app.pages.hybrid_retest_page import HybridRetestPage
from desktop_app.pages.model_export_page import ModelExportPage
from desktop_app.pages.sample_library_page import SampleLibraryPage
from desktop_app.pages.defect_trace_page import DefectTracePage
from desktop_app.pages.auto_focus_page import AutoFocusPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._ctx = AppContext.instance()
        bind(self, "app.title", setter="setWindowTitle")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.setStyleSheet(ThemeManager.instance().get_stylesheet())
        self._sidebar_collapsed = False
        self._build_ui()
        self._connect_signals()
        self._sidebar_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self._sidebar_shortcut.activated.connect(self._toggle_sidebar)
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Top: sidebar toggle + project selector
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(6, 3, 10, 3)
        top_layout.setSpacing(6)

        self._sidebar_btn = QPushButton("☰")
        self._sidebar_btn.setObjectName("sidebarToggleBtn")
        self._sidebar_btn.setFixedSize(28, 28)
        self._sidebar_btn.setToolTip(tr("sidebar.toggle_tooltip"))
        self._sidebar_btn.clicked.connect(self._toggle_sidebar)
        top_layout.addWidget(self._sidebar_btn)

        self._selector = ProjectSelector()
        top_layout.addWidget(self._selector, 1)
        root_layout.addWidget(top_bar)

        # Middle: nav + stacked pages
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._nav = NavigationBar()
        self._splitter.addWidget(self._nav)

        self._pages = QStackedWidget()

        # ── [0] workbench ──
        workbench_container = QWidget()
        self._workbench_tabs = QTabWidget()
        self._workbench_page = ProjectWorkbenchPage()
        self._project_center = ProjectCenterPage()
        self._workbench_tabs.addTab(self._workbench_page, tr("nav.workbench"))
        self._workbench_tabs.addTab(self._project_center, tr("nav.project_center"))
        wl = QVBoxLayout(workbench_container)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(self._workbench_tabs)
        self._pages.addWidget(workbench_container)
        self._workbench_container = workbench_container

        # ── [1] device_setup ──
        device_container = QWidget()
        self._device_tabs = QTabWidget()
        self._camera_workbench_page = CameraWorkbenchPage()
        self._production_line_com_page = ProductionLineComPage()
        self._device_tabs.addTab(self._camera_workbench_page, tr("camera_workbench.title"))
        self._device_tabs.addTab(self._production_line_com_page, tr("production_line_com.title"))
        dl = QVBoxLayout(device_container)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.addWidget(self._device_tabs)
        self._pages.addWidget(device_container)
        self._device_container = device_container

        # ── [2] site_capture ──
        site_capture_container = QWidget()
        self._site_capture_tabs = QTabWidget()
        self._capture_page = CapturePage()
        self._site_production_page = ProductionRunPage()
        self._site_capture_tabs.addTab(self._capture_page, tr("capture.title"))
        self._site_capture_tabs.addTab(self._site_production_page, tr("production.title"))
        scl = QVBoxLayout(site_capture_container)
        scl.setContentsMargins(0, 0, 0, 0)
        scl.addWidget(self._site_capture_tabs)
        self._pages.addWidget(site_capture_container)
        self._site_capture_container = site_capture_container

        # ── [3] sample_review ──
        sample_review_container = QWidget()
        self._sample_review_tabs = QTabWidget()
        self._review_classify_page = SampleClassificationPage()
        self._review_bbox_page = BboxAnnotationPage()
        self._field_workflow_page = FieldWorkflowPage()
        self._sample_library_page = SampleLibraryPage()
        self._review_dataset_page = DatasetVersionPage()
        self._sample_review_tabs.addTab(self._review_classify_page, tr("classify.title"))
        self._sample_review_tabs.addTab(self._review_bbox_page, tr("bbox.page_title"))
        self._sample_review_tabs.addTab(self._field_workflow_page, tr("field_workflow.title"))
        self._sample_review_tabs.addTab(self._sample_library_page, tr("nav.sample_library"))
        self._sample_review_tabs.addTab(self._review_dataset_page, tr("dataset.title"))
        srl = QVBoxLayout(sample_review_container)
        srl.setContentsMargins(0, 0, 0, 0)
        srl.addWidget(self._sample_review_tabs)
        self._pages.addWidget(sample_review_container)
        self._sample_review_container = sample_review_container

        # ── [4] model_iteration (reuse existing training container) ──
        training_container = QWidget()
        self._training_tabs = QTabWidget()
        self._training_page = TrainingPage()
        self._training_jobs_page = TrainingJobsPage()
        self._model_version_page = ModelVersionPage()
        self._training_tabs.addTab(self._training_page, tr("training.title"))
        self._training_tabs.addTab(self._training_jobs_page, tr("jobs.title"))
        self._training_tabs.addTab(self._model_version_page, tr("model.title"))
        tl = QVBoxLayout(training_container)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(self._training_tabs)
        self._pages.addWidget(training_container)
        self._training_container = training_container

        # ── [5] hybrid_runtime ──
        hybrid_runtime_container = QWidget()
        self._hybrid_runtime_tabs = QTabWidget()
        self._hybrid_production_page = ProductionRunPage()
        self._hybrid_retest_page = HybridRetestPage()
        self._defect_trace_page = DefectTracePage()
        self._hybrid_runtime_tabs.addTab(self._hybrid_production_page, tr("production.title"))
        self._hybrid_runtime_tabs.addTab(self._hybrid_retest_page, tr("nav.hybrid_retest"))
        self._hybrid_runtime_tabs.addTab(self._defect_trace_page, tr("nav.defect_trace"))
        hrl = QVBoxLayout(hybrid_runtime_container)
        hrl.setContentsMargins(0, 0, 0, 0)
        hrl.addWidget(self._hybrid_runtime_tabs)
        self._pages.addWidget(hybrid_runtime_container)
        self._hybrid_runtime_container = hybrid_runtime_container

        # ── [6] performance ──
        performance_container = QWidget()
        self._performance_tabs = QTabWidget()
        self._perf_inference_page = InferencePage()
        self._perf_evaluation_page = EvaluationPage()
        self._perf_comparison_page = ModelComparisonPage()
        self._benchmark_page = BenchmarkPage()
        self._performance_tabs.addTab(self._perf_inference_page, tr("inference.title"))
        self._performance_tabs.addTab(self._perf_evaluation_page, tr("eval.title"))
        self._performance_tabs.addTab(self._perf_comparison_page, tr("compare.title"))
        self._performance_tabs.addTab(self._benchmark_page, tr("nav.benchmark"))
        pl = QVBoxLayout(performance_container)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(self._performance_tabs)
        self._pages.addWidget(performance_container)
        self._performance_container = performance_container

        # ── [7] delivery ──
        delivery_container = QWidget()
        self._delivery_tabs = QTabWidget()
        self._delivery_report_page = ReportPage()
        self._delivery_export_page = ModelExportPage()
        self._delivery_tabs.addTab(self._delivery_report_page, tr("report.title"))
        self._delivery_tabs.addTab(self._delivery_export_page, tr("export.title"))
        dvl = QVBoxLayout(delivery_container)
        dvl.setContentsMargins(0, 0, 0, 0)
        dvl.addWidget(self._delivery_tabs)
        self._pages.addWidget(delivery_container)
        self._delivery_container = delivery_container

        # ── [8] maintenance ──
        maintenance_container = QWidget()
        self._maintenance_tabs = QTabWidget()
        self._log_center_page = LogCenterPage()
        self._backup_page = BackupRestorePage()
        self._settings_page = SystemSettingsPage()
        self._help_page = HelpPage()
        self._maintenance_tabs.addTab(self._log_center_page, tr("log_center.title"))
        self._maintenance_tabs.addTab(self._backup_page, tr("backup.title"))
        self._maintenance_tabs.addTab(self._settings_page, tr("settings.title"))
        self._maintenance_tabs.addTab(self._help_page, tr("help.title"))
        mtl = QVBoxLayout(maintenance_container)
        mtl.setContentsMargins(0, 0, 0, 0)
        mtl.addWidget(self._maintenance_tabs)
        self._pages.addWidget(maintenance_container)
        self._maintenance_container = maintenance_container

        # ── [9] auto_focus ──
        af_container = QWidget()
        self._auto_focus_page = AutoFocusPage()
        afl = QVBoxLayout(af_container)
        afl.setContentsMargins(0, 0, 0, 0)
        afl.addWidget(self._auto_focus_page)
        self._pages.addWidget(af_container)
        self._af_container = af_container

        self._splitter.addWidget(self._pages)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setHandleWidth(1)
        self._splitter.setSizes([200, 980])
        root_layout.addWidget(self._splitter, 1)

        # Bottom: status bar
        self._status_bar = AppStatusBar()
        self.setStatusBar(self._status_bar)

    def _connect_signals(self) -> None:
        self._nav.page_selected.connect(self._on_page_selected)
        self._selector.customer_changed.connect(self._on_context_changed)
        self._selector.project_changed.connect(self._on_context_changed)
        self._selector.spec_changed.connect(self._on_context_changed)
        # Training completion auto-refreshes model version history.
        self._training_page.data_changed.connect(self._model_version_page.refresh)
        # Project center CRUD keeps top-bar selector in sync.
        self._project_center.data_changed.connect(self._selector.refresh)
        self._selector.refreshed.connect(self._refresh_current_page)
        # Cross-page navigation
        self._ctx.navigate_to_project_center.connect(self._on_navigate_to_project_center)
        self._ctx.navigate_to_production.connect(self._on_navigate_to_production)
        self._ctx.navigate_to_site_production.connect(self._on_navigate_to_site_production)
        self._ctx.navigate_to_page.connect(self._on_page_selected)

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set tab labels on language change."""
        self._workbench_tabs.setTabText(0, tr("nav.workbench"))
        self._workbench_tabs.setTabText(1, tr("nav.project_center"))

        self._device_tabs.setTabText(0, tr("camera_workbench.title"))
        self._device_tabs.setTabText(1, tr("production_line_com.title"))

        self._site_capture_tabs.setTabText(0, tr("capture.title"))
        self._site_capture_tabs.setTabText(1, tr("production.title"))

        self._sample_review_tabs.setTabText(0, tr("classify.title"))
        self._sample_review_tabs.setTabText(1, tr("bbox.page_title"))
        self._sample_review_tabs.setTabText(2, tr("field_workflow.title"))
        self._sample_review_tabs.setTabText(3, tr("nav.sample_library"))
        self._sample_review_tabs.setTabText(4, tr("dataset.title"))

        self._training_tabs.setTabText(0, tr("training.title"))
        self._training_tabs.setTabText(1, tr("jobs.title"))
        self._training_tabs.setTabText(2, tr("model.title"))

        self._hybrid_runtime_tabs.setTabText(0, tr("production.title"))
        self._hybrid_runtime_tabs.setTabText(1, tr("nav.hybrid_retest"))
        self._hybrid_runtime_tabs.setTabText(2, tr("nav.defect_trace"))

        self._performance_tabs.setTabText(0, tr("inference.title"))
        self._performance_tabs.setTabText(1, tr("eval.title"))
        self._performance_tabs.setTabText(2, tr("compare.title"))
        self._performance_tabs.setTabText(3, tr("nav.benchmark"))

        self._delivery_tabs.setTabText(0, tr("report.title"))
        self._delivery_tabs.setTabText(1, tr("export.title"))

        self._maintenance_tabs.setTabText(0, tr("log_center.title"))
        self._maintenance_tabs.setTabText(1, tr("backup.title"))
        self._maintenance_tabs.setTabText(2, tr("settings.title"))
        self._maintenance_tabs.setTabText(3, tr("help.title"))

    def _on_theme_changed(self) -> None:
        """Re-apply global stylesheet when theme changes."""
        self.setStyleSheet(ThemeManager.instance().get_stylesheet())

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        self._nav.set_collapsed(self._sidebar_collapsed)
        self._sidebar_btn.setText("☰" if not self._sidebar_collapsed else "›")
        self._sidebar_btn.setToolTip(tr("sidebar.toggle_tooltip"))
        self._splitter.setSizes([48 if self._sidebar_collapsed else 200, 1132])

    def _on_page_selected(self, page_id: str) -> None:
        if page_id == "workbench":
            self._pages.setCurrentWidget(self._workbench_container)
        elif page_id == "device_setup":
            self._pages.setCurrentWidget(self._device_container)
        elif page_id == "site_capture":
            self._pages.setCurrentWidget(self._site_capture_container)
        elif page_id == "sample_review":
            self._pages.setCurrentWidget(self._sample_review_container)
        elif page_id == "model_iteration":
            self._pages.setCurrentWidget(self._training_container)
        elif page_id == "hybrid_runtime":
            self._pages.setCurrentWidget(self._hybrid_runtime_container)
        elif page_id == "performance":
            self._pages.setCurrentWidget(self._performance_container)
        elif page_id == "delivery":
            self._pages.setCurrentWidget(self._delivery_container)
        elif page_id == "maintenance":
            self._pages.setCurrentWidget(self._maintenance_container)
        elif page_id == "auto_focus":
            self._pages.setCurrentWidget(self._af_container)
        self._update_status()

    def _open_runtime_page(self, mode_value: str, session_id: str) -> None:
        """Unified runtime navigation: parse mode, pick container, link session.

        Routes BASELINE_CAPTURE / SETUP_CAPTURE to site_capture;
        all other modes (including invalid) to hybrid_runtime.
        """
        try:
            mode = RuntimeMode(mode_value)
        except ValueError:
            mode = RuntimeMode.STABLE_PRODUCTION

        if mode_targets_site_capture(mode):
            page = self._site_production_page
            container = self._site_capture_container
            tabs = self._site_capture_tabs
            tab_index = 1
        else:
            page = self._hybrid_production_page
            container = self._hybrid_runtime_container
            tabs = self._hybrid_runtime_tabs
            tab_index = 0

        page.set_runtime_mode(mode)
        if session_id:
            page.link_capture_session(session_id)
        tabs.setCurrentIndex(tab_index)
        self._pages.setCurrentWidget(container)

    def _on_navigate_to_production(self, mode_value: str, session_id: str) -> None:
        """Navigate to hybrid_runtime container (backward-compat signal wrapper)."""
        self._open_runtime_page(mode_value, session_id)

    def _on_navigate_to_site_production(self, mode_value: str, session_id: str) -> None:
        """Navigate to site_capture container (backward-compat signal wrapper)."""
        self._open_runtime_page(mode_value, session_id)

    def _on_navigate_to_project_center(self) -> None:
        """Switch to workbench container and select the project-center tab."""
        self._pages.setCurrentWidget(self._workbench_container)
        self._workbench_tabs.setCurrentIndex(1)  # project-center tab

    def _on_context_changed(self, _value: str) -> None:
        self._update_status()
        self._workbench_page.refresh()

    def _refresh_current_page(self) -> None:
        """Refresh the page/tab currently visible behind the top selector."""
        self._update_status()
        page = self._current_visible_page()
        self._invoke_page_refresh(page)

    def _current_visible_page(self) -> QWidget:
        container = self._pages.currentWidget()
        tab_by_container = {
            self._workbench_container: self._workbench_tabs,
            self._device_container: self._device_tabs,
            self._site_capture_container: self._site_capture_tabs,
            self._sample_review_container: self._sample_review_tabs,
            self._training_container: self._training_tabs,
            self._hybrid_runtime_container: self._hybrid_runtime_tabs,
            self._performance_container: self._performance_tabs,
            self._delivery_container: self._delivery_tabs,
            self._maintenance_container: self._maintenance_tabs,
        }
        tabs = tab_by_container.get(container)
        if tabs is not None and tabs.currentWidget() is not None:
            return tabs.currentWidget()
        return container

    @staticmethod
    def _invoke_page_refresh(page: QWidget | None) -> None:
        if page is None:
            return
        for method_name in (
            "refresh",
            "_on_refresh",
            "_refresh",
            "_refresh_all",
            "_refresh_sessions",
            "_refresh_models",
            "_refresh_list",
            "_refresh_status",
        ):
            method = getattr(page, method_name, None)
            if callable(method):
                method()
                return

    def _update_status(self) -> None:
        self._status_bar.set_context_text(
            tr(
                "status.current_context",
                customer=self._ctx.current_customer_name or "—",
                project=self._ctx.current_project_name or "—",
                spec=self._ctx.current_spec_name or "—",
            )
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._selector.refresh()

    def closeEvent(self, event) -> None:
        self._selector.persist_current_selection()
        super().closeEvent(event)
