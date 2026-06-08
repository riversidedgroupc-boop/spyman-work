"""Camera controller abstract interface.

Defines the contract for line-scan camera operations during autofocus.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class CameraControllerBase(ABC):
    """Abstract line-scan camera controller.

    Provides methods for focus-specific image capture. Real implementations
    should handle encoder synchronization, exposure locking, and trigger modes.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the camera."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection. Must be idempotent."""
        ...

    @abstractmethod
    def lock_exposure_gain(self) -> None:
        """Lock exposure time and gain for consistent focus evaluation.

        Critical: during autofocus, exposure and gain MUST remain constant
        across all Z positions, otherwise clarity scores are not comparable.
        """
        ...

    @abstractmethod
    def set_focus_capture_mode(self) -> None:
        """Configure camera for focus capture mode.

        This should set:
        - Fixed trigger mode (e.g., encoder-synced line trigger)
        - Fixed ROI (full width for focus evaluation)
        - Appropriate line rate for the focus speed mode
        """
        ...

    @abstractmethod
    def capture_by_rows(self, row_count: int) -> np.ndarray:
        """Capture a fixed number of line-scan rows.

        Args:
            row_count: Number of lines to capture.

        Returns:
            2D numpy array (rows, cols) — the line-scan image.
        """
        ...

    @abstractmethod
    def capture_by_encoder_length(self, length_mm: float) -> np.ndarray:
        """Capture using encoder-triggered lines for a fixed physical length.

        Args:
            length_mm: Physical length in millimeters to capture.

        Returns:
            2D numpy array (rows, cols) — the line-scan image.
        """
        ...

    @abstractmethod
    def capture_focus_sample(
        self, length_mm: float, speed_mode: str
    ) -> np.ndarray:
        """Capture a complete focus sample at the current Z position.

        This is the primary method called by the autofocus pipeline.
        It handles: encoder sync, line capture, image assembly.

        Args:
            length_mm: Physical sample length in mm.
            speed_mode: "low_speed" or "normal" — affects line rate.

        Returns:
            2D numpy array — the assembled line-scan image.
        """
        ...

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Get camera status."""
        ...

    def set_z_position(self, z_mm: float) -> None:
        """Notify camera of current Z position for focus simulation.

        Default no-op. Mock implementations override this to simulate defocus blur.
        Real implementations may use this for internal bookkeeping.
        """
