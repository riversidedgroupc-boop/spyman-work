"""System settings page — paths, health status, version info."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QLabel,
    QFileDialog,
    QComboBox,
)

from core.storage import _db_path
from runtime.health_monitor import HealthMonitor
from runtime.system_monitor import SystemMonitor
from desktop_app.constants import APP_NAME, APP_VERSION
from desktop_app.i18n import tr, bind, I18nManager
from desktop_app.theme_manager import ThemeManager


class SystemSettingsPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._health = HealthMonitor()
        self._sys_mon = SystemMonitor()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Paths group
        self._paths_grp = QGroupBox()
        bind(self._paths_grp, "settings.paths_group", setter="setTitle")
        paths_form = QFormLayout(self._paths_grp)
        self._data_dir_edit = QLineEdit("data/")
        data_dir_label = QLabel()
        bind(data_dir_label, "settings.data_dir")
        paths_form.addRow(data_dir_label, self._make_browse_row(self._data_dir_edit))
        self._model_dir_edit = QLineEdit("models/")
        model_dir_label = QLabel()
        bind(model_dir_label, "settings.model_dir")
        paths_form.addRow(model_dir_label, self._make_browse_row(self._model_dir_edit))
        self._log_dir_edit = QLineEdit("logs/")
        log_dir_label = QLabel()
        bind(log_dir_label, "settings.log_dir")
        paths_form.addRow(log_dir_label, self._make_browse_row(self._log_dir_edit))
        self._db_label = QLabel(_db_path())
        self._db_label.setObjectName("secondaryLabel")
        db_path_label = QLabel()
        bind(db_path_label, "settings.db_path")
        paths_form.addRow(db_path_label, self._db_label)
        layout.addWidget(self._paths_grp)

        # Health group
        self._health_grp = QGroupBox()
        bind(self._health_grp, "settings.health_group", setter="setTitle")
        health_form = QFormLayout(self._health_grp)
        self._disk_label = QLabel("—")
        disk_label = QLabel()
        bind(disk_label, "settings.disk")
        health_form.addRow(disk_label, self._disk_label)
        self._uptime_label = QLabel("—")
        uptime_label = QLabel()
        bind(uptime_label, "settings.uptime")
        health_form.addRow(uptime_label, self._uptime_label)
        self._cpu_label = QLabel("—")
        cpu_label = QLabel()
        bind(cpu_label, "settings.cpu")
        health_form.addRow(cpu_label, self._cpu_label)
        self._mem_label = QLabel("—")
        mem_label = QLabel()
        bind(mem_label, "settings.memory")
        health_form.addRow(mem_label, self._mem_label)
        layout.addWidget(self._health_grp)

        # Version group
        self._ver_grp = QGroupBox()
        bind(self._ver_grp, "settings.version_group", setter="setTitle")
        ver_form = QFormLayout(self._ver_grp)
        ver_app_label = QLabel()
        bind(ver_app_label, "settings.version_app")
        ver_form.addRow(ver_app_label, QLabel(APP_NAME))
        ver_num_label = QLabel()
        bind(ver_num_label, "settings.version_num")
        ver_form.addRow(ver_num_label, QLabel(APP_VERSION))
        ver_phase_label = QLabel()
        bind(ver_phase_label, "settings.version_phase")
        self._phase_value_label = QLabel()
        bind(self._phase_value_label, "settings.version_phase_value")
        ver_form.addRow(ver_phase_label, self._phase_value_label)
        layout.addWidget(self._ver_grp)

        # Language group
        self._lang_grp = QGroupBox()
        bind(self._lang_grp, "settings.language_group", setter="setTitle")
        lang_form = QFormLayout(self._lang_grp)
        self._lang_combo = QComboBox()
        self._lang_combo.addItem(tr("settings.language_zh"), "zh")
        self._lang_combo.addItem(tr("settings.language_en"), "en")
        current = I18nManager.instance().language
        idx = self._lang_combo.findData(current)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_label = QLabel()
        bind(lang_label, "settings.language_label")
        lang_form.addRow(lang_label, self._lang_combo)
        layout.addWidget(self._lang_grp)

        # Theme group
        self._theme_grp = QGroupBox()
        bind(self._theme_grp, "settings.theme_group", setter="setTitle")
        theme_form = QFormLayout(self._theme_grp)
        self._theme_combo = QComboBox()
        self._theme_combo.addItem(tr("settings.theme_light"), "light")
        self._theme_combo.addItem(tr("settings.theme_dark"), "dark")
        current_theme = "dark" if ThemeManager.instance().is_dark() else "light"
        idx2 = self._theme_combo.findData(current_theme)
        if idx2 >= 0:
            self._theme_combo.setCurrentIndex(idx2)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_label = QLabel()
        bind(theme_label, "settings.theme_label")
        theme_form.addRow(theme_label, self._theme_combo)
        layout.addWidget(self._theme_grp)

        layout.addStretch()

    def _refresh_text(self, lang: str = "") -> None:
        """Re-set language combo items and health labels on language change."""
        # Rebuild language combo (preserve selection)
        cur = self._lang_combo.currentData()
        self._lang_combo.blockSignals(True)
        self._lang_combo.clear()
        self._lang_combo.addItem(tr("settings.language_zh"), "zh")
        self._lang_combo.addItem(tr("settings.language_en"), "en")
        idx = self._lang_combo.findData(cur)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._lang_combo.blockSignals(False)

        # Rebuild theme combo (preserve selection)
        cur_theme = self._theme_combo.currentData()
        self._theme_combo.blockSignals(True)
        self._theme_combo.clear()
        self._theme_combo.addItem(tr("settings.theme_light"), "light")
        self._theme_combo.addItem(tr("settings.theme_dark"), "dark")
        idx2 = self._theme_combo.findData(cur_theme)
        if idx2 >= 0:
            self._theme_combo.setCurrentIndex(idx2)
        self._theme_combo.blockSignals(False)

        self._refresh_status()

    def _make_browse_row(self, edit):
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit)
        btn = QPushButton("...")
        btn.setFixedWidth(36)
        btn.clicked.connect(lambda: self._browse_dir(edit))
        row.addWidget(btn)
        return row_widget

    def _browse_dir(self, edit):
        d = QFileDialog.getExistingDirectory(self, tr("dialog.select_dir"))
        if d:
            edit.setText(d)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_status()
        self._timer.start(5000)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def _on_language_changed(self, index):
        lang = self._lang_combo.itemData(index)
        if lang:
            I18nManager.instance().set_language(lang)

    def _on_theme_changed(self, index):
        theme_key = self._theme_combo.itemData(index)
        if theme_key == "dark":
            from desktop_app.theme_manager import PALETTE_DARK
            ThemeManager.instance().set_theme(PALETTE_DARK)
        else:
            from desktop_app.theme_manager import PALETTE_LIGHT
            ThemeManager.instance().set_theme(PALETTE_LIGHT)

    def _refresh_status(self):
        health = self._health.get_health()
        self._disk_label.setText(
            tr(
                "settings.disk_fmt",
                free=health["disk_free_gb"],
                total=health["disk_total_gb"],
                pct=health["disk_percent"],
            )
        )
        uptime_s = int(health["uptime_seconds"])
        self._uptime_label.setText(
            tr(
                "settings.uptime_fmt",
                h=uptime_s // 3600,
                m=(uptime_s % 3600) // 60,
                s=uptime_s % 60,
            )
        )

        self._sys_mon.update()
        sys_status = self._sys_mon.get_status()
        self._cpu_label.setText(
            f"{sys_status['cpu_percent']:.1f}%"
            if sys_status["cpu_percent"] >= 0
            else tr("settings.cpu_na")
        )
        self._mem_label.setText(
            f"{sys_status['memory_percent']:.1f}%"
            if sys_status["memory_percent"] > 0
            else tr("settings.cpu_na")
        )
