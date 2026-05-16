"""Tests for ONNX runner guardrails."""

from __future__ import annotations

import numpy as np
import pytest

from model_runners.onnx_runner import OnnxModelRunner


def test_onnx_runner_rejects_channel_first_yolo_layout():
    runner = OnnxModelRunner("model.onnx")
    output = np.zeros((1, 84, 8400), dtype=np.float32)

    with pytest.raises(ValueError, match="Unsupported YOLO ONNX layout"):
        runner._parse_yolo_output(output, img_w=640, img_h=640)

