"""
Copper Tube Surface Defect Model Evaluation & Fusion Verification Tool.

Usage:
    streamlit run app.py
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Optional

import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config_loader import ConfigLoader
from src.utils.file_utils import collect_images, ensure_dir
from src.utils.image_utils import get_image_size, load_image_rgb
from src.utils.logger import setup_logger
from src.utils.timer import BatchTimer

from src.dataset.annotation_parser import parse_yolo_annotation, find_label_file
from src.dataset.dataset_loader import DatasetLoader
from src.dataset.label_schema import (
    CLASS_ID_MAP, OK_CLASSES, NG_CLASSES, ACCEPTABLE_MICRO_CLASSES,
    BORDERLINE_CLASS, MAJOR_DEFECT_CLASSES,
    is_ok, is_ng, get_label_group,
)

from src.fusion.decision_types import (
    FinalDecision, FusionStrategy, FusionDecision,
    UnifiedPrediction, ImageRecord,
)
from src.fusion.rule_engine import RuleEngine
from src.fusion.fusion_strategies import (
    get_strategy_name, get_strategy_description, list_strategies,
)

from src.inference.yolo_runner import YoloRunner
from src.inference.patchcore_runner import PatchCoreRunner
from src.inference.efficientad_runner import EfficientADRunner
from src.inference.fastflow_runner import FastFlowRunner
from src.inference.opencv_runner import OpenCVRunner

from src.metrics.industrial_metrics import (
    compute_industrial_metrics, compute_strategy_comparison,
)
from src.metrics.detection_metrics import confusion_matrix_data
from src.metrics.confusion_analysis import analyze_misclassifications, group_by_error_type

from src.visualization.result_viewer import create_result_visualization
from src.visualization.charts import (
    create_confusion_matrix_chart, create_metrics_bar_chart,
    create_strategy_comparison_chart,
)

from src.postprocess.candidate_builder import build_defect_candidates

from src.reports.excel_report import ExcelReport

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="铜管缺陷评测工具",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
DEFAULTS = {
    "config_loader": None,
    "dataset_loader": None,
    "records": [],
    "yolo_runner": None,
    "patchcore_runner": None,
    "efficientad_runner": None,
    "fastflow_runner": None,
    "opencv_runner": None,
    "rule_engine": None,
    "models_loaded": False,
    "inference_run": False,
    "batch_timer": BatchTimer(),
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def init_config() -> ConfigLoader:
    if st.session_state.config_loader is None:
        st.session_state.config_loader = ConfigLoader(
            Path(__file__).parent / "configs"
        )
    return st.session_state.config_loader


def _pixel_size_from_config() -> tuple[float, float]:
    """Read pixel size from dataset config, falling back to 0.01 mm/px."""
    try:
        dataset_cfg = init_config().load("dataset")
        pixel_cfg = dataset_cfg.get("pixel_size_mm", {})
        return float(pixel_cfg.get("x", 0.01)), float(pixel_cfg.get("y", 0.01))
    except Exception:
        return 0.01, 0.01


def build_candidates_for_image(
    image_path: str | Path,
    yolo_result: UnifiedPrediction | None = None,
    patchcore_result: UnifiedPrediction | None = None,
    efficientad_result: UnifiedPrediction | None = None,
    fastflow_result: UnifiedPrediction | None = None,
    opencv_result: UnifiedPrediction | None = None,
):
    """Build feature-enriched candidates for rule-based fusion."""
    try:
        width, height = get_image_size(image_path)
    except Exception:
        width, height = 640, 640

    return build_defect_candidates(
        yolo_result=yolo_result,
        patchcore_result=patchcore_result,
        efficientad_result=efficientad_result,
        fastflow_result=fastflow_result,
        opencv_result=opencv_result,
        image_width=width,
        image_height=height,
        pixel_size_mm=_pixel_size_from_config(),
    )

def load_all_runners(models_cfg: dict) -> dict:
    """Load all enabled model runners. Returns dict of runner_name -> runner."""
    runners: dict[str, object] = {}

    yolo_cfg = models_cfg.get("yolo", {})
    if yolo_cfg.get("enabled", False):
        try:
            runner = YoloRunner(yolo_cfg)
            runner.load_model()
            runners["yolo"] = runner
            st.session_state.yolo_runner = runner
        except Exception as e:
            st.warning(f"YOLO 加载失败: {e}")

    patchcore_cfg = models_cfg.get("patchcore", {})
    if patchcore_cfg.get("enabled", False):
        try:
            runner = PatchCoreRunner(patchcore_cfg)
            runner.load_model()
            runners["patchcore"] = runner
            st.session_state.patchcore_runner = runner
        except Exception as e:
            st.warning(f"PatchCore 加载失败: {e}")

    efficientad_cfg = models_cfg.get("efficientad", {})
    if efficientad_cfg.get("enabled", False):
        try:
            runner = EfficientADRunner(efficientad_cfg)
            runner.load_model()
            runners["efficientad"] = runner
            st.session_state.efficientad_runner = runner
        except Exception as e:
            st.warning(f"EfficientAD 加载失败: {e}")

    fastflow_cfg = models_cfg.get("fastflow", {})
    if fastflow_cfg.get("enabled", False):
        try:
            runner = FastFlowRunner(fastflow_cfg)
            runner.load_model()
            runners["fastflow"] = runner
            st.session_state.fastflow_runner = runner
        except Exception as e:
            st.warning(f"FastFlow 加载失败: {e}")

    opencv_cfg = models_cfg.get("opencv", {})
    if opencv_cfg.get("enabled", False):
        try:
            runner = OpenCVRunner(opencv_cfg)
            runner.load_model()
            runners["opencv"] = runner
            st.session_state.opencv_runner = runner
        except Exception as e:
            st.warning(f"OpenCV 加载失败: {e}")

    return runners


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("🔍 铜管缺陷评测工具")

# --- Config paths ---
st.sidebar.header("📁 数据路径")

image_dir = st.sidebar.text_input(
    "图片目录",
    value="data/images",
    key="sidebar_image_dir",
)
label_dir = st.sidebar.text_input(
    "标注目录",
    value="data/labels",
    key="sidebar_label_dir",
)
split_file = st.sidebar.text_input(
    "数据集划分文件 (可选)",
    value="",
    key="sidebar_split_file",
)

st.sidebar.divider()

# --- Model switches ---
st.sidebar.header("🤖 模型设置")

enable_yolo = st.sidebar.checkbox("启用 YOLO", value=True)
yolo_model_path = st.sidebar.text_input(
    "YOLO 模型路径",
    value="models/yolo/best.pt",
    disabled=not enable_yolo,
)
yolo_conf = st.sidebar.slider(
    "YOLO conf 阈值", 0.1, 1.0, 0.6, 0.05,
    disabled=not enable_yolo,
)

enable_patchcore = st.sidebar.checkbox("启用 PatchCore", value=False)
patchcore_mode = st.sidebar.selectbox(
    "PatchCore 模式",
    ["mock", "import", "real"],
    disabled=not enable_patchcore,
)
patchcore_result_file = st.sidebar.text_input(
    "PatchCore 结果文件",
    value="outputs/cache/patchcore_results.csv",
    disabled=not enable_patchcore,
)

enable_efficientad = st.sidebar.checkbox("启用 EfficientAD", value=False)
efficientad_mode = st.sidebar.selectbox(
    "EfficientAD 模式",
    ["mock", "import", "real"],
    disabled=not enable_efficientad,
)

enable_fastflow = st.sidebar.checkbox("启用 FastFlow", value=False)
fastflow_mode = st.sidebar.selectbox(
    "FastFlow 模式",
    ["mock", "import", "real"],
    disabled=not enable_fastflow,
)

enable_opencv = st.sidebar.checkbox("启用 OpenCV 规则检测", value=True)

st.sidebar.divider()

# --- Fusion strategy ---
st.sidebar.header("🔗 融合策略")

strategies_list = list_strategies()
strategy_options = {s["name"]: s["id"] for s in strategies_list}
selected_strategy_name = st.sidebar.selectbox(
    "融合策略",
    list(strategy_options.keys()),
    index=4,  # Default: Rule Based
)
selected_strategy = strategy_options[selected_strategy_name]

st.sidebar.divider()

# --- Thresholds ---
st.sidebar.header("📏 阈值参数")

anomaly_threshold = st.sidebar.slider(
    "Anomaly score 阈值", 0.0, 1.0, 0.65, 0.05,
)

min_defect_area = st.sidebar.number_input(
    "最小缺陷面积 (px)", value=8, min_value=1, max_value=1000,
)

acceptable_micro_area = st.sidebar.number_input(
    "最大可接受微缺陷面积 (px)", value=30, min_value=1, max_value=500,
)

acceptable_scratch_len = st.sidebar.number_input(
    "最大可接受划伤长度 (mm)", value=0.5, min_value=0.1, max_value=10.0, step=0.1,
)

ng_scratch_len = st.sidebar.number_input(
    "NG 划伤长度阈值 (mm)", value=2.0, min_value=0.5, max_value=50.0, step=0.5,
)

micro_density = st.sidebar.number_input(
    "微缺陷密度阈值 (每米)", value=50, min_value=1, max_value=500,
)

st.sidebar.divider()

# --- Load models button ---
if st.sidebar.button("🔄 加载模型", use_container_width=True):
    with st.spinner("正在加载模型..."):
        cfg = init_config()
        models_cfg = cfg.load("models")

        # Apply UI overrides
        models_cfg["yolo"]["enabled"] = enable_yolo
        models_cfg["yolo"]["model_path"] = yolo_model_path
        models_cfg["yolo"]["conf_threshold"] = yolo_conf

        models_cfg["patchcore"]["enabled"] = enable_patchcore
        models_cfg["patchcore"]["mode"] = patchcore_mode
        models_cfg["patchcore"]["result_file"] = patchcore_result_file

        models_cfg["efficientad"]["enabled"] = enable_efficientad
        models_cfg["efficientad"]["mode"] = efficientad_mode

        models_cfg["fastflow"]["enabled"] = enable_fastflow
        models_cfg["fastflow"]["mode"] = fastflow_mode

        models_cfg["opencv"]["enabled"] = enable_opencv

        runners = load_all_runners(models_cfg)
        st.session_state.models_loaded = bool(runners)

        # Init rule engine
        fusion_cfg = cfg.load("fusion_rules")
        fusion_cfg["yolo"]["conf_threshold"] = yolo_conf
        fusion_cfg["anomaly"]["patchcore_score_threshold"] = anomaly_threshold
        fusion_cfg["anomaly"]["efficientad_score_threshold"] = anomaly_threshold
        fusion_cfg["anomaly"]["fastflow_score_threshold"] = anomaly_threshold
        fusion_cfg["geometry"]["min_defect_area_px"] = min_defect_area
        fusion_cfg["geometry"]["acceptable_micro_area_px"] = acceptable_micro_area
        fusion_cfg["geometry"]["acceptable_scratch_length_mm"] = acceptable_scratch_len
        fusion_cfg["geometry"]["ng_scratch_length_mm"] = ng_scratch_len
        fusion_cfg["density"]["max_micro_defect_count_per_meter"] = micro_density

        st.session_state.rule_engine = RuleEngine(fusion_cfg)
        st.success(f"已加载 {len(runners)} 个模型: {', '.join(runners.keys())}")

# --- Scan dataset ---
if st.sidebar.button("📊 扫描数据集", use_container_width=True):
    with st.spinner("正在扫描数据集..."):
        try:
            cfg = init_config()
            loader = DatasetLoader(
                image_dir=image_dir,
                label_dir=label_dir,
                class_map=CLASS_ID_MAP,
            )
            records = loader.scan()
            st.session_state.records = records
            st.session_state.dataset_loader = loader
            st.success(f"扫描完成: {len(records)} 张图片")
        except Exception as e:
            st.error(f"数据集扫描失败: {e}")

st.sidebar.divider()

# --- Quick actions ---
st.sidebar.header("⚡ 快捷操作")

if st.sidebar.button("🚀 运行批量测试", use_container_width=True, type="primary"):
    st.session_state.run_batch = True

if st.sidebar.button("📥 导出 Excel 报告", use_container_width=True):
    st.session_state.export_excel = True

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📋 项目说明",
    "📊 数据集概览",
    "🔍 单图测试",
    "📈 批量评测",
    "🔄 融合策略对比",
    "⚠️ 误判样本池",
    "📥 报告导出",
])

# ===========================================================================
# Tab 1: Project Info
# ===========================================================================
with tab1:
    st.title("铜管表面缺陷模型评测与融合验证工具")
    st.markdown("---")

    col_desc, col_config = st.columns([3, 2])

    with col_desc:
        st.markdown("""
        ### 用途

        本工具用于**研发阶段**快速评测不同模型和融合策略在铜管表面缺陷检测任务上的效果。

        ### 核心能力

        - **多模型推理**: YOLO (已知缺陷) + PatchCore/EfficientAD/FastFlow (异常检测) + OpenCV (传统规则)
        - **融合策略**: 6 种策略，综合多模型结果、几何特征、密度规则
        - **工业指标**: OK 误报率、NG 漏检率、可接受微缺陷误报率、未知缺陷召回率
        - **误判分析**: 自动分类误判样本，辅助模型迭代

        ### 判定逻辑

        | 判定 | 含义 |
        |------|------|
        | **OK** | 表面正常，无明显缺陷 |
        | **ACCEPTABLE_MICRO_DEFECT** | 存在微小缺陷但工艺可接受 |
        | **SUSPECT** | 可疑，需人工复判 |
        | **NG** | 不合格，明显缺陷 |

        ### 使用流程

        1. 在左侧 sidebar 设置数据路径和模型配置
        2. 点击「扫描数据集」加载数据
        3. 点击「加载模型」初始化推理器
        4. 在「单图测试」验证单张效果
        5. 在「批量评测」运行全量测试
        6. 在「融合策略对比」比较不同策略
        7. 在「误判样本池」分析问题样本
        8. 在「报告导出」生成 Excel 报告
        """)

    with col_config:
        st.markdown("### 当前配置")
        st.json({
            "图片目录": image_dir,
            "标注目录": label_dir,
            "YOLO": "启用" if enable_yolo else "禁用",
            "PatchCore": f"启用 ({patchcore_mode})" if enable_patchcore else "禁用",
            "EfficientAD": f"启用 ({efficientad_mode})" if enable_efficientad else "禁用",
            "FastFlow": f"启用 ({fastflow_mode})" if enable_fastflow else "禁用",
            "OpenCV": "启用" if enable_opencv else "禁用",
            "融合策略": selected_strategy_name,
            "YOLO conf": yolo_conf,
            "Anomaly threshold": anomaly_threshold,
            "已加载模型": st.session_state.models_loaded,
        })

    st.markdown("---")
    st.caption(
        "⚠️ 重要提醒：OK_micro_defect 是工艺可接受微缺陷，不应简单判为 NG。"
        "Borderline 样本不加入正常库，仅用于评估边界。未知异常应优先判 SUSPECT 而非 NG。"
    )

# ===========================================================================
# Tab 2: Dataset Overview
# ===========================================================================
with tab2:
    st.header("数据集概览")

    records = st.session_state.records

    if not records:
        st.info("尚未扫描数据集。请在左侧 sidebar 点击「📊 扫描数据集」。")
    else:
        loader = st.session_state.dataset_loader
        stats = loader.get_statistics() if loader else {}

        total = stats.get("total_images", len(records))
        annotated_count = stats.get("annotated", 0)
        unannotated_count = stats.get("unannotated", 0)
        annotation_rate = annotated_count / max(total, 1)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("总图片数", total)
        col2.metric("已标注", annotated_count)
        col3.metric("未标注", unannotated_count)
        col4.metric("标注率", f"{annotation_rate:.1%}")

        st.divider()

        # Class distribution
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("类别分布")
            class_counts = stats.get("counts_by_class", {})
            if class_counts:
                df_classes = pd.DataFrame(
                    {"类别": list(class_counts.keys()), "数量": list(class_counts.values())}
                ).sort_values("数量", ascending=False)
                st.dataframe(df_classes, use_container_width=True, hide_index=True)

        with col_right:
            st.subheader("分组统计")
            group_counts = stats.get("counts_by_group", {})
            if group_counts:
                df_groups = pd.DataFrame(
                    {"分组": list(group_counts.keys()), "数量": list(group_counts.values())}
                )
                st.dataframe(df_groups, use_container_width=True, hide_index=True)

                # Bar chart
                st.bar_chart(df_groups.set_index("分组"))

        # Image list
        st.divider()
        st.subheader("图片列表")

        filter_group = st.selectbox(
            "按分组筛选",
            ["全部", "ok", "ng", "acceptable_micro", "borderline", "unannotated"],
        )

        filtered = records
        if filter_group == "unannotated":
            filtered = [r for r in records if not r.has_annotation]
        elif filter_group != "全部":
            filtered = loader.filter_by_group(records, filter_group) if loader else []

        if filtered:
            rows = []
            for rec in filtered[:200]:  # Limit display
                rows.append({
                    "图片": Path(rec.image_path).name,
                    "标签": rec.true_label if rec.has_annotation else "(未标注)",
                    "路径": rec.image_path,
                    "分组": get_label_group(rec.true_label) if rec.has_annotation else "unannotated",
                })
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
                column_config={"路径": st.column_config.TextColumn(width="large")},
            )
            if len(filtered) > 200:
                st.caption(f"显示前 200 条，共 {len(filtered)} 条")
        else:
            st.caption("无匹配图片")

# ===========================================================================
# Tab 3: Single Image Test
# ===========================================================================
with tab3:
    st.header("单图测试")

    if not records:
        st.info("请先在 sidebar 扫描数据集。")
    elif not st.session_state.models_loaded:
        st.info("请先在 sidebar 点击「加载模型」。")
    else:
        # Image selector
        image_names = [Path(r.image_path).name for r in records]
        selected_name = st.selectbox("选择图片", image_names)
        selected_record = next(
            (r for r in records if Path(r.image_path).name == selected_name), None
        )

        if selected_record is None:
            st.error("未找到所选图片")
        else:
            image_path = selected_record.image_path

            if st.button("🔍 运行推理", type="primary"):
                with st.spinner("正在推理..."):
                    results: dict[str, UnifiedPrediction | None] = {}
                    timer = BatchTimer()

                    # YOLO
                    yolo_runner = st.session_state.yolo_runner
                    if yolo_runner and yolo_runner.is_loaded:
                        try:
                            t0 = time.perf_counter()
                            results["yolo"] = yolo_runner.predict(image_path)
                            timer.record("yolo", (time.perf_counter() - t0) * 1000)
                        except Exception as e:
                            st.warning(f"YOLO 推理失败: {e}")

                    # PatchCore
                    pc_runner = st.session_state.patchcore_runner
                    if pc_runner and pc_runner.is_loaded:
                        try:
                            t0 = time.perf_counter()
                            results["patchcore"] = pc_runner.predict(image_path)
                            timer.record("patchcore", (time.perf_counter() - t0) * 1000)
                        except Exception as e:
                            st.warning(f"PatchCore 推理失败: {e}")

                    # EfficientAD
                    ea_runner = st.session_state.efficientad_runner
                    if ea_runner and ea_runner.is_loaded:
                        try:
                            t0 = time.perf_counter()
                            results["efficientad"] = ea_runner.predict(image_path)
                            timer.record("efficientad", (time.perf_counter() - t0) * 1000)
                        except Exception as e:
                            st.warning(f"EfficientAD 推理失败: {e}")

                    # FastFlow
                    ff_runner = st.session_state.fastflow_runner
                    if ff_runner and ff_runner.is_loaded:
                        try:
                            t0 = time.perf_counter()
                            results["fastflow"] = ff_runner.predict(image_path)
                            timer.record("fastflow", (time.perf_counter() - t0) * 1000)
                        except Exception as e:
                            st.warning(f"FastFlow 推理失败: {e}")

                    # OpenCV
                    cv_runner = st.session_state.opencv_runner
                    if cv_runner and cv_runner.is_loaded:
                        try:
                            t0 = time.perf_counter()
                            results["opencv"] = cv_runner.predict(image_path)
                            timer.record("opencv", (time.perf_counter() - t0) * 1000)
                        except Exception as e:
                            st.warning(f"OpenCV 推理失败: {e}")

                    # Fusion
                    rule_engine = st.session_state.rule_engine
                    if rule_engine:
                        candidates = build_candidates_for_image(
                            image_path,
                            yolo_result=results.get("yolo"),
                            patchcore_result=results.get("patchcore"),
                            efficientad_result=results.get("efficientad"),
                            fastflow_result=results.get("fastflow"),
                            opencv_result=results.get("opencv"),
                        )
                        t0 = time.perf_counter()
                        fusion = rule_engine.decide(
                            image_path=image_path,
                            strategy=FusionStrategy(selected_strategy),
                            yolo_result=results.get("yolo"),
                            patchcore_result=results.get("patchcore"),
                            efficientad_result=results.get("efficientad"),
                            fastflow_result=results.get("fastflow"),
                            opencv_result=results.get("opencv"),
                            candidates=candidates,
                        )
                        fusion.runtime_ms = (time.perf_counter() - t0) * 1000
                        results["fusion"] = fusion  # type: ignore[assignment]

                    st.session_state.last_single_result = {
                        "image_path": image_path,
                        "results": results,
                        "timer": timer,
                        "record": selected_record,
                    }

            # Display results
            if "last_single_result" in st.session_state:
                res = st.session_state.last_single_result
                img_path = res["image_path"]
                results = res["results"]
                timer = res["timer"]
                record = res["record"]

                st.divider()

                # Visualization
                col_img, col_info = st.columns([3, 2])

                with col_img:
                    st.subheader("检测结果")

                    fusion = results.get("fusion")
                    viz = create_result_visualization(
                        image_path=img_path,
                        yolo_result=results.get("yolo"),
                        anomaly_result=results.get("patchcore") or results.get("efficientad"),
                        opencv_result=results.get("opencv"),
                        fusion_decision=fusion if isinstance(fusion, FusionDecision) else None,
                        ground_truth_boxes=(
                            [(a.bbox_xyxy[0], a.bbox_xyxy[1], a.bbox_xyxy[2], a.bbox_xyxy[3])
                             for a in record.annotations]
                            if record and record.annotations else None
                        ),
                    )
                    st.image(viz, use_container_width=True)

                with col_info:
                    st.subheader("判定结果")

                    if isinstance(fusion, FusionDecision):
                        decision = fusion.final_decision.value
                        color_map = {
                            "OK": "green",
                            "ACCEPTABLE_MICRO_DEFECT": "orange",
                            "SUSPECT": "red",
                            "NG": "red",
                        }
                        st.markdown(
                            f"### :{color_map.get(decision, 'gray')}[{decision}]"
                        )
                        st.markdown(f"**原因**: {fusion.reason}")

                    st.divider()
                    st.subheader("推理耗时")
                    timing = timer.summary()
                    for model_name, t in timing.items():
                        st.text(f"{model_name}: {t['avg_ms']:.1f} ms")

                    st.divider()
                    st.subheader("标注信息")
                    if record and record.has_annotation:
                        st.text(f"真实标签: {record.true_label}")
                        st.text(f"标注框数: {len(record.annotations)}")
                    else:
                        st.text("无标注")

                # Detection details
                st.divider()
                st.subheader("检测详情")

                det_cols = st.columns(min(len(results), 4))
                for i, (model_name, result) in enumerate(results.items()):
                    with det_cols[i % 4]:
                        if isinstance(result, UnifiedPrediction):
                            st.markdown(f"**{model_name.upper()}**")
                            if result.predictions:
                                for p in result.predictions:
                                    st.text(
                                        f"{p.class_name}: {p.confidence:.3f}"
                                    )
                            elif result.anomaly and result.anomaly.image_score > 0:
                                st.text(f"Anomaly: {result.anomaly.image_score:.3f}")
                            else:
                                st.text("无检出")
                            st.text(f"{(result.runtime_ms):.1f} ms")

                # Defect candidates table
                if isinstance(fusion, FusionDecision) and fusion.candidates:
                    st.divider()
                    st.subheader("候选缺陷特征")
                    cand_rows = []
                    for c in fusion.candidates:
                        cand_rows.append({
                            "ID": c.candidate_id,
                            "来源": c.source_model.value,
                            "类别": c.class_name,
                            "置信度": f"{c.confidence:.3f}",
                            "面积(px)": f"{c.area_px:.0f}",
                            "长(px)": f"{c.length_px:.0f}",
                            "宽(px)": f"{c.width_px:.0f}",
                            "长宽比": f"{c.aspect_ratio:.2f}",
                            "异常分": f"{c.max_anomaly_score:.3f}",
                            "长划伤": "是" if c.is_long_scratch_like else "否",
                            "点状": "是" if c.is_point_like else "否",
                        })
                    st.dataframe(pd.DataFrame(cand_rows), use_container_width=True, hide_index=True)

# ===========================================================================
# Tab 4: Batch Evaluation
# ===========================================================================
with tab4:
    st.header("批量评测")

    if not records:
        st.info("请先在 sidebar 扫描数据集。")
    elif not st.session_state.models_loaded:
        st.info("请先在 sidebar 点击「加载模型」。")
    else:
        run_batch = st.button("🚀 运行批量测试", type="primary") or st.session_state.get("run_batch", False)
        st.session_state.run_batch = False

        if run_batch:
            target_records = records
            # Apply split filter if specified
            if split_file and Path(split_file).exists():
                from src.dataset.split_manager import SplitManager
                sm = SplitManager()
                target_records = sm.filter_by_split(records, split_file)
                st.info(f"使用划分文件: {split_file} ({len(target_records)} 张)")

            if len(target_records) > 500:
                st.warning(f"数据集较大 ({len(target_records)} 张)，推理可能需要较长时间。")

            progress = st.progress(0)
            status = st.empty()

            results_list: list[ImageRecord] = []
            timer = BatchTimer()
            total = len(target_records)

            for idx, rec in enumerate(target_records):
                status.text(f"推理中: {Path(rec.image_path).name} ({idx + 1}/{total})")
                progress.progress((idx + 1) / total)

                try:
                    yolo_result = None
                    if st.session_state.yolo_runner and st.session_state.yolo_runner.is_loaded:
                        t0 = time.perf_counter()
                        yolo_result = st.session_state.yolo_runner.predict(rec.image_path)
                        timer.record("yolo", (time.perf_counter() - t0) * 1000)
                        rec.yolo_result = yolo_result

                    patchcore_result = None
                    if st.session_state.patchcore_runner and st.session_state.patchcore_runner.is_loaded:
                        t0 = time.perf_counter()
                        patchcore_result = st.session_state.patchcore_runner.predict(rec.image_path)
                        timer.record("patchcore", (time.perf_counter() - t0) * 1000)
                        rec.patchcore_result = patchcore_result

                    efficientad_result = None
                    if st.session_state.efficientad_runner and st.session_state.efficientad_runner.is_loaded:
                        t0 = time.perf_counter()
                        efficientad_result = st.session_state.efficientad_runner.predict(rec.image_path)
                        timer.record("efficientad", (time.perf_counter() - t0) * 1000)
                        rec.efficientad_result = efficientad_result

                    fastflow_result = None
                    if st.session_state.fastflow_runner and st.session_state.fastflow_runner.is_loaded:
                        t0 = time.perf_counter()
                        fastflow_result = st.session_state.fastflow_runner.predict(rec.image_path)
                        timer.record("fastflow", (time.perf_counter() - t0) * 1000)
                        rec.fastflow_result = fastflow_result

                    opencv_result = None
                    if st.session_state.opencv_runner and st.session_state.opencv_runner.is_loaded:
                        t0 = time.perf_counter()
                        opencv_result = st.session_state.opencv_runner.predict(rec.image_path)
                        timer.record("opencv", (time.perf_counter() - t0) * 1000)
                        rec.opencv_result = opencv_result

                    # Fusion
                    if st.session_state.rule_engine:
                        candidates = build_candidates_for_image(
                            rec.image_path,
                            yolo_result=yolo_result,
                            patchcore_result=patchcore_result,
                            efficientad_result=efficientad_result,
                            fastflow_result=fastflow_result,
                            opencv_result=opencv_result,
                        )
                        t0 = time.perf_counter()
                        fusion = st.session_state.rule_engine.decide(
                            image_path=rec.image_path,
                            strategy=FusionStrategy(selected_strategy),
                            yolo_result=yolo_result,
                            patchcore_result=patchcore_result,
                            efficientad_result=efficientad_result,
                            fastflow_result=fastflow_result,
                            opencv_result=opencv_result,
                            candidates=candidates,
                        )
                        fusion.runtime_ms = (time.perf_counter() - t0) * 1000
                        rec.fusion_decision = fusion

                    results_list.append(rec)

                except Exception as e:
                    st.warning(f"推理失败 {rec.image_path}: {e}")

            progress.progress(1.0)
            status.text("推理完成！")

            # Analyze misclassifications
            misclassified = analyze_misclassifications(results_list)

            st.session_state.batch_results = results_list
            st.session_state.batch_misclassified = misclassified
            st.session_state.batch_timer = timer
            st.session_state.inference_run = True

            st.success(
                f"批量推理完成: {len(results_list)} 张图片, "
                f"误判 {len(misclassified)} 张"
            )

        # Show results if available
        if st.session_state.get("inference_run"):
            results_list = st.session_state.get("batch_results", [])
            misclassified = st.session_state.get("batch_misclassified", [])
            timer = st.session_state.get("batch_timer", BatchTimer())

            st.divider()

            # Metrics summary
            st.subheader("指标汇总")

            annotated = [r for r in results_list if r.has_annotation]
            if annotated:
                true_labels = [r.true_label for r in annotated]
                pred_decisions = [
                    r.fusion_decision.final_decision.value
                    if r.fusion_decision else "OK"
                    for r in annotated
                ]
                inf_times = [
                    r.fusion_decision.runtime_ms if r.fusion_decision else 0
                    for r in annotated
                ]

                metrics = compute_industrial_metrics(true_labels, pred_decisions, inf_times)

                col1, col2, col3, col4, col5, col6 = st.columns(6)
                col1.metric("OK 误报率", f"{metrics.ok_false_positive_rate:.3f}")
                col2.metric("NG 漏检率", f"{metrics.ng_miss_rate:.3f}")
                col3.metric("微缺陷误报率", f"{metrics.acceptable_micro_fp_rate:.3f}")
                col4.metric("未知缺陷召回率", f"{metrics.unknown_defect_recall:.3f}")
                col5.metric("临界缺陷检出率", f"{metrics.borderline_detection_rate:.3f}")
                col6.metric("平均推理时间", f"{metrics.avg_inference_time_ms:.0f} ms")
            else:
                st.info("无已标注样本，无法计算监督指标。")

            st.divider()

            # Results table
            st.subheader("结果明细")

            # Filters
            filter_cols = st.columns(4)
            with filter_cols[0]:
                show_filter = st.selectbox(
                    "筛选类型",
                    ["全部", "正确", "误判", "OK", "NG", "SUSPECT", "ACCEPTABLE_MICRO_DEFECT"],
                    key="batch_filter",
                )
            with filter_cols[1]:
                true_label_filter = st.selectbox(
                    "真实标签",
                    ["全部"] + list(CLASS_ID_MAP.values()),
                    key="batch_true_label",
                )

            filtered_results = results_list
            if show_filter == "正确":
                filtered_results = [r for r in filtered_results if not r.is_misclassified]
            elif show_filter == "误判":
                filtered_results = [r for r in filtered_results if r.is_misclassified]
            elif show_filter in ("OK", "NG", "SUSPECT", "ACCEPTABLE_MICRO_DEFECT"):
                filtered_results = [
                    r for r in filtered_results
                    if r.fusion_decision and r.fusion_decision.final_decision.value == show_filter
                ]

            if true_label_filter != "全部":
                filtered_results = [
                    r for r in filtered_results if r.true_label == true_label_filter
                ]

            if filtered_results:
                rows = []
                for rec in filtered_results[:200]:
                    fd = rec.fusion_decision
                    rows.append({
                        "图片": Path(rec.image_path).name,
                        "真实标签": rec.true_label,
                        "最终判定": fd.final_decision.value if fd else "N/A",
                        "原因": fd.reason if fd else "",
                        "YOLO检出数": len(rec.yolo_result.predictions) if rec.yolo_result else 0,
                        "PatchCore分": (
                            f"{rec.patchcore_result.anomaly.image_score:.3f}"
                            if rec.patchcore_result else "N/A"
                        ),
                        "是否正确": "❌" if rec.is_misclassified else "✅",
                        "耗时(ms)": f"{fd.runtime_ms:.0f}" if fd else "N/A",
                    })

                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                )
                if len(filtered_results) > 200:
                    st.caption(f"显示前 200 条，共 {len(filtered_results)} 条")
            else:
                st.caption("无匹配结果")

            # Timing summary
            st.divider()
            st.subheader("推理耗时统计")
            timing_summary = timer.summary()
            if timing_summary:
                timing_rows = []
                for model_name, data in timing_summary.items():
                    timing_rows.append({
                        "模型": model_name,
                        "总耗时(ms)": f"{data['total_ms']:.0f}",
                        "平均(ms)": f"{data['avg_ms']:.1f}",
                        "调用次数": data["count"],
                    })
                st.dataframe(pd.DataFrame(timing_rows), use_container_width=True, hide_index=True)

# ===========================================================================
# Tab 5: Strategy Comparison
# ===========================================================================
with tab5:
    st.header("融合策略对比")

    if not st.session_state.get("inference_run"):
        st.info("请先在「批量评测」Tab 中运行批量测试。")
    else:
        results_list = st.session_state.get("batch_results", [])
        annotated = [r for r in results_list if r.has_annotation]

        if not annotated:
            st.info("无已标注样本，无法进行策略对比。")
        else:
            true_labels = [r.true_label for r in annotated]

            if st.button("🔄 运行所有策略对比", type="primary"):
                with st.spinner("正在对比所有融合策略..."):
                    rule_engine = st.session_state.rule_engine
                    if rule_engine is None:
                        st.error("Rule engine 未初始化")
                    else:
                        strategy_results: dict[str, tuple[list, list, list]] = {}

                        for strategy in FusionStrategy:
                            pred_decisions = []
                            inf_times = []

                            for rec in annotated:
                                candidates = build_candidates_for_image(
                                    rec.image_path,
                                    yolo_result=rec.yolo_result,
                                    patchcore_result=rec.patchcore_result,
                                    efficientad_result=rec.efficientad_result,
                                    fastflow_result=rec.fastflow_result,
                                    opencv_result=rec.opencv_result,
                                )
                                t0 = time.perf_counter()
                                fusion = rule_engine.decide(
                                    image_path=rec.image_path,
                                    strategy=strategy,
                                    yolo_result=rec.yolo_result,
                                    patchcore_result=rec.patchcore_result,
                                    efficientad_result=rec.efficientad_result,
                                    fastflow_result=rec.fastflow_result,
                                    opencv_result=rec.opencv_result,
                                    candidates=candidates,
                                )
                                pred_decisions.append(fusion.final_decision.value)
                                inf_times.append((time.perf_counter() - t0) * 1000)

                            strategy_results[get_strategy_name(strategy)] = (
                                true_labels, pred_decisions, inf_times,
                            )

                        comparison = compute_strategy_comparison(strategy_results)
                        st.session_state.strategy_comparison = comparison
                        st.success(f"完成 {len(comparison)} 种策略对比")

            # Display comparison
            if "strategy_comparison" in st.session_state:
                comparison = st.session_state.strategy_comparison

                st.subheader("策略对比表")
                df_comp = pd.DataFrame(comparison)
                st.dataframe(df_comp, use_container_width=True, hide_index=True)

                # Chart
                st.subheader("策略对比图")
                chart_buf = create_strategy_comparison_chart(comparison)
                st.image(chart_buf, use_container_width=True)

                # Best strategy highlight
                st.subheader("最优策略推荐")
                if comparison:
                    # Score: lower is better for FPR/miss, higher for recall
                    best_ok = min(comparison, key=lambda c: c["ok_fpr"])
                    best_ng = min(comparison, key=lambda c: c["ng_miss_rate"])
                    best_unknown = max(comparison, key=lambda c: c["unknown_recall"])

                    rec_cols = st.columns(3)
                    rec_cols[0].metric(
                        "最低 OK 误报率",
                        f"{best_ok['ok_fpr']:.3f}",
                        delta=f"策略: {best_ok['strategy']}",
                    )
                    rec_cols[1].metric(
                        "最低 NG 漏检率",
                        f"{best_ng['ng_miss_rate']:.3f}",
                        delta=f"策略: {best_ng['strategy']}",
                    )
                    rec_cols[2].metric(
                        "最高未知缺陷召回率",
                        f"{best_unknown['unknown_recall']:.3f}",
                        delta=f"策略: {best_unknown['strategy']}",
                    )

# ===========================================================================
# Tab 6: Misclassified Sample Pool
# ===========================================================================
with tab6:
    st.header("误判样本池")

    if not st.session_state.get("inference_run"):
        st.info("请先在「批量评测」Tab 中运行批量测试。")
    else:
        results_list = st.session_state.get("batch_results", [])
        misclassified = st.session_state.get("batch_misclassified", [])

        if not misclassified:
            # Re-analyze if needed
            misclassified = analyze_misclassifications(results_list)
            st.session_state.batch_misclassified = misclassified

        error_groups = group_by_error_type(misclassified)

        # Summary counts
        st.subheader("误判统计")
        cols = st.columns(5)
        group_labels = [
            ("OK 误报", "OK_false_positive", len(error_groups.get("OK_false_positive", []))),
            ("NG 漏检", "NG_miss", len(error_groups.get("NG_miss", []))),
            ("微缺陷误报", "acceptable_micro_fp", len(error_groups.get("acceptable_micro_fp", []))),
            ("未知缺陷漏检", "unknown_miss", len(error_groups.get("unknown_miss", []))),
            ("Borderline", "borderline", len(error_groups.get("borderline", []))),
        ]
        for i, (label, key, count) in enumerate(group_labels):
            cols[i % 5].metric(label, count)

        # Additional analysis groups
        cols2 = st.columns(2)
        cols2[0].metric(
            "YOLO 未识别但异常高分",
            len(error_groups.get("yolo_miss_anomaly_high", [])),
        )
        cols2[1].metric(
            "YOLO 命中但异常低分",
            len(error_groups.get("yolo_hit_anomaly_low", [])),
        )

        st.divider()

        # Browse by error type
        error_type = st.selectbox(
            "错误类型",
            [
                "OK_false_positive",
                "NG_miss",
                "acceptable_micro_fp",
                "unknown_miss",
                "borderline",
                "yolo_miss_anomaly_high",
                "yolo_hit_anomaly_low",
            ],
            format_func=lambda x: {
                "OK_false_positive": "OK 误报 (OK→NG/SUSPECT)",
                "NG_miss": "NG 漏检 (NG→OK/ACCEPTABLE)",
                "acceptable_micro_fp": "微缺陷误报 (OK_micro→NG)",
                "unknown_miss": "未知缺陷漏检 (NG_unknown→OK)",
                "borderline": "临界样本 (Borderline)",
                "yolo_miss_anomaly_high": "YOLO 未识别但异常高分",
                "yolo_hit_anomaly_low": "YOLO 命中但异常低分",
            }.get(x, x),
        )

        group = error_groups.get(error_type, [])

        if group:
            st.subheader(f"共 {len(group)} 张")

            # Show image grid
            cols_per_row = 3
            for i, rec in enumerate(group[:30]):
                if i % cols_per_row == 0:
                    img_cols = st.columns(cols_per_row)

                with img_cols[i % cols_per_row]:
                    try:
                        img = load_image_rgb(rec.image_path)
                        fd = rec.fusion_decision
                        decision = fd.final_decision.value if fd else "N/A"

                        # Add decision overlay color border via caption
                        st.image(img, caption=f"{Path(rec.image_path).name}", use_container_width=True)
                        st.caption(
                            f"真实: {rec.true_label} → 判定: {decision}\n"
                            f"原因: {fd.reason if fd else 'N/A'}"
                        )
                    except Exception:
                        st.text(f"无法加载: {Path(rec.image_path).name}")

            if len(group) > 30:
                st.caption(f"显示前 30 张，共 {len(group)} 张")
        else:
            st.caption("该类别无误判样本")

# ===========================================================================
# Tab 7: Report Export
# ===========================================================================
with tab7:
    st.header("报告导出")

    if not st.session_state.get("inference_run"):
        st.info("请先在「批量评测」Tab 中运行批量测试。")
    else:
        results_list = st.session_state.get("batch_results", [])
        misclassified = st.session_state.get("batch_misclassified", [])

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Excel 报告")
            if st.button("📥 导出 Excel 报告", type="primary", use_container_width=True):
                with st.spinner("正在生成 Excel 报告..."):
                    try:
                        output_dir = ensure_dir("outputs/reports")
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        output_path = output_dir / f"copper_defect_report_{timestamp}.xlsx"

                        report = ExcelReport(output_path)

                        # Summary sheet
                        annotated = [r for r in results_list if r.has_annotation]
                        true_labels = [r.true_label for r in annotated]
                        pred_decisions = [
                            r.fusion_decision.final_decision.value
                            if r.fusion_decision else "OK"
                            for r in annotated
                        ]
                        inf_times = [
                            r.fusion_decision.runtime_ms if r.fusion_decision else 0
                            for r in annotated
                        ]
                        metrics = compute_industrial_metrics(true_labels, pred_decisions, inf_times)

                        report.add_summary_sheet({
                            "total_images": len(results_list),
                            "ok_fpr": metrics.ok_false_positive_rate,
                            "ng_miss_rate": metrics.ng_miss_rate,
                            "acceptable_micro_fpr": metrics.acceptable_micro_fp_rate,
                            "unknown_recall": metrics.unknown_defect_recall,
                            "borderline_detection_rate": metrics.borderline_detection_rate,
                            "avg_inference_time_ms": metrics.avg_inference_time_ms,
                        })

                        # Image results
                        report.add_image_results_sheet(results_list)

                        # Defect candidates
                        all_candidates = []
                        for rec in results_list:
                            if rec.fusion_decision:
                                all_candidates.extend(rec.fusion_decision.candidates)
                        report.add_defect_candidates_sheet(all_candidates)

                        # Misclassified
                        misclassified = analyze_misclassifications(results_list)
                        report.add_misclassified_sheet(misclassified)

                        # Strategy comparison (if available)
                        if "strategy_comparison" in st.session_state:
                            report.add_strategy_comparison_sheet(
                                st.session_state.strategy_comparison
                            )

                        saved_path = report.save()
                        st.success(f"报告已保存: {saved_path}")

                        # Offer download
                        with open(saved_path, "rb") as f:
                            st.download_button(
                                "⬇️ 下载 Excel 报告",
                                f,
                                file_name=Path(saved_path).name,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            )
                    except Exception as e:
                        st.error(f"导出失败: {e}")

        with col2:
            st.subheader("可视化导出")

            export_viz = st.checkbox("导出带标注的可视化图片", value=True)
            max_viz = st.number_input("最大导出图片数", value=50, min_value=1, max_value=200)

            if st.button("🖼️ 导出可视化图片", use_container_width=True):
                with st.spinner("正在导出可视化图片..."):
                    try:
                        viz_dir = ensure_dir("outputs/visualizations/export")
                        count = 0

                        for rec in results_list[:max_viz]:
                            try:
                                viz = create_result_visualization(
                                    image_path=rec.image_path,
                                    yolo_result=rec.yolo_result,
                                    anomaly_result=rec.patchcore_result,
                                    opencv_result=rec.opencv_result,
                                    fusion_decision=rec.fusion_decision,
                                )
                                out_name = Path(rec.image_path).stem + "_viz.png"
                                viz_bgr = viz[..., ::-1]  # RGB to BGR for cv2
                                import cv2
                                cv2.imwrite(str(viz_dir / out_name), viz_bgr)
                                count += 1
                            except Exception as e:
                                st.warning(f"导出失败 {Path(rec.image_path).name}: {e}")

                        st.success(f"已导出 {count} 张可视化图片到: {viz_dir}")
                    except Exception as e:
                        st.error(f"导出失败: {e}")

            st.divider()
            st.subheader("HTML 报告")
            if st.button("🌐 导出 HTML 报告", use_container_width=True):
                with st.spinner("正在生成 HTML 报告..."):
                    try:
                        from src.reports.html_report import generate_html_report

                        annotated = [r for r in results_list if r.has_annotation]
                        true_labels = [r.true_label for r in annotated]
                        pred_decisions = [
                            r.fusion_decision.final_decision.value
                            if r.fusion_decision else "OK"
                            for r in annotated
                        ]
                        inf_times = [
                            r.fusion_decision.runtime_ms if r.fusion_decision else 0
                            for r in annotated
                        ]
                        metrics = compute_industrial_metrics(true_labels, pred_decisions, inf_times)

                        html_dir = ensure_dir("outputs/reports")
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        html_path = html_dir / f"copper_defect_report_{timestamp}.html"

                        generate_html_report(
                            title="铜管表面缺陷评测报告",
                            metrics={
                                "total_images": len(results_list),
                                "ok_fpr": metrics.ok_false_positive_rate,
                                "ng_miss_rate": metrics.ng_miss_rate,
                                "acceptable_micro_fpr": metrics.acceptable_micro_fp_rate,
                                "unknown_recall": metrics.unknown_defect_recall,
                                "borderline_detection_rate": metrics.borderline_detection_rate,
                                "avg_inference_time_ms": metrics.avg_inference_time_ms,
                            },
                            records=results_list[:100],
                            output_path=html_path,
                        )
                        st.success(f"HTML 报告已保存: {html_path}")
                    except Exception as e:
                        st.error(f"导出失败: {e}")


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.caption(
    "铜管表面缺陷模型评测与融合验证工具 v0.1.0\n"
    "研发评估用途，非最终在线检测软件"
)
