"""Defect acceptance rule UI.

Phase 3: Classify defects into A/B/C/UNKNOWN levels for deployment decisions.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from core.schema import DetectionBox
from core.defect_rules import (
    DefectRuleConfig,
    apply_defect_rules,
    summarize_defect_levels,
    LEVEL_A,
    LEVEL_B,
    LEVEL_C,
    LEVEL_UNKNOWN,
    LEVEL_LOW_CONF,
)


def render_defect_rules_ui(
    predictions_by_image: dict[str, list[DetectionBox]] | None = None,
):
    """Render the defect acceptance rule configuration and results."""
    st.header("缺陷判定规则")

    # --- Rule configuration ---
    st.subheader("规则配置")

    col1, col2, col3 = st.columns(3)
    with col1:
        min_alarm_size = st.number_input(
            "最小报警尺寸 (mm)",
            min_value=0.01,
            max_value=10.0,
            value=0.07,
            step=0.01,
            key="rule_min_alarm_size",
        )
        severe_size = st.number_input(
            "严重缺陷尺寸 (mm)",
            min_value=0.05,
            max_value=20.0,
            value=0.15,
            step=0.01,
            key="rule_severe_size",
        )
    with col2:
        min_alarm_conf = st.slider(
            "最小报警置信度",
            min_value=0.0,
            max_value=1.0,
            value=0.25,
            step=0.05,
            key="rule_min_alarm_conf",
        )
        density_window = st.number_input(
            "密度窗口 (m)",
            min_value=0.5,
            max_value=10.0,
            value=3.0,
            step=0.5,
            key="rule_density_window",
        )
    with col3:
        density_count = st.number_input(
            "密度报警数量",
            min_value=1,
            max_value=50,
            value=3,
            key="rule_density_count",
        )

    # Class name configuration
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        acceptable_classes = st.text_input(
            "可接受缺陷类别 (逗号分隔)",
            value="scratch_light,spot_tiny",
            key="rule_acceptable_classes",
        )
    with col_b:
        severe_classes = st.text_input(
            "严重缺陷类别 (逗号分隔)",
            value="scratch_deep,hole,dent_large",
            key="rule_severe_classes",
        )
    with col_c:
        unknown_classes = st.text_input(
            "未知缺陷类别 (逗号分隔)",
            value="unknown,anomaly",
            key="rule_unknown_classes",
        )

    pixel_size_mm = st.number_input(
        "像素尺寸校准 (mm/px)",
        min_value=0.001,
        max_value=10.0,
        value=0.01,
        step=0.001,
        key="rule_pixel_size",
        help="每个像素对应的实际毫米数。设为 0 则禁用尺寸判定。",
    )

    config = DefectRuleConfig(
        min_alarm_size_mm=min_alarm_size,
        severe_size_mm=severe_size,
        min_alarm_confidence=min_alarm_conf,
        acceptable_class_names=[n.strip() for n in acceptable_classes.split(",") if n.strip()],
        severe_class_names=[n.strip() for n in severe_classes.split(",") if n.strip()],
        unknown_class_names=[n.strip() for n in unknown_classes.split(",") if n.strip()],
        density_window_m=density_window,
        density_alarm_count=int(density_count),
    )

    # --- Apply rules ---
    if predictions_by_image is None:
        st.info("暂无预测数据。请先运行模型推理。")
        return

    if st.button("应用规则", type="primary", key="rule_apply"):
        px_mm = pixel_size_mm if pixel_size_mm > 0 else None
        results = apply_defect_rules(predictions_by_image, config, px_mm)
        st.session_state.rule_results = results
        st.session_state.rule_config = config

    if "rule_results" not in st.session_state:
        return

    results = st.session_state.rule_results
    config_applied = st.session_state.get("rule_config", config)

    # --- Summary ---
    st.divider()
    st.subheader("缺陷等级汇总")

    summary = summarize_defect_levels(results)
    by_level = summary["by_level"]

    level_cols = st.columns(5)
    level_info = [
        ("A级-严重", by_level.get(LEVEL_A, 0), "red", "必须报警"),
        ("B级-一般", by_level.get(LEVEL_B, 0), "orange", "记录/可选报警"),
        ("C级-可接受", by_level.get(LEVEL_C, 0), "green", "不报警"),
        ("未知缺陷", by_level.get(LEVEL_UNKNOWN, 0), "blue", "送人工复核"),
        ("低置信度", by_level.get(LEVEL_LOW_CONF, 0), "gray", "送人工复核"),
    ]

    for i, (name, count, color, desc) in enumerate(level_info):
        with level_cols[i]:
            st.metric(name, count, delta=desc)

    st.divider()
    st.subheader("缺陷明细")

    # Flatten results to a table
    all_items = []
    for img_name, items in results.items():
        for item in items:
            all_items.append({
                "图片": img_name,
                "类别": item["class_name"],
                "置信度": f"{item['confidence']:.3f}",
                "等级": item["level"],
                "预估尺寸(mm)": f"{item['estimated_size_mm']:.3f}" if item["estimated_size_mm"] else "N/A",
                "BBox": str(item["bbox"]),
            })

    if all_items:
        # Filter by level
        level_filter = st.multiselect(
            "按等级筛选",
            [LEVEL_A, LEVEL_B, LEVEL_C, LEVEL_UNKNOWN, LEVEL_LOW_CONF],
            default=[LEVEL_A, LEVEL_UNKNOWN],
        )

        filtered = [item for item in all_items if item["等级"] in level_filter]
        st.dataframe(
            pd.DataFrame(filtered),
            use_container_width=True,
            hide_index=True,
        )

        # Download filtered results
        csv_data = pd.DataFrame(filtered).to_csv(index=False)
        st.download_button(
            "下载缺陷判定结果 CSV",
            csv_data,
            file_name="defect_rule_results.csv",
            mime="text/csv",
        )
    else:
        st.caption("无缺陷检出")
