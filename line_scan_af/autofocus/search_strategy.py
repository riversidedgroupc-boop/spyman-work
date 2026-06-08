"""Search point generation strategies for autofocus.

Generates Z position lists for coarse search, fine search, and history-based
local search. All methods are static pure functions.
"""

from __future__ import annotations

import numpy as np


class SearchStrategy:
    """Generates Z-axis search points for autofocus sweeps."""

    @staticmethod
    def generate_coarse_grid(
        z_min: float, z_max: float, step_mm: float
    ) -> list[float]:
        """Generate evenly-spaced coarse search points.

        Args:
            z_min: Minimum Z position (mm).
            z_max: Maximum Z position (mm).
            step_mm: Step size between points.

        Returns:
            Sorted list of Z positions.
        """
        if step_mm <= 0:
            raise ValueError(f"Step must be positive, got {step_mm}")
        if z_min >= z_max:
            raise ValueError(f"z_min ({z_min}) must be < z_max ({z_max})")

        num_points = int(np.ceil((z_max - z_min) / step_mm)) + 1
        points = np.linspace(z_min, z_max, num_points)
        return [round(float(p), 3) for p in points]

    @staticmethod
    def generate_fine_grid(
        center_z: float, step_mm: float, n_points: int = 11
    ) -> list[float]:
        """Generate fine search points centered around a best guess.

        Args:
            center_z: Center Z position (typically the coarse-search best).
            step_mm: Fine step size (smaller than coarse).
            n_points: Number of points (should be odd for symmetry).

        Returns:
            Sorted list of Z positions.
        """
        if step_mm <= 0:
            raise ValueError(f"Step must be positive, got {step_mm}")
        if n_points < 3:
            raise ValueError(f"Need at least 3 points, got {n_points}")

        half_range = (n_points - 1) / 2 * step_mm
        points = np.linspace(center_z - half_range, center_z + half_range, n_points)
        return [round(float(p), 3) for p in points]

    @staticmethod
    def generate_history_local_grid(
        history_z: float, range_mm: float, step_mm: float
    ) -> list[float]:
        """Generate search points around a historical best focus.

        Args:
            history_z: Previously recorded best Z position.
            range_mm: Search half-range (± from history_z).
            step_mm: Step size.

        Returns:
            Sorted list of Z positions.
        """
        if range_mm <= 0:
            raise ValueError(f"Range must be positive, got {range_mm}")
        if step_mm <= 0:
            raise ValueError(f"Step must be positive, got {step_mm}")

        z_min = history_z - range_mm
        z_max = history_z + range_mm
        return SearchStrategy.generate_coarse_grid(z_min, z_max, step_mm)

    @staticmethod
    def clamp_points(
        points: list[float], z_min: float, z_max: float
    ) -> list[float]:
        """Clamp Z positions to valid range, preserving uniqueness and order.

        Args:
            points: Z position list.
            z_min: Minimum allowed Z.
            z_max: Maximum allowed Z.

        Returns:
            Clamped, de-duplicated, sorted list.
        """
        clamped = [max(z_min, min(z_max, p)) for p in points]
        unique = sorted(set(round(p, 3) for p in clamped))
        return unique

    @staticmethod
    def validate_search_parameters(
        z_min: float, z_max: float, coarse_step: float, fine_step: float
    ) -> list[str]:
        """Validate search parameters and return list of issues.

        Args:
            z_min: Minimum Z position.
            z_max: Maximum Z position.
            coarse_step: Coarse search step.
            fine_step: Fine search step.

        Returns:
            List of validation issue strings (empty = valid).
        """
        issues = []
        if z_min >= z_max:
            issues.append(f"z_min ({z_min}) >= z_max ({z_max})")
        if coarse_step <= 0:
            issues.append(f"coarse_step ({coarse_step}) <= 0")
        if fine_step <= 0:
            issues.append(f"fine_step ({fine_step}) <= 0")
        if fine_step >= coarse_step:
            issues.append(f"fine_step ({fine_step}) >= coarse_step ({coarse_step})")
        if (z_max - z_min) < coarse_step:
            issues.append(f"Search range ({z_max - z_min}) < coarse_step ({coarse_step})")
        return issues
