"""Runtime mode definitions for the production runtime view.

The production runtime page is reused across the full workflow by
parameterizing its mode. Each mode controls:
- whether a model is required
- which model types are loaded
- which overlays are shown
- whether manual triage actions are available
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path


class RuntimeMode(Enum):
    SETUP_CAPTURE = "setup_capture"
    BASELINE_CAPTURE = "baseline_capture"
    ANOMALY_ASSISTED_CAPTURE = "anomaly_assisted_capture"
    HYBRID_CAPTURE = "hybrid_capture"
    STABLE_PRODUCTION = "stable_production"
    BENCHMARK_REPLAY = "benchmark_replay"


# Maps each runtime mode to its model requirements
RUNTIME_MODE_MODEL_REQUIREMENTS: dict[RuntimeMode, dict[str, bool]] = {
    RuntimeMode.SETUP_CAPTURE: {"yolo": False, "patchcore": False},
    RuntimeMode.BASELINE_CAPTURE: {"yolo": False, "patchcore": False},
    RuntimeMode.ANOMALY_ASSISTED_CAPTURE: {"yolo": False, "patchcore": True},
    RuntimeMode.HYBRID_CAPTURE: {"yolo": False, "patchcore": False},  # optional for both
    RuntimeMode.STABLE_PRODUCTION: {"yolo": False, "patchcore": False},  # at least one model required
    RuntimeMode.BENCHMARK_REPLAY: {"yolo": False, "patchcore": False},
}

# Which modes support manual OK/NG/Uncertain triage without a model
RUNTIME_MODE_MANUAL_TRIAGE: set[RuntimeMode] = {
    RuntimeMode.SETUP_CAPTURE,
    RuntimeMode.BASELINE_CAPTURE,
}

# Which modes can run with zero models loaded
RUNTIME_MODE_NO_MODEL_OK: set[RuntimeMode] = {
    RuntimeMode.SETUP_CAPTURE,
    RuntimeMode.BASELINE_CAPTURE,
    RuntimeMode.BENCHMARK_REPLAY,
}


def mode_requires_model(mode: RuntimeMode) -> bool:
    """Return True if mode cannot start without at least one model."""
    return mode not in RUNTIME_MODE_NO_MODEL_OK


def mode_allows_manual_triage(mode: RuntimeMode) -> bool:
    return mode in RUNTIME_MODE_MANUAL_TRIAGE


# -- Navigation routing ------------------------------------------------------

_SITE_CAPTURE_MODES: frozenset[RuntimeMode] = frozenset(
    {
        RuntimeMode.SETUP_CAPTURE,
        RuntimeMode.BASELINE_CAPTURE,
    }
)


def mode_targets_site_capture(mode: RuntimeMode) -> bool:
    """Return True if *mode* should open in site_capture rather than hybrid_runtime."""
    return mode in _SITE_CAPTURE_MODES


# -- Path resolver for C++ runtime state/config ---------------------------------


def cpp_runtime_paths(base_dir: Path, run_id: str) -> tuple[Path, Path]:
    """Return (state_path, config_path) scoped to a single run.

    Example:
        state, config = cpp_runtime_paths(Path("/data"), "run_001")
        # state  -> /data/runtime/run_001/state.json
        # config -> /data/runtime/run_001/config.json
    """
    runtime_dir = base_dir / "runtime" / run_id
    return runtime_dir / "state.json", runtime_dir / "config.json"


def validate_model_selection(
    mode: RuntimeMode,
    *,
    yolo_model_id: str = "",
    anomaly_model_id: str = "",
) -> bool:
    """Validate selected models for a runtime mode.

    Some modes require a specific model family, while hybrid/production only
    require at least one selected model.
    """
    requirements = RUNTIME_MODE_MODEL_REQUIREMENTS[mode]
    if requirements.get("yolo", False) and not yolo_model_id:
        return False
    if requirements.get("patchcore", False) and not anomaly_model_id:
        return False
    if mode_requires_model(mode) and not yolo_model_id and not anomaly_model_id:
        return False
    return True
