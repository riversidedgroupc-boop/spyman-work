"""Help page — system documentation and user guide."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser

from desktop_app.constants import APP_NAME, APP_VERSION, NAV_ITEMS
from desktop_app.i18n import tr, I18nManager
from desktop_app.theme_manager import ThemeManager


# ── Module descriptions displayed in the feature table ──

_USAGE_MODULES: dict[str, dict[str, str]] = {
    "workbench": {
        "zh": "项目状态总览与流程入口。按项目配置、设备配置、现场采集、样本复核、模型训练、联合检测、性能验证、报告交付 8 个步骤展示当前进度。",
        "en": "Project status overview and workflow entry. Shows the 8-step flow: project config, device setup, site capture, sample review, model training, hybrid detection, performance validation, and delivery.",
    },
    "device_setup": {
        "zh": "设备配置入口。相机工作台用于按规格生成 1-6 个相机槽位、扫描设备、绑定真实相机、设置参数和预览图像；产线通讯用于 PLC 与编码器联调。",
        "en": "Device setup entry. Camera Workbench creates 1-6 spec-based camera slots, scans devices, binds physical cameras, edits parameters, and previews images. Production Line Communication handles PLC and encoder checks.",
    },
    "site_capture": {
        "zh": "现场会话、实景运行、样本分类和数据集版本生成。未选择模型时可做调试采集和手动分类；需要检测或异常辅助时再选择模型。",
        "en": "Field Session, live run, sample classification, and dataset version generation. Without a selected model, it can still run setup capture and manual triage; detection or anomaly-assisted modes require model selection.",
    },
    "sample_review": {
        "zh": "样本复核入口。包含样本分类、边界框标注、现场复核工作区、历史样本库和数据集版本管理。",
        "en": "Sample review entry. Includes sample classification, bounding-box annotation, field review workspace, historical sample library, and dataset version management.",
    },
    "model_iteration": {
        "zh": "模型训练（YOLO 检测 / PatchCore 异常检测）、训练任务管理、模型版本管理（激活/回滚）、模型导出（ONNX / TensorRT）。",
        "en": "Model training (YOLO detection / PatchCore anomaly detection), training job management, model version management (activate/rollback), and model export (ONNX / TensorRT).",
    },
    "hybrid_runtime": {
        "zh": "联合检测运行、混合复检和缺陷追溯。支持 YOLO 检测、异常检测以及两者融合后的复核流程。",
        "en": "Hybrid detection runtime, hybrid retest, and defect trace. Supports YOLO detection, anomaly detection, and combined review flow.",
    },
    "performance": {
        "zh": "模型推理测试、评估报告生成（mAP 等）、多模型对比、性能压测与实时资源监控（CPU/GPU/显存/内存/磁盘）。",
        "en": "Model inference testing, evaluation reports (mAP etc.), model comparison, and performance benchmarking with live resource monitoring (CPU/GPU/VRAM/RAM/disk).",
    },
    "delivery": {
        "zh": "报告生成与导出（Markdown / HTML / PDF / CSV / JSON）、模型部署包导出。",
        "en": "Report generation & export (Markdown / HTML / PDF / CSV / JSON) and model deployment package export.",
    },
    "maintenance": {
        "zh": "日志中心（6 类日志：应用/相机/推理/系统/错误/审计）、配置备份恢复、系统设置（语言/主题切换）、帮助文档。",
        "en": "Log center (6 categories: app/camera/inference/system/error/audit), backup & restore, system settings (language/theme), and help documentation.",
    },
}


def _theme_css() -> str:
    """Return the HTML body CSS block using the current theme palette."""
    c = ThemeManager.current()
    return f"""
    body {{
        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
        font-size: 14px; line-height: 1.72; color: {c.TEXT_PRIMARY};
        background-color: {c.BG_MAIN}; padding: 22px 32px; max-width: 980px;
    }}
    h1 {{ font-size: 23px; color: {c.TEXT_PRIMARY}; border-bottom: 2px solid {c.PRIMARY}; padding-bottom: 6px; margin-top: 26px; }}
    h2 {{ font-size: 17px; color: {c.PRIMARY_LIGHT}; margin-top: 22px; }}
    ol, ul {{ padding-left: 22px; }}
    li {{ margin: 5px 0; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td {{ padding: 6px 0; vertical-align: top; }}
    .module-name {{ white-space: nowrap; padding-right: 18px; width: 190px; }}
    .qa-key {{ white-space: nowrap; padding-right: 18px; width: 160px; color: {c.TEXT_PRIMARY}; }}
    .note {{ color: {c.TEXT_SECONDARY}; font-size: 12px; margin-top: 26px; }}
    a {{ color: {c.PRIMARY_LIGHT}; }}
    .done {{ color: {c.SUCCESS}; }}
    .wip {{ color: {c.WARNING}; }}
"""


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

    # ── Titles ──
    overview_title = "系统概览" if is_zh else "System Overview"
    quick_start = "推荐流程" if is_zh else "Recommended Workflow"
    modules_title = "功能模块" if is_zh else "Feature Modules"
    camera_title = "相机工作台流程" if is_zh else "Camera Workbench Workflow"
    production_title = "实景运行与联合检测" if is_zh else "Live Detection & Hybrid Runtime"
    sampling_title = "采样模式" if is_zh else "Sampling Modes"
    lifecycle_title = "模型生命周期" if is_zh else "Model Lifecycle"
    settings_title = "系统设置" if is_zh else "System Settings"
    shortcuts_title = "键盘快捷键" if is_zh else "Keyboard Shortcuts"
    qa_title = "常见问题排查" if is_zh else "Troubleshooting"
    tips_title = "使用建议" if is_zh else "Operational Tips"
    roadmap_title = "待完成功能" if is_zh else "Upcoming Features"

    # ── Overview ──
    if is_zh:
        overview = (
            f"<p><b>{APP_NAME}</b> 是面向铜管（及其他金属材料）表面缺陷检测的工业视觉系统，"
            f"基于 PySide6 桌面应用框架，支持浅色/深色主题切换。</p>"
            f"<p>当前版本: <b>{APP_VERSION}</b> — 现场试运行版。</p>"
            f"<p>覆盖完整工作流：项目配置 → 相机工作台 → 现场会话 → 样本复核 → YOLO/PatchCore 训练 → "
            f"联合检测 → 性能验证 → 报告交付。</p>"
        )
    else:
        overview = (
            f"<p><b>{APP_NAME}</b> is an industrial vision system for surface defect "
            f"detection on copper tubes (and other metal materials), built on the "
            f"PySide6 desktop application framework with light/dark theme support.</p>"
            f"<p>Current version: <b>{APP_VERSION}</b> — Field trial edition.</p>"
            f"<p>Covers the full workflow: project config → Camera Workbench → Field Session → "
            f"sample review → YOLO/PatchCore training → hybrid detection → performance validation → delivery.</p>"
        )

    # ── Quick start steps ──
    if is_zh:
        quick_steps = [
            "在「项目工作台」确认当前客户、项目和产品规格；没有规格时先到「项目配置」创建规格。",
            "进入「设备配置 → 相机工作台」，系统按规格相机数量生成相机槽位；点击「扫描设备」后将真实相机绑定到 camera_01 至 camera_06。",
            "在每个相机的绑定弹窗中设置曝光、增益、触发模式、行频、包大小、缓存等参数，并用预览区确认图像。",
            "在「设备配置 → 产线通讯」检查 PLC 连接和编码器参数。",
            "在「现场采集」建立现场会话，导入或监听样本，完成 OK/NG/缺陷类别分类，生成数据集版本。",
            "在「模型训练」提交训练任务（YOLO 检测 / PatchCore 异常检测），训练完成后在「模型版本」中评估并激活模型。",
            "在「性能验证」做推理测试、批量评估（mAP）和多模型对比，确认模型可用。",
            "进入「联合检测」启动在线检测；调试采集可以不选择模型，检测和异常辅助模式需要选择对应模型。",
            "检测结束后到「报告交付」导出报告（Markdown/HTML/PDF/CSV/JSON）。",
            "升级、调参或现场交付前，在「系统维护 → 备份恢复」创建备份。",
        ]
    else:
        quick_steps = [
            "In Project Workbench, confirm the current customer, project, and product spec; if no spec exists, create it in Project Config.",
            "In Device Setup → Camera Workbench, the app creates camera slots from the spec camera count; click Scan Devices and bind physical cameras to camera_01 through camera_06.",
            "In each camera binding dialog, set exposure, gain, trigger mode, line rate, packet size, buffer count, and verify the image in Preview.",
            "In Device Setup → Production Line Communication, check PLC connection and encoder parameters.",
            "In Site Capture, create a Field Session, import or watch samples, classify OK/NG/defect categories, and generate dataset versions.",
            "In Model Training, submit training jobs (YOLO detection / PatchCore anomaly detection), then evaluate and activate the model in Model Versions.",
            "In Performance Validation, run inference tests, batch evaluation (mAP), and model comparison to confirm the model is ready.",
            "In Hybrid Detection, start online detection. Setup capture can run without a selected model; detection and anomaly-assisted modes require the corresponding model.",
            "After detection, export reports from Report Delivery (Markdown/HTML/PDF/CSV/JSON).",
            "Before upgrades, tuning, or field delivery, create a backup in Maintenance → Backup & Restore.",
        ]

    # ── Camera management steps ──
    if is_zh:
        camera_steps = [
            "顶部按钮区包含「扫描设备」和「全部连接」。先扫描，再批量连接或逐个连接。",
            "相机槽位固定展示为一列，槽位名称为 camera_01 至 camera_06；点击槽位后打开绑定与参数弹窗。",
            "绑定弹窗中先选真实设备，再设置角色（上方、左侧、右侧、备用），最后点击「确认绑定」。",
            "参数区包含曝光、增益、触发模式、触发源、像素格式、行频、宽度、块高、包大小、包间隔和缓存。",
            "预览区用于查看当前相机图像；诊断区显示连接状态、采集状态、行频、丢行、超时和最后错误。",
            "多相机现场必须优先按 SN 绑定，MAC 作为备选，IP 仅作辅助参考。",
            "连接失败时检查 SDK 状态、相机供电、网线、网口 IP、相机 IP 和日志中心的相机日志。",
        ]
        adapter_info = (
            "支持的相机适配器：<b>FolderWatcherCameraAdapter</b>（目录监听模式，无需额外安装）、"
            "<b>HikvisionMVSAdapter</b>（需安装海康 MVS SDK）、"
            "<b>BaslerPylonAdapter</b>（需安装 pypylon）。"
            "未安装对应 SDK 时适配器状态显示「SDK 未安装」。"
        )
    else:
        camera_steps = [
            "The top action row contains Scan Devices and Connect All. Scan first, then connect all cameras or connect them one by one.",
            "Camera slots are shown as one vertical list: camera_01 through camera_06. Click a slot to open the binding and parameter dialog.",
            "In the binding dialog, select the physical device, set the role (Top, Left, Right, Spare), then click Confirm Bind.",
            "Parameter controls include exposure, gain, trigger mode, trigger source, pixel format, line rate, width, block height, packet size, inter-packet delay, and buffer count.",
            "Preview shows the current camera image. Diagnostics shows connection state, acquisition state, line rate, dropped lines, timeouts, and last error.",
            "On multi-camera sites, always bind by SN first, MAC as fallback, and use IP only as auxiliary reference.",
            "If connection fails, check SDK status, camera power, network cable, NIC IP, camera IP, and camera logs in Log Center.",
        ]
        adapter_info = (
            "Supported camera adapters: <b>FolderWatcherCameraAdapter</b> (directory watch, no extra install), "
            "<b>HikvisionMVSAdapter</b> (requires MVS SDK), "
            "<b>BaslerPylonAdapter</b> (requires pypylon). "
            "When the SDK is not installed, the status shows 'SDK not installed'."
        )

    # ── Production / hybrid runtime steps ──
    if is_zh:
        production_steps = [
            "确认当前项目、规格和激活模型正确。",
            "选择运行模式：调试采集、基线采集、异常辅助、联合检测或稳定生产。",
            "选择采样模式：连续采集、按时间、按距离（需编码器）或手动触发。",
            "连接采集源后启动检测，观察实时画面和 OK/NG 统计、缺陷类型、置信度、编码器位置。",
            "如吞吐不足，查看「性能验证 → 性能压测」的实时性能区；如保存压力大，关注磁盘指标。",
            "检测结束后到「报告交付」导出报告，必要时同步导出 CSV/JSON 供追溯分析。",
        ]
    else:
        production_steps = [
            "Confirm the current project, spec, and active model are correct.",
            "Select runtime mode: Setup Capture, Baseline Capture, Anomaly-Assisted, Hybrid Detection, or Stable Production.",
            "Select sampling mode: Continuous, By Time, By Distance (requires encoder), or Manual Trigger.",
            "Connect the acquisition source and start detection. Monitor live frames, OK/NG stats, defect type, confidence, and encoder position.",
            "If throughput is insufficient, check the live metrics area in Performance → Benchmark; for disk pressure, focus on disk metrics.",
            "After detection, export reports from Report Delivery and include CSV/JSON for traceability when needed.",
        ]

    # ── Sampling modes table ──
    if is_zh:
        sampling_table = """
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>directory_watch</b></td>
                <td>连续采集：持续监听目录，每一帧都处理（默认模式）</td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>by_time</b></td>
                <td>按时间：按固定时间间隔采集，如每 0.5 秒抓一帧</td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>by_distance</b></td>
                <td>按距离：按编码器距离间隔采集，如每 0.1 米抓一帧</td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>manual</b></td>
                <td>手动触发：点击按钮抓图</td></tr>
        """
    else:
        sampling_table = """
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>directory_watch</b></td>
                <td>Continuous: watches the directory and processes every frame (default)</td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>by_time</b></td>
                <td>By Time: captures at fixed time intervals, for example every 0.5 s</td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>by_distance</b></td>
                <td>By Distance: captures at fixed encoder distance intervals, for example every 0.1 m</td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>manual</b></td>
                <td>Manual Trigger: captures one frame when the user clicks the button</td></tr>
        """

    # ── Model lifecycle ──
    c = ThemeManager.current()
    if is_zh:
        lifecycle = (
            f'已创建 → 训练中 → 已完成 → 已评估 → 已验证 → 候选 → '
            f'<span style="color:{c.SUCCESS};"><b>在线</b></span> → 已回滚 → 已归档'
        )
        lifecycle_note = "同一项目同时只有一个在线模型，激活新模型会自动下线旧模型。"
    else:
        lifecycle = (
            f'created → training → completed → evaluated → verified → candidate '
            f'→ <span style="color:{c.SUCCESS};"><b>active</b></span>'
            f'→ rolled_back → archived'
        )
        lifecycle_note = "Only one active model per project at a time. Activating a new model automatically deactivates the previous one."

    # ── System settings ──
    if is_zh:
        settings_items = """
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>语言</b></td>
                <td>中文和英文切换，快捷键 <kbd>Ctrl+L</kbd></td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>主题</b></td>
                <td>浅色（Fluent Design 默认）/ 深色 切换，持久化到本地配置</td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>健康检查</b></td>
                <td>数据库、磁盘空间、日志目录等系统健康状态检查</td></tr>
        """
    else:
        settings_items = """
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>Language</b></td>
                <td>Switch between Chinese and English, shortcut <kbd>Ctrl+L</kbd></td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>Theme</b></td>
                <td>Light (Fluent Design, default) / Dark mode, persisted to local config</td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><b>Health Check</b></td>
                <td>System health status check for database, disk space, and log directory</td></tr>
        """

    # ── QA ──
    if is_zh:
        qa_items = [
            ("看不到相机", "确认 MVS SDK 可加载，检查相机供电、网线、网口 IP 和相机 IP 是否同网段。"),
            ("相机绑定错乱", "重新扫描后按 SN 选择设备再绑定，不要按发现顺序判断相机编号。"),
            ("画面过暗或过亮", "在相机工作台的绑定弹窗中调整曝光和增益，预览确认后保存到当前规格。"),
            ("检测过程卡顿", "先看「性能压测」下方的 CPU/GPU/显存/内存/磁盘实时指标，再用压测复现实测压力。"),
            ("模型结果不稳定", "回到「性能验证」做批量评估，检查阈值、样本覆盖和当前激活模型版本。"),
            ("配置改坏了", "到「备份恢复」页选择最近可用备份恢复。恢复前确认备份内容和时间。"),
        ]
    else:
        qa_items = [
            ("No camera found", "Check MVS SDK loading, camera power, network cable, NIC IP, and whether camera IP is in the same subnet."),
            ("Wrong camera binding", "Scan again, select device by SN and bind explicitly. Do not infer Camera 1/2/3 by discovery order."),
            ("Image too dark/bright", "Adjust Exposure Time and Gain in Camera Management, preview, then save the parameter template."),
            ("Detection stutter", "Check live CPU/GPU/VRAM/RAM/disk metrics in Performance → Benchmark, then reproduce with a benchmark run."),
            ("Unstable model results", "Run batch evaluation in Performance Validation and check thresholds, sample coverage, and active model version."),
            ("Broken configuration", "Restore a recent backup from Backup & Restore after checking its timestamp and contents."),
        ]

    # ── Tips ──
    if is_zh:
        tips = [
            "每次换相机、换网口或换现场工位后，重新扫描并核对 SN/MAC。",
            "现场调参前先创建备份，调参后保存参数模板并记录客户、产品和相机槽位。",
            "检测只使用已评估并激活的模型，不建议直接拿训练完成的模型上线。",
            "日志中心按时间排查最高效：先找错误日志，再回看相机、推理和系统日志。",
        ]
    else:
        tips = [
            "After changing cameras, NICs, or stations, scan again and verify SN/MAC.",
            "Create a backup before field tuning; after tuning, save templates with customer, product, and camera slot context.",
            "Use only evaluated and activated models for production inspection.",
            "For diagnosis, filter Log Center by time first: start with errors, then camera, inference, and system logs.",
        ]

    # ── Roadmap ──
    if is_zh:
        roadmap = """
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="done">✓</span> Modbus TCP PLC 通讯</td>
            <td>已集成基础框架，支持 TCP Socket / Modbus TCP 连接测试</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="done">✓</span> 相机适配器</td>
            <td>MVS / Basler pylon 适配器已集成（需安装对应 SDK）</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="done">✓</span> ONNX / TensorRT 模型导出</td>
            <td>模型导出页支持 FP32/FP16/INT8 精度导出</td></tr>
            <tr><td style="white-space:nowrap;padding-right:16px;"><span class="done">✓</span> 相机工作台</td>
            <td>相机槽位、绑定弹窗、参数配置、预览和诊断已合并到单一工作台</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="wip">◐</span> RS422 编码器实机串口通讯</td>
            <td>框架已就位，实机串口对接待完成</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="wip">◐</span> PatchCore 完整训练流程</td>
            <td>训练框架已集成，anomalib coreset 构建待完善</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="wip">◐</span> HybridTrainer 全自动复合训练</td>
            <td>YOLO + PatchCore 联合训练流程待自动化</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;">○ 疑似异常采样策略</td>
            <td>后端已有 SamplingController 支持，待集成到生产 UI</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;">○ Web 远程监控面板</td>
            <td>规划中</td></tr>
        """
    else:
        roadmap = """
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="done">✓</span> Modbus TCP PLC communication</td>
            <td>Basic framework integrated: TCP Socket / Modbus TCP connection test</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="done">✓</span> Camera adapters</td>
            <td>MVS / Basler pylon adapters integrated (requires SDK installation)</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="done">✓</span> ONNX / TensorRT export</td>
            <td>Model export page supports FP32/FP16/INT8 precision</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="done">✓</span> Camera Workbench</td>
            <td>Camera slots, binding dialog, parameter control, preview, and diagnostics are merged into one workspace</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="wip">◐</span> RS422 encoder serial communication</td>
            <td>Framework ready, real serial port integration pending</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="wip">◐</span> Full PatchCore training pipeline</td>
            <td>Training framework integrated, anomalib coreset construction to be completed</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;"><span class="wip">◐</span> HybridTrainer automation</td>
            <td>YOLO + PatchCore joint training workflow to be automated</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;">○ Suspected anomaly sampling</td>
            <td>Backend SamplingController supports it; UI integration pending</td></tr>
        <tr><td style="white-space:nowrap;padding-right:16px;">○ Web remote monitoring dashboard</td>
            <td>Planned</td></tr>
        """

    # ── Shortcuts ──
    if is_zh:
        shortcuts = """
            <tr><td style="white-space:nowrap;padding-right:24px;"><kbd>Ctrl+B</kbd></td>
                <td>切换侧边栏展开/折叠</td></tr>
            <tr><td style="white-space:nowrap;padding-right:24px;"><kbd>Ctrl+L</kbd></td>
                <td>切换语言 (中文 ↔ English)</td></tr>
        """
    else:
        shortcuts = """
            <tr><td style="white-space:nowrap;padding-right:24px;"><kbd>Ctrl+B</kbd></td>
                <td>Toggle sidebar</td></tr>
            <tr><td style="white-space:nowrap;padding-right:24px;"><kbd>Ctrl+L</kbd></td>
                <td>Toggle language (中文 ↔ English)</td></tr>
        """

    def ordered(items: list[str]) -> str:
        return "".join(f"<li>{item}</li>" for item in items)

    qa_html = "".join(
        f"<tr><td class='qa-key'><b>{k}</b></td><td>{v}</td></tr>" for k, v in qa_items
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{_theme_css()}</style></head>
<body>

<h1>{overview_title}</h1>
{overview}

<h1>{quick_start}</h1>
<ol>{ordered(quick_steps)}</ol>

<h1>{modules_title}</h1>
<table>{_module_table(lang)}</table>

<h1>{camera_title}</h1>
<ol>{ordered(camera_steps)}</ol>
<p>{adapter_info}</p>

<h1>{production_title}</h1>
<ol>{ordered(production_steps)}</ol>

<h1>{sampling_title}</h1>
<table>{sampling_table}</table>

<h1>{lifecycle_title}</h1>
<p style="font-family:monospace;font-size:13px;">{lifecycle}</p>
<p>{lifecycle_note}</p>

<h1>{settings_title}</h1>
<table>{settings_items}</table>

<h1>{shortcuts_title}</h1>
<table>{shortcuts}</table>

<h1>{qa_title}</h1>
<table>{qa_html}</table>

<h1>{tips_title}</h1>
<ul>{ordered(tips)}</ul>

<h1>{roadmap_title}</h1>
<table>{roadmap}</table>

<p class="note">{"提示：左侧导航最后一个入口始终是「帮助」。现场排查时如果不确定先看哪里，优先查看「性能验证 → 性能压测」的实时性能区和「系统维护 → 日志中心」。数据库文件位于 workspace app_data/app.db（旧版 data/app.db 存在时自动回退）。" if is_zh else "Note: Help is always the final navigation entry. For field diagnosis, start with the live metrics area in Performance → Benchmark and Log Center when unsure. Database: workspace app_data/app.db (falls back to legacy data/app.db if present)."}</p>

</body></html>"""


def _build_zh_content() -> str:
    return _render_usage_html("zh")


def _build_en_content() -> str:
    return _render_usage_html("en")


class HelpPage(QWidget):
    """System help and documentation browser."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        c = ThemeManager.current()
        self._browser.setStyleSheet(f"background: {c.BG_MAIN}; border: none;")
        lang = I18nManager.instance().language
        self._browser.setHtml(_build_zh_content() if lang == "zh" else _build_en_content())
        layout.addWidget(self._browser)

    def _refresh_text(self, lang: str = "") -> None:
        self._browser.setHtml(_build_zh_content() if lang == "zh" else _build_en_content())

    def _on_theme_changed(self) -> None:
        """Re-render HTML with updated theme palette."""
        c = ThemeManager.current()
        self._browser.setStyleSheet(f"background: {c.BG_MAIN}; border: none;")
        lang = I18nManager.instance().language
        self._browser.setHtml(_build_zh_content() if lang == "zh" else _build_en_content())
