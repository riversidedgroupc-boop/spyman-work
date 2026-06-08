"""Serial port Z-axis stage controller.

Controls a Z-axis stage via serial port (RS232/RS485).
Currently a skeleton implementation — actual serial protocol commands
need to be filled in when the hardware protocol is known.
"""

from __future__ import annotations

import logging
from typing import Any

from line_scan_af.controllers.stage_controller_base import StageControllerBase

logger = logging.getLogger(__name__)


class SerialStageController(StageControllerBase):
    """Stage controller using serial port communication.

    TODO: Fill in actual serial protocol commands once the hardware
    communication protocol is specified. Currently implements the full
    interface with placeholder serial I/O.
    """

    def __init__(
        self,
        stage_id: str,
        port: str = "COM3",
        baudrate: int = 115200,
        timeout_s: float = 1.0,
        z_min_mm: float = 0.0,
        z_max_mm: float = 30.0,
    ) -> None:
        self._stage_id = stage_id
        self._port = port
        self._baudrate = baudrate
        self._timeout_s = timeout_s
        self._z_min = z_min_mm
        self._z_max = z_max_mm

        self._connected = False
        self._homed = False
        self._position: float = -1.0
        self._moving = False
        self._serial: Any = None  # serial.Serial instance when connected

    def connect(self) -> bool:
        try:
            import serial  # noqa: F811

            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=self._timeout_s,
            )
            self._connected = True
            logger.info("[%s] Serial stage connected on %s", self._stage_id, self._port)
            return True
        except Exception as e:
            logger.error("[%s] Serial connect failed: %s", self._stage_id, e)
            return False

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False
        self._homed = False
        logger.info("[%s] Serial stage disconnected", self._stage_id)

    def home(self) -> bool:
        if not self._connected:
            return False
        # TODO: Send actual homing command via serial
        logger.warning("[%s] Serial homing: protocol not implemented (TODO)", self._stage_id)
        self._homed = True
        self._position = self._z_min
        return True

    def is_homed(self) -> bool:
        return self._homed

    def move_to(self, z_mm: float) -> bool:
        if not self._connected:
            return False
        # Soft limit check
        if z_mm < self._z_min or z_mm > self._z_max:
            logger.error("[%s] Position %.3f out of bounds [%.1f, %.1f]", self._stage_id, z_mm, self._z_min, self._z_max)
            return False
        # TODO: Send actual move command via serial
        logger.debug("[%s] Serial move to %.3f mm (TODO: protocol)", self._stage_id, z_mm)
        self._moving = True
        return True

    def move_relative(self, dz_mm: float) -> bool:
        return self.move_to(self._position + dz_mm)

    def wait_until_done(self, timeout_s: float) -> bool:
        # TODO: Poll serial for move complete status
        self._moving = False
        return True

    def get_position(self) -> float:
        # TODO: Query actual position via serial
        return self._position

    def stop(self) -> None:
        # TODO: Send stop command via serial
        self._moving = False
        logger.info("[%s] Normal stop", self._stage_id)

    def emergency_stop(self) -> None:
        # TODO: Send emergency stop command via serial
        self._moving = False
        logger.warning("[%s] Emergency stop!", self._stage_id)

    def is_moving(self) -> bool:
        return self._moving

    def get_status(self) -> dict[str, Any]:
        return {
            "stage_id": self._stage_id,
            "connected": self._connected,
            "homed": self._homed,
            "position_mm": round(self._position, 3),
            "moving": self._moving,
            "error": None,
            "driver_type": "serial",
            "port": self._port,
        }
