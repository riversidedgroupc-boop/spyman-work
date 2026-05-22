"""GPU inference scheduler — single-consumer loop with micro-batch and priority routing."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable

from gpu_scheduler.micro_batch import MicroBatchAccumulator
from gpu_scheduler.model_pool import ModelEnginePool
from gpu_scheduler.priority_router import PriorityRouter, RoutingDecision, RoutingStrategy
from gpu_scheduler.stats import SchedulerStats, InferenceTiming, TileResult
from runtime.unified_image_pool import UnifiedImagePool, TileEntry

logger = logging.getLogger(__name__)


class GPUInferenceScheduler:
    """Single-consumer GPU inference loop.

    Pulls tiles from UnifiedImagePool, accumulates micro-batches, routes to
    appropriate model engines via PriorityRouter, and publishes results.
    """

    def __init__(
        self,
        pool: UnifiedImagePool,
        model_pool: ModelEnginePool,
        strategy: RoutingStrategy = RoutingStrategy.HYBRID_YOLO_FIRST,
        batch_size: int = 4,
        max_wait_ms: float = 10.0,
    ):
        self._pool = pool
        self._model_pool = model_pool
        self._router = PriorityRouter(strategy)

        self._batch_acc = MicroBatchAccumulator(batch_size, max_wait_ms)
        self._pending: dict[str, list[RoutingDecision]] = {
            "yolo": [],
            "patchcore": [],
            "classification": [],
        }

        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._stats = SchedulerStats()

        self._on_ng: Callable | None = None
        self._on_result: Callable | None = None

    # ── Callbacks ──

    def set_on_ng(self, callback: Callable) -> None:
        self._on_ng = callback

    def set_on_result(self, callback: Callable) -> None:
        self._on_result = callback

    # ── Lifecycle ──

    def start(self) -> None:
        self._running.set()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=5)

    def is_running(self) -> bool:
        return self._running.is_set()

    # ── Main loop ──

    def _loop(self) -> None:
        while self._running.is_set():
            # 1. Pull tiles from pool
            batch = self._pool.pop_batch(self._batch_acc.batch_size)
            if batch:
                for tile in batch:
                    ready = self._batch_acc.accumulate(tile)
                    if ready:
                        self._enqueue_tiles(ready)
            elif self._batch_acc.should_flush_timeout():
                ready = self._batch_acc.flush()
                if ready:
                    self._enqueue_tiles(ready)

            # 2. Process P0 queue (yolo or patchcore depending on strategy)
            self._process_queue("yolo")
            self._process_queue("patchcore")

            # 3. Process P2 queue (classification — lowest priority, throttle)
            self._process_queue("classification")

            # 4. If nothing to do, brief sleep
            if not any(self._pending.values()) and self._batch_acc.current_size() == 0:
                time.sleep(0.005)

    def _enqueue_tiles(self, tiles: list[TileEntry]) -> None:
        for tile in tiles:
            decision = self._router.route_initial(tile)
            self._pending[decision.action].append(decision)

    def _process_queue(self, model_type: str) -> None:
        decisions = self._pending.get(model_type, [])
        if not decisions:
            return

        if not self._model_pool.is_loaded(model_type):
            self._pending[model_type] = []
            self._stats.dropped_tiles += len(decisions)
            return

        tiles = [d.tile for d in decisions]
        images = [t.image for t in tiles]

        t0 = time.perf_counter()
        try:
            results = self._model_pool.infer(model_type, images)
        except Exception:
            logger.exception("Inference failed for %s", model_type)
            self._pending[model_type] = []
            return
        elapsed_ms = (time.perf_counter() - t0) * 1000

        timing = InferenceTiming(
            model_type=model_type,
            tile_count=len(tiles),
            elapsed_ms=elapsed_ms,
            inference_ms=elapsed_ms,
        )
        self._stats.record_inference(timing)

        now = datetime.now().isoformat()

        for decision, result in zip(decisions, results):
            tile = decision.tile
            tile_result = TileResult(
                tile_id=tile.tile_id,
                camera_id=tile.camera_id,
                run_id=tile.run_id,
                product_id=tile.product_id,
                model_type=model_type,
                model_version=result.get("model_version", "unknown"),
                result_type=result.get("result_type", "OK"),
                defect_type=result.get("defect_type", ""),
                confidence=result.get("confidence", 0.0),
                bbox=result.get("bbox"),
                inference_time_ms=elapsed_ms / max(len(decisions), 1),
                gpu_device_id=self._model_pool.device_id,
                meter_start=tile.meter_start,
                meter_end=tile.meter_end,
                created_time=now,
            )

            if self._on_result:
                self._emit_callback(self._on_result, tile, tile_result)
            if tile_result.result_type in ("NG", "UNKNOWN") and self._on_ng:
                self._emit_callback(self._on_ng, tile, tile_result)

            next_decision = self._router.route_after_result(tile, model_type, result)
            if next_decision.action in ("yolo", "patchcore", "classification"):
                self._pending[next_decision.action].append(next_decision)

        self._pending[model_type] = []

    # ── Query ──

    def get_stats(self) -> SchedulerStats:
        return self._stats

    @staticmethod
    def _emit_callback(callback: Callable, tile: TileEntry, result: TileResult) -> None:
        try:
            callback(tile, result)
        except TypeError:
            callback(result)

    def switch_strategy(self, strategy: RoutingStrategy) -> None:
        self._router.switch_strategy(strategy)
        logger.info("Routing strategy switched to %s", strategy.value)
