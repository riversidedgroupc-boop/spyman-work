"""Meter-position defect analysis dashboard.

Phase 3: Visualize defect distribution along copper tube length.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px

from core.schema import DetectionBox
from core.position_analysis import (
    load_image_position_map,
    assign_detection_positions,
    bin_defects_by_meter,
    detect_continuous_defect_segments,
    summarize_position_statistics,
)


def render_position_dashboard(
    predictions_by_image: dict[str, list[DetectionBox]] | None = None,
):
    """Render the defect meter-position analysis section."""
    st.header("缺陷米数定位与趋势分析")

    # --- Position data input ---
    st.subheader("位置数据导入")

    col1, col2 = st.columns(2)
    with col1:
        position_csv = st.text_input(
            "位置 CSV 文件路径",
            value="data/positions.csv",
            key="pos_csv_path",
            help="CSV 需包含列: image_name, meter_start, meter_end",
        )
    with col2:
        bin_size = st.number_input(
            "分箱大小 (米)",
            min_value=0.1,
            max_value=10.0,
            value=1.0,
            step=0.5,
            key="pos_bin_size",
        )

    position_map: dict[str, dict] = {}

    if position_csv:
        try:
            position_map = load_image_position_map(position_csv)
            st.success(f"已加载 {len(position_map)} 张图片的位置信息")
        except FileNotFoundError:
            st.warning(f"位置文件不存在: {position_csv}")
        except Exception as e:
            st.warning(f"加载位置文件失败: {e}")

    if predictions_by_image is None:
        st.info("暂无预测数据。请先运行模型推理。")
        return

    if not position_map:
        st.info("请提供位置 CSV 文件以启用米数分析。")
        return

    # --- Analysis ---
    positioned = assign_detection_positions(predictions_by_image, position_map)
    stats = summarize_position_statistics(positioned)

    # --- Summary ---
    st.divider()
    st.subheader("位置统计")

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("总检测数", stats["total_detections"])
    col_b.metric("已定位", stats["positioned_count"])
    col_c.metric("未定位", stats["unpositioned_count"])
    if stats["mean_meter"] is not None:
        col_d.metric("平均米数", f"{stats['mean_meter']:.2f}m")

    if stats["meter_range"]:
        st.text(f"米数范围: {stats['meter_range'][0]:.2f}m ~ {stats['meter_range'][1]:.2f}m")

    # --- Defect list by position ---
    st.divider()
    st.subheader("缺陷明细 (按米数排序)")

    valid = sorted(
        [d for d in positioned if d["meter"] is not None],
        key=lambda d: d["meter"],
    )

    if valid:
        rows = []
        for d in valid[:200]:
            rows.append({
                "图片": d["image_name"],
                "米数": f"{d['meter']:.3f}",
                "类别": d["class_name"],
                "置信度": f"{d['confidence']:.3f}",
                "BBox": str(d["bbox"]),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if len(valid) > 200:
            st.caption(f"显示前 200 条，共 {len(valid)} 条")

    # --- Defect count per meter chart ---
    st.divider()
    st.subheader("缺陷密度趋势")

    binned = bin_defects_by_meter(valid, bin_size_m=bin_size)
    if not binned.empty:
        try:
            fig = px.bar(
                binned,
                x="meter_start",
                y="count",
                title=f"每 {bin_size}m 缺陷数量",
                labels={"meter_start": "起始米数 (m)", "count": "缺陷数量"},
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"图表渲染失败: {e}")
            st.dataframe(binned, use_container_width=True, hide_index=True)

    # --- Continuous defect segments ---
    st.divider()
    st.subheader("连续缺陷段")

    max_gap = st.number_input(
        "最大间断 (米)",
        min_value=0.1,
        max_value=10.0,
        value=0.5,
        step=0.1,
        key="pos_max_gap",
    )

    segments = detect_continuous_defect_segments(valid, max_gap_m=max_gap)
    if segments:
        seg_rows = []
        for seg in segments:
            seg_rows.append({
                "起始米数": f"{seg['start_meter']:.2f}",
                "结束米数": f"{seg['end_meter']:.2f}",
                "长度(m)": f"{seg['end_meter'] - seg['start_meter']:.2f}",
                "缺陷数": seg["defect_count"],
                "类别": ", ".join(sorted(seg["class_names"])),
            })
        st.dataframe(pd.DataFrame(seg_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("无连续缺陷段")

    # --- Class distribution by meter ---
    st.divider()
    st.subheader("分类分布 (按米数范围)")

    if "class_distribution" in stats and stats["class_distribution"]:
        dist_df = pd.DataFrame(
            {"类别": list(stats["class_distribution"].keys()), "数量": list(stats["class_distribution"].values())}
        ).sort_values("数量", ascending=False)
        st.dataframe(dist_df, use_container_width=True, hide_index=True)

        try:
            fig2 = px.pie(dist_df, values="数量", names="类别", title="缺陷类别分布")
            st.plotly_chart(fig2, use_container_width=True)
        except Exception:
            pass
    else:
        st.caption("无分类数据")
