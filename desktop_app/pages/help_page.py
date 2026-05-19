"""Help page — system documentation and user guide."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser

from desktop_app.constants import APP_NAME, APP_VERSION, NAV_ITEMS
from desktop_app.i18n import tr, bind, I18nManager


# ── i18n key constants used in this page ──

_HELP_KEYS: dict[str, dict[str, str]] = {
    "help.title": {"zh": "帮助", "en": "Help"},
    "help.overview": {"zh": "系统概览", "en": "System Overview"},
    "help.modules": {"zh": "功能模块", "en": "Feature Modules"},
    "help.sampling": {"zh": "采样模式", "en": "Sampling Modes"},
    "help.model_lifecycle": {"zh": "模型生命周期", "en": "Model Lifecycle"},
    "help.shortcuts": {"zh": "键盘快捷键", "en": "Keyboard Shortcuts"},
    "help.roadmap": {"zh": "V7 路线图", "en": "V7 Roadmap"},
    "help.toc": {"zh": "目录", "en": "Table of Contents"},
}


# ── Module descriptions mapped from nav ids ──

_MODULE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "project_center": {
        "zh": "管理客户、项目、产品规格。创建和编辑检测项目的组织结构。",
        "en": "Manage customers, projects, and product specifications. Create and edit the organizational structure of inspection projects.",
    },
    "capture": {
        "zh": "采集会话管理、样本图像分类、数据集版本生成。",
        "en": "Capture session management, sample image classification, and dataset version generation.",
    },
    "training": {
        "zh": "训练配置、训练任务提交、模型版本管理（激活/回滚）。",
        "en": "Training configuration, job submission, and model version management (activate/rollback).",
    },
    "evaluation": {
        "zh": "模型推理测试、评估报告生成、多模型对比。",
        "en": "Model inference testing, evaluation report generation, and multi-model comparison.",
    },
    "production": {
        "zh": "多相机实时检测运行，支持多种采样策略，编码器位置追踪。",
        "en": "Multi-camera real-time inspection with multiple sampling strategies and encoder position tracking.",
    },
    "device_config": {
        "zh": "设备总览、相机配置、PLC 配置、编码器配置。",
        "en": "Device overview, camera configuration, PLC configuration, and encoder configuration.",
    },
    "reports": {
        "zh": "多格式报告导出（Markdown / HTML / PDF / CSV / JSON）。",
        "en": "Multi-format report export (Markdown / HTML / PDF / CSV / JSON).",
    },
    "log_center": {
        "zh": "6 类日志查看（应用/相机/推理/系统/错误/审计），支持级别过滤和搜索。",
        "en": "6-category log viewer (App/Camera/Inference/System/Error/Audit) with level filtering and search.",
    },
    "backup": {
        "zh": "配置备份创建、恢复、删除；支持数据库、配置文件、模型文件选择性备份。",
        "en": "Backup creation, restoration, and deletion; selective backup of database, configs, and model files.",
    },
    "settings": {
        "zh": "系统设置：语言切换、目录配置、系统健康检查。",
        "en": "System settings: language toggle, directory configuration, and system health check.",
    },
}


def _build_en_content() -> str:
    return _render_html("en")


def _build_zh_content() -> str:
    return _render_html("zh")


def _render_html(lang: str) -> str:
    la = lang  # shorthand

    def t(k: str) -> str:
        return _HELP_KEYS.get(k, {}).get(la, k)

    def tr_mod(nav_id: str) -> str:
        for item in NAV_ITEMS:
            if item["id"] == nav_id:
                return item.get("label", nav_id)
        return nav_id

    modules_html = ""
    for item in NAV_ITEMS:
        nid = item["id"]
        icon = item.get("icon", "")
        label = item.get("label", nid)
        desc = _MODULE_DESCRIPTIONS.get(nid, {}).get(la, "")
        modules_html += f"""
        <tr>
            <td style="white-space:nowrap;padding-right:16px;vertical-align:top;">
                <b>{icon} {label}</b>
            </td>
            <td style="padding-bottom:8px;">{desc}</td>
        </tr>"""

    sampling_table = """
        <tr><td style="white-space:nowrap;padding-right:16px;"><b>directory_watch</b></td>
            <td>{s_dirwatch}</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><b>by_time</b></td>
            <td>{s_bytime}</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><b>by_distance</b></td>
            <td>{s_bydist}</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><b>suspected_anomaly</b></td>
            <td>{s_susp}</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><b>manual</b></td>
            <td>{s_manual}</td></tr>
    """.format(
        s_dirwatch="目录监听，每一帧都处理" if la == "zh" else "Directory watch, process every frame",
        s_bytime="按固定时间间隔采集" if la == "zh" else "Capture at fixed time intervals",
        s_bydist="按固定距离间隔采集（需编码器）" if la == "zh" else "Capture at fixed distance intervals (requires encoder)",
        s_susp="异常检测触发（V7 路线图）" if la == "zh" else "Anomaly detection trigger (V7 roadmap)",
        s_manual="手动按钮抓图" if la == "zh" else "Manual capture via button click",
    )

    lifecycle_en = """
        created → training → completed → evaluated → verified → candidate
        → <span style="color:#4CAF50;"><b>active</b></span>
        → rolled_back → archived
    """
    lifecycle_zh = """
        created（已创建）→ training（训练中）→ completed（已完成）→ evaluated（已评估）
        → verified（已验证）→ candidate（候选）→ <span style="color:#4CAF50;"><b>active（在线）</b></span>
        → rolled_back（已回滚）→ archived（已归档）
    """
    lifecycle = lifecycle_zh if la == "zh" else lifecycle_en

    roadmap_en = """<ul>
        <li>HybridTrainer full implementation (YOLO + PatchCore composite training)</li>
        <li>PatchCore full training (anomalib integration + coreset construction)</li>
        <li>RS422 encoder real device integration</li>
        <li>Hikvision MVS / Basler Pylon industrial camera drivers</li>
        <li>Real-time PLC communication (Modbus TCP)</li>
        <li>Suspected anomaly sampling strategy</li>
        <li>GPU inference acceleration (CUDA / TensorRT)</li>
        <li>Web remote monitoring dashboard</li>
    </ul>"""
    roadmap_zh = """<ul>
        <li>HybridTrainer 完整实现（YOLO + PatchCore 复合训练）</li>
        <li>PatchCore 完整训练（anomalib 集成 + coreset 构建）</li>
        <li>RS422 编码器实机对接</li>
        <li>海康 MVS / Basler Pylon 工业相机实机驱动</li>
        <li>实时 PLC 通讯（Modbus TCP）</li>
        <li>疑似异常采样策略</li>
        <li>GPU 推理加速（CUDA / TensorRT）</li>
        <li>Web 远程监控面板</li>
    </ul>"""
    roadmap = roadmap_zh if la == "zh" else roadmap_en

    shortcuts = """
        <tr><td style="white-space:nowrap;padding-right:24px;"><kbd>Ctrl+B</kbd></td>
            <td>{sc_sidebar}</td></tr>
        <tr><td style="white-space:nowrap;padding-right:24px;"><kbd>Ctrl+L</kbd></td>
            <td>{sc_lang}</td></tr>
    """.format(
        sc_sidebar="切换侧边栏" if la == "zh" else "Toggle sidebar",
        sc_lang="切换语言 (zh ↔ en)" if la == "zh" else "Toggle language (zh ↔ en)",
    )

    overview_zh = f"""
        <p><b>{APP_NAME}</b> 是面向铜管（及其他金属材料）表面缺陷检测的工业视觉系统，
        基于 PySide6 桌面应用框架。</p>
        <p>当前版本: <b>{APP_VERSION}</b> — 现场试运行版 / 工程化交付版。</p>
        <p>支持项目管理、多相机实时采集、YOLO 训练推理、缺陷追溯、
        日志中心、配置备份恢复。</p>
    """
    overview_en = f"""
        <p><b>{APP_NAME}</b> is an industrial vision system for surface defect
        detection on copper tubes (and other metal materials), built on the
        PySide6 desktop application framework.</p>
        <p>Current version: <b>{APP_VERSION}</b> — Field trial / engineering delivery edition.</p>
        <p>Supports project management, multi-camera real-time acquisition, YOLO
        training & inference, defect tracing, log center, and configuration
        backup & restore.</p>
    """
    overview = overview_zh if la == "zh" else overview_en

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
    body {{
        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
        font-size: 14px; line-height: 1.7; color: #ddd;
        background-color: #1e1e2e; padding: 24px 32px; max-width: 860px;
    }}
    h1 {{ font-size: 22px; color: #fff; border-bottom: 2px solid #4A90D9; padding-bottom: 6px; margin-top: 32px; }}
    h2 {{ font-size: 17px; color: #9ECBFF; margin-top: 24px; }}
    p  {{ margin: 8px 0; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td {{ padding: 4px 0; vertical-align: top; }}
    kbd {{
        background: #333; color: #eee; border: 1px solid #555;
        border-radius: 3px; padding: 1px 6px; font-size: 12px; font-family: monospace;
    }}
    ul {{ margin: 4px 0; padding-left: 20px; }}
    li {{ margin: 3px 0; }}
    a  {{ color: #9ECBFF; }}
</style></head>
<body>

<h1>{t("help.overview")}</h1>
{overview}

<h1>{t("help.modules")}</h1>
<table>{modules_html}</table>

<h1>{t("help.sampling")}</h1>
<table>{sampling_table}</table>

<h1>{t("help.model_lifecycle")}</h1>
<p style="font-family:monospace;font-size:13px;">{lifecycle}</p>
<p>{'同一项目同时只有一个 active（在线）模型，激活新模型会自动下线旧模型。' if la == 'zh' else 'Only one active model per project at a time. Activating a new model automatically deactivates the previous one.'}</p>

<h1>{t("help.shortcuts")}</h1>
<table>{shortcuts}</table>

<h1>{t("help.roadmap")}</h1>
{roadmap}

<p style="color:#888;margin-top:40px;font-size:12px;">
{'数据库: SQLite 单文件 data/app.db | 测试: pytest tests/ -q' if la == 'zh' else 'Database: SQLite single-file data/app.db | Tests: pytest tests/ -q'}
</p>

</body></html>"""


class HelpPage(QWidget):
    """System help and documentation browser."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet("background: #1e1e2e; border: none;")
        lang = I18nManager.instance().language
        self._browser.setHtml(
            _build_zh_content() if lang == "zh" else _build_en_content()
        )
        layout.addWidget(self._browser)

    def _refresh_text(self, lang: str = "") -> None:
        self._browser.setHtml(
            _build_zh_content() if lang == "zh" else _build_en_content()
        )
