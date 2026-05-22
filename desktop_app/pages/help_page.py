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
    return _render_usage_html("en")


def _build_zh_content() -> str:
    return _render_usage_html("zh")


_USAGE_MODULES: dict[str, dict[str, str]] = {
    "project_center": {
        "zh": "先建立客户、项目和产品规格。后续采集、训练、验证、生产运行都会按当前项目归档。",
        "en": "Create customers, projects, and product specifications first. Capture, training, evaluation, and production data are grouped by the active project.",
    },
    "capture": {
        "zh": "用于现场采图、样本分类和生成数据集版本。先建采集会话，再导入或监听相机图片，最后进入样本分类。",
        "en": "Use this for field image capture, sample classification, and dataset versioning. Create a capture session, import or watch images, then classify samples.",
    },
    "training": {
        "zh": "配置训练参数、提交训练任务、管理模型版本。训练完成后先评估，再把可上线模型激活。",
        "en": "Configure training, submit jobs, and manage model versions. Evaluate a finished model before activating it for production.",
    },
    "evaluation": {
        "zh": "对模型做单图推理、批量验证和模型对比。用于确认误检、漏检、置信度阈值和上线风险。",
        "en": "Run single-image inference, batch validation, and model comparison. Use it to check false positives, misses, confidence thresholds, and release risk.",
    },
    "production": {
        "zh": "生产检测入口。选择采样模式，连接相机/目录源，启动采集与推理，观察 OK/NG、位置和运行状态。",
        "en": "Production inspection entry point. Select a sampling mode, connect camera or folder sources, start acquisition and inference, and monitor OK/NG results.",
    },
    "device_config": {
        "zh": "配置设备、相机、PLC、编码器和相机管理。相机管理页用于扫描、绑定、连接、参数下发、预览和诊断。",
        "en": "Configure devices, cameras, PLC, encoders, and camera management. Camera Management scans, binds, connects, applies parameters, previews, and diagnoses cameras.",
    },
    "benchmark": {
        "zh": "压测采集、缓存、GPU 调度、磁盘写入等链路，并在同一页面实时显示 CPU、GPU、显存、内存、磁盘和 SPI。",
        "en": "Stress-test acquisition, buffering, GPU scheduling, and disk writing while showing live CPU, GPU, VRAM, memory, disk, and SPI metrics on the same page.",
    },
    "reports": {
        "zh": "导出训练、验证、检测和生产报告。需要交付或复盘时，从这里生成 Markdown/HTML/PDF/CSV/JSON。",
        "en": "Export training, evaluation, inspection, and production reports in Markdown, HTML, PDF, CSV, or JSON formats.",
    },
    "log_center": {
        "zh": "查看应用、相机、推理、系统、错误和审计日志。排查异常时先按时间和日志级别过滤。",
        "en": "View app, camera, inference, system, error, and audit logs. Filter by time and level when diagnosing issues.",
    },
    "backup": {
        "zh": "备份和恢复数据库、配置和模型文件。现场调参或升级前建议先创建备份。",
        "en": "Back up and restore database, config, and model files. Create a backup before field tuning or upgrades.",
    },
    "settings": {
        "zh": "切换语言、检查目录配置和系统健康状态。路径错误、依赖缺失时先看这里。",
        "en": "Switch language, check directory settings, and inspect system health. Start here for path or dependency issues.",
    },
    "help": {
        "zh": "查看当前使用说明、推荐操作流程和常见问题。",
        "en": "Read the current user guide, recommended workflow, and common troubleshooting notes.",
    },
}


def _module_table(lang: str) -> str:
    rows = []
    for item in NAV_ITEMS:
        nav_id = item["id"]
        label = tr(f"nav.{nav_id}")
        desc = _USAGE_MODULES.get(nav_id, {}).get(lang, "")
        rows.append(
            f"""
            <tr>
                <td class="module-name"><b>{item.get("icon", "")} {label}</b></td>
                <td>{desc}</td>
            </tr>"""
        )
    return "\n".join(rows)


