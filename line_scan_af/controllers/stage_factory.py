"""Stage controller factory with registration pattern.

Supports runtime selection of stage driver type (mock, serial, plc, motion_card)
via configuration, so the AF pipeline never depends on a specific implementation.
"""

from __future__ import annotations

import logging
from typing import Any

from line_scan_af.controllers.stage_controller_base import StageControllerBase

logger = logging.getLogger(__name__)

# Global registry: driver_type_name -> controller class
_stage_registry: dict[str, type[StageControllerBase]] = {}


def register_stage_type(name: str, cls: type[StageControllerBase]) -> None:
    """Register a stage controller class for a given driver type name."""
    _stage_registry[name] = cls
    logger.debug("Registered stage driver type: %s -> %s", name, cls.__name__)


def create_stage(
    stage_id: str,
    driver_type: str,
    driver_config: dict[str, Any],
    motion_config: dict[str, Any] | None = None,
) -> StageControllerBase:
    """Create a stage controller instance based on configuration.

    Args:
        stage_id: Unique identifier for this stage (e.g. "Z_STAGE_1").
        driver_type: One of "mock", "serial", "plc", "motion_card".
        driver_config: Driver-specific configuration dict.
        motion_config: Default motion parameters (z_min, z_max, etc.).

    Returns:
        A StageControllerBase instance.

    Raises:
        ValueError: If driver_type is not registered.
    """
    if driver_type not in _stage_registry:
        raise ValueError(
            f"Unknown stage driver type '{driver_type}'. "
            f"Available: {list(_stage_registry.keys())}"
        )

    cls = _stage_registry[driver_type]
    motion = motion_config or {}

    if driver_type == "mock":
        from line_scan_af.controllers.mock_stage_controller import MockStageController

        return MockStageController(
            stage_id=stage_id,
            z_min_mm=motion.get("z_min_mm", 0.0),
            z_max_mm=motion.get("z_max_mm", 30.0),
        )

    elif driver_type == "serial":
        from line_scan_af.controllers.serial_stage_controller import SerialStageController

        return SerialStageController(
            stage_id=stage_id,
            port=driver_config.get("port", "COM3"),
            baudrate=driver_config.get("baudrate", 115200),
            timeout_s=driver_config.get("timeout_s", 1.0),
            z_min_mm=motion.get("z_min_mm", 0.0),
            z_max_mm=motion.get("z_max_mm", 30.0),
        )

    elif driver_type == "plc":
        from line_scan_af.controllers.plc_stage_controller import PlcStageController

        return PlcStageController(
            stage_id=stage_id,
            plc_address=driver_config.get("plc_address", "192.168.1.100"),
            plc_protocol=driver_config.get("plc_protocol", "modbus_tcp"),
            z_min_mm=motion.get("z_min_mm", 0.0),
            z_max_mm=motion.get("z_max_mm", 30.0),
        )

    elif driver_type == "motion_card":
        from line_scan_af.controllers.motion_card_stage_controller import MotionCardStageController

        return MotionCardStageController(
            stage_id=stage_id,
            card_type=driver_config.get("card_type", "galil"),
            axis=driver_config.get("axis", 0),
            z_min_mm=motion.get("z_min_mm", 0.0),
            z_max_mm=motion.get("z_max_mm", 30.0),
        )

    else:
        raise ValueError(f"Unhandled driver type: {driver_type}")


# ---- Register known types ----
def _register_defaults() -> None:
    """Register all built-in stage controller types."""
    from line_scan_af.controllers.mock_stage_controller import MockStageController
    from line_scan_af.controllers.serial_stage_controller import SerialStageController
    from line_scan_af.controllers.plc_stage_controller import PlcStageController
    from line_scan_af.controllers.motion_card_stage_controller import MotionCardStageController

    register_stage_type("mock", MockStageController)
    register_stage_type("serial", SerialStageController)
    register_stage_type("plc", PlcStageController)
    register_stage_type("motion_card", MotionCardStageController)


_register_defaults()
