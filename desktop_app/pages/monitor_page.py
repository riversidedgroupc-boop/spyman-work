"""Real-time performance monitor page — system and pipeline metrics dashboard."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QGridLayout,
    QLabel,
    QProgressBar,
    QFrame,
)

from desktop_app.i18n import tr, I18nManager
from desktop_app.theme_manager import ThemeManager


def _fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


def _fmt_mb(v: float) -> str:
    return f"{v:.0f} MB"


def _fmt_gb(v: float) -> str:
    return f"{v:.2f} GB"


def _fmt_ms(v: float) -> str:
    return f"{v:.2f} ms"


def _fmt_num(v: int | float) -> str:
    return f"{v:.0f}" if isinstance(v, float) and v == int(v) else f"{v:.1f}"


class _GaugeWidget(QFrame):
    """Single metric: label + value + colored progress bar."""

    def __init__(self, title: str, unit: str = "", warn_at: float = 80, crit_at: float = 95):
        super().__init__()
        self._warn_at = warn_at
        self._crit_at = crit_at
        self._unit = unit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        self._label = QLabel(title)
        self._label.setObjectName("secondaryLabel")
        layout.addWidget(self._label)

        self._value = QLabel("—")
        self._value.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self._value)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        layout.addWidget(self._bar)

    def update_value(self, value: float) -> None:
        text = f"{value:.1f}{self._unit}" if self._unit else f"{value:.1f}"
        self._value.setText(text)
        pct = min(value, 100.0)
        self._bar.setValue(int(pct))

        c = ThemeManager.current()
        if value >= self._crit_at:
            self._bar.setStyleSheet(
                f"QProgressBar {{ background: {c.BG_INPUT}; border: none; }} "
                f"QProgressBar::chunk {{ background: {c.GAUGE_RED}; border-radius: 2px; }}"
            )
        elif value >= self._warn_at:
            self._bar.setStyleSheet(
                f"QProgressBar {{ background: {c.BG_INPUT}; border: none; }} "
                f"QProgressBar::chunk {{ background: {c.GAUGE_ORANGE}; border-radius: 2px; }}"
            )
        else:
            self._bar.setStyleSheet(
                f"QProgressBar {{ background: {c.BG_INPUT}; border: none; }} "
                f"QProgressBar::chunk {{ background: {c.GAUGE_GREEN}; border-radius: 2px; }}"
            )

    def refresh_style(self) -> None:
        """Re-apply label style after theme change."""
        # label uses #secondaryLabel QSS — no action needed
        pass


class _InfoTile(QFrame):
    """Info tile: label + value, no bar."""

    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        self._label = QLabel(title)
        self._label.setObjectName("secondaryLabel")
        layout.addWidget(self._label)

        self._value = QLabel("—")
        self._value.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self._value)

    def set_text(self, text: str) -> None:
        self._value.setText(text)


class MonitorPage(QWidget):
    """Real-time dashboard showing system and pipeline health."""

    def __init__(self, parent=None, compact: bool = False):
        super().__init__(parent)
        self._compact = compact
        self._nvml_available = False
        self._gpu_handle = None
        self._init_gpu()
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1000)
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _init_gpu(self) -> None:
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml_available = True
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            self._nvml_available = False

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        if self._compact:
            self._build_compact_ui(layout)
            return

        # --- System resources ---
        self._sys_group = QGroupBox(tr("monitor.sys_resources"))
        sys_grid = QGridLayout(self._sys_group)
        sys_grid.setSpacing(8)

        self._cpu_gauge = _GaugeWidget(tr("monitor.cpu"), "%", warn_at=70, crit_at=90)
        sys_grid.addWidget(self._cpu_gauge, 0, 0)

        self._ram_gauge = _GaugeWidget(tr("monitor.memory"), "%", warn_at=80, crit_at=90)
        sys_grid.addWidget(self._ram_gauge, 0, 1)

        self._gpu_gauge = _GaugeWidget(tr("monitor.gpu"), "%", warn_at=80, crit_at=95)
        sys_grid.addWidget(self._gpu_gauge, 0, 2)

        self._vram_gauge = _GaugeWidget(tr("monitor.vram"), "%", warn_at=80, crit_at=92)
        sys_grid.addWidget(self._vram_gauge, 0, 3)

        self._disk_gauge = _GaugeWidget(tr("monitor.disk"), "%", warn_at=80, crit_at=90)
        sys_grid.addWidget(self._disk_gauge, 1, 0)

        self._ram_used_tile = _InfoTile(tr("monitor.ram_used"))
        sys_grid.addWidget(self._ram_used_tile, 1, 1)

        self._vram_used_tile = _InfoTile(tr("monitor.vram_used"))
        sys_grid.addWidget(self._vram_used_tile, 1, 2)

        self._disk_free_tile = _InfoTile(tr("monitor.disk_free"))
        sys_grid.addWidget(self._disk_free_tile, 1, 3)

        layout.addWidget(self._sys_group)

        # --- Pipeline ---
        self._pipe_group = QGroupBox(tr("monitor.pipeline"))
        pipe_grid = QGridLayout(self._pipe_group)
        pipe_grid.setSpacing(8)

        self._pool_depth = _InfoTile(tr("monitor.pool_depth"))
        pipe_grid.addWidget(self._pool_depth, 0, 0)

        self._pool_usage = _GaugeWidget(tr("monitor.pool_usage"), "%", warn_at=70, crit_at=90)
        pipe_grid.addWidget(self._pool_usage, 0, 1)

        self._tiles_dropped = _InfoTile(tr("monitor.tiles_dropped"))
        pipe_grid.addWidget(self._tiles_dropped, 0, 2)

        self._spi_value = _GaugeWidget(tr("monitor.spi_value"), "", warn_at=60, crit_at=85)
        pipe_grid.addWidget(self._spi_value, 0, 3)

        self._infer_avg = _InfoTile(tr("monitor.infer_avg"))
        pipe_grid.addWidget(self._infer_avg, 1, 0)

        self._infer_p95 = _InfoTile(tr("monitor.infer_p95"))
        pipe_grid.addWidget(self._infer_p95, 1, 1)

        self._disk_level = _InfoTile(tr("monitor.disk_level"))
        pipe_grid.addWidget(self._disk_level, 1, 2)

        self._writer_stats = _InfoTile(tr("monitor.writer_stats"))
        pipe_grid.addWidget(self._writer_stats, 1, 3)

        layout.addWidget(self._pipe_group)

        # --- SPI explanation ---
        self._spi_group = QGroupBox(tr("monitor.spi_breakdown"))
        spi_layout = QHBoxLayout(self._spi_group)
        spi_layout.setSpacing(8)

        self._spi_cam = _GaugeWidget(tr("monitor.cam_weight"), "%", warn_at=70, crit_at=85)
        spi_layout.addWidget(self._spi_cam)
        self._spi_cpu = _GaugeWidget(tr("monitor.cpu_weight"), "%", warn_at=70, crit_at=85)
        spi_layout.addWidget(self._spi_cpu)
        self._spi_gpu = _GaugeWidget(tr("monitor.gpu_weight"), "%", warn_at=70, crit_at=85)
        spi_layout.addWidget(self._spi_gpu)
        self._spi_mem = _GaugeWidget(tr("monitor.mem_weight"), "%", warn_at=70, crit_at=85)
        spi_layout.addWidget(self._spi_mem)
        self._spi_disk = _GaugeWidget(tr("monitor.disk_weight"), "%", warn_at=70, crit_at=85)
        spi_layout.addWidget(self._spi_disk)

        layout.addWidget(self._spi_group)
        layout.addStretch()

    def _build_compact_ui(self, layout: QVBoxLayout) -> None:
        self._compact_group = QGroupBox(tr("monitor.compact_title"))
        grid = QGridLayout(self._compact_group)
        grid.setSpacing(8)

        self._cpu_gauge = _GaugeWidget(tr("monitor.cpu"), "%", warn_at=70, crit_at=90)
        grid.addWidget(self._cpu_gauge, 0, 0)
        self._ram_gauge = _GaugeWidget(tr("monitor.memory"), "%", warn_at=80, crit_at=90)
        grid.addWidget(self._ram_gauge, 0, 1)
        self._gpu_gauge = _GaugeWidget(tr("monitor.gpu"), "%", warn_at=80, crit_at=95)
        grid.addWidget(self._gpu_gauge, 0, 2)
        self._vram_gauge = _GaugeWidget(tr("monitor.vram"), "%", warn_at=80, crit_at=92)
        grid.addWidget(self._vram_gauge, 0, 3)
        self._disk_gauge = _GaugeWidget(tr("monitor.disk"), "%", warn_at=80, crit_at=90)
        grid.addWidget(self._disk_gauge, 0, 4)
        self._spi_value = _GaugeWidget(tr("monitor.spi_value"), "", warn_at=60, crit_at=85)
        grid.addWidget(self._spi_value, 0, 5)

        self._ram_used_tile = _InfoTile(tr("monitor.ram_used"))
        grid.addWidget(self._ram_used_tile, 1, 0)
        self._vram_used_tile = _InfoTile(tr("monitor.vram_used"))
        grid.addWidget(self._vram_used_tile, 1, 1)
        self._disk_free_tile = _InfoTile(tr("monitor.disk_free"))
        grid.addWidget(self._disk_free_tile, 1, 2)
        self._spi_cpu = _GaugeWidget(tr("monitor.cpu_weight"), "%", warn_at=70, crit_at=85)
        grid.addWidget(self._spi_cpu, 1, 3)
        self._spi_gpu = _GaugeWidget(tr("monitor.gpu_weight"), "%", warn_at=70, crit_at=85)
        grid.addWidget(self._spi_gpu, 1, 4)
        self._spi_disk = _GaugeWidget(tr("monitor.disk_weight"), "%", warn_at=70, crit_at=85)
        grid.addWidget(self._spi_disk, 1, 5)

        self._spi_cam = _GaugeWidget(tr("monitor.cam_weight"), "%", warn_at=70, crit_at=85)
        self._spi_mem = _GaugeWidget(tr("monitor.mem_weight"), "%", warn_at=70, crit_at=85)

        layout.addWidget(self._compact_group)

    def _refresh(self):
        cpu_pct, ram_pct, ram_used_gb, ram_total_gb = self._sample_cpu()
        gpu_pct, vram_pct, vram_used_mb, vram_total_mb = self._sample_gpu()
        disk_pct, disk_free_gb = self._sample_disk()

        self._cpu_gauge.update_value(cpu_pct)
        self._ram_gauge.update_value(ram_pct)
        self._gpu_gauge.update_value(gpu_pct)
        self._vram_gauge.update_value(vram_pct)
        self._disk_gauge.update_value(disk_pct)

        self._ram_used_tile.set_text(f"{_fmt_gb(ram_used_gb)} / {_fmt_gb(ram_total_gb)}")
        self._vram_used_tile.set_text(f"{_fmt_mb(vram_used_mb)} / {_fmt_mb(vram_total_mb)}")
        self._disk_free_tile.set_text(_fmt_gb(disk_free_gb))

        # SPI breakdown
        self._spi_cam.update_value(0)  # not available without active pipeline
        self._spi_cpu.update_value(cpu_pct)
        self._spi_gpu.update_value(gpu_pct)
        self._spi_mem.update_value(disk_pct)  # mem component uses disk for now
        self._spi_disk.update_value(disk_pct)

        spi = cpu_pct * 0.20 + gpu_pct * 0.30 + ram_pct * 0.15 + disk_pct * 0.15
        self._spi_value.update_value(spi)

    def _sample_cpu(self) -> tuple:
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=0)
            mem = psutil.virtual_memory()
            return cpu, mem.percent, mem.used / (1024**3), mem.total / (1024**3)
        except Exception:
            return 0, 0, 0, 0

    def _sample_gpu(self) -> tuple:
        if not self._nvml_available or self._gpu_handle is None:
            return 0, 0, 0, 0
        try:
            import pynvml

            util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
            vram_pct = mem_info.used / max(mem_info.total, 1) * 100
            return util.gpu, vram_pct, mem_info.used / (1024**2), mem_info.total / (1024**2)
        except Exception:
            return 0, 0, 0, 0

    def _sample_disk(self) -> tuple:
        try:
            import shutil

            usage = shutil.disk_usage(".")
            pct = usage.used / max(usage.total, 1) * 100
            return pct, usage.free / (1024**3)
        except Exception:
            return 0, 0

    def _refresh_text(self, lang: str = "") -> None:
        """Update all gauge/tile titles and group box titles on language change."""
        if not self._compact:
            self._sys_group.setTitle(tr("monitor.sys_resources"))
            self._pipe_group.setTitle(tr("monitor.pipeline"))
            self._spi_group.setTitle(tr("monitor.spi_breakdown"))
        else:
            self._compact_group.setTitle(tr("monitor.compact_title"))

        # Update gauge labels
        for gauge, key in [
            (self._cpu_gauge, "monitor.cpu"),
            (self._ram_gauge, "monitor.memory"),
            (self._gpu_gauge, "monitor.gpu"),
            (self._vram_gauge, "monitor.vram"),
            (self._disk_gauge, "monitor.disk"),
        ]:
            gauge._label.setText(tr(key))

        # Update tile labels
        for tile, key in [
            (self._ram_used_tile, "monitor.ram_used"),
            (self._vram_used_tile, "monitor.vram_used"),
            (self._disk_free_tile, "monitor.disk_free"),
        ]:
            tile._label.setText(tr(key))

        if not self._compact:
            # Pipeline gauges
            for gauge, key in [
                (self._pool_usage, "monitor.pool_usage"),
                (self._spi_value, "monitor.spi_value"),
            ]:
                gauge._label.setText(tr(key))
            for tile, key in [
                (self._pool_depth, "monitor.pool_depth"),
                (self._tiles_dropped, "monitor.tiles_dropped"),
                (self._infer_avg, "monitor.infer_avg"),
                (self._infer_p95, "monitor.infer_p95"),
                (self._disk_level, "monitor.disk_level"),
                (self._writer_stats, "monitor.writer_stats"),
            ]:
                tile._label.setText(tr(key))

            # SPI weights
            for gauge, key in [
                (self._spi_cam, "monitor.cam_weight"),
                (self._spi_cpu, "monitor.cpu_weight"),
                (self._spi_gpu, "monitor.gpu_weight"),
                (self._spi_mem, "monitor.mem_weight"),
                (self._spi_disk, "monitor.disk_weight"),
            ]:
                gauge._label.setText(tr(key))

    def _on_theme_changed(self) -> None:
        """Re-apply bar colors and label styles after theme toggle."""
        # Trigger gauge updates to refresh bar colors
        self._refresh()
