"""Priority router — routes tiles to models based on configured strategy."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from runtime.unified_image_pool import TileEntry


class RoutingStrategy(str, Enum):
    COLD_START = "cold_start"          # PatchCore → all tiles
    HYBRID_YOLO_FIRST = "hybrid_yolo_first"  # YOLO → all; uncertain → PatchCore
    PATCHCORE_FIRST = "patchcore_first"      # PatchCore → all; anomaly → YOLO


@dataclass
class RoutingDecision:
    """What to do with a tile (or batch) after the current step."""
    tile: TileEntry
    action: str  # "yolo", "patchcore", "classification", "release", "save", "human_review"
    priority: int = 0  # 0 = highest (P0)
    previous_result: dict[str, Any] | None = None


class PriorityRouter:
    """Routes tiles based on the current routing strategy.

    Three strategies:
    - cold_start: All tiles → PatchCore (P0), anomaly → human review (P1)
    - hybrid_yolo_first: All tiles → YOLO (P0), uncertain → PatchCore (P1), NG → save (P0)
    - patchcore_first: All tiles → PatchCore (P0), anomaly → YOLO (P1), NG → save (P0)
    """

    def __init__(self, strategy: RoutingStrategy = RoutingStrategy.HYBRID_YOLO_FIRST):
        self._strategy = strategy

    @property
    def strategy(self) -> RoutingStrategy:
        return self._strategy

    def switch_strategy(self, new_strategy: RoutingStrategy) -> None:
        self._strategy = new_strategy

    def route_initial(self, tile: TileEntry) -> RoutingDecision:
        """Determine the first model to run on a tile."""
        if self._strategy == RoutingStrategy.COLD_START:
            return RoutingDecision(tile=tile, action="patchcore", priority=0)
        elif self._strategy == RoutingStrategy.PATCHCORE_FIRST:
            return RoutingDecision(tile=tile, action="patchcore", priority=0)
        else:  # HYBRID_YOLO_FIRST (default)
            return RoutingDecision(tile=tile, action="yolo", priority=0)

    def route_after_result(
        self, tile: TileEntry, model_type: str, result: dict[str, Any]
    ) -> RoutingDecision:
        """Determine next action after a model returns a result."""
        result_type = result.get("result_type", "OK")
        confidence = result.get("confidence", 0.0)

        if self._strategy == RoutingStrategy.COLD_START:
            if result_type == "NG":
                return RoutingDecision(tile=tile, action="human_review", priority=1, previous_result=result)
            return RoutingDecision(tile=tile, action="release", priority=2)

        if self._strategy == RoutingStrategy.PATCHCORE_FIRST:
            if model_type == "patchcore" and result_type == "NG":
                return RoutingDecision(tile=tile, action="yolo", priority=1, previous_result=result)
            if model_type == "yolo":
                if result_type == "NG":
                    return RoutingDecision(tile=tile, action="save", priority=0, previous_result=result)
                return RoutingDecision(tile=tile, action="release", priority=2)
            return RoutingDecision(tile=tile, action="release", priority=2)

        # HYBRID_YOLO_FIRST
        if model_type == "yolo":
            if result_type == "NG" and confidence >= 0.7:
                return RoutingDecision(tile=tile, action="save", priority=0, previous_result=result)
            elif result_type == "NG" and confidence < 0.7:
                return RoutingDecision(tile=tile, action="classification", priority=2, previous_result=result)
            elif result_type == "UNKNOWN" or (result_type == "OK" and confidence < 0.5):
                return RoutingDecision(tile=tile, action="patchcore", priority=1, previous_result=result)
            else:
                return RoutingDecision(tile=tile, action="release", priority=2)
        elif model_type == "patchcore":
            if result_type == "NG":
                return RoutingDecision(tile=tile, action="save", priority=0, previous_result=result)
            return RoutingDecision(tile=tile, action="release", priority=2)
        elif model_type == "classification":
            return RoutingDecision(tile=tile, action="save", priority=0, previous_result=result)

        return RoutingDecision(tile=tile, action="release", priority=2)
