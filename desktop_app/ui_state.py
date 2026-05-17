"""Persist lightweight desktop UI state across launches."""
from __future__ import annotations

import json
import os
from typing import Any


def _state_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(base, "config")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "ui_state.json")


def load_ui_state() -> dict[str, Any]:
    path = _state_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_ui_state(**updates) -> None:
    state = load_ui_state()
    state.update(updates)
    with open(_state_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
