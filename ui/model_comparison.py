"""Multi-model comparison UI for Phase 3."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.cache import (
    build_prediction_cache_key,
    has_prediction_cache,
    load_predictions,
    save_predictions,
)
from core.deployment_metrics import compute_deployment_summary
from core.schema import DetectionBox, ImagePrediction
from model_runners.registry import get_runner
from src.utils.file_utils import collect_images


def _predictions_to_dict(results: list[ImagePrediction] | None) -> dict[str, list[DetectionBox]]:
    """Convert ImagePrediction results to dict keyed by image name."""
    out: dict[str, list[DetectionBox]] = {}
    for pred in results or []:
        image_name = getattr(pred, "image_name", "")
        if image_name:
            out[image_name] = list(getattr(pred, "detections", []) or [])
    return out


def _load_prediction_file(path: str | Path) -> list[ImagePrediction]:
    """Load cached/exported prediction JSON into ImagePrediction objects."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    predictions: list[ImagePrediction] = []
    for item in data:
        image_name = item.get("image_name", "")
        detections = []
        for det in item.get("detections", []):
            detections.append(
                DetectionBox(
                    image_name=det.get("image_name") or image_name,
                    class_id=int(det.get("class_id", 0)),
                    class_name=str(det.get("class_name", "defect")),
                    confidence=float(det.get("confidence", 0.0)),
                    bbox=list(det.get("bbox", [0, 0, 0, 0])),
                )
            )
        predictions.append(ImagePrediction(image_name=image_name, detections=detections))
    return predictions


def _run_model(run: dict[str, Any], image_root: str, use_cache: bool) -> tuple[list[ImagePrediction], dict]:
    """Run one registered model or load a prediction file."""
    model_type = str(run.get("model_type", "")).lower()
    model_path = str(run.get("model_path", "")).strip()

    if model_type == "prediction_file":
        if not model_path or not Path(model_path).exists():
            raise FileNotFoundError(f"Prediction file not found: {model_path}")
        t0 = time.perf_counter()
        predictions = _load_prediction_file(model_path)
        total_ms = (time.perf_counter() - t0) * 1000.0
        avg_ms = total_ms / max(len(predictions), 1)
        return predictions, {"avg_ms": avg_ms, "total_ms": total_ms}

    if model_type not in {"yolo", "onnx"}:
        raise ValueError(f"Unsupported model type for automatic inference: {run.get('model_type')}")

    if not model_path or not Path(model_path).exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not image_root or not Path(image_root).exists():
        raise FileNotFoundError(f"Image folder not found: {image_root}")

    image_paths = collect_images(image_root)
    if not image_paths:
        raise FileNotFoundError(f"No images found in: {image_root}")

    device = str(run.get("device", "cpu")).lower()
    if device.startswith("cuda"):
        device = "cuda"

    config = {
        "confidence": float(run.get("confidence", 0.25)),
        "iou": float(run.get("iou", 0.45)),
        "image_size": int(run.get("image_size", 640)),
        "device": device,
    }
    if model_type == "onnx":
        config["output_format"] = "yolo_nx"

    cache_key = build_prediction_cache_key(model_path, image_root, config, None)
    if use_cache and has_prediction_cache(cache_key):
        predictions = load_predictions(cache_key)
        return predictions, {
            "avg_ms": 0.0,
            "total_ms": 0.0,
            "cache_hit": True,
            "num_images": len(predictions),
        }

    runner_cls = get_runner(model_type)
    runner = runner_cls(model_path, None, config)
    runner.load()

    predictions: list[ImagePrediction] = []
    progress = st.progress(0)
    status = st.empty()
    t0 = time.perf_counter()
    failed = 0
    total = len(image_paths)

    for idx, image_path in enumerate(image_paths, start=1):
        status.text(f"Running {run['model_name']}: {Path(image_path).name} ({idx}/{total})")
        try:
            predictions.append(runner.predict_image(image_path))
        except Exception as exc:
            failed += 1
            st.warning(f"Inference failed for {Path(image_path).name}: {exc}")
            predictions.append(ImagePrediction(image_name=Path(image_path).name, detections=[]))
        progress.progress(idx / total)

    total_ms = (time.perf_counter() - t0) * 1000.0
    progress.empty()
    status.empty()

    save_predictions(cache_key, predictions)
    return predictions, {
        "avg_ms": total_ms / max(total, 1),
        "total_ms": total_ms,
        "failed": failed,
        "num_images": total,
        "cache_hit": False,
    }


