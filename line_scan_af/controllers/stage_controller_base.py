"""Z-axis stage controller abstract interface.

All hardware implementations (serial, mock, PLC, motion card) MUST inherit from
StageControllerBase and implement all abstract methods.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class StageControllerBase(ABC):
    """Abstract Z-axis stage controller.

    Each line-scan camera has one dedicated Z stage. This ABC defines the
    contract that all stage implementations must fulfill, enabling runtime
    switching between serial, PLC, motion card, and mock controllers.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the stage hardware.

        Returns:
            True if connection successful, False otherwise.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection and release resources. Must be idempotent."""
        ...

    @abstractmethod
    def home(self) -> bool:
        """Execute homing sequence.

        Returns:
            True if homing completed successfully.
        """
        ...

    @abstractmethod
    def is_homed(self) -> bool:
        """Check if stage has been homed.

        Returns:
            True if stage is homed and ready for absolute moves.
        """
        ...

    @abstractmethod
    def move_to(self, z_mm: float) -> bool:
        """Initiate absolute move to target Z position in mm.

        This method should return immediately after commanding the move;
        call wait_until_done() to block until the move completes.

        Args:
            z_mm: Target position in millimeters.

        Returns:
            True if command was accepted.
        """
        ...

    @abstractmethod
    def move_relative(self, dz_mm: float) -> bool:
        """Initiate relative move by dz_mm.

        Args:
            dz_mm: Distance to move in mm (positive = away from tube).

        Returns:
            True if command was accepted.
        """
        ...

    @abstractmethod
    def wait_until_done(self, timeout_s: float) -> bool:
        """Block until the current move completes or timeout expires.

        Args:
            timeout_s: Maximum time to wait in seconds.

        Returns:
            True if move completed within timeout, False if timed out.
        """
        ...

    @abstractmethod
    def get_position(self) -> float:
        """Get current Z position in mm.

        Returns:
            Current position. Returns -1.0 if position is unknown.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Normal stop — decelerate and hold position."""
        ...

    @abstractmethod
    def emergency_stop(self) -> None:
        """Emergency stop — cut power / immediate halt. Must be callable at any time."""
        ...

    @abstractmethod
    def is_moving(self) -> bool:
        """Check if stage is currently in motion.

        Returns:
            True if stage is moving.
        """
        ...

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Get comprehensive stage status.

        Returns:
            Dict with keys: connected, homed, position_mm, moving, error, status_text.
        """
        ...

    # ---- Template method: backlash-compensated approach ----

    def move_to_with_backlash_compensation(
        self, target_z_mm: float, backlash_mm: float
    ) -> bool:
        """Move to target using single-direction approach to eliminate backlash.

        Strategy: approach from below (negative direction), so overshoot past
        the target by backlash_mm, then move forward to the target. This ensures
        the final approach is always in the same direction.

        Args:
            target_z_mm: Desired Z position.
            backlash_mm: Backlash compensation distance.

        Returns:
            True if move completed successfully.
        """
        current_z = self.get_position()
        approach_z = target_z_mm - backlash_mm

        # If we are above the approach point, move below it first
        if current_z > approach_z:
            logger.debug(
                "Backlash comp: moving from %.3f to approach %.3f",
                current_z,
                approach_z,
            )
            if not self.move_to(approach_z):
                logger.error("Backlash comp: approach move failed")
                return False
            if not self.wait_until_done(timeout_s=5.0):
                logger.error("Backlash comp: approach move timed out")
                return False

        # Final move to target (always approaching from below)
        logger.debug("Backlash comp: final move to %.3f", target_z_mm)
        if not self.move_to(target_z_mm):
            logger.error("Backlash comp: final move failed")
            return False

        return self.wait_until_done(timeout_s=5.0)
