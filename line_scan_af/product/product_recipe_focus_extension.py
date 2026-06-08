"""Product recipe focus extension — save/load focus results per product.

Extends product recipe JSON files with line_scan_focus fields for each camera.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from line_scan_af.product.focus_profile import FocusResult, MultiFocusResult

logger = logging.getLogger(__name__)


class ProductRecipeFocusExtension:
    """Manages focus data within product recipe files."""

    def __init__(self, recipes_dir: str | Path = "product_recipes") -> None:
        self._recipes_dir = Path(recipes_dir)

    def save_focus_results(
        self,
        product_name: str,
        multi_result: MultiFocusResult | dict,
        diameter_mm: float = 0.0,
    ) -> None:
        """Save multi-camera focus results into the product recipe.

        Args:
            product_name: Product identifier (e.g. "CopperTube_8mm").
            multi_result: MultiFocusResult or dict from multi_camera_af_manager.
            diameter_mm: Tube diameter.
        """
        self._recipes_dir.mkdir(parents=True, exist_ok=True)
        recipe_path = self._recipes_dir / f"{product_name}.json"

        # Load existing recipe or create new
        if recipe_path.exists():
            recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        else:
            recipe = {
                "product_name": product_name,
                "diameter_mm": diameter_mm,
                "material": "",
                "line_scan_focus": {},
            }

        # Convert to dict if needed
        if isinstance(multi_result, MultiFocusResult):
            results_dict = {
                cam_id: r.model_dump() for cam_id, r in multi_result.results.items()
            }
        else:
            results_dict = multi_result.get("results", {})

        # Update focus data for each camera
        if "line_scan_focus" not in recipe:
            recipe["line_scan_focus"] = {}

        for cam_id, cam_result in results_dict.items():
            cam_key = cam_id.lower()
            recipe["line_scan_focus"][cam_key] = {
                "stage_id": cam_result.get("stage_id", ""),
                "best_z_mm": cam_result.get("best_z_mm", 0.0),
                "center_score": cam_result.get("center_score", 0.0),
                "left_score": cam_result.get("left_score", 0.0),
                "right_score": cam_result.get("right_score", 0.0),
                "edge_score_ratio_left": cam_result.get("edge_score_ratio_left", 0.0),
                "edge_score_ratio_right": cam_result.get("edge_score_ratio_right", 0.0),
                "dof_check": cam_result.get("dof_check", ""),
                "verify_score": cam_result.get("verify_score", 0.0),
                "roi_profile": cam_result.get("roi_profile", ""),
                "curve_file": cam_result.get("curve_file", ""),
                "sample_image": cam_result.get("sample_image", ""),
                "updated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        recipe_path.write_text(
            json.dumps(recipe, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Saved focus results for '%s' to %s", product_name, recipe_path)

    def load_focus_results(self, product_name: str) -> dict[str, Any] | None:
        """Load focus results for a product.

        Returns:
            Dict with per-camera focus data, or None if not found.
        """
        recipe_path = self._recipes_dir / f"{product_name}.json"
        if not recipe_path.exists():
            logger.info("No recipe found for product '%s'", product_name)
            return None

        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        return recipe.get("line_scan_focus", {})

    def get_history_z(self, product_name: str, camera_id: str) -> float | None:
        """Get the historical best Z for a specific camera+product.

        Args:
            product_name: Product name.
            camera_id: Camera ID (e.g. "CAM1").

        Returns:
            Best Z in mm, or None if no history exists.
        """
        focus_data = self.load_focus_results(product_name)
        if not focus_data:
            return None

        cam_key = camera_id.lower()
        cam_data = focus_data.get(cam_key)
        if cam_data and "best_z_mm" in cam_data:
            return cam_data["best_z_mm"]

        return None
