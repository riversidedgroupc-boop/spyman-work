"""Manual review and sample feedback loop UI.

Phase 3: Allow humans to review detections and mark them for model iteration.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import pandas as pd
from PIL import Image

from core.review import (
    ReviewRecord,
    REVIEW_LABELS,
    create_review_record,
    save_review_records,
    load_review_records,
    summarize_review_records,
    DEFAULT_REVIEW_PATH,
)


def render_manual_review(
    predictions_by_image: dict | None = None,
    image_root: str = "data/images",
):
    """Render the manual review interface."""
    st.header("人工复核与样本回流")

    # --- Review records ---
    review_path = st.text_input(
        "复核记录文件路径",
        value=str(DEFAULT_REVIEW_PATH),
        key="review_path",
    )

    # Load existing records
    existing_records: list[ReviewRecord] = []
    try:
        existing_records = load_review_records(review_path)
    except Exception:
        pass

    # --- Review summary ---
    if existing_records:
        st.subheader("复核汇总")
        summary = summarize_review_records(existing_records)
        by_label = summary["by_label"]

        cols = st.columns(4)
        label_display = [
            ("真实缺陷", "true_defect"),
            ("误报", "false_positive"),
            ("可接受微缺陷", "acceptable_minor_defect"),
            ("未知缺陷", "unknown_defect"),
            ("标注错误", "label_error"),
            ("回流训练", "retrain_candidate"),
            ("忽略", "ignore"),
        ]
        for i, (display, key) in enumerate(label_display):
            with cols[i % 4]:
                st.metric(display, by_label.get(key, 0))

        st.divider()

    # --- New review ---
    st.subheader("新建复核")

    if predictions_by_image is None:
        st.info("暂无预测数据。请先运行模型推理，或手动输入复核信息。")
        # Manual entry fallback
        with st.expander("手动输入复核"):
            _manual_review_form(existing_records, review_path)
        return

    # Select an image to review
    image_names = sorted(predictions_by_image.keys())
    if not image_names:
        st.info("无预测结果可供复核。")
        return

    selected_image = st.selectbox("选择图片", image_names, key="review_select_img")

    if selected_image:
        detections = predictions_by_image.get(selected_image, [])

        # Show image
        img_path = Path(image_root) / selected_image
        if img_path.exists():
            try:
                img = Image.open(img_path)
                st.image(img, caption=selected_image, use_container_width=True)
            except Exception:
                st.warning(f"无法加载图片: {img_path}")

        if not detections:
            st.caption("该图片无检出")
        else:
            st.subheader(f"检出框 ({len(detections)})")

            for i, det in enumerate(detections):
                with st.container():
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.text(
                            f"#{i}: {det.class_name} | conf={det.confidence:.3f} | bbox={det.bbox}"
                        )
                    with col_b:
                        review_label = st.selectbox(
                            "标记",
                            REVIEW_LABELS,
                            key=f"review_label_{selected_image}_{i}",
                        )
                        reviewer_note = st.text_input(
                            "备注",
                            key=f"review_note_{selected_image}_{i}",
                        )

                        if st.button("保存", key=f"review_save_{selected_image}_{i}"):
                            rec = create_review_record(
                                image_name=selected_image,
                                detection_id=f"{selected_image}_det{i}",
                                class_name=det.class_name,
                                confidence=det.confidence,
                                bbox=det.bbox,
                                review_label=review_label,
                                reviewer_note=reviewer_note,
                            )
                            save_review_records([rec], review_path)
                            st.success(f"已保存: {review_label}")
                            st.rerun()

                    st.divider()

    # --- Export for retraining ---
    st.divider()
    st.subheader("样本回流导出")
    if st.button("导出回流样本", key="review_export_btn"):
        from core.sample_export import export_reviewed_samples

        out_dir = Path("outputs/sample_exports/review_export")
        result = export_reviewed_samples(
            existing_records,
            image_root=image_root,
            output_dir=out_dir,
            copy_images=True,
        )
        st.success(
            f"导出完成: {result['exported']} 条记录 → {result['output_dir']}\n"
            f"复制 {result['copied']} 张, 跳过 {result['skipped']} 张"
        )
        if result["errors"]:
            st.warning(f"错误: {result['errors'][:5]}")


def _manual_review_form(existing_records: list[ReviewRecord], review_path: str):
    """Fallback manual review form when no predictions are available."""
    img_name = st.text_input("图片名称", key="manual_img_name")
    class_name = st.text_input("缺陷类别", value="unknown", key="manual_class")
    confidence = st.slider("置信度", 0.0, 1.0, 0.5, key="manual_conf")
    bbox_str = st.text_input("BBox (x1,y1,x2,y2)", value="0,0,100,100", key="manual_bbox")
    review_label = st.selectbox("标记", REVIEW_LABELS, key="manual_label")
    note = st.text_input("备注", key="manual_note")

    if st.button("保存手动记录", key="manual_save"):
        try:
            bbox = [float(v.strip()) for v in bbox_str.split(",")]
            if len(bbox) != 4:
                st.error("BBox 格式错误，需要 4 个数值")
            else:
                rec = create_review_record(
                    image_name=img_name or "manual_entry",
                    detection_id=f"manual_{len(existing_records)}",
                    class_name=class_name,
                    confidence=confidence,
                    bbox=bbox,
                    review_label=review_label,
                    reviewer_note=note,
                )
                save_review_records([rec], review_path)
                st.success("已保存")
        except ValueError:
            st.error("BBox 数值解析失败")
