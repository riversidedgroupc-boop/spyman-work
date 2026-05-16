"""Streamlit UI for advanced evaluation metrics (mAP, PR curves, confusion matrix)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from core.schema import DetectionBox, ImagePrediction
from core.metrics import build_pr_curve, compute_map
from core.confusion import build_detection_confusion_matrix, MISSED_LABEL, BACKGROUND_LABEL
from src.dataset.label_schema import class_name_to_id


def _bbox_to_pixel_xyxy(bbox: list[float], image_path: str | Path) -> list[float]:
    """Convert normalized xyxy boxes to pixels, leaving pixel boxes unchanged."""
    values = [float(v) for v in bbox]
    if len(values) != 4:
        return values

    if not all(0.0 <= v <= 1.0 for v in values):
        return values

    from PIL import Image

    with Image.open(image_path) as img:
        width, height = img.size

    return [
        values[0] * width,
        values[1] * height,
        values[2] * width,
        values[3] * height,
    ]


def _class_id_from_name(class_name: str) -> int:
    """Return a stable class id for known labels, falling back to 0."""
    cid = class_name_to_id(class_name)
    return cid if cid >= 0 else 0


def _build_gt_from_records(records: list) -> dict[str, list[DetectionBox]]:
    """Convert Phase 1 ImageRecord annotations to DetectionBox dict."""
    gt_by_image: dict[str, list[DetectionBox]] = {}
    for rec in records:
        if not rec.has_annotation:
            continue
        img_name = Path(rec.image_path).name
        boxes = []
        for ann in rec.annotations:
            boxes.append(DetectionBox(
                image_name=img_name,
                class_id=_class_id_from_name(ann.class_name),
                class_name=ann.class_name,
                confidence=1.0,
                bbox=_bbox_to_pixel_xyxy(list(ann.bbox_xyxy), rec.image_path),
            ))
        gt_by_image[img_name] = boxes
    return gt_by_image


def _build_pred_from_external(predictions: list[ImagePrediction]) -> dict[str, list[DetectionBox]]:
    """Convert external ImagePrediction list to dict keyed by image name."""
    pred_by_image: dict[str, list[DetectionBox]] = {}
    for pred in predictions:
        pred_by_image[pred.image_name] = pred.detections
    return pred_by_image


def _build_pred_from_phase1(records: list) -> dict[str, list[DetectionBox]]:
    """Convert Phase 1 inference results to DetectionBox dict using YOLO results."""
    pred_by_image: dict[str, list[DetectionBox]] = {}
    for rec in records:
        img_name = Path(rec.image_path).name
        detections = []

        if rec.yolo_result:
            for p in rec.yolo_result.predictions:
                conf = p.confidence
                if p.score is not None:
                    conf = p.score
                detections.append(DetectionBox(
                    image_name=img_name,
                    class_id=_class_id_from_name(p.class_name),
                    class_name=p.class_name,
                    confidence=conf,
                    bbox=list(p.bbox_xyxy),
                ))

        pred_by_image[img_name] = detections
    return pred_by_image


def _collect_class_info(
    gt_by_image: dict[str, list[DetectionBox]],
    pred_by_image: dict[str, list[DetectionBox]],
) -> tuple[list[int], dict[int, str]]:
    """Collect unique class IDs and names from GT and predictions."""
    class_names: dict[int, str] = {}

    def _add_box(b: DetectionBox):
        if b.class_id not in class_names:
            class_names[b.class_id] = b.class_name

    for boxes in gt_by_image.values():
        for b in boxes:
            _add_box(b)
    for boxes in pred_by_image.values():
        for b in boxes:
            _add_box(b)

    class_ids = sorted(class_names.keys())
    return class_ids, class_names


def render_advanced_metrics(records=None, external_predictions=None):
    """Render the advanced evaluation metrics section.

    Parameters
    ----------
    records:
        Phase 1 ImageRecord list from batch evaluation.
    external_predictions:
        List of ``ImagePrediction`` from external model inference.
    """
    st.header("高级评估分析")

    # ------------------------------------------------------------------
    # Data source selection
    # ------------------------------------------------------------------
    data_source = st.radio(
        "预测数据来源",
        ["外部模型推理（新 Tab）", "Phase 1 批量推理 YOLO 结果"],
        key="adv_data_source",
        horizontal=True,
    )

    gt_by_image: dict[str, list[DetectionBox]] = {}
    pred_by_image: dict[str, list[DetectionBox]] = {}

    if data_source == "外部模型推理（新 Tab）":
        if not external_predictions:
            st.warning("暂无外部模型推理结果。请先在「外部模型推理」Tab 运行推理并点击「传递结果」。")
            return
        pred_by_image = _build_pred_from_external(external_predictions)
        if records:
            gt_by_image = _build_gt_from_records(records)
    else:
        if not records:
            st.warning("暂无 Phase 1 批量推理结果。请先在「批量评测」Tab 运行批量测试。")
            return
        gt_by_image = _build_gt_from_records(records)
        pred_by_image = _build_pred_from_phase1(records)

    if not gt_by_image:
        st.warning("无已标注样本。请确保数据集包含标注文件。")
        return

    if not pred_by_image:
        st.warning("无预测结果。")
        return

    # Collect class info
    class_ids, class_names = _collect_class_info(gt_by_image, pred_by_image)

    if not class_ids:
        st.warning("未检测到任何类别。")
        return

    st.success(
        f"已准备 {len(gt_by_image)} 张标注图片, "
        f"{sum(len(v) for v in pred_by_image.values())} 个预测框, "
        f"{len(class_ids)} 个类别"
    )

    # ------------------------------------------------------------------
    # IoU threshold
    # ------------------------------------------------------------------
    st.divider()
    col_iou, col_class = st.columns(2)

    with col_iou:
        iou_threshold = st.slider(
            "IoU 匹配阈值", 0.1, 0.95, 0.5, 0.05,
            key="adv_iou_threshold",
            help="IoU >= 此阈值视为匹配成功",
        )

    with col_class:
        selected_class_idx = st.selectbox(
            "选择类别查看 PR 曲线",
            list(range(len(class_ids))),
            format_func=lambda i: class_names.get(class_ids[i], f"class_{class_ids[i]}"),
            key="adv_selected_class",
        )

    selected_class_id = class_ids[selected_class_idx]

    # ------------------------------------------------------------------
    # mAP computation
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("mAP 指标")

    use_coco_range = st.checkbox(
        "mAP@0.5:0.95 (COCO 标准，10 个阈值)", value=True,
        key="adv_coco_range",
    )

    if use_coco_range:
        thresholds = np.arange(0.50, 1.0, 0.05).tolist()
    else:
        thresholds = [iou_threshold]

    map_result = compute_map(gt_by_image, pred_by_image, class_ids, thresholds)

    # Display mAP metrics
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("mAP", f"{map_result['map']:.4f}")
    with col_m2:
        st.metric("mAP@0.5", f"{map_result['map_50']:.4f}")
    with col_m3:
        count_gt = sum(
            sum(1 for b in boxes if b.class_id in set(class_ids))
            for boxes in gt_by_image.values()
        )
        st.metric("GT 框总数", count_gt)

    # Per-class table
    if map_result["per_class"]:
        st.subheader("各类别 AP")
        per_class_rows = []
        for cid, info in map_result["per_class"].items():
            per_class_rows.append({
                "类别": class_names.get(cid, f"class_{cid}"),
                "AP": f"{info['ap']:.4f}",
                "AP@0.5": f"{info['ap50']:.4f}",
                "GT 数量": info["num_gt"],
                "预测数量": info["num_predictions"],
            })
        st.dataframe(
            pd.DataFrame(per_class_rows),
            use_container_width=True,
            hide_index=True,
        )

    # Per-threshold table
    if len(thresholds) > 1:
        st.subheader("各 IoU 阈值 mAP")
        thr_rows = [{"IoU": f"{t:.2f}", "mAP": f"{v:.4f}"} for t, v in map_result["thresholds"].items()]
        st.dataframe(
            pd.DataFrame(thr_rows),
            use_container_width=True,
            hide_index=True,
        )

    # ------------------------------------------------------------------
    # PR Curve
    # ------------------------------------------------------------------
    st.divider()
    st.subheader(f"PR 曲线 — {class_names.get(selected_class_id, f'class_{selected_class_id}')}")

    pr_data = build_pr_curve(
        gt_by_image, pred_by_image,
        class_id=selected_class_id,
        iou_threshold=iou_threshold,
    )

    if pr_data["recall"] and pr_data["precision"]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pr_data["recall"],
            y=pr_data["precision"],
            mode="lines",
            fill="tozeroy",
            name=f"AP={pr_data['ap']:.4f}",
            line=dict(color="#1f77b4", width=2),
        ))
        fig.update_layout(
            title=f"PR Curve (IoU={iou_threshold})",
            xaxis_title="Recall",
            yaxis_title="Precision",
            xaxis_range=[0, 1],
            yaxis_range=[0, 1.05],
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.caption(f"AP@{iou_threshold}: {pr_data['ap']:.4f}")
    else:
        st.info(f"无数据绘制该类别的 PR 曲线（可能有 0 个 GT 或 0 个预测）。")

    # ------------------------------------------------------------------
    # Confusion Matrix
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("检测混淆矩阵")

    cm_df = build_detection_confusion_matrix(
        gt_by_image, pred_by_image,
        class_names=class_names,
        iou_threshold=iou_threshold,
    )

    # Display as heatmap
    fig_cm = px.imshow(
        cm_df.values,
        x=list(cm_df.columns),
        y=list(cm_df.index),
        text_auto=True,
        color_continuous_scale="Blues",
        aspect="auto",
    )
    fig_cm.update_layout(
        title="Detection Confusion Matrix",
        xaxis_title="Predicted",
        yaxis_title="Ground Truth",
        height=400 + 20 * len(class_ids),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig_cm, use_container_width=True)

    # Also show as table
    with st.expander("查看混淆矩阵表格"):
        st.dataframe(cm_df, use_container_width=True)

    # Summary statistics
    st.divider()
    st.subheader("误检/漏检统计")

    total_missed = int(cm_df[MISSED_LABEL].sum()) if MISSED_LABEL in cm_df.columns else 0
    total_bg = int(cm_df.loc[BACKGROUND_LABEL].sum()) if BACKGROUND_LABEL in cm_df.index else 0
    total_correct = int(cm_df.values.sum()) - total_missed - total_bg

    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.metric("正确匹配", total_correct)
    col_s2.metric("漏检 (FN)", total_missed)
    col_s3.metric("误检 (FP)", total_bg)

    if not pred_by_image or all(len(v) == 0 for v in pred_by_image.values()):
        st.info("当前无预测结果。运行外部模型推理以生成预测。")
