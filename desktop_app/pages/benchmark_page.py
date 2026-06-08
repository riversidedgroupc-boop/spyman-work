"""Benchmark page — stress test configuration, run control, results and export."""

from __future__ import annotations

import json
import os
from datetime import datetime
from threading import Thread

from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QLabel,
    QProgressBar,
    QTextEdit,
    QGridLayout,
    QFileDialog,
)

from core.dataset_version import list_dataset_versions
from core.model_version import list_model_versions
from desktop_app.i18n import tr, I18nManager, _STRINGS
from desktop_app.pages.monitor_page import MonitorPage
from desktop_app.app_context import AppContext
from desktop_app.theme_manager import ThemeManager


_MODEL_COMBO_OPTIONS = [
    ("benchmark.model_yolo", "yolo"),
    ("benchmark.model_patchcore", "patchcore"),
    ("benchmark.model_hybrid", "yolo+patchcore"),
]

_SAVE_MODE_OPTIONS = [
    ("benchmark.save_ng_only", "save_ng_only"),
    ("benchmark.save_all", "save_all"),
    ("benchmark.save_ng_ok_sampling", "save_ng_ok_sampling"),
    ("benchmark.result_only", "result_only"),
]

_SOURCE_TYPE_OPTIONS = [
    ("benchmark.source_simulated", "simulated"),
    ("benchmark.source_real_camera", "real_camera"),
    ("benchmark.source_history_replay", "history_replay"),
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


class BenchmarkPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._runner = None
        self._running = False
        self._last_report = None
        self._run_dir: str = ""
        self._build_ui()
        self._ctx.project_changed.connect(self._refresh_version_selectors)
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Config ---
        config_group = QGroupBox(tr("benchmark.config"))
        form = QFormLayout(config_group)

        self._camera_count = QSpinBox()
        self._camera_count.setRange(1, 16)
        self._camera_count.setValue(3)
        form.addRow(tr("benchmark.camera_count"), self._camera_count)

        self._line_speed = QDoubleSpinBox()
        self._line_speed.setRange(10, 500)
        self._line_speed.setValue(80.0)
        self._line_speed.setSuffix(
            " m/min" if I18nManager.instance().language != "zh" else " 米/分钟"
        )
        form.addRow(tr("benchmark.line_speed"), self._line_speed)

        self._model_combo = QComboBox()
        _replace_combo_options(self._model_combo, _MODEL_COMBO_OPTIONS)
        form.addRow(tr("benchmark.model_combo"), self._model_combo)

        self._save_mode = QComboBox()
        _replace_combo_options(self._save_mode, _SAVE_MODE_OPTIONS)
        form.addRow(tr("benchmark.save_mode"), self._save_mode)

        self._batch_size = QSpinBox()
        self._batch_size.setRange(1, 32)
        self._batch_size.setValue(4)
        form.addRow(tr("benchmark.batch_size"), self._batch_size)

        self._duration = QSpinBox()
        self._duration.setRange(10, 7200)
        self._duration.setValue(1800)
        self._duration.setSuffix(" s" if I18nManager.instance().language != "zh" else " 秒")
        form.addRow(tr("benchmark.duration"), self._duration)

        self._speed_multiplier = QComboBox()
        self._speed_multiplier.addItems(["0.5x", "1x", "2x", "4x", "8x"])
        self._speed_multiplier.setCurrentIndex(1)
        form.addRow(tr("benchmark.speed_multiplier"), self._speed_multiplier)

        self._source_type = QComboBox()
        _replace_combo_options(self._source_type, _SOURCE_TYPE_OPTIONS)
        form.addRow(tr("benchmark.source_type"), self._source_type)

        self._dataset_version_combo = QComboBox()
        self._dataset_version_combo.addItem("(auto)", "")
        form.addRow(tr("benchmark.dataset_version"), self._dataset_version_combo)

        self._model_version_combo = QComboBox()
        self._model_version_combo.addItem("(auto)", "")
        form.addRow(tr("benchmark.model_version"), self._model_version_combo)

        self._backend_combo = QComboBox()
        self._backend_combo.addItems(["auto", "pytorch", "onnx", "tensorrt"])
        form.addRow(tr("benchmark.backend"), self._backend_combo)

        layout.addWidget(config_group)

        # --- Control buttons ---
        btn_layout = QHBoxLayout()
        self._start_btn = QPushButton(tr("benchmark.start"))
        self._start_btn.clicked.connect(self._start_benchmark)
        btn_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton(tr("benchmark.stop"))
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_benchmark)
        btn_layout.addWidget(self._stop_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        btn_layout.addWidget(self._progress, 1)

        # Export buttons
        self._export_md_btn = QPushButton(tr("benchmark.export_md"))
        self._export_md_btn.setEnabled(False)
        self._export_md_btn.clicked.connect(self._export_markdown)
        btn_layout.addWidget(self._export_md_btn)

        self._export_json_btn = QPushButton(tr("benchmark.export_json"))
        self._export_json_btn.setEnabled(False)
        self._export_json_btn.clicked.connect(self._export_json)
        btn_layout.addWidget(self._export_json_btn)

        layout.addLayout(btn_layout)

        # --- Status ---
        self._status_label = QLabel(tr("benchmark.ready"))
        self._status_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; padding: 4px;")
        layout.addWidget(self._status_label)

        # --- Results ---
        results_group = QGroupBox(tr("benchmark.results"))
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
            label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY};")
            results_layout.addWidget(label, row, col)
            value = QLabel("—")
            value.setStyleSheet("font-weight: bold;")
            results_layout.addWidget(value, row, col + 1)
            self._result_labels[key] = value

        layout.addWidget(results_group)

        # --- Advice ---
        advice_group = QGroupBox(tr("benchmark.hardware_advice"))
        advice_layout = QVBoxLayout(advice_group)
        self._advice_text = QTextEdit()
        self._advice_text.setReadOnly(True)
        self._advice_text.setMaximumHeight(120)
        advice_layout.addWidget(self._advice_text)
        layout.addWidget(advice_group)

        # Keep live system metrics visible while the stress test is running.
        self._monitor_page = MonitorPage(compact=True)
        layout.addWidget(self._monitor_page, 1)

    def _refresh_version_selectors(self, project_id: str = "") -> None:
        """Reload dataset/model version combos when project changes."""
        pid = project_id or self._ctx.current_project_id

        # Dataset versions
        self._dataset_version_combo.clear()
        self._dataset_version_combo.addItem(tr("benchmark.auto_select"), "")
        if pid:
            for dv in list_dataset_versions(project_id=pid):
                label = f"{dv.version_name} ({dv.source_type}, {dv.image_count} imgs)"
                self._dataset_version_combo.addItem(label, dv.version_id)

        # Model versions
        self._model_version_combo.clear()
        self._model_version_combo.addItem(tr("benchmark.auto_select"), "")
        if pid:
            for mv in list_model_versions(project_id=pid):
                label = f"{mv.model_name} ({mv.model_type}, {mv.status})"
                self._model_version_combo.addItem(label, mv.model_id)

    def _start_benchmark(self):
        from benchmark.benchmark_runner import BenchmarkRunner, BenchmarkConfig
        from benchmark.input_source import SimulatedTileSource, SpeedMultiplierSource
        from benchmark.synthetic_engines import SyntheticModelEngine
        from runtime.unified_image_pool import UnifiedImagePool
        from gpu_scheduler.model_pool import ModelEnginePool
        from gpu_scheduler.scheduler import GPUInferenceScheduler
        from storage_v8.async_writer import AsyncDiskWriter
        from storage_v8.save_policy import SaveMode, SavePolicyManager
        from core.workspace_paths import get_project_dir, ensure_dir

        multi = float(self._speed_multiplier.currentText().replace("x", ""))
        pool = UnifiedImagePool(memory_budget_mb=512)
        model_pool = ModelEnginePool(device_id=0)
        model_pool.register("yolo", SyntheticModelEngine("yolo", vram_mb=512))
        model_pool.register("patchcore", SyntheticModelEngine("patchcore", vram_mb=768))
        model_pool.register("classification", SyntheticModelEngine("classification", vram_mb=256))
        selected_combo = self._model_combo.currentData() or "yolo"
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

        # Resolve benchmark output path via workspace
        pid = self._ctx.current_project_id
        if pid:
            from core.project import get_project

            proj = get_project(pid)
            customer_id = proj.customer_id if proj else "unknown"
            bench_base = ensure_dir(os.path.join(get_project_dir(customer_id, pid), "benchmarks"))
        else:
            from core.workspace_paths import get_benchmark_root

            bench_base = ensure_dir(get_benchmark_root())
        run_dir = ensure_dir(
            os.path.join(
                bench_base,
                f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            )
        )
        writer = AsyncDiskWriter(
            base_dir=run_dir,
            policy=SavePolicyManager(SaveMode(self._save_mode.currentData() or "save_ng_only")),
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
            model_combo=self._model_combo.currentData() or "yolo",
            save_mode=self._save_mode.currentData() or "save_ng_only",
            batch_size=self._batch_size.value(),
            duration_sec=self._duration.value(),
            source_type=self._source_type.currentData() or "simulated",
            speed_multiplier=multi,
            backend=self._backend_combo.currentText(),
            project_id=self._ctx.current_project_id or "",
            dataset_version_id=self._dataset_version_combo.currentData() or "",
            model_version_id=self._model_version_combo.currentData() or "",
        )

        # Save benchmark config metadata alongside run output
        self._run_dir = run_dir
        import dataclasses

        with open(os.path.join(run_dir, "benchmark_config.json"), "w", encoding="utf-8") as f:
            json.dump(dataclasses.asdict(config), f, ensure_ascii=False, indent=2)

        self._runner = BenchmarkRunner(source, pool, scheduler, writer)
        self._running = True
        self._last_report = None
        self._last_error = ""

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._export_md_btn.setEnabled(False)
        self._export_json_btn.setEnabled(False)
        self._progress.setValue(0)
        self._status_label.setText(tr("benchmark.running"))
        self._status_label.setStyleSheet(f"color: {ThemeManager.current().WARNING}; padding: 4px;")

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
        self._status_label.setText(tr("benchmark.stopped"))
        self._status_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; padding: 4px;")

    def _poll_progress(self):
        if self._running:
            return

        self._poll_timer.stop()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setValue(100)

        report = self._last_report
        if report is None:
            self._status_label.setText(tr("benchmark.no_result"))
            self._status_label.setStyleSheet(f"color: {ThemeManager.current().ERROR}; padding: 4px;")
            return

        self._status_label.setText(tr("benchmark.completed"))
        self._status_label.setStyleSheet(f"color: {ThemeManager.current().SUCCESS}; padding: 4px;")
        self._export_md_btn.setEnabled(True)
        self._export_json_btn.setEnabled(True)

        # Auto-save report JSON alongside run data
        if self._run_dir:
            from benchmark.report_exporter import export_json

            try:
                with open(
                    os.path.join(self._run_dir, "benchmark_report.json"), "w", encoding="utf-8"
                ) as f:
                    f.write(export_json(report))
            except OSError:
                pass

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
            self,
            tr("benchmark.export_md"),
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
            self,
            tr("benchmark.export_json"),
            f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON (*.json)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(export_json(self._last_report))

    def _refresh_text(self, lang: str = "") -> None:
        # Find and update group box titles
        for child in self.findChildren(QGroupBox):
            current = child.title()
            for key in [
                "benchmark.config",
                "benchmark.results",
                "benchmark.hardware_advice",
            ]:
                if current == tr(key) or any(
                    current == _STRINGS.get(key, {}).get(lang_key, "") for lang_key in ("zh", "en")
                ):
                    child.setTitle(tr(key))
                    break
        # Buttons
        self._start_btn.setText(tr("benchmark.start"))
        self._stop_btn.setText(tr("benchmark.stop"))
        self._export_md_btn.setText(tr("benchmark.export_md"))
        self._export_json_btn.setText(tr("benchmark.export_json"))
        _replace_combo_options(self._model_combo, _MODEL_COMBO_OPTIONS)
        _replace_combo_options(self._save_mode, _SAVE_MODE_OPTIONS)
        _replace_combo_options(self._source_type, _SOURCE_TYPE_OPTIONS)
        # Status
        current_status = self._status_label.text()
        for key in [
            "benchmark.ready",
            "benchmark.running",
            "benchmark.stopped",
            "benchmark.completed",
            "benchmark.no_result",
        ]:
            if current_status == tr(key) or any(
                current_status == _STRINGS.get(key, {}).get(lang_key, "")
                for lang_key in ("zh", "en")
            ):
                self._status_label.setText(tr(key))
                break
        # Refresh dataset/model version selector placeholders
        if hasattr(self, "_dataset_version_combo"):
            if self._dataset_version_combo.count() > 0:
                self._dataset_version_combo.setItemText(0, tr("benchmark.auto_select"))
        if hasattr(self, "_model_version_combo"):
            if self._model_version_combo.count() > 0:
                self._model_version_combo.setItemText(0, tr("benchmark.auto_select"))
        # Update suffix for speed/duration (these are set per-build, simple re-apply)
        self._line_speed.setSuffix(" m/min" if lang != "zh" else " 米/分钟")
        self._duration.setSuffix(" s" if lang != "zh" else " 秒")

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._status_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; padding: 4px;")
        # STATIC: all values use TEXT_SECONDARY, iterate _result_labels
        for v in self._result_labels.values():
            v.setStyleSheet(f"color: {c.TEXT_SECONDARY};")

