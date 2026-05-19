"""Main application window."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QSplitter, QTabWidget, QPushButton,
)

from desktop_app.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
)
from desktop_app.theme import get_stylesheet
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.navigation import NavigationBar
from desktop_app.widgets.project_selector import ProjectSelector
from desktop_app.widgets.status_bar import AppStatusBar
from desktop_app.pages.project_center_page import ProjectCenterPage
from desktop_app.pages.capture_page import CapturePage
from desktop_app.pages.sample_classification_page import SampleClassificationPage
from desktop_app.pages.dataset_version_page import DatasetVersionPage
from desktop_app.pages.training_page import TrainingPage
from desktop_app.pages.training_jobs_page import TrainingJobsPage
from desktop_app.pages.model_version_page import ModelVersionPage
from desktop_app.pages.inference_page import InferencePage
from desktop_app.pages.evaluation_page import EvaluationPage
from desktop_app.pages.model_comparison_page import ModelComparisonPage
from desktop_app.app_context import AppContext
from desktop_app.pages.production_run_page import ProductionRunPage
from desktop_app.pages.device_config_page import DeviceConfigPage
from desktop_app.pages.camera_config_page import CameraConfigPage
from desktop_app.pages.plc_config_page import PlcConfigPage
from desktop_app.pages.encoder_config_page import EncoderConfigPage
from desktop_app.pages.defect_trace_page import DefectTracePage
from desktop_app.pages.report_page import ReportPage
from desktop_app.pages.system_settings_page import SystemSettingsPage
from desktop_app.pages.log_center_page import LogCenterPage
from desktop_app.pages.backup_restore_page import BackupRestorePage
from desktop_app.pages.help_page import HelpPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._ctx = AppContext.instance()
        bind(self, "app.title", setter="setWindowTitle")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.setStyleSheet(get_stylesheet())
        self._sidebar_collapsed = False
        self._build_ui()
        self._connect_signals()
        self._sidebar_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self._sidebar_shortcut.activated.connect(self._toggle_sidebar)
        I18nManager.instance().language_changed.connect(self._refresh_text)

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
        self._sidebar_btn.setToolTip("切换边栏  Ctrl+B")
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

        # Data pages (capture, classification, dataset) under a tab widget
        data_container = QWidget()
        self._data_tabs = QTabWidget()
        self._capture_page = CapturePage()
        self._classify_page = SampleClassificationPage()
        self._dataset_page = DatasetVersionPage()
        self._data_tabs.addTab(self._capture_page, tr("capture.title"))
        self._data_tabs.addTab(self._classify_page, tr("classify.title"))
        self._data_tabs.addTab(self._dataset_page, tr("dataset.title"))
        data_layout2 = QVBoxLayout(data_container)
        data_layout2.setContentsMargins(0, 0, 0, 0)
        data_layout2.addWidget(self._data_tabs)
        self._pages.addWidget(data_container)
        self._data_container = data_container

        # Training pages (replacing "training" placeholder)
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

        # Evaluation pages (replacing "evaluation" placeholder)
        eval_container = QWidget()
        self._eval_tabs = QTabWidget()
        self._inference_page = InferencePage()
        self._evaluation_page = EvaluationPage()
        self._comparison_page = ModelComparisonPage()
        self._eval_tabs.addTab(self._inference_page, tr("inference.title"))
        self._eval_tabs.addTab(self._evaluation_page, tr("eval.title"))
        self._eval_tabs.addTab(self._comparison_page, tr("compare.title"))
        el = QVBoxLayout(eval_container)
        el.setContentsMargins(0, 0, 0, 0)
        el.addWidget(self._eval_tabs)
        self._pages.addWidget(eval_container)
        self._eval_container = eval_container

        # Production page (replacing "production" placeholder)
        self._production_page = ProductionRunPage()
        self._pages.addWidget(self._production_page)

        # Device config pages (replacing "device_config" placeholder)
        device_container = QWidget()
        self._device_tabs = QTabWidget()
        self._device_config_page = DeviceConfigPage()
        self._camera_config_page = CameraConfigPage()
        self._plc_config_page = PlcConfigPage()
        self._encoder_config_page = EncoderConfigPage()
        self._device_tabs.addTab(self._device_config_page, tr("device.title"))
        self._device_tabs.addTab(self._camera_config_page, tr("camera.title"))
        self._device_tabs.addTab(self._plc_config_page, tr("plc.title"))
        self._device_tabs.addTab(self._encoder_config_page, tr("encoder.title"))
        dl = QVBoxLayout(device_container)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.addWidget(self._device_tabs)
        self._pages.addWidget(device_container)
        self._device_container = device_container

        # Reports page
        self._report_page = ReportPage()
        self._pages.addWidget(self._report_page)

        # System settings page
        self._settings_page = SystemSettingsPage()
        self._pages.addWidget(self._settings_page)

        # Log center page (Phase 3)
        self._log_center_page = LogCenterPage()
        self._pages.addWidget(self._log_center_page)

        # Backup restore page (Phase 3)
        self._backup_page = BackupRestorePage()
        self._pages.addWidget(self._backup_page)

        # Help page
        self._help_page = HelpPage()
        self._pages.addWidget(self._help_page)

        # Real page: project center
        self._project_center = ProjectCenterPage()
        self._pages.addWidget(self._project_center)

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

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set tab labels on language change."""
        self._data_tabs.setTabText(0, tr("capture.title"))
        self._data_tabs.setTabText(1, tr("classify.title"))
        self._data_tabs.setTabText(2, tr("dataset.title"))

        self._training_tabs.setTabText(0, tr("training.title"))
        self._training_tabs.setTabText(1, tr("jobs.title"))
        self._training_tabs.setTabText(2, tr("model.title"))

        self._eval_tabs.setTabText(0, tr("inference.title"))
        self._eval_tabs.setTabText(1, tr("eval.title"))
        self._eval_tabs.setTabText(2, tr("compare.title"))

        self._device_tabs.setTabText(0, tr("device.title"))
        self._device_tabs.setTabText(1, tr("camera.title"))
        self._device_tabs.setTabText(2, tr("plc.title"))
        self._device_tabs.setTabText(3, tr("encoder.title"))

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        self._nav.set_collapsed(self._sidebar_collapsed)
        self._sidebar_btn.setText("☰" if not self._sidebar_collapsed else "›")
        self._sidebar_btn.setToolTip("切换边栏  Ctrl+B")
        self._splitter.setSizes([48 if self._sidebar_collapsed else 200, 1132])

    def _on_page_selected(self, page_id: str) -> None:
        if page_id == "project_center":
            self._pages.setCurrentWidget(self._project_center)
        elif page_id == "capture":
            self._pages.setCurrentWidget(self._data_container)
        elif page_id == "training":
            self._pages.setCurrentWidget(self._training_container)
        elif page_id == "evaluation":
            self._pages.setCurrentWidget(self._eval_container)
        elif page_id == "production":
            self._pages.setCurrentWidget(self._production_page)
        elif page_id == "device_config":
            self._pages.setCurrentWidget(self._device_container)
        elif page_id == "reports":
            self._pages.setCurrentWidget(self._report_page)
        elif page_id == "settings":
            self._pages.setCurrentWidget(self._settings_page)
        elif page_id == "log_center":
            self._pages.setCurrentWidget(self._log_center_page)
        elif page_id == "backup":
            self._pages.setCurrentWidget(self._backup_page)
        elif page_id == "help":
            self._pages.setCurrentWidget(self._help_page)
        self._update_status()

    def _on_context_changed(self, _value: str) -> None:
        self._update_status()

    def _update_status(self) -> None:
        self._status_bar.set_context_text(
            tr("status.current_context",
               customer=self._ctx.current_customer_name or '—',
               project=self._ctx.current_project_name or '—',
               spec=self._ctx.current_spec_name or '—')
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._selector.refresh()

    def closeEvent(self, event) -> None:
        self._selector.persist_current_selection()
        super().closeEvent(event)