def _render_usage_html(lang: str) -> str:
    is_zh = lang == "zh"
    title = "使用方法" if is_zh else "How to Use"
    quick_start = "推荐流程" if is_zh else "Recommended Workflow"
    modules = "功能入口" if is_zh else "Feature Entries"
    camera_title = "相机管理基础流程" if is_zh else "Camera Management Workflow"
    production_title = "生产运行流程" if is_zh else "Production Workflow"
    qa_title = "常见问题排查" if is_zh else "Troubleshooting"
    tips_title = "使用建议" if is_zh else "Operational Tips"

    if is_zh:
        quick_steps = [
            "在“项目中心”创建或选择客户、项目、产品规格。",
            "在“设备配置 -> 相机管理”扫描相机，按 SN/MAC 绑定到 camera_01 到 camera_06，并保存绑定。",
            "在相机管理页连接相机，设置曝光、增益、触发、行频、包大小、包间隔、缓存等参数，预览确认画面正常。",
            "在“现场数据”建立采集会话，导入样本或监听目录，完成 OK/NG/缺陷类别分类。",
            "在“训练中心”训练模型，并在“验证中心”做推理、评估和模型对比。",
            "确认模型可用后激活模型，再进入“生产运行”启动在线检测。",
            "生产过程中使用“压测中心”的实时性能区和“日志中心”观察资源占用、相机状态、推理异常和写盘异常。",
            "升级、调参或现场交付前，在“备份恢复”创建备份。",
        ]
        camera_steps = [
            "点击“扫描设备”，确认列表中能看到型号、SN、IP、MAC。",
            "选择一个逻辑槽位，例如 camera_01，再在设备下拉框中选择真实相机。",
            "选择物理角色，例如上方、左侧、右侧或备用，然后点击“绑定并连接”。",
            "不要依赖枚举顺序。多相机现场必须用 SN 优先绑定，MAC 作为备选，IP 只作为辅助信息。",
            "调好参数后点击“保存绑定”和“保存模板”，软件重启后可按绑定关系恢复。",
            "点击“开始预览”检查灰度图、曝光、增益、行频和最后一帧时间。",
            "连接失败时先看 SDK 状态、相机供电、网线、网口 IP、相机 IP 和日志中心的相机日志。",
        ]
        production_steps = [
            "确认当前项目和激活模型正确。",
            "选择采样模式：目录监听、按时间、按距离、疑似异常或手动抓图。",
            "连接采集源后启动生产运行，观察 OK/NG、缺陷类型、置信度和编码器位置。",
            "如果吞吐不足，先看“压测中心”下方的实时性能区；如果保存压力大，重点看磁盘指标。",
            "生产结束后到“报告中心”导出报告，必要时同步导出 CSV/JSON 供追溯分析。",
        ]
        qa_items = [
            ("看不到相机", "先确认 MVS SDK 可加载，再检查相机供电、网线、网口 IP 和相机 IP 是否同网段。"),
            ("相机绑定错乱", "重新扫描后按 SN 选择设备再绑定，不要按发现顺序判断 Camera 1/2/3。"),
            ("画面过暗或过亮", "在相机管理页调整 Exposure Time 和 Gain，预览确认后保存参数模板。"),
            ("生产运行卡顿", "先看压测中心下方的 CPU/GPU/显存/内存/磁盘实时指标，再用压测复现实测压力。"),
            ("模型结果不稳定", "回到验证中心做批量评估，检查阈值、样本覆盖和当前激活模型版本。"),
            ("配置改坏", "到备份恢复页选择最近可用备份恢复。恢复前确认备份内容和时间。"),
        ]
        tips = [
            "每次换相机、换网口或换现场工位后，都重新扫描并核对 SN/MAC。",
            "现场调参前先创建备份，调参后保存参数模板并记录客户、产品和相机槽位。",
            "生产检测只使用已评估并激活的模型，不建议直接拿训练完成模型上线。",
            "日志中心按时间排查最有效：先找错误日志，再回看相机、推理和系统日志。",
        ]
    else:
        quick_steps = [
            "Create or select the customer, project, and product specification in Project Center.",
            "Open Device Config -> Camera Management, scan cameras, bind SN/MAC to camera_01 through camera_06, and save bindings.",
            "Connect cameras, set exposure, gain, trigger, line rate, packet size, inter-packet delay, and buffer count, then preview images.",
            "Create a capture session in Field Data, import or watch samples, and classify OK/NG/defect categories.",
            "Train models in Training Center, then evaluate and compare them in Validation Center.",
            "Activate the validated model and start online inspection from Production Run.",
            "During production, use the live metrics area in Benchmark Center and Log Center to track resources, camera status, inference errors, and disk errors.",
            "Before upgrades, tuning, or field delivery, create a backup in Backup & Restore.",
        ]
        camera_steps = [
            "Click Scan Devices and verify model, SN, IP, and MAC in the device list.",
            "Select a logical slot such as camera_01, then select the physical camera from the device dropdown.",
            "Select a physical role such as top, left, right, or spare, then click Bind & Connect.",
            "Do not rely on enumeration order. Multi-camera sites must bind by SN first, MAC second, and use IP only as auxiliary information.",
            "After tuning, save the binding and parameter template so the setup can be restored after restart.",
            "Start Preview to check grayscale image quality, exposure, gain, line rate, and last frame time.",
            "If connection fails, check SDK status, power, cable, NIC IP, camera IP, and camera logs.",
        ]
        production_steps = [
            "Confirm the active project and active model.",
            "Select a sampling mode: directory watch, by time, by distance, suspected anomaly, or manual capture.",
            "Connect the acquisition source and start production. Monitor OK/NG, defect type, confidence, and encoder position.",
            "If throughput is insufficient, check the live metrics area at the bottom of Benchmark Center; for disk pressure, focus on disk metrics.",
            "After production, export reports from Report Center and include CSV/JSON when traceability analysis is needed.",
        ]
        qa_items = [
            ("No camera found", "Check MVS SDK loading, power, cable, NIC IP, and whether camera IP is in the same subnet."),
            ("Wrong camera binding", "Scan again, select the device by SN, and bind it explicitly. Do not infer Camera 1/2/3 by discovery order."),
            ("Image too dark or bright", "Adjust Exposure Time and Gain in Camera Management, preview, then save the parameter template."),
            ("Production stutter", "Check live CPU/GPU/VRAM/memory/disk metrics at the bottom of Benchmark Center, then reproduce pressure with a benchmark run."),
            ("Unstable model result", "Run batch evaluation in Validation Center and check thresholds, sample coverage, and active model version."),
            ("Broken configuration", "Restore a recent backup from Backup & Restore after checking its timestamp and contents."),
        ]
        tips = [
            "After changing cameras, NICs, or stations, scan again and verify SN/MAC.",
            "Create a backup before field tuning; after tuning, save templates with customer, product, and camera slot context.",
            "Use only evaluated and activated models for production inspection.",
            "For diagnosis, filter Log Center by time first, then inspect camera, inference, and system logs.",
        ]

    def ordered(items: list[str]) -> str:
        return "".join(f"<li>{item}</li>" for item in items)

    qa_html = "".join(f"<tr><td class='qa-key'><b>{k}</b></td><td>{v}</td></tr>" for k, v in qa_items)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
    body {{
        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
        font-size: 14px; line-height: 1.72; color: #ddd;
        background-color: #1e1e2e; padding: 22px 32px; max-width: 980px;
    }}
    h1 {{ font-size: 23px; color: #fff; border-bottom: 2px solid #4A90D9; padding-bottom: 6px; margin-top: 26px; }}
    h2 {{ font-size: 17px; color: #9ECBFF; margin-top: 22px; }}
    ol, ul {{ padding-left: 22px; }}
    li {{ margin: 5px 0; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td {{ padding: 6px 0; vertical-align: top; }}
    .module-name {{ white-space: nowrap; padding-right: 18px; width: 190px; }}
    .qa-key {{ white-space: nowrap; padding-right: 18px; width: 160px; color: #fff; }}
    .note {{ color: #B0B0B0; font-size: 12px; margin-top: 26px; }}
</style></head>
<body>
<h1>{title}</h1>
        <p>{'本页是当前版本的操作说明，重点覆盖从项目建立、相机绑定、样本采集、模型训练到生产检测的完整使用路径。' if is_zh else 'This page describes the current operating workflow from project setup, camera binding, sample capture, model training, to production inspection.'}</p>

<h1>{quick_start}</h1>
<ol>{ordered(quick_steps)}</ol>

<h1>{camera_title}</h1>
<ol>{ordered(camera_steps)}</ol>

<h1>{production_title}</h1>
<ol>{ordered(production_steps)}</ol>

<h1>{modules}</h1>
<table>{_module_table(lang)}</table>

<h1>{qa_title}</h1>
<table>{qa_html}</table>

<h1>{tips_title}</h1>
<ul>{ordered(tips)}</ul>

<p class="note">{'提示：左侧导航最后一个入口始终是“帮助”。如果现场排查时不确定先看哪里，优先查看“压测中心”的实时性能区和“日志中心”。' if is_zh else 'Note: Help is always the final navigation entry. For field diagnosis, start with the live metrics area in Benchmark Center and Log Center when unsure.'}</p>
</body></html>"""


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
