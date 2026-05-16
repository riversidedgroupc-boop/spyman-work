"""Tests for YOLO runner device handling."""

from __future__ import annotations

import os

from src.inference.yolo_runner import YoloRunner


def test_auto_device_falls_back_to_cpu_without_cuda(monkeypatch):
    class _Cuda:
        @staticmethod
        def is_available() -> bool:
            return False

    class _Torch:
        cuda = _Cuda()

    import src.inference.yolo_runner as yolo_runner

    fake_torch = _Torch()
    monkeypatch.setattr(yolo_runner, "torch", fake_torch)
    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)

    runner = YoloRunner({"device": "auto"})

    assert runner.device_str == "cpu"
    assert runner.device == "cpu"
    # Restore real torch
    monkeypatch.undo()


def test_ultralytics_config_dir_defaults_to_project_outputs(monkeypatch):
    monkeypatch.delenv("YOLO_CONFIG_DIR", raising=False)

    YoloRunner._ensure_ultralytics_config_dir()

    assert os.environ["YOLO_CONFIG_DIR"].endswith(r"outputs\ultralytics")
