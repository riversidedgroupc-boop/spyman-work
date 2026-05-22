"""Benchmark page — stress test configuration, run control, results and export."""
from __future__ import annotations

import os
from datetime import datetime
from threading import Thread

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QSpinBox, QDoubleSpinBox, QPushButton, QLabel,
    QProgressBar, QTextEdit, QMessageBox, QGridLayout, QFileDialog,
)

from desktop_app.i18n import tr, I18nManager
from desktop_app.pages.monitor_page import MonitorPage


class BenchmarkPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._runner = None
        self._running = False
        self._last_report = None
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Config ---
        config_group = QGroupBox("压测配置")
        form = QFormLayout(config_group)

        self._camera_count = QSpinBox()
        self._camera_count.setRange(1, 16)
        self._camera_count.setValue(3)
        form.addRow("相机数量", self._camera_count)

        self._line_speed = QDoubleSpinBox()
        self._line_speed.setRange(10, 500)
        self._line_speed.setValue(80.0)
        self._line_speed.setSuffix(" 米/分钟")
        form.addRow("产线速度", self._line_speed)

        self._model_combo = QComboBox()
        self._model_combo.addItems(["yolo", "patchcore", "yolo+patchcore"])
        form.addRow("模型组合", self._model_combo)

        self._save_mode = QComboBox()
        self._save_mode.addItems(["save_ng_only", "save_all", "save_ng_ok_sampling", "result_only"])
        form.addRow("保存模式", self._save_mode)

        self._batch_size = QSpinBox()
        self._batch_size.setRange(1, 32)
        self._batch_size.setValue(4)
        form.addRow("推理批次", self._batch_size)

        self._duration = QSpinBox()
        self._duration.setRange(10, 7200)
        self._duration.setValue(1800)
        self._duration.setSuffix(" 秒")
        form.addRow("压测时长", self._duration)

        self._speed_multiplier = QComboBox()
        self._speed_multiplier.addItems(["0.5x", "1x", "2x", "4x", "8x"])
        self._speed_multiplier.setCurrentIndex(1)
        form.addRow("速度倍率", self._speed_multiplier)

        self._source_type = QComboBox()
        self._source_type.addItems(["simulated", "real_camera", "history_replay"])
        form.addRow("数据源", self._source_type)

        layout.addWidget(config_group)

        # --- Control buttons ---
        btn_layout = QHBoxLayout()
        self._start_btn = QPushButton("开始压测")
        self._start_btn.clicked.connect(self._start_benchmark)
        btn_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_benchmark)
        btn_layout.addWidget(self._stop_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        btn_layout.addWidget(self._progress, 1)

        # Export buttons
        self._export_md_btn = QPushButton("导出 Markdown")
        self._export_md_btn.setEnabled(False)
        self._export_md_btn.clicked.connect(self._export_markdown)
        btn_layout.addWidget(self._export_md_btn)

        self._export_json_btn = QPushButton("导出 JSON")
        self._export_json_btn.setEnabled(False)
        self._export_json_btn.clicked.connect(self._export_json)
        btn_layout.addWidget(self._export_json_btn)

        layout.addLayout(btn_layout)

        # --- Status ---
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("color: #888; padding: 4px;")
        layout.addWidget(self._status_label)

        # --- Results ---
        results_group = QGroupBox("压测结果")
        results_layout = QGridLayout(results_group)

        self._result_labels: dict[str, QLabel] = {}
        metrics = [
            ("avg_tiles_sec", "平均吞吐 (tiles/s)"),
            ("max_tiles_sec", "峰值吞吐 (tiles/s)"),
            ("avg_latency_ms", "平均延迟 (ms)"),
            ("p95_latency_ms", "P95 延迟 (ms)"),
            ("p99_latency_ms", "P99 延迟 (ms)"),
            ("avg_cpu_pct", "平均 CPU (%)"),
            ("peak_cpu_pct", "峰值 CPU (%)"),
            ("avg_gpu_pct", "平均 GPU (%)"),
            ("peak_gpu_pct", "峰值 GPU (%)"),
            ("avg_vram_mb", "平均显存 (MB)"),
            ("peak_vram_mb", "峰值显存 (MB)"),
            ("avg_ram_gb", "平均内存 (GB)"),
            ("peak_ram_gb", "峰值内存 (GB)"),
            ("avg_spi", "平均 SPI"),
            ("peak_spi", "峰值 SPI"),
            ("total_tiles", "总 Tile 数"),
            ("total_dropped", "丢弃 Tile 数"),
            ("total_saved", "保存图片数"),
            ("hardware_tier", "推荐硬件"),
        ]
        for i, (key, label_text) in enumerate(metrics):
            row, col = i // 4, (i % 4) * 2
            label = QLabel(label_text + ":")
            label.setStyleSheet("color: #888;")
            results_layout.addWidget(label, row, col)
            value = QLabel("—")
            value.setStyleSheet("font-weight: bold;")
            results_layout.addWidget(value, row, col + 1)
            self._result_labels[key] = value

        layout.addWidget(results_group)

        # --- Advice ---
        advice_group = QGroupBox("硬件建议")
        advice_layout = QVBoxLayout(advice_group)
        self._advice_text = QTextEdit()
        self._advice_text.setReadOnly(True)
        self._advice_text.setMaximumHeight(120)
        advice_layout.addWidget(self._advice_text)
        layout.addWidget(advice_group)

        # Keep live system metrics visible while the stress test is running.
        self._monitor_page = MonitorPage(compact=True)
        layout.addWidget(self._monitor_page, 1)

    def _start_benchmark(self):
        from benchmark.benchmark_runner import BenchmarkRunner, BenchmarkConfig
        from benchmark.input_source import SimulatedTileSource, SpeedMultiplierSource
        from benchmark.synthetic_engines import SyntheticModelEngine
        from runtime.unified_image_pool import UnifiedImagePool
        from gpu_scheduler.model_pool import ModelEnginePool
        from gpu_scheduler.scheduler import GPUInferenceScheduler
        from storage_v8.async_writer import AsyncDiskWriter
        from storage_v8.save_policy import SaveMode, SavePolicyManager

        multi = float(self._speed_multiplier.currentText().replace("x", ""))
        pool = UnifiedImagePool(memory_budget_mb=512)
        model_pool = ModelEnginePool(device_id=0)
        model_pool.register("yolo", SyntheticModelEngine("yolo", vram_mb=512))
        model_pool.register("patchcore", SyntheticModelEngine("patchcore", vram_mb=768))
        model_pool.register("classification", SyntheticModelEngine("classification", vram_mb=256))
        selected_combo = self._model_combo.currentText()
        if "yolo" in selected_combo:
            model_pool.load("yolo", "synthetic")
        if "patchcore" in selected_combo:
            model_pool.load("patchcore", "synthetic")
        model_pool.load("classification", "synthetic")
        scheduler = GPUInferenceScheduler(
            pool=pool,
            model_pool=model_pool,
            batch_size=self._batch_size.value(),
            max_wait_ms=10.0,
        )
        writer = AsyncDiskWriter(
            base_dir=os.path.join(os.getcwd(), "data", "benchmark"),
            policy=SavePolicyManager(SaveMode(self._save_mode.currentText())),
        )
        source = SpeedMultiplierSource(
            SimulatedTileSource(
                camera_count=self._camera_count.value(),
                line_speed_mpm=self._line_speed.value(),
            ),
            multiplier=multi,
        )

        config = BenchmarkConfig(
            camera_count=self._camera_count.value(),
            line_speed_mpm=self._line_speed.value(),
            model_combo=self._model_combo.currentText(),
            save_mode=self._save_mode.currentText(),
            batch_size=self._batch_size.value(),
            duration_sec=self._duration.value(),
            source_type=self._source_type.currentText(),
            speed_multiplier=multi,
        )

        self._runner = BenchmarkRunner(source, pool, scheduler, writer)
        self._running = True
        self._last_report = None
        self._last_error = ""

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._export_md_btn.setEnabled(False)
        self._export_json_btn.setEnabled(False)
        self._progress.setValue(0)
        self._status_label.setText("运行中...")
        self._status_label.setStyleSheet("color: #ff9800; padding: 4px;")

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_progress)
        self._poll_timer.start(500)

        def progress_cb(ratio, _snapshot):
            self._progress.setValue(int(ratio * 100))

        self._thread = Thread(
            target=lambda: self._run_benchmark(config, progress_cb),
            daemon=True,
        )
        self._thread.start()

    def _run_benchmark(self, config, progress_cb):
        try:
            self._last_report = self._runner.run(config, progress_callback=progress_cb)
        except Exception as e:
            self._last_error = str(e)
            self._last_report = None
        self._running = False

    def _stop_benchmark(self):
        if self._runner:
            self._runner.stop()
        self._running = False
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("已停止")
        self._status_label.setStyleSheet("color: #888; padding: 4px;")

    def _poll_progress(self):
        if self._running:
            return

        self._poll_timer.stop()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setValue(100)

        report = self._last_report
        if report is None:
            self._status_label.setText("压测未产生结果")
            self._status_label.setStyleSheet("color: #f44336; padding: 4px;")
            return

        self._status_label.setText("完成")
        self._status_label.setStyleSheet("color: #4caf50; padding: 4px;")
        self._export_md_btn.setEnabled(True)
        self._export_json_btn.setEnabled(True)

        self._display_report(report)

    def _display_report(self, report):
        r = report
        self._result_labels["avg_tiles_sec"].setText(f"{r.avg_tiles_per_sec:.1f}")
        self._result_labels["max_tiles_sec"].setText(f"{r.max_tiles_per_sec:.1f}")
        self._result_labels["avg_latency_ms"].setText(f"{r.avg_latency_ms:.2f}")
        self._result_labels["p95_latency_ms"].setText(f"{r.p95_latency_ms:.2f}")
        self._result_labels["p99_latency_ms"].setText(f"{r.p99_latency_ms:.2f}")
        self._result_labels["avg_cpu_pct"].setText(f"{r.avg_cpu_pct:.1f}")
        self._result_labels["peak_cpu_pct"].setText(f"{r.peak_cpu_pct:.1f}")
        self._result_labels["avg_gpu_pct"].setText(f"{r.avg_gpu_pct:.1f}")
        self._result_labels["peak_gpu_pct"].setText(f"{r.peak_gpu_pct:.1f}")
        self._result_labels["avg_vram_mb"].setText(f"{r.avg_vram_mb:.1f}")
        self._result_labels["peak_vram_mb"].setText(f"{r.peak_vram_mb:.1f}")
        self._result_labels["avg_ram_gb"].setText(f"{r.avg_ram_gb:.2f}")
        self._result_labels["peak_ram_gb"].setText(f"{r.peak_ram_gb:.2f}")
        self._result_labels["avg_spi"].setText(f"{r.avg_spi:.1f}")
        self._result_labels["peak_spi"].setText(f"{r.peak_spi:.1f}")
        self._result_labels["total_tiles"].setText(str(r.total_tiles))
        self._result_labels["total_dropped"].setText(str(r.total_dropped))
        self._result_labels["total_saved"].setText(str(r.total_saved))

        if r.hardware_advice:
            tier = r.hardware_advice.get("tier", r.hardware_advice.get("recommended_tier", "?"))
            self._result_labels["hardware_tier"].setText(str(tier))
            advice_lines = []
            if "summary" in r.hardware_advice:
                advice_lines.append(r.hardware_advice["summary"])
            notes = r.hardware_advice.get("notes", "")
            if notes:
                advice_lines.append(notes)
            advice_lines.append(f"SPI 范围: {r.avg_spi:.1f} ~ {r.peak_spi:.1f}")
            self._advice_text.setPlainText("\n".join(advice_lines))

    def _export_markdown(self):
        from benchmark.report_exporter import export_markdown

        if self._last_report is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Markdown 报告",
            f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            "Markdown (*.md)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(export_markdown(self._last_report))

    def _export_json(self):
        from benchmark.report_exporter import export_json

        if self._last_report is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 JSON 报告",
            f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON (*.json)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(export_json(self._last_report))

    def _refresh_text(self, lang: str = "") -> None:
        pass
