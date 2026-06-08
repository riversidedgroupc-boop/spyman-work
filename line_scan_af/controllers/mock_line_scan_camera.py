"""Mock line-scan camera for development without hardware.

Generates synthetic tube-surface images with a known best-focus Z position
for algorithm validation.
"""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from line_scan_af.controllers.camera_controller_base import CameraControllerBase

logger = logging.getLogger(__name__)


class MockLineScanCamera(CameraControllerBase):
    """Simulates a line-scan camera with synthetic tube surface images.

    Generates images where clarity varies with Z position:
    - At z=best_focus_z, the image is sharpest
    - As |z - best_focus_z| increases, Gaussian blur increases
    - This allows testing the AF algorithm with a known ground truth

    The synthetic image contains:
    - Random surface texture (Perlin-noise-like)
    - High-frequency details (fine scratches)
    - Edge features (simulated tube boundaries)
    """

    def __init__(
        self,
        camera_id: str = "mock_cam",
        image_width: int = 2048,
        image_height: int = 512,
        best_focus_z: float = 12.35,
        blur_scale: float = 2.0,  # sigma = |z - best| * blur_scale
        simulate_overexpose: bool = False,
        simulate_underexpose: bool = False,
        seed: int = 42,
    ) -> None:
        self._camera_id = camera_id
        self._width = image_width
        self._height = image_height
        self._best_focus_z = best_focus_z
        self._blur_scale = blur_scale
        self._simulate_overexpose = simulate_overexpose
        self._simulate_underexpose = simulate_underexpose

        self._connected = False
        self._exposure_locked = False
        self._focus_mode = False
        self._current_z: float = 0.0
        self._rng = np.random.RandomState(seed)

        # Pre-generate base texture (shared across all Z for reproducibility)
        self._base_texture = self._generate_base_texture()

    def connect(self) -> bool:
        self._connected = True
        logger.info("[%s] Mock camera connected", self._camera_id)
        return True

    def disconnect(self) -> None:
        self._connected = False
        logger.info("[%s] Mock camera disconnected", self._camera_id)

    def lock_exposure_gain(self) -> None:
        self._exposure_locked = True
        logger.info("[%s] Exposure/gain locked", self._camera_id)

    def set_focus_capture_mode(self) -> None:
        self._focus_mode = True
        logger.info("[%s] Focus capture mode set", self._camera_id)

    def set_z_position(self, z_mm: float) -> None:
        """Set the simulated Z position for defocus simulation."""
        self._current_z = z_mm

    def capture_by_rows(self, row_count: int) -> np.ndarray:
        return self._generate_image(row_count)

    def capture_by_encoder_length(self, length_mm: float) -> np.ndarray:
        # Simulate: 10 rows per mm
        rows = int(length_mm * 10)
        return self._generate_image(min(rows, self._height))

    def capture_focus_sample(
        self, length_mm: float, speed_mode: str
    ) -> np.ndarray:
        rows = int(length_mm * 10)
        return self._generate_image(min(rows, self._height))

    def get_status(self) -> dict[str, Any]:
        return {
            "camera_id": self._camera_id,
            "connected": self._connected,
            "exposure_locked": self._exposure_locked,
            "focus_mode": self._focus_mode,
        }

    # ---- Image generation ----

    def _generate_base_texture(self) -> np.ndarray:
        """Generate a synthetic tube surface texture."""
        # Low-frequency base
        x = np.linspace(0, 4 * np.pi, self._width)
        y = np.linspace(0, 2 * np.pi, self._height)
        xx, yy = np.meshgrid(x, y)

        base = (
            np.sin(xx * 3) * np.cos(yy * 5) * 40
            + np.sin(xx * 7 + yy * 3) * 30
            + np.cos(xx * 11 - yy * 2) * 20
        )

        # High-frequency "scratch" details
        for _ in range(50):
            x0 = self._rng.randint(0, self._width)
            y0 = self._rng.randint(0, self._height)
            length = self._rng.randint(20, 200)
            angle = self._rng.uniform(0, np.pi)
            dx = int(length * np.cos(angle))
            dy = int(length * np.sin(angle))
            intensity = self._rng.randint(30, 80)
            cv2.line(
                base.astype(np.float32),
                (x0, y0),
                (min(x0 + dx, self._width - 1), min(y0 + dy, self._height - 1)),
                intensity,
                1,
            )

        # Normalize to [50, 200]
        base = 128 + base
        base = np.clip(base, 50, 200).astype(np.uint8)

        # Add salt-and-pepper noise for high-frequency content
        noise = self._rng.randint(0, 30, base.shape, dtype=np.uint8)
        base = cv2.add(base, noise)

        return base

    def _generate_image(self, row_count: int) -> np.ndarray:
        """Generate an image at the current Z with appropriate defocus blur."""
        if row_count <= 0:
            row_count = self._height

        # Crop or pad to requested row count
        h = min(row_count, self._height)
        img = self._base_texture[:h, :].copy()

        # Apply defocus blur based on Z distance from best focus
        z_error = abs(self._current_z - self._best_focus_z)
        sigma = z_error * self._blur_scale

        if sigma > 0.1:
            # Use Gaussian blur to simulate defocus
            ksize = int(sigma * 6) | 1  # odd kernel size
            ksize = max(3, min(ksize, 51))
            img = cv2.GaussianBlur(img, (ksize, ksize), sigma)

        # Simulate exposure issues if configured
        if self._simulate_overexpose and self._rng.rand() < 0.3:
            img = cv2.add(img, np.full_like(img, 60, dtype=np.uint8))
        if self._simulate_underexpose and self._rng.rand() < 0.3:
            img = cv2.subtract(img, np.full_like(img, 40, dtype=np.uint8))

        return img
