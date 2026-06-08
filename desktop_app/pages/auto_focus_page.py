# ruff: noqa: E402
"""Auto Focus page — 换型自动对焦, single-page widget for the CX-vision desktop app."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from desktop_app.i18n import I18nManager
from desktop_app.theme_manager import ThemeManager
from desktop_app.workers.autofocus_worker import AutofocusWorker
from line_scan_af.autofocus.focus_unit import FocusUnit
from line_scan_af.autofocus.roi_manager import ROIManager
from line_scan_af.autofocus.tube_roi_model import TubeROIModel
from line_scan_af.config.config_loader import (
    AutofocusConfig,
    CameraStageBinding,
    StageDriverConfig,
    load_autofocus_config,
    load_camera_stage_binding,
    load_stage_driver_config,
)
from line_scan_af.controllers.camera_controller_base import CameraControllerBase
from line_scan_af.controllers.mock_line_scan_camera import MockLineScanCamera
from line_scan_af.controllers.mock_stage_controller import MockStageController
from line_scan_af.controllers.stage_controller_base import StageControllerBase
from line_scan_af.controllers.stage_factory import create_stage
from line_scan_af.ui.roi_overlay_widget import draw_roi_overlay

logger = logging.getLogger(__name__)

_PRODUCTS = [
    {"name": "CopperTube_6mm", "diameter_mm": 6.0, "material": "copper"},
    {"name": "CopperTube_8mm", "diameter_mm": 8.0, "material": "copper"},
    {"name": "CopperTube_10mm", "diameter_mm": 10.0, "material": "copper"},
    {"name": "CopperTube_12mm", "diameter_mm": 12.0, "material": "copper"},
    {"name": "SteelTube_8mm", "diameter_mm": 8.0, "material": "steel"},
]

# Color-coded DOF status
DOF_COLORS: dict[str, tuple[str, str]] = {
    "PASS": ("#DCFCE7", "#15803D"),
    "WARNING": ("#FEF3C7", "#B45309"),
    "FAIL": ("#FEE2E2", "#B91C1C"),
    "SUCCESS": ("#DCFCE7", "#15803D"),
    "FAILED": ("#FEE2E2", "#B91C1C"),
}


class _FocusCurveCanvas(FigureCanvasQTAgg):
    """Matplotlib canvas for the focus sharpness curve."""

    def __init__(self, parent=None) -> None:
        self._fig = Figure(figsize=(5, 2.5), dpi=100)
        self._ax = self._fig.add_subplot(111)
        self._fig.tight_layout(pad=0.5)
        super().__init__(self._fig)
        self.setParent(parent)
        self._ax.set_xlabel("Z (mm)")
        self._ax.set_ylabel("Score")
        self._ax.set_title("Focus Curve")
        self._line = None
        self._best_marker = None
        self._fig.tight_layout(pad=0.8)

    def update_curve(self, zs: list[float], scores: list[float], best_z: float | None = None) -> None:
        self._ax.clear()
        self._ax.set_xlabel("Z (mm)")
        self._ax.set_ylabel("Score")

        if zs and scores:
            self._ax.plot(zs, scores, "b.-", markersize=4, linewidth=1.5)

            if best_z is not None and zs:
                idx = min(range(len(zs)), key=lambda i: abs(zs[i] - best_z))
                self._ax.plot(zs[idx], scores[idx], "r*", markersize=10)

            self._ax.set_title("Focus Curve")

        self._fig.tight_layout(pad=0.8)
        self.draw()


class AutoFocusPage(QWidget):
    """Full autofocus control page — single QWidget, no tabs."""

    data_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: AutofocusWorker | None = None
        self._units: list[FocusUnit] = []
        self._results: dict[str, dict] = {}
        self._curve_zs: dict[str, list[float]] = {}
        self._curve_scores: dict[str, list[float]] = {}
        self._current_image: np.ndarray | None = None
        self._current_rois: dict[str, tuple] = {}
        self._config: dict = {}
        self._binding: CameraStageBinding | None = None
        self._driver_cfg: StageDriverConfig | None = None
        self._last_run_success = False

        self._build_ui()
        self._load_configs()
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    # ---- UI Construction ----

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # ── Title row ──
        title_row = QHBoxLayout()
        self._title = QLabel("换型自动对焦")
        self._title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_row.addWidget(self._title)
        title_row.addStretch()

        self._mode_label = QLabel("Mock 模式")
        palette = ThemeManager.current()
        self._mode_label.setStyleSheet(f"color: {palette.TEXT_SECONDARY};")
        title_row.addWidget(self._mode_label)
        layout.addLayout(title_row)

        # ── Control bar ──
        control = QGroupBox()
        ctrl_layout = QHBoxLayout(control)
        ctrl_layout.setContentsMargins(10, 8, 10, 8)
        ctrl_layout.setSpacing(10)

        product_label = QLabel("产品规格:")
        ctrl_layout.addWidget(product_label)
        self._product_cb = QComboBox()
        self._product_cb.addItems([p["name"] for p in _PRODUCTS])
        ctrl_layout.addWidget(self._product_cb)

        ctrl_layout.addStretch()

        self._run_btn = QPushButton("▶ 三相机顺序对焦")
        self._run_btn.setMinimumHeight(32)
        self._run_btn.clicked.connect(self._start_autofocus)
        ctrl_layout.addWidget(self._run_btn)

        self._stop_btn = QPushButton("⏹ 停止")
        self._stop_btn.setMinimumHeight(32)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._cancel)
        ctrl_layout.addWidget(self._stop_btn)

        self._estop_btn = QPushButton("🛑 急停")
        self._estop_btn.setMinimumHeight(32)
        self._estop_btn.setObjectName("dangerBtn")
        self._estop_btn.setEnabled(False)
        self._estop_btn.clicked.connect(self._emergency_stop)
        ctrl_layout.addWidget(self._estop_btn)

        self._save_btn = QPushButton("💾 保存配方")
        self._save_btn.setMinimumHeight(32)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_recipe)
        ctrl_layout.addWidget(self._save_btn)

        layout.addWidget(control)

        # ── Progress bar ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Main content: left (status) + right (image + curve) ──
        main_row = QHBoxLayout()
        main_row.setSpacing(10)

        # Left: camera status cards
        status_panel = QGroupBox("相机/滑轨状态")
        status_layout = QVBoxLayout(status_panel)
        status_layout.setSpacing(6)

        self._cam_cards: dict[str, dict[str, QLabel]] = {}
        for cam_id in ["CAM1", "CAM2", "CAM3"]:
            card = QGroupBox()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 6, 8, 6)
            card_layout.setSpacing(2)

            name_label = QLabel(cam_id)
            name_label.setStyleSheet(f"font-weight: bold; font-size: 13px;")
            card_layout.addWidget(name_label)

            status_label = QLabel("待机")
            card_layout.addWidget(status_label)

            detail_label = QLabel("")
            palette_c = ThemeManager.current()
            detail_label.setStyleSheet(f"font-size: 11px; color: {palette_c.TEXT_SECONDARY};")
            card_layout.addWidget(detail_label)

            status_layout.addWidget(card)
            self._cam_cards[cam_id] = {
                "name": name_label,
                "status": status_label,
                "detail": detail_label,
            }

        status_layout.addStretch()
        main_row.addWidget(status_panel, 1)

        # Right: image + curve
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        image_group = QGroupBox("实时图像与 ROI")
        img_layout = QVBoxLayout(image_group)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumHeight(180)
        self._image_label.setStyleSheet("background-color: #1A1A1A; border-radius: 4px;")
        self._image_label.setText("等待采图...")
        img_layout.addWidget(self._image_label)
        right_panel.addWidget(image_group, 2)

        curve_group = QGroupBox("对焦曲线")
        curve_layout = QVBoxLayout(curve_group)
        self._curve_canvas = _FocusCurveCanvas()
        curve_layout.addWidget(self._curve_canvas)
        right_panel.addWidget(curve_group, 3)

        main_row.addLayout(right_panel, 3)
        layout.addLayout(main_row, 1)

        # ── Results table ──
        result_group = QGroupBox("对焦结果")
        result_layout = QVBoxLayout(result_group)
        self._result_table = QTableWidget(0, 8)
        self._result_table.setHorizontalHeaderLabels(
            ["Camera", "Status", "Best Z (mm)", "Center", "Left", "Right", "DOF", "Error"]
        )
        self._result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._result_table.setMaximumHeight(120)
        result_layout.addWidget(self._result_table)
        layout.addWidget(result_group)

        # ── Log area ──
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(500)
        self._log.setMinimumHeight(100)
        pal = ThemeManager.current()
        self._log.setStyleSheet(
            f"background-color: {pal.BG_MAIN}; color: {pal.TEXT_PRIMARY};"
            f"font-family: 'Consolas', 'Courier New', monospace; font-size: 11px;"
        )
        log_layout.addWidget(self._log)
        layout.addWidget(log_group)

    # ---- Config ----

    def _load_configs(self) -> None:
        try:
            af_cfg = load_autofocus_config()
            self._config = af_cfg.model_dump()
            self._binding = load_camera_stage_binding()
            self._driver_cfg = load_stage_driver_config()
            self._add_log("配置加载完成 — Mock 模式")
        except Exception as e:
            self._add_log(f"配置加载失败: {e}")

    def _abort_startup(self, message: str) -> None:
        logger.error(message)
        self._add_log(f"Autofocus startup aborted: {message}")
        for unit in self._units:
            try:
                unit.stage_controller.disconnect()
            except Exception:
                logger.warning("Failed to disconnect stage during startup abort", exc_info=True)
            try:
                unit.camera_controller.disconnect()
            except Exception:
                logger.warning("Failed to disconnect camera during startup abort", exc_info=True)
        self._units.clear()
        QMessageBox.critical(self, "Autofocus startup failed", message)

    # ---- AF lifecycle ----

    def _start_autofocus(self) -> None:
        product = _PRODUCTS[self._product_cb.currentIndex()]
        self._results.clear()
        self._last_run_success = False
        self._save_btn.setEnabled(False)
        self._clear_curve()
        self._result_table.setRowCount(0)
        self._add_log(f"启动自动对焦: {product['name']} (⌀{product['diameter_mm']}mm)")

        # Build focus units
        motion = self._driver_cfg.default_motion
        self._units.clear()

        driver_type = self._driver_cfg.stage_driver_type
        driver_config: dict = getattr(self._driver_cfg, driver_type, {})

        for unit_cfg in self._binding.focus_units:
            # ---- Stage via factory ----
            try:
                stage = create_stage(
                    unit_cfg.stage_id,
                    driver_type,
                    driver_config,
                    motion,
                )
            except Exception:
                logger.exception("create_stage failed for %s", unit_cfg.stage_id)
                if driver_type != "mock":
                    self._abort_startup(
                        f"Stage {unit_cfg.stage_id} creation failed for driver '{driver_type}'."
                    )
                    return
                stage = MockStageController(
                    stage_id=unit_cfg.stage_id,
                    z_min_mm=motion.get("z_min_mm", 0.0),
                    z_max_mm=motion.get("z_max_mm", 30.0),
                )
            try:
                if not stage.connect():
                    stage.disconnect()
                    self._abort_startup(f"Stage {unit_cfg.stage_id} connect returned False.")
                    return
            except Exception as e:
                logger.exception("stage %s connect failed", unit_cfg.stage_id)
                try:
                    stage.disconnect()
                except Exception:
                    logger.warning("stage %s disconnect failed", unit_cfg.stage_id, exc_info=True)
                self._abort_startup(f"Stage {unit_cfg.stage_id} connect failed: {e}")
                return
            try:
                if not stage.home():
                    stage.disconnect()
                    self._abort_startup(f"Stage {unit_cfg.stage_id} home returned False.")
                    return
            except Exception as e:
                logger.exception("stage %s home failed", unit_cfg.stage_id)
                try:
                    stage.disconnect()
                except Exception:
                    logger.warning("stage %s disconnect failed", unit_cfg.stage_id, exc_info=True)
                self._abort_startup(f"Stage {unit_cfg.stage_id} home failed: {e}")
                return

            # ---- Camera ----
            if driver_type == "mock":
                camera: CameraControllerBase = MockLineScanCamera(
                    camera_id=unit_cfg.camera_id,
                    best_focus_z=12.35,
                )
            else:
                try:
                    from line_scan_af.controllers.line_scan_camera_controller import (
                        LineScanCameraController,
                    )

                    camera = LineScanCameraController(
                        camera_id=unit_cfg.camera_id,
                        camera_config=driver_config,
                    )
                except Exception:
                    logger.exception("LineScanCameraController failed for %s", unit_cfg.camera_id)
                    stage.disconnect()
                    self._abort_startup(
                        f"Camera {unit_cfg.camera_id} creation failed for driver '{driver_type}'."
                    )
                    return
            try:
                if not camera.connect():
                    stage.disconnect()
                    self._abort_startup(f"Camera {unit_cfg.camera_id} connect returned False.")
                    return
                camera.lock_exposure_gain()
                camera.set_focus_capture_mode()
            except Exception as e:
                logger.exception("camera %s setup failed", unit_cfg.camera_id)
                try:
                    camera.disconnect()
                except Exception:
                    logger.warning("camera %s disconnect failed", unit_cfg.camera_id, exc_info=True)
                stage.disconnect()
                self._abort_startup(f"Camera {unit_cfg.camera_id} setup failed: {e}")
                return

            roi_model = TubeROIModel(tube_diameter_mm=product["diameter_mm"])
            roi_mgr = ROIManager.from_model(roi_model, unit_cfg.camera_id)

            unit = FocusUnit(
                camera_id=unit_cfg.camera_id,
                stage_id=unit_cfg.stage_id,
                light_id=unit_cfg.light_id,
                enabled=unit_cfg.enabled,
                stage_controller=stage,
                camera_controller=camera,
                roi_manager=roi_mgr,
            )
            self._units.append(unit)

        self._add_log(f"硬件驱动类型: {driver_type}  |  focus_units={len(self._units)}")

        # Create worker
        self._worker = AutofocusWorker(
            focus_units=self._units,
            config=self._config,
            binding=self._binding,
            driver_cfg=self._driver_cfg,
            product_name=product["name"],
        )
        self._worker.score_computed.connect(self._on_score_computed)
        self._worker.camera_done.connect(self._on_camera_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.message.connect(self._add_log)
        self._worker.error.connect(self._on_error)
        self._worker.curve_updated.connect(self._on_curve_updated)
        self._worker.finished.connect(self._on_finished)
        self._worker.progress.connect(self._on_progress)

        self._set_running(True)
        self._progress.setVisible(True)
        self._worker.start()

    def _cancel(self) -> None:
        self._add_log("用户请求停止...")
        if self._worker:
            self._worker.cancel()

    def _emergency_stop(self) -> None:
        self._add_log("🛑 急停触发!")
        if self._worker:
            self._worker.cancel()
        for unit in self._units:
            if unit.stage_controller:
                unit.stage_controller.emergency_stop()

    def _save_recipe(self) -> None:
        if not self._results:
            QMessageBox.information(self, "提示", "没有对焦结果可保存")
            return
        if not self._last_run_success or not all(
            result.get("status") == "SUCCESS" for result in self._results.values()
        ):
            QMessageBox.warning(
                self,
                "Cannot save",
                "Only a fully successful autofocus run can be saved to the product recipe.",
            )
            return
        product = _PRODUCTS[self._product_cb.currentIndex()]
        from line_scan_af.product.product_recipe_focus_extension import ProductRecipeFocusExtension
        ext = ProductRecipeFocusExtension()
        ext.save_focus_results(
            product["name"],
            {"run_id": datetime.now().strftime("run_%Y%m%d_%H%M%S"), "results": self._results},
            product["diameter_mm"],
        )
        self._add_log(f"已保存到产品配方: {product['name']}")
        QMessageBox.information(self, "保存成功", f"对焦结果已保存到 {product['name']} 配方")

    # ---- Signal handlers ----

    def _on_score_computed(self, cam_id: str, z_mm: float, score: float) -> None:
        self._add_log(f"[{cam_id}] Z={z_mm:.3f} score={score:.1f}")
        # Update mock camera image for current camera
        for unit in self._units:
            if unit.camera_id == cam_id and isinstance(unit.camera_controller, MockLineScanCamera):
                unit.camera_controller.set_z_position(z_mm)
                img = unit.camera_controller.capture_by_rows(512)
                self._show_image(cam_id, img, unit.roi_manager)

    def _on_curve_updated(self, zs: list[float], scores: list[float]) -> None:
        if zs and scores:
            best_z = zs[scores.index(max(scores))]
            self._curve_canvas.update_curve(zs, scores, best_z)

    def _on_camera_done(self, cam_id: str, result: dict) -> None:
        self._results[cam_id] = result
        self._refresh_result_table()
        self._update_cam_card(cam_id, result)

    def _on_all_done(self, final_result: dict) -> None:
        self._last_run_success = bool(final_result.get("success"))
        if final_result.get("success"):
            self._add_log("✅ 三相机自动对焦全部完成")
        else:
            self._add_log(f"⚠ 部分对焦失败: {final_result.get('results', {})}")

    def _on_error(self, msg: str) -> None:
        self._add_log(f"❌ 错误: {msg}")

    def _on_finished(self) -> None:
        self._set_running(False)
        self._progress.setVisible(False)
        self._save_btn.setEnabled(
            self._last_run_success
            and bool(self._results)
            and all(result.get("status") == "SUCCESS" for result in self._results.values())
        )

    def _on_progress(self, current: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(current)

    # ---- Helpers ----

    def _set_running(self, running: bool) -> None:
        self._run_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._estop_btn.setEnabled(running)

    def _add_log(self, msg: str) -> None:
        now = datetime.now().strftime("[%H:%M:%S]")
        self._log.appendPlainText(f"{now} {msg}")

    def _show_image(self, cam_id: str, img: np.ndarray, roi_mgr) -> None:
        if img is None or img.size == 0:
            return
        rois = {
            "center": roi_mgr.get_center_roi(),
            "left": roi_mgr.get_left_roi(),
            "right": roi_mgr.get_right_roi(),
        }
        try:
            overlay = draw_roi_overlay(img, **rois)
        except Exception:
            overlay = img.copy()
            if len(overlay.shape) == 2:
                overlay = np.stack([overlay] * 3, axis=-1)

        # draw_roi_overlay returns BGR, convert to RGB for QImage
        if len(overlay.shape) == 3 and overlay.shape[2] == 3:
            overlay_rgb = overlay[..., ::-1].copy()  # BGR → RGB + copy for contiguous memory
        elif len(overlay.shape) == 2:
            overlay_rgb = np.stack([overlay] * 3, axis=-1).copy()
        else:
            overlay_rgb = overlay.copy()

        h, w = overlay_rgb.shape[:2]
        bytes_per_line = w * 3
        qimg = QImage(overlay_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaledToWidth(550, Qt.TransformationMode.SmoothTransformation)
        self._image_label.setPixmap(pix)

    def _update_cam_card(self, cam_id: str, result: dict) -> None:
        cards = self._cam_cards.get(cam_id)
        if not cards:
            return
        status = result.get("status", "?")
        if status == "SUCCESS":
            cards["status"].setText("✅ 完成")
            cards["detail"].setText(
                f"Best Z={result.get('best_z_mm', 0):.3f} mm  "
                f"Center={result.get('center_score', 0):.0f}  "
                f"DOF={result.get('dof_check', '?')}"
            )
        else:
            cards["status"].setText("❌ 失败")
            cards["detail"].setText(result.get("error", "Unknown error"))

    def _refresh_result_table(self) -> None:
        self._result_table.setRowCount(len(self._results))
        for i, (cam_id, r) in enumerate(self._results.items()):
            items = [
                cam_id,
                r.get("status", "?"),
                f"{r.get('best_z_mm', 0):.3f}" if r.get("best_z_mm") else "-",
                f"{r.get('center_score', 0):.0f}" if r.get("center_score") else "-",
                f"{r.get('left_score', 0):.0f}" if r.get("left_score") else "-",
                f"{r.get('right_score', 0):.0f}" if r.get("right_score") else "-",
                r.get("dof_check", "-"),
                r.get("error", "-"),
            ]
            for j, text in enumerate(items):
                self._result_table.setItem(i, j, QTableWidgetItem(text))

    def _clear_curve(self) -> None:
        self._curve_canvas.update_curve([], [])

    # ---- i18n & theme ----

    def _refresh_text(self, lang: str = "") -> None:
        self._title.setText("换型自动对焦")

    def _on_theme_changed(self) -> None:
        pal = ThemeManager.current()
        self._log.setStyleSheet(
            f"background-color: {pal.BG_MAIN}; color: {pal.TEXT_PRIMARY};"
            f"font-family: 'Consolas', 'Courier New', monospace; font-size: 11px;"
        )
