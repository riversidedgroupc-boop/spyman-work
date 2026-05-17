"""Display labels for internal enum values used by the desktop UI."""
from __future__ import annotations


PROJECT_TYPE_OPTIONS = [
    ("surface_inspection", "表面检测"),
    ("dimensional", "尺寸检测"),
    ("assembly", "装配检测"),
    ("other", "其他"),
]

PROJECT_STATUS_OPTIONS = [
    ("active", "进行中"),
    ("paused", "暂停"),
    ("completed", "已完成"),
    ("archived", "已归档"),
]

SESSION_STATUS_OPTIONS = [
    ("created", "已创建"),
    ("running", "运行中"),
    ("completed", "已完成"),
    ("cancelled", "已取消"),
    ("failed", "失败"),
]

TRAINING_STATUS_OPTIONS = [
    ("created", "已创建"),
    ("queued", "排队中"),
    ("running", "训练中"),
    ("completed", "已完成"),
    ("failed", "失败"),
    ("candidate", "候选"),
    ("archived", "已归档"),
]

MODEL_STATUS_OPTIONS = [
    ("created", "已创建"),
    ("training", "训练中"),
    ("completed", "已完成"),
    ("evaluating", "评估中"),
    ("evaluated", "已评估"),
    ("verified", "已验证"),
    ("candidate", "候选"),
    ("active", "已启用"),
    ("rolled_back", "已回退"),
    ("archived", "已归档"),
]

MODEL_TYPE_OPTIONS = [
    ("yolo", "YOLO"),
    ("onnx", "ONNX"),
    ("patchcore", "PatchCore"),
]

CLASS_LABEL_OPTIONS = [
    ("OK", "OK"),
    ("NG_A", "NG-A 缺陷"),
    ("NG_B", "NG-B 缺陷"),
    ("UNKNOWN", "未知"),
    ("INTERFERENCE", "干扰"),
    ("UNCERTAIN", "不确定"),
]

PLC_METHOD_OPTIONS = [
    ("tcp_socket", "TCP Socket"),
    ("modbus_tcp", "Modbus TCP"),
    ("serial_port", "串口"),
    ("http", "HTTP"),
]


def label_for(options: list[tuple[str, str]], value: str) -> str:
    return dict(options).get(value, value)


def value_for(options: list[tuple[str, str]], label: str) -> str:
    reverse = {display: value for value, display in options}
    return reverse.get(label, label)


def project_type_label(value: str) -> str:
    return label_for(PROJECT_TYPE_OPTIONS, value)


def project_status_label(value: str) -> str:
    return label_for(PROJECT_STATUS_OPTIONS, value)


def session_status_label(value: str) -> str:
    return label_for(SESSION_STATUS_OPTIONS, value)


def training_status_label(value: str) -> str:
    return label_for(TRAINING_STATUS_OPTIONS, value)


def model_status_label(value: str) -> str:
    return label_for(MODEL_STATUS_OPTIONS, value)


def model_type_label(value: str) -> str:
    return label_for(MODEL_TYPE_OPTIONS, value)


def class_label(value: str) -> str:
    try:
        from desktop_app.label_config import label_text

        return label_text(value)
    except Exception:
        return label_for(CLASS_LABEL_OPTIONS, value)