def render_model_comparison(
    ground_truths_by_image: dict[str, list[DetectionBox]] | None = None,
    image_root: str = "data/images",
):
    """Render the multi-model comparison section."""
    st.header("多模型对比分析")

    if "model_run_registry" not in st.session_state:
        st.session_state.model_run_registry = []

    registry = st.session_state.model_run_registry

    with st.expander("添加模型运行", expanded=len(registry) == 0):
        col1, col2, col3 = st.columns(3)
        with col1:
            model_name = st.text_input("模型名称", value="", key="cmp_model_name")
            model_type = st.selectbox(
                "模型类型",
                ["YOLO", "ONNX", "prediction_file", "custom"],
                key="cmp_model_type",
            )
        with col2:
            model_path = st.text_input("模型路径/预测文件", value="", key="cmp_model_path")
            confidence = st.slider("Confidence", 0.01, 1.0, 0.25, 0.01, key="cmp_conf")
        with col3:
            iou_thr = st.slider("NMS IoU", 0.1, 0.9, 0.45, 0.05, key="cmp_iou")
            image_size = st.number_input("Image Size", 320, 1920, 640, 32, key="cmp_img_size")
            device = st.selectbox("Device", ["cpu", "cuda:0"], key="cmp_device")

        if st.button("添加模型运行", key="cmp_add_run"):
            if model_name:
                registry.append(
                    {
                        "run_id": uuid.uuid4().hex[:8],
                        "model_name": model_name,
                        "model_type": model_type,
                        "model_path": model_path,
                        "confidence": confidence,
                        "iou": iou_thr,
                        "image_size": image_size,
                        "device": device,
                        "predictions": None,
                        "metrics": {},
                        "timing": {},
                    }
                )
                st.session_state.model_run_registry = registry
                st.success(f"已添加模型运行: {model_name}")
                st.rerun()
            else:
                st.warning("请输入模型名称")

    if not registry:
        st.info("尚未添加模型运行。请先添加至少一个模型。")
        return

    st.subheader(f"已注册模型运行 ({len(registry)})")
    for i, run in enumerate(registry):
        col_a, col_b = st.columns([5, 1])
        with col_a:
            status = "done" if run.get("predictions") is not None else "pending"
            st.text(
                f"{run['model_name']} | {run['model_type']} | conf={run['confidence']} | "
                f"IoU={run['iou']} | {status}"
            )
        with col_b:
            if st.button("删除", key=f"cmp_del_{i}"):
                registry.pop(i)
                st.session_state.model_run_registry = registry
                st.rerun()

    st.divider()
    use_cache = st.checkbox("使用推理缓存", value=True, key="cmp_use_cache")
    selected_run_id = st.selectbox(
        "选择要运行的模型",
        [r["run_id"] for r in registry],
        format_func=lambda rid: next(r["model_name"] for r in registry if r["run_id"] == rid),
        key="cmp_selected_run",
    )

    col_run, col_all, _ = st.columns([2, 2, 4])
    with col_run:
        run_selected = st.button("运行选中模型", key="cmp_run_selected")
    with col_all:
        run_all = st.button("运行所有模型", key="cmp_run_all")

    if run_selected or run_all:
        targets = registry if run_all else [r for r in registry if r["run_id"] == selected_run_id]
        for run in targets:
            with st.spinner(f"运行 {run['model_name']} ..."):
                try:
                    predictions, timing = _run_model(run, image_root, use_cache=use_cache)
                    run["predictions"] = predictions
                    run["timing"] = timing
                    st.success(
                        f"{run['model_name']} 完成: {len(predictions)} 张, "
                        f"avg={timing.get('avg_ms', 0):.1f} ms/img"
                    )
                except Exception as exc:
                    st.error(f"{run['model_name']} 运行失败: {exc}")
        st.session_state.model_run_registry = registry

    if not any(r.get("predictions") is not None for r in registry):
        return

    ground_truths = ground_truths_by_image or {}

    st.subheader("模型对比表")
    rows = []
    for run in registry:
        preds = run.get("predictions")
        if preds is None:
            rows.append(
                {
                    "Model": run["model_name"],
                    "Miss Rate": "N/A",
                    "False Alarms": "N/A",
                    "FP/m": "N/A",
                    "Review Load": "N/A",
                    "Avg ms/img": "N/A",
                    "Notes": "未运行",
                }
            )
            continue

        preds_dict = _predictions_to_dict(preds)
        timing_list = [float(run.get("timing", {}).get("avg_ms", 0.0))]
        dep_summary = compute_deployment_summary(ground_truths, preds_dict, timing_list=timing_list)
        run["metrics"] = dep_summary
        rows.append(
            {
                "Model": run["model_name"],
                "Miss Rate": f"{dep_summary.get('miss_rate', 0):.3f}",
                "False Alarms": dep_summary.get("false_positives", "N/A"),
                "FP/m": dep_summary.get("false_alarms_per_meter", "N/A"),
                "Review Load": f"{dep_summary.get('review_load_ratio', 0):.1%}",
                "Avg ms/img": f"{run.get('timing', {}).get('avg_ms', 0):.1f}",
                "Notes": "cache" if run.get("timing", {}).get("cache_hit") else "",
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("推荐")
    valid_runs = [r for r in registry if r.get("predictions") is not None]
    if valid_runs and ground_truths:
        best = min(valid_runs, key=lambda r: r.get("metrics", {}).get("miss_rate", 1.0))
        summary = best.get("metrics", {})
        miss_rate = summary.get("miss_rate", 0.0)
        fp_per_m = summary.get("false_alarms_per_meter")
        avg_ms = best.get("timing", {}).get("avg_ms", 0.0)

        if miss_rate > 0.05:
            recommendation = "不建议上线：漏检率偏高"
        elif fp_per_m is not None and fp_per_m > 1.0:
            recommendation = "需要调优：误报负载偏高"
        elif avg_ms > 50:
            recommendation = "需要加速：推理时间超标"
        else:
            recommendation = "可作为试运行候选"

        st.info(f"**模型上线建议**: {recommendation}")
        col_c1, col_c2, col_c3 = st.columns(3)
        col_c1.metric("最低漏检率", f"{miss_rate:.1%}", delta=f"模型: {best['model_name']}")
        col_c2.metric("平均推理", f"{avg_ms:.0f}ms")
        col_c3.metric("复核比例", f"{summary.get('review_load_ratio', 0):.1%}")
    elif valid_runs:
        st.info("已完成推理。导入标注后可计算漏检率并给出上线建议。")
