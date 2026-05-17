"""Configurable sample classification labels."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


DEFAULT_LABELS = [
    {"value": "OK", "label": "OK", "color": "#2E7D32"},
    {"value": "NG_A", "label": "NG-A 缺陷", "color": "#C62828"},
    {"value": "NG_B", "label": "NG-B 缺陷", "color": "#E65100"},
    {"value": "UNKNOWN", "label": "未知", "color": "#6A1B9A"},
    {"value": "INTERFERENCE", "label": "干扰", "color": "#0277BD"},
    {"value": "UNCERTAIN", "label": "不确定", "color": "#F57F17"},
]


@dataclass(frozen=True)
class LabelOption:
    value: str
    label: str
    color: str


def _config_path() -> str:
    env_path = os.environ.get("COPPER_VISION_LABEL_CONFIG_PATH", "")
    if env_path:
        return env_path
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(base, "config")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "class_labels.json")


def load_label_options() -> list[LabelOption]:
    path = _config_path()
    raw = DEFAULT_LABELS
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                raw = loaded
        except Exception:
            raw = DEFAULT_LABELS

    labels: list[LabelOption] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        label = str(item.get("label", value)).strip()
        color = str(item.get("color", "#607D8B")).strip() or "#607D8B"
        if value and label:
            labels.append(LabelOption(value=value, label=label, color=color))
    return labels or [LabelOption(**item) for item in DEFAULT_LABELS]


def save_label_options(options: list[LabelOption]) -> None:
    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([option.__dict__ for option in options], f, ensure_ascii=False, indent=2)


def add_label(label: str, color: str = "#607D8B") -> LabelOption:
    label = label.strip()
    if not label:
        raise ValueError("label is required")
    options = load_label_options()
    existing_values = {opt.value for opt in options}
    value = _make_value(label, existing_values)
    option = LabelOption(value=value, label=label, color=color)
    options.append(option)
    save_label_options(options)
    return option


def remove_label(value: str) -> None:
    options = [opt for opt in load_label_options() if opt.value != value]
    save_label_options(options)


def label_text(value: str) -> str:
    for option in load_label_options():
        if option.value == value:
            return option.label
    return value


def label_color(value: str) -> str:
    for option in load_label_options():
        if option.value == value:
            return option.color
    return "#607D8B"


def _make_value(label: str, existing_values: set[str]) -> str:
    base = "".join(ch if ch.isalnum() else "_" for ch in label.strip()).strip("_").upper()
    if not base:
        base = "LABEL"
    value = base
    suffix = 2
    while value in existing_values:
        value = f"{base}_{suffix}"
        suffix += 1
    return value
