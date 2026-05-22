"""Real-time performance monitor page — system and pipeline metrics dashboard."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QLabel, QProgressBar, QFrame,
)

from desktop_app.i18n import tr, I18nManager


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
        self._label.setStyleSheet("color: #888; font-size: 11px;")
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

        if value >= self._crit_at:
            self._bar.setStyleSheet(
                "QProgressBar { background: #333; border: none; } "
                "QProgressBar::chunk { background: #f44336; border-radius: 2px; }"
            )
        elif value >= self._warn_at:
            self._bar.setStyleSheet(
                "QProgressBar { background: #333; border: none; } "
                "QProgressBar::chunk { background: #ff9800; border-radius: 2px; }"
            )
        else:
            self._bar.setStyleSheet(
                "QProgressBar { background: #333; border: none; } "
                "QProgressBar::chunk { background: #4caf50; border-radius: 2px; }"
            )


class _InfoTile(QFrame):
    """Info tile: label + value, no bar."""

    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        self._label = QLabel(title)
        self._label.setStyleSheet("color: #888; font-size: 11px;")
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
        sys_group = QGroupBox("系统资源")
        sys_grid = QGridLayout(sys_group)
        sys_grid.setSpacing(8)

        self._cpu_gauge = _GaugeWidget("CPU", "%", warn_at=70, crit_at=90)
        sys_grid.addWidget(self._cpu_gauge, 0, 0)

        self._ram_gauge = _GaugeWidget("内存", "%", warn_at=80, crit_at=90)
        sys_grid.addWidget(self._ram_gauge, 0, 1)

        self._gpu_gauge = _GaugeWidget("GPU", "%", warn_at=80, crit_at=95)
        sys_grid.addWidget(self._gpu_gauge, 0, 2)

        self._vram_gauge = _GaugeWidget("显存", "%", warn_at=80, crit_at=92)
        sys_grid.addWidget(self._vram_gauge, 0, 3)

        self._disk_gauge = _GaugeWidget("磁盘", "%", warn_at=80, crit_at=90)
        sys_grid.addWidget(self._disk_gauge, 1, 0)

        self._ram_used_tile = _InfoTile("内存占用")
        sys_grid.addWidget(self._ram_used_tile, 1, 1)

        self._vram_used_tile = _InfoTile("显存占用")
        sys_grid.addWidget(self._vram_used_tile, 1, 2)

        self._disk_free_tile = _InfoTile("磁盘剩余")
        sys_grid.addWidget(self._disk_free_tile, 1, 3)

        layout.addWidget(sys_group)

        # --- Pipeline ---
        pipe_group = QGroupBox("流水线")
        pipe_grid = QGridLayout(pipe_group)
        pipe_grid.setSpacing(8)

        self._pool_depth = _InfoTile("图像池深度")
        pipe_grid.addWidget(self._pool_depth, 0, 0)

        self._pool_usage = _GaugeWidget("池使用率", "%", warn_at=70, crit_at=90)
        pipe_grid.addWidget(self._pool_usage, 0, 1)

        self._tiles_dropped = _InfoTile("丢弃 Tile 数")
        pipe_grid.addWidget(self._tiles_dropped, 0, 2)

        self._spi_value = _GaugeWidget("SPI 系统压力指数", "", warn_at=60, crit_at=85)
        pipe_grid.addWidget(self._spi_value, 0, 3)

        self._infer_avg = _InfoTile("平均推理耗时")
        pipe_grid.addWidget(self._infer_avg, 1, 0)

        self._infer_p95 = _InfoTile("P95 推理耗时")
        pipe_grid.addWidget(self._infer_p95, 1, 1)

        self._disk_level = _InfoTile("磁盘等级")
        pipe_grid.addWidget(self._disk_level, 1, 2)

        self._writer_stats = _InfoTile("已写入图片")
        pipe_grid.addWidget(self._writer_stats, 1, 3)

        layout.addWidget(pipe_group)

        # --- SPI explanation ---
        spi_group = QGroupBox("SPI 构成")
        spi_layout = QHBoxLayout(spi_group)
        spi_layout.setSpacing(8)

        self._spi_cam = _GaugeWidget("相机 (20%)", "%", warn_at=70, crit_at=85)
        spi_layout.addWidget(self._spi_cam)
        self._spi_cpu = _GaugeWidget("CPU (20%)", "%", warn_at=70, crit_at=85)
        spi_layout.addWidget(self._spi_cpu)
        self._spi_gpu = _GaugeWidget("GPU (30%)", "%", warn_at=70, crit_at=85)
        spi_layout.addWidget(self._spi_gpu)
        self._spi_mem = _GaugeWidget("内存 (15%)", "%", warn_at=70, crit_at=85)
        spi_layout.addWidget(self._spi_mem)
        self._spi_disk = _GaugeWidget("磁盘 (15%)", "%", warn_at=70, crit_at=85)
        spi_layout.addWidget(self._spi_disk)

        layout.addWidget(spi_group)
        layout.addStretch()

    def _build_compact_ui(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("实时性能监控")
        grid = QGridLayout(group)
        grid.setSpacing(8)

        self._cpu_gauge = _GaugeWidget("CPU", "%", warn_at=70, crit_at=90)
        grid.addWidget(self._cpu_gauge, 0, 0)
        self._ram_gauge = _GaugeWidget("内存", "%", warn_at=80, crit_at=90)
        grid.addWidget(self._ram_gauge, 0, 1)
        self._gpu_gauge = _GaugeWidget("GPU", "%", warn_at=80, crit_at=95)
        grid.addWidget(self._gpu_gauge, 0, 2)
        self._vram_gauge = _GaugeWidget("显存", "%", warn_at=80, crit_at=92)
        grid.addWidget(self._vram_gauge, 0, 3)
        self._disk_gauge = _GaugeWidget("磁盘", "%", warn_at=80, crit_at=90)
        grid.addWidget(self._disk_gauge, 0, 4)
        self._spi_value = _GaugeWidget("SPI", "", warn_at=60, crit_at=85)
        grid.addWidget(self._spi_value, 0, 5)

        self._ram_used_tile = _InfoTile("内存占用")
        grid.addWidget(self._ram_used_tile, 1, 0)
        self._vram_used_tile = _InfoTile("显存占用")
        grid.addWidget(self._vram_used_tile, 1, 1)
        self._disk_free_tile = _InfoTile("磁盘剩余")
        grid.addWidget(self._disk_free_tile, 1, 2)
        self._spi_cpu = _GaugeWidget("CPU 权重", "%", warn_at=70, crit_at=85)
        grid.addWidget(self._spi_cpu, 1, 3)
        self._spi_gpu = _GaugeWidget("GPU 权重", "%", warn_at=70, crit_at=85)
        grid.addWidget(self._spi_gpu, 1, 4)
        self._spi_disk = _GaugeWidget("磁盘权重", "%", warn_at=70, crit_at=85)
        grid.addWidget(self._spi_disk, 1, 5)

        self._spi_cam = _GaugeWidget("相机", "%", warn_at=70, crit_at=85)
        self._spi_mem = _GaugeWidget("内存权重", "%", warn_at=70, crit_at=85)

        layout.addWidget(group)

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
        self._spi_cam.update_value(0)   # not available without active pipeline
        self._spi_cpu.update_value(cpu_pct)
        self._spi_gpu.update_value(gpu_pct)
        self._spi_mem.update_value(ram_pct)
        self._spi_disk.update_value(disk_pct)

        spi = (
            cpu_pct * 0.20
            + gpu_pct * 0.30
            + ram_pct * 0.15
            + disk_pct * 0.15
        )
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
        pass
