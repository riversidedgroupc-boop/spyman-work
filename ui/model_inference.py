"""Streamlit UI for external model inference (YOLO .pt, ONNX .onnx)."""

from __future__ import annotations

import time
from pathlib import Path

import streamlit as st
import pandas as pd

from core.schema import ImagePrediction
from core.cache import (
    build_prediction_cache_key,
    save_predictions,
    load_predictions,
    has_prediction_cache,
    clear_cache,
)
from model_runners.registry import list_supported_runners, get_runner
from src.utils.file_utils import collect_images


def render_model_inference():
    """Render the external model inference section."""
    st.header("外部模型推理")

    # ------------------------------------------------------------------
    # Model selection
    # ------------------------------------------------------------------
    col_model, col_device = st.columns([2, 1])

    with col_model:
        runners_meta = list_supported_runners()
        runner_options = {m["name"]: m["type"] for m in runners_meta}
        selected_name = st.selectbox(
            "模型类型",
            list(runner_options.keys()),
            key="ext_model_type",
        )
        model_type = runner_options[selected_name]

    with col_device:
        _cuda_available = False
        try:
            import torch
            _cuda_available = torch.cuda.is_available()
        except ImportError:
            pass

        device = st.selectbox(
            "推理设备",
            ["CPU", "CUDA"],
            index=1 if _cuda_available else 0,
            key="ext_device",
        )

    # ------------------------------------------------------------------
    # Model path & class names
    # ------------------------------------------------------------------
    col_path, col_class = st.columns(2)

    with col_path:
        model_path = st.text_input(
            "模型文件路径",
            value="models/yolo/best.pt",
            key="ext_model_path",
        )

    with col_class:
        class_mode = st.radio(
            "类别名称来源",
            ["使用模型内置名称", "手动输入"],
            key="ext_class_mode",
            horizontal=True,
        )

    class_names: dict[int, str] | None = None
    if class_mode == "手动输入":
        class_text = st.text_area(
            "类别名称（每行一个，从 class_id=0 开始）",
            value="",
            placeholder="scratch\ndent\npit\nstain",
            key="ext_class_names",
            height=120,
        )
        if class_text.strip():
            lines = [l.strip() for l in class_text.strip().splitlines() if l.strip()]
            class_names = {i: name for i, name in enumerate(lines)}
    else:
        class_names = None  # runner will use model's built-in names

    # ------------------------------------------------------------------
    # Image folder
    # ------------------------------------------------------------------
    image_folder = st.text_input(
        "图片目录",
        value="data/images",
        key="ext_image_folder",
    )

    # ------------------------------------------------------------------
    # Inference parameters
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("推理参数")

    col_c1, col_c2, col_c3 = st.columns(3)

    with col_c1:
        confidence = st.slider(
            "置信度阈值", 0.01, 1.0, 0.25, 0.01,
            key="ext_confidence",
        )
    with col_c2:
        nms_iou = st.slider(
            "NMS IoU 阈值", 0.1, 1.0, 0.45, 0.05,
            key="ext_nms_iou",
        )
    with col_c3:
        image_size = st.selectbox(
            "推理尺寸", [320, 416, 512, 640, 768, 1024],
            index=3,
            key="ext_image_size",
        )

    # ------------------------------------------------------------------
    # Cache controls
    # ------------------------------------------------------------------
    st.divider()
    col_cache1, col_cache2 = st.columns([3, 1])

    with col_cache1:
        use_cache = st.checkbox("使用缓存结果", value=True, key="ext_use_cache")
    with col_cache2:
        if st.button("清除当前缓存", key="ext_clear_cache"):
            if "ext_cache_key" in st.session_state:
                clear_cache(st.session_state.ext_cache_key)
                st.session_state.pop("ext_predictions", None)
                st.session_state.pop("external_predictions", None)
                st.success("缓存已清除")

    # ------------------------------------------------------------------
    # Run inference
    # ------------------------------------------------------------------
    st.divider()

    run_clicked = st.button(
        "🚀 开始推理", type="primary", use_container_width=True,
        key="ext_run_inference",
    )

    if run_clicked:
        if not model_path or not Path(model_path).exists():
            st.error(f"模型文件不存在: {model_path}")
            return

        if not image_folder or not Path(image_folder).exists():
            st.error(f"图片目录不存在: {image_folder}")
            return

        # Collect images
        image_paths = collect_images(image_folder)
        if not image_paths:
            st.error(f"图片目录无图片文件: {image_folder}")
            return

        st.info(f"找到 {len(image_paths)} 张图片")

        # Build config dict
        config = {
            "confidence": confidence,
            "iou": nms_iou,
            "image_size": image_size,
            "device": device.lower(),
        }
        if model_type == "onnx":
            config["output_format"] = "yolo_nx"

        # Cache key
        cache_key = build_prediction_cache_key(
            model_path, image_folder, config, class_names,
        )
        st.session_state.ext_cache_key = cache_key

        # Try cache
        if use_cache and has_prediction_cache(cache_key):
            with st.spinner("正在加载缓存结果..."):
                predictions = load_predictions(cache_key)
                st.session_state.ext_predictions = predictions
                st.session_state.external_predictions = predictions
                st.success(f"已从缓存加载 {len(predictions)} 张图片的预测结果")
            return

        # Run inference
        try:
            runner_cls = get_runner(model_type)
            runner = runner_cls(model_path, class_names, config)
            runner.load()
        except ImportError as e:
            st.error(f"依赖缺失: {e}")
            return
        except Exception as e:
            st.error(f"模型加载失败: {e}")
            return

        progress_bar = st.progress(0)
        status_text = st.empty()

        predictions: list[ImagePrediction] = []
        total = len(image_paths)
        failed = 0

        t_start = time.perf_counter()
        for i, img_path in enumerate(image_paths):
            status_text.text(f"推理中: {Path(img_path).name} ({i + 1}/{total})")
            try:
                pred = runner.predict_image(img_path)
                predictions.append(pred)
            except Exception as e:
                st.warning(f"推理失败 {Path(img_path).name}: {e}")
                failed += 1
                predictions.append(ImagePrediction(
                    image_name=Path(img_path).name,
                    detections=[],
                ))
            progress_bar.progress((i + 1) / total)

        elapsed = time.perf_counter() - t_start
        status_text.text(
            f"推理完成: {len(predictions)} 张, "
            f"失败 {failed} 张, 耗时 {elapsed:.1f}s"
        )

        # Save to cache
        if predictions:
            save_predictions(cache_key, predictions)
            st.success(f"预测结果已缓存 ({len(predictions)} 张)")

        st.session_state.ext_predictions = predictions
        st.session_state.external_predictions = predictions

    # ------------------------------------------------------------------
    # Display results
    # ------------------------------------------------------------------
    if "ext_predictions" not in st.session_state or not st.session_state.ext_predictions:
        return

    predictions = st.session_state.ext_predictions
    st.divider()
    st.subheader("推理结果")

    # Summary
    total_dets = sum(len(p.detections) for p in predictions)
    images_with_dets = sum(1 for p in predictions if p.detections)

    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.metric("推理图片数", len(predictions))
    col_s2.metric("总检出数", total_dets)
    col_s3.metric("有检出的图片数", images_with_dets)

    # Per-image detection count distribution
    if total_dets > 0:
        st.divider()
        st.subheader("检出分布")

        det_counts = [len(p.detections) for p in predictions]
        import numpy as np

        df_dist = pd.DataFrame({
            "统计量": ["最小值", "最大值", "均值", "中位数"],
            "值": [
                np.min(det_counts),
                np.max(det_counts),
                f"{np.mean(det_counts):.1f}",
                f"{np.median(det_counts):.1f}",
            ],
        })
        st.dataframe(df_dist, use_container_width=True, hide_index=True)

    # Preview table (first 100 detections)
    if total_dets > 0:
        st.divider()
        st.subheader("预测结果预览")

        rows = []
        for pred in predictions[:50]:
            for d in pred.detections:
                rows.append({
                    "图片": d.image_name,
                    "类别ID": d.class_id,
                    "类别": d.class_name,
                    "置信度": f"{d.confidence:.3f}",
                    "bbox": f"[{d.bbox[0]:.0f}, {d.bbox[1]:.0f}, {d.bbox[2]:.0f}, {d.bbox[3]:.0f}]",
                })
                if len(rows) >= 100:
                    break
            if len(rows) >= 100:
                break

        if rows:
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )
            if total_dets > 100:
                st.caption(f"显示前 100 条检测，共 {total_dets} 条")

    # Store normalized predictions for downstream use
    if st.button("📤 将预测结果传递给评估模块", use_container_width=True):
        st.session_state.external_predictions = predictions
        st.success("预测结果已传递！请前往「高级评估分析」Tab 查看指标。")
