# V8 实时性能调度与硬件选型评估 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 copper-defect-eval-tool 升级为支持统一图像池、单GPU多模型调度、磁盘分桶保存、压测评估的实时检测系统

**Architecture:** 新建 4 个顶层模块（gpu_scheduler, storage_v8, benchmark）加 runtime 增强。采用 P0 优先策略，按依赖链：内存基础 → GPU调度 → 存储 → 压测 → 集成 → UI

**Tech Stack:** Python 3.12+, NumPy, PySide6, SQLite, psutil, nvidia-ml-py, torch/ultralytics

---

## 文件结构总览

### 新建文件

| 文件 | 职责 |
|------|------|
| `runtime/ring_buffer.py` | 升级版 RAMRingBuffer — 预分配+无锁+背压 |
| `runtime/unified_image_pool.py` | UnifiedImagePool — 多相机 tile 统一入口 |
| `gpu_scheduler/__init__.py` | 包初始化 |
| `gpu_scheduler/stats.py` | 推理统计数据类型 |
| `gpu_scheduler/model_pool.py` | ModelEnginePool — 模型加载/卸载/显存监控 |
| `gpu_scheduler/micro_batch.py` | MicroBatchAccumulator — 批次累积逻辑 |
| `gpu_scheduler/priority_router.py` | PriorityRouter — 策略路由（3种策略） |
| `gpu_scheduler/scheduler.py` | GPUInferenceScheduler — 主调度器 |
| `storage_v8/__init__.py` | 包初始化 |
| `storage_v8/image_index.py` | ImageIndexDB — image_index.db CRUD |
| `storage_v8/save_policy.py` | SavePolicyManager — 4种保存策略 |
| `storage_v8/bucket_manager.py` | StorageBucketManager — 分桶切换 |
| `storage_v8/async_writer.py` | AsyncDiskWriter — 队列+后台写入 |
| `benchmark/__init__.py` | 包初始化 |
| `benchmark/metrics_collector.py` | MetricsCollector — CPU/GPU/内存/磁盘采样 |
| `benchmark/spi_calculator.py` | SpiCalculator — SPI 计算 |
| `benchmark/hardware_advisor.py` | HardwareAdvisor — 硬件等级推荐 |
| `benchmark/input_source.py` | 4种输入源 |
| `benchmark/benchmark_runner.py` | BenchmarkRunner — 压测引擎 |
| `benchmark/report_exporter.py` | 压测报告导出 |

### 修改文件

- `runtime/acquisition_pipeline.py` — 接入 UnifiedImagePool
- `runtime/inference_pipeline.py` — 适配 GPUInferenceScheduler
- `desktop_app/main_window.py` — 注册 benchmark 页
- `desktop_app/navigation.py` — 添加导航项
- `pyproject.toml` — 添加 nvidia-ml-py 依赖

---

## Phase 1: 内存基础（Agent 1 核心）

### Task 1.1: RAMRingBuffer

**Files:**
- Create: `runtime/ring_buffer.py`
- Test: `tests/test_ring_buffer.py`

- [ ] **Step 1: 写测试**

```python
"""Tests for RAMRingBuffer."""
import numpy as np
import pytest
import time
from runtime.ring_buffer import RAMRingBuffer, RingBufferStats


def test_put_and_get_single():
    buf = RAMRingBuffer(max_slots=8, slot_shape=(3, 320, 320), dtype=np.uint8)
    data = np.ones((3, 320, 320), dtype=np.uint8) * 42
    assert buf.put(data) is True
    result = buf.get()
    assert result is not None
    assert result[0, 0, 0] == 42
    assert buf.size() == 0


def test_capacity_enforced():
    buf = RAMRingBuffer(max_slots=4, slot_shape=(1, 10, 10), dtype=np.uint8)
    for i in range(10):
        buf.put(np.full((1, 10, 10), i, dtype=np.uint8))
    # Only last 4 survive
    assert buf.size() == 4
    stats = buf.stats()
    assert stats.dropped >= 6


def test_get_returns_none_when_empty():
    buf = RAMRingBuffer(max_slots=8, slot_shape=(1, 10, 10), dtype=np.uint8)
    assert buf.get() is None


def test_usage_ratio():
    buf = RAMRingBuffer(max_slots=10, slot_shape=(1, 10, 10), dtype=np.uint8)
    for i in range(6):
        buf.put(np.full((1, 10, 10), i, dtype=np.uint8))
    assert 0.5 < buf.usage_ratio() < 0.7


def test_drop_policy_oldest():
    buf = RAMRingBuffer(max_slots=3, slot_shape=(1, 10, 10), dtype=np.uint8, drop_policy="oldest")
    buf.put(np.full((1, 10, 10), 1, dtype=np.uint8))
    buf.put(np.full((1, 10, 10), 2, dtype=np.uint8))
    buf.put(np.full((1, 10, 10), 3, dtype=np.uint8))
    buf.put(np.full((1, 10, 10), 4, dtype=np.uint8))  # drops oldest (value=1)
    first = buf.get()
    assert first[0, 0, 0] == 2  # 1 was dropped


def test_stats_accurate():
    buf = RAMRingBuffer(max_slots=10, slot_shape=(1, 10, 10), dtype=np.uint8)
    for i in range(5):
        buf.put(np.full((1, 10, 10), i, dtype=np.uint8))
    for _ in range(3):
        buf.get()
    stats = buf.stats()
    assert stats.total_puts == 5
    assert stats.total_gets == 3
    assert stats.current_size == 2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_ring_buffer.py -v
```

- [ ] **Step 3: 实现 RAMRingBuffer**

```python
"""RAM ring buffer with pre-allocated numpy slots and lock-free SPSC operations."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass
class RingBufferStats:
    total_puts: int = 0
    total_gets: int = 0
    current_size: int = 0
    dropped: int = 0


class RAMRingBuffer:
    """Pre-allocated ring buffer for fixed-shape numpy arrays.

    Uses pre-allocated memory slots to avoid GC pressure at high throughput.
    Thread-safe for single-producer-multiple-consumers.
    """

    def __init__(
        self,
        max_slots: int = 200,
        slot_shape: tuple[int, ...] = (3, 320, 320),
        dtype: type = np.uint8,
        drop_policy: Literal["oldest", "newest"] = "oldest",
    ):
        self._max_slots = max_slots
        self._slots = np.zeros((max_slots,) + slot_shape, dtype=dtype)
        self._write_idx = 0
        self._read_idx = 0
        self._count = 0
        self._lock = threading.Lock()
        self._stats = RingBufferStats()
        self._drop_policy = drop_policy

    def put(self, data: np.ndarray) -> bool:
        """Copy data into the next write slot. Returns False if dropped."""
        with self._lock:
            self._stats.total_puts += 1
            if self._count >= self._max_slots:
                self._stats.dropped += 1
                if self._drop_policy == "oldest":
                    self._read_idx = (self._read_idx + 1) % self._max_slots
                    self._count -= 1
                else:
                    return False
            np.copyto(self._slots[self._write_idx], data)
            self._write_idx = (self._write_idx + 1) % self._max_slots
            self._count += 1
            return True

    def get(self) -> np.ndarray | None:
        """Return a copy of the next readable slot, or None if empty."""
        with self._lock:
            self._stats.total_gets += 1
            if self._count == 0:
                return None
            data = self._slots[self._read_idx].copy()
            self._read_idx = (self._read_idx + 1) % self._max_slots
            self._count -= 1
            return data

    def size(self) -> int:
        with self._lock:
            return self._count

    def usage_ratio(self) -> float:
        with self._lock:
            return self._count / max(self._max_slots, 1)

    def stats(self) -> RingBufferStats:
        s = RingBufferStats(
            total_puts=self._stats.total_puts,
            total_gets=self._stats.total_gets,
            dropped=self._stats.dropped,
        )
        s.current_size = self._count
        return s

    def clear(self) -> None:
        with self._lock:
            self._write_idx = 0
            self._read_idx = 0
            self._count = 0
            self._stats = RingBufferStats()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_ring_buffer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add runtime/ring_buffer.py tests/test_ring_buffer.py
git commit -m "feat: add RAMRingBuffer with pre-allocated numpy slots and drop policies"
```

---

### Task 1.2: UnifiedImagePool

**Files:**
- Create: `runtime/unified_image_pool.py`
- Test: `tests/test_unified_image_pool.py`

- [ ] **Step 1: 写测试**

```python
"""Tests for UnifiedImagePool."""
import numpy as np
from runtime.unified_image_pool import UnifiedImagePool, TileEntry, PoolStats


def make_tile(camera_id: str = "Camera_01", block_id: str = "BLK_001") -> TileEntry:
    return TileEntry(
        tile_id=f"{block_id}_T_000_000",
        run_id="run_test",
        customer_id="test_cust",
        product_id="test_prod",
        camera_id=camera_id,
        block_id=block_id,
        tile_index=0,
        tile_x=0,
        tile_y=0,
        meter_start=100.0,
        meter_end=100.5,
        encoder_count_start=1000,
        encoder_count_end=1005,
        timestamp="2026-05-20T20:30:00",
        image=np.ones((3, 320, 320), dtype=np.uint8) * 128,
    )


def test_push_and_pop_batch():
    pool = UnifiedImagePool(max_pool_size=100, memory_budget_mb=256)
    for i in range(5):
        pool.push(make_tile(camera_id=f"Cam_{i%3}"))
    batch = pool.pop_batch(3)
    assert len(batch) == 3
    assert pool.size() == 2


def test_pop_batch_returns_available_when_short():
    pool = UnifiedImagePool(max_pool_size=100, memory_budget_mb=256)
    pool.push(make_tile())
    pool.push(make_tile())
    batch = pool.pop_batch(4)
    assert len(batch) == 2


def test_pool_size_limit():
    pool = UnifiedImagePool(max_pool_size=10, memory_budget_mb=256, drop_policy="oldest")
    for i in range(20):
        pool.push(make_tile(block_id=f"BLK_{i:03d}"))
    assert pool.size() <= 10
    stats = pool.stats()
    assert stats.dropped > 0


def test_memory_budget():
    # 每 tile ~300KB, 设定 1MB budget → 最多约 3 tile
    pool = UnifiedImagePool(max_pool_size=1000, memory_budget_mb=1, drop_policy="oldest")
    for i in range(20):
        pool.push(make_tile(block_id=f"BLK_{i:03d}"))
    assert pool.size() <= 4  # ~1MB / ~300KB


def test_stats():
    pool = UnifiedImagePool(max_pool_size=100, memory_budget_mb=256)
    for i in range(8):
        pool.push(make_tile(block_id=f"BLK_{i:03d}"))
    for _ in range(3):
        pool.pop_batch(2)
    stats = pool.stats()
    assert stats.total_pushes == 8
    assert stats.total_pops >= 3
    assert stats.total_dropped == 0


def test_camera_distribution():
    pool = UnifiedImagePool(max_pool_size=100, memory_budget_mb=256)
    for i in range(9):
        pool.push(make_tile(camera_id=f"Camera_{i%3 + 1:02d}"))
    dist = pool.camera_distribution()
    assert dist["Camera_01"] == 3
    assert dist["Camera_02"] == 3
    assert dist["Camera_03"] == 3
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_unified_image_pool.py -v
```

- [ ] **Step 3: 实现 UnifiedImagePool**

```python
"""Unified image pool — single entry point for all camera tiles."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Literal

import numpy as np


@dataclass
class TileEntry:
    """A tile with complete metadata for traceability."""
    tile_id: str
    run_id: str
    customer_id: str
    product_id: str
    camera_id: str
    block_id: str
    tile_index: int
    tile_x: int
    tile_y: int
    meter_start: float
    meter_end: float
    encoder_count_start: int
    encoder_count_end: int
    timestamp: str
    image: np.ndarray  # (3, 320, 320) uint8 or (320, 320) uint8 for Mono8


@dataclass
class PoolStats:
    total_pushes: int = 0
    total_pops: int = 0
    total_dropped: int = 0
    current_size: int = 0
    max_observed_size: int = 0
    pool_usage_ratio: float = 0.0


class UnifiedImagePool:
    """Thread-safe pool for all camera tiles with memory budget control.

    All camera workers push tiles; the GPU scheduler is the sole consumer.
    """

    TILE_BYTES = 3 * 320 * 320  # ~307,200 bytes per uint8 RGB tile

    def __init__(
        self,
        max_pool_size: int = 1000,
        memory_budget_mb: int = 512,
        drop_policy: Literal["oldest", "newest"] = "oldest",
    ):
        self._max_pool_size = max_pool_size
        self._memory_budget_mb = memory_budget_mb
        self._max_slots_by_memory = max(1, (memory_budget_mb * 1024 * 1024) // self.TILE_BYTES)
        self._effective_max = min(max_pool_size, self._max_slots_by_memory)
        self._drop_policy = drop_policy

        self._items: list[TileEntry] = []
        self._lock = threading.Lock()
        self._stats = PoolStats()
        self._camera_counts: dict[str, int] = {}

    def push(self, tile: TileEntry) -> bool:
        """Push a tile into the pool. Returns False if dropped."""
        with self._lock:
            self._stats.total_pushes += 1
            if len(self._items) >= self._effective_max:
                self._stats.total_dropped += 1
                if self._drop_policy == "oldest":
                    dropped = self._items.pop(0)
                    self._camera_counts[dropped.camera_id] = max(
                        0, self._camera_counts.get(dropped.camera_id, 0) - 1
                    )
                else:
                    return False
            self._items.append(tile)
            self._camera_counts[tile.camera_id] = self._camera_counts.get(tile.camera_id, 0) + 1
            self._stats.current_size = len(self._items)
            self._stats.max_observed_size = max(self._stats.max_observed_size, self._stats.current_size)
            self._stats.pool_usage_ratio = self._stats.current_size / max(self._effective_max, 1)
            return True

    def pop_batch(self, batch_size: int) -> list[TileEntry]:
        """Pop up to batch_size tiles. Returns empty list if pool is empty."""
        with self._lock:
            self._stats.total_pops += 1
            n = min(batch_size, len(self._items))
            if n == 0:
                return []
            batch = self._items[:n]
            self._items = self._items[n:]
            for t in batch:
                self._camera_counts[t.camera_id] = max(
                    0, self._camera_counts.get(t.camera_id, 0) - 1
                )
            self._stats.current_size = len(self._items)
            self._stats.pool_usage_ratio = self._stats.current_size / max(self._effective_max, 1)
            return batch

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def usage_ratio(self) -> float:
        with self._lock:
            return len(self._items) / max(self._effective_max, 1)

    def camera_distribution(self) -> dict[str, int]:
        with self._lock:
            return dict(self._camera_counts)

    def stats(self) -> PoolStats:
        with self._lock:
            s = PoolStats(
                total_pushes=self._stats.total_pushes,
                total_pops=self._stats.total_pops,
                total_dropped=self._stats.total_dropped,
                current_size=len(self._items),
                max_observed_size=self._stats.max_observed_size,
                pool_usage_ratio=len(self._items) / max(self._effective_max, 1),
            )
            return s

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._camera_counts.clear()
            self._stats = PoolStats()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_unified_image_pool.py -v
```

- [ ] **Step 5: Commit**

```bash
git add runtime/unified_image_pool.py tests/test_unified_image_pool.py
git commit -m "feat: add UnifiedImagePool with memory budget and camera distribution tracking"
```

---

## Phase 2: GPU 调度（Agent 2 核心）

### Task 2.1: GPU Scheduler 统计类型

**Files:**
- Create: `gpu_scheduler/__init__.py`
- Create: `gpu_scheduler/stats.py`

- [ ] **Step 1: 写 stats.py**

```python
"""Inference statistics types for GPU scheduler."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InferenceTiming:
    """Per-inference timing record."""
    model_type: str = ""
    tile_count: int = 0
    elapsed_ms: float = 0.0
    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    postprocess_ms: float = 0.0


@dataclass
class SchedulerStats:
    """Cumulative scheduler statistics."""
    total_tiles_processed: int = 0
    total_batches: int = 0
    total_inference_time_ms: float = 0.0
    avg_inference_ms: float = 0.0
    p95_inference_ms: float = 0.0
    p99_inference_ms: float = 0.0
    queue_depth: int = 0
    max_queue_depth: int = 0
    dropped_tiles: int = 0
    model_switches: int = 0
    gpu_utilization_pct: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0

    # per-model breakdown
    per_model: dict[str, "ModelStats"] = field(default_factory=dict)

    # rolling window for percentile calculation
    _recent_latencies: list[float] = field(default_factory=list)
    _max_recent: int = 1000

    def record_inference(self, timing: InferenceTiming) -> None:
        self.total_tiles_processed += timing.tile_count
        self.total_batches += 1
        self.total_inference_time_ms += timing.elapsed_ms

        self._recent_latencies.append(timing.inference_ms)
        if len(self._recent_latencies) > self._max_recent:
            self._recent_latencies = self._recent_latencies[-self._max_recent:]

        if self._recent_latencies:
            sorted_lat = sorted(self._recent_latencies)
            self.avg_inference_ms = sum(sorted_lat) / len(sorted_lat)
            self.p95_inference_ms = sorted_lat[int(len(sorted_lat) * 0.95)]
            self.p99_inference_ms = sorted_lat[int(len(sorted_lat) * 0.99)]

        ms = self._recent_latencies
        if timing.model_type not in self.per_model:
            self.per_model[timing.model_type] = ModelStats(model_type=timing.model_type)
        self.per_model[timing.model_type].record(timing.inference_ms, timing.tile_count)


@dataclass
class ModelStats:
    """Per-model cumulative statistics."""
    model_type: str = ""
    inference_count: int = 0
    total_tiles: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    ng_count: int = 0
    _recent_latencies: list[float] = field(default_factory=list)
    _max_recent: int = 200

    def record(self, latency_ms: float, tile_count: int) -> None:
        self.inference_count += 1
        self.total_tiles += tile_count
        self._recent_latencies.append(latency_ms)
        if len(self._recent_latencies) > self._max_recent:
            self._recent_latencies = self._recent_latencies[-self._max_recent:]
        if self._recent_latencies:
            sorted_l = sorted(self._recent_latencies)
            self.avg_latency_ms = sum(sorted_l) / len(sorted_l)
            self.p95_latency_ms = sorted_l[int(len(sorted_l) * 0.95)]


@dataclass
class TileResult:
    """Inference result for a single tile — carries full traceability metadata."""
    tile_id: str
    camera_id: str
    run_id: str
    product_id: str
    model_type: str
    model_version: str
    result_type: str  # OK / NG / UNKNOWN
    defect_type: str
    confidence: float
    bbox: list[int] | None  # [x1, y1, x2, y2] in block coords
    inference_time_ms: float
    gpu_device_id: int
    meter_start: float
    meter_end: float
    created_time: str = ""
```

- [ ] **Step 2: Commit**

```bash
git add gpu_scheduler/__init__.py gpu_scheduler/stats.py
git commit -m "feat: add GPU scheduler stats types (SchedulerStats, ModelStats, TileResult)"
```

---

### Task 2.2: ModelEnginePool

**Files:**
- Create: `gpu_scheduler/model_pool.py`
- Test: `tests/test_model_pool.py`

- [ ] **Step 1: 写测试**

```python
"""Tests for ModelEnginePool."""
import numpy as np
from gpu_scheduler.model_pool import ModelEnginePool, ModelEngine


class FakeYOLOEngine(ModelEngine):
    def __init__(self):
        self._loaded = False
        self.load_count = 0
        self.unload_count = 0
        self.infer_count = 0

    @property
    def model_type(self) -> str:
        return "yolo"

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, model_path: str, device_id: int = 0) -> bool:
        self.load_count += 1
        self._loaded = True
        return True

    def unload(self) -> None:
        self.unload_count += 1
        self._loaded = False

    def infer_batch(self, images: list[np.ndarray]) -> list[dict]:
        self.infer_count += 1
        return [{"result_type": "OK", "confidence": 0.95, "bbox": None} for _ in images]

    @property
    def vram_mb(self) -> float:
        return 500.0


def test_load_and_unload():
    pool = ModelEnginePool(device_id=0)
    engine = FakeYOLOEngine()
    pool.register("yolo", engine)
    assert pool.load("yolo", "models/yolo/best.pt")
    assert pool.is_loaded("yolo")
    pool.unload("yolo")
    assert not pool.is_loaded("yolo")
    assert engine.load_count == 1
    assert engine.unload_count >= 1


def test_load_unknown_type_raises():
    pool = ModelEnginePool(device_id=0)
    with pytest.raises(ValueError, match="not registered"):
        pool.load("unknown", "some/path")


def test_infer_batch():
    pool = ModelEnginePool(device_id=0)
    engine = FakeYOLOEngine()
    pool.register("yolo", engine)
    pool.load("yolo", "models/yolo/best.pt")
    images = [np.ones((3, 320, 320), dtype=np.uint8) for _ in range(3)]
    results = pool.infer("yolo", images)
    assert len(results) == 3
    assert engine.infer_count == 1


def test_register_replaces_existing():
    pool = ModelEnginePool(device_id=0)
    e1 = FakeYOLOEngine()
    e2 = FakeYOLOEngine()
    pool.register("yolo", e1)
    pool.register("yolo", e2)
    assert pool._engines["yolo"] is e2


def test_list_loaded():
    pool = ModelEnginePool(device_id=0)
    pool.register("yolo", FakeYOLOEngine())
    pool.register("patchcore", FakeYOLOEngine())
    pool.load("yolo", "models/yolo/best.pt")
    loaded = pool.list_loaded()
    assert "yolo" in loaded
    assert "patchcore" not in loaded
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_model_pool.py -v
```

- [ ] **Step 3: 实现 ModelEnginePool**

```python
"""Model engine pool — manages model lifecycle, loading, and inference dispatch."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger(__name__)


class ModelEngine(ABC):
    """Abstract engine for a single model type."""

    @property
    @abstractmethod
    def model_type(self) -> str: ...

    @property
    @abstractmethod
    def is_loaded(self) -> bool: ...

    @abstractmethod
    def load(self, model_path: str, device_id: int = 0) -> bool: ...

    @abstractmethod
    def unload(self) -> None: ...

    @abstractmethod
    def infer_batch(self, images: list[np.ndarray]) -> list[dict]: ...

    @property
    @abstractmethod
    def vram_mb(self) -> float: ...


class ModelEnginePool:
    """Manages multiple model engines sharing a single GPU device."""

    def __init__(self, device_id: int = 0):
        self._device_id = device_id
        self._engines: dict[str, ModelEngine] = {}
        self._vram_limit_mb: float = 0.0

    def register(self, model_type: str, engine: ModelEngine) -> None:
        self._engines[model_type] = engine

    def load(self, model_type: str, model_path: str) -> bool:
        engine = self._engines.get(model_type)
        if engine is None:
            raise ValueError(f"Model type '{model_type}' not registered")
        if engine.is_loaded:
            return True
        success = engine.load(model_path, self._device_id)
        if success:
            logger.info("Loaded %s -> %s (VRAM: %.0f MB)", model_type, model_path, engine.vram_mb)
        return success

    def unload(self, model_type: str) -> None:
        engine = self._engines.get(model_type)
        if engine and engine.is_loaded:
            engine.unload()

    def unload_all(self) -> None:
        for engine in self._engines.values():
            if engine.is_loaded:
                engine.unload()

    def is_loaded(self, model_type: str) -> bool:
        engine = self._engines.get(model_type)
        return engine is not None and engine.is_loaded

    def infer(self, model_type: str, images: list[np.ndarray]) -> list[dict]:
        engine = self._engines.get(model_type)
        if engine is None:
            raise ValueError(f"Model type '{model_type}' not registered")
        if not engine.is_loaded:
            raise RuntimeError(f"Model '{model_type}' is not loaded")
        return engine.infer_batch(images)

    def list_loaded(self) -> list[str]:
        return [t for t, e in self._engines.items() if e.is_loaded]

    @property
    def total_vram_mb(self) -> float:
        return sum(e.vram_mb for e in self._engines.values() if e.is_loaded)

    @property
    def device_id(self) -> int:
        return self._device_id
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_model_pool.py -v
```

- [ ] **Step 5: Commit**

```bash
git add gpu_scheduler/model_pool.py tests/test_model_pool.py
git commit -m "feat: add ModelEnginePool for unified GPU model lifecycle management"
```

---

### Task 2.3: MicroBatchAccumulator

**Files:**
- Create: `gpu_scheduler/micro_batch.py`
- Test: `tests/test_micro_batch.py`

- [ ] **Step 1: 写 micro_batch.py 和测试**

```python
"""Micro-batch accumulator — gathers tiles into inference batches."""
from __future__ import annotations

import time
from runtime.unified_image_pool import TileEntry


class MicroBatchAccumulator:
    """Accumulates tiles into batches based on size or timeout.

    Rules (either triggers inference):
    - Batch size reaches `batch_size` → emit immediately
    - Time since first tile reaches `max_wait_ms` → emit immediately
    """

    def __init__(self, batch_size: int = 4, max_wait_ms: float = 10.0):
        self._batch_size = batch_size
        self._max_wait_ms = max_wait_ms
        self._buffer: list[TileEntry] = []
        self._first_tile_time: float | None = None

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def max_wait_ms(self) -> float:
        return self._max_wait_ms

    def accumulate(self, tile: TileEntry) -> list[TileEntry] | None:
        """Add a tile. Returns a batch if ready, or None if accumulating."""
        now = time.time()
        if self._first_tile_time is None:
            self._first_tile_time = now
        self._buffer.append(tile)

        # Condition 1: batch full
        if len(self._buffer) >= self._batch_size:
            return self._flush()
        # Condition 2: timeout
        elapsed = (now - self._first_tile_time) * 1000
        if elapsed >= self._max_wait_ms:
            return self._flush()
        return None

    def flush(self) -> list[TileEntry] | None:
        """Force-flush current buffer. Returns None if empty."""
        if not self._buffer:
            return None
        return self._flush()

    def _flush(self) -> list[TileEntry] | None:
        batch = self._buffer
        self._buffer = []
        self._first_tile_time = None
        return batch if batch else None

    def current_size(self) -> int:
        return len(self._buffer)
```

- [ ] **Step 2: 运行测试确认通过**

测试应当验证：batch_size 触发、max_wait 触发、空 flush 返回 None、flush 后 buffer 为空。

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_micro_batch.py -v
```

- [ ] **Step 3: Commit**

```bash
git add gpu_scheduler/micro_batch.py tests/test_micro_batch.py
git commit -m "feat: add MicroBatchAccumulator with size and timeout triggers"
```

---

### Task 2.4: PriorityRouter

**Files:**
- Create: `gpu_scheduler/priority_router.py`
- Test: `tests/test_priority_router.py`

- [ ] **Step 1: 实现 PriorityRouter**

```python
"""Priority router — routes tiles to models based on configured strategy."""
from __future__ import annotations

from dataclasses import dataclass, field
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
```

- [ ] **Step 2: 运行测试确认通过**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_priority_router.py -v
```

- [ ] **Step 3: Commit**

```bash
git add gpu_scheduler/priority_router.py tests/test_priority_router.py
git commit -m "feat: add PriorityRouter with 3 routing strategies (cold_start, hybrid, patchcore_first)"
```

---

### Task 2.5: GPUInferenceScheduler

**Files:**
- Create: `gpu_scheduler/scheduler.py`
- Test: `tests/test_gpu_scheduler.py`

- [ ] **Step 1: 实现 GPUInferenceScheduler**

```python
"""GPU inference scheduler — single-consumer loop with micro-batch and priority routing."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable

import numpy as np

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

    # ── Main loop ──

    def _loop(self) -> None:
        while self._running.is_set():
            # 1. Pull tiles from pool
            batch = self._pool.pop_batch(self._batch_acc.batch_size)
            if batch:
                for tile in batch:
                    decision = self._router.route_initial(tile)
                    self._pending[decision.action].append(decision)

            # 2. Process P0 queue (yolo or patchcore depending on strategy)
            self._process_queue("yolo")
            self._process_queue("patchcore")

            # 3. Process P2 queue (classification — lowest priority, throttle)
            self._process_queue("classification")

            # 4. If nothing to do, brief sleep
            if not any(self._pending.values()):
                time.sleep(0.005)

    def _process_queue(self, model_type: str) -> None:
        decisions = self._pending.get(model_type, [])
        if not decisions:
            return

        if not self._model_pool.is_loaded(model_type):
            # Drop tiles for unloaded models
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

        # Route each result
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

            # Notify listeners
            if self._on_result:
                self._on_result(tile_result)
            if tile_result.result_type == "NG" and self._on_ng:
                self._on_ng(tile_result)

            # Route to next step
            next_decision = self._router.route_after_result(tile, model_type, result)
            if next_decision.action in ("yolo", "patchcore", "classification"):
                self._pending[next_decision.action].append(next_decision)
            # "save", "release", "human_review" are terminal — handled by external callbacks

        self._pending[model_type] = []

    # ── Query ──

    def get_stats(self) -> SchedulerStats:
        return self._stats

    def switch_strategy(self, strategy: RoutingStrategy) -> None:
        self._router.switch_strategy(strategy)
        logger.info("Routing strategy switched to %s", strategy.value)
```

- [ ] **Step 2: 运行测试确认通过**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_gpu_scheduler.py -v
```

- [ ] **Step 3: Commit**

```bash
git add gpu_scheduler/scheduler.py tests/test_gpu_scheduler.py
git commit -m "feat: add GPUInferenceScheduler with single-consumer loop and micro-batch routing"
```

---

## Phase 3: 存储系统（Agent 3 核心）

### Task 3.1: ImageIndexDB

**Files:**
- Create: `storage_v8/__init__.py`
- Create: `storage_v8/image_index.py`
- Test: `tests/test_image_index.py`

- [ ] **Step 1: 实现 ImageIndexDB**

```python
"""Image index database — image_index.db schema and CRUD."""
from __future__ import annotations

import os
import sqlite3


def _index_db_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_dir = os.path.join(base, "data")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "image_index.db")


class ImageIndexDB:
    """SQLite index for saved images with traceability metadata."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or _index_db_path()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS image_index (
                image_id       TEXT PRIMARY KEY,
                run_id         TEXT NOT NULL,
                customer_id    TEXT NOT NULL,
                product_id     TEXT NOT NULL,
                camera_id      TEXT NOT NULL,
                bucket_id      TEXT NOT NULL,
                file_path      TEXT NOT NULL,
                result_type    TEXT NOT NULL,
                defect_type    TEXT DEFAULT '',
                model_version  TEXT NOT NULL,
                model_type     TEXT NOT NULL,
                tile_id        TEXT NOT NULL,
                block_id       TEXT NOT NULL,
                meter_start    REAL,
                meter_end      REAL,
                meter_center   REAL,
                tile_x         INTEGER,
                tile_y         INTEGER,
                confidence     REAL DEFAULT 0.0,
                created_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bucket_registry (
                bucket_id       TEXT PRIMARY KEY,
                run_id          TEXT NOT NULL,
                camera_id       TEXT NOT NULL,
                bucket_type     TEXT NOT NULL,
                bucket_path     TEXT NOT NULL,
                image_count     INTEGER DEFAULT 0,
                total_size_mb   REAL DEFAULT 0.0,
                max_image_count INTEGER,
                max_size_mb     REAL,
                created_at      TEXT NOT NULL,
                closed_at       TEXT,
                status          TEXT DEFAULT 'open'
            );

            CREATE INDEX IF NOT EXISTS idx_img_run_camera ON image_index(run_id, camera_id);
            CREATE INDEX IF NOT EXISTS idx_img_defect ON image_index(defect_type);
            CREATE INDEX IF NOT EXISTS idx_img_meter ON image_index(run_id, meter_center);
            CREATE INDEX IF NOT EXISTS idx_img_result ON image_index(result_type);
            CREATE INDEX IF NOT EXISTS idx_img_bucket ON image_index(bucket_id);
        """)
        conn.commit()
        conn.close()

    def insert_image(self, data: dict) -> None:
        conn = self._get_conn()
        cols = [
            "image_id", "run_id", "customer_id", "product_id", "camera_id",
            "bucket_id", "file_path", "result_type", "defect_type",
            "model_version", "model_type", "tile_id", "block_id",
            "meter_start", "meter_end", "meter_center", "tile_x", "tile_y",
            "confidence", "created_at",
        ]
        placeholders = ", ".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO image_index ({', '.join(cols)}) VALUES ({placeholders})",
            [data.get(c, None) for c in cols],
        )
        conn.commit()
        conn.close()

    def query_by_run(
        self, run_id: str, result_type: str | None = None, camera_id: str | None = None,
        meter_min: float | None = None, meter_max: float | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[dict]:
        conn = self._get_conn()
        where = ["run_id = ?"]
        params: list = [run_id]
        if result_type:
            where.append("result_type = ?")
            params.append(result_type)
        if camera_id:
            where.append("camera_id = ?")
            params.append(camera_id)
        if meter_min is not None:
            where.append("meter_center >= ?")
            params.append(meter_min)
        if meter_max is not None:
            where.append("meter_center <= ?")
            params.append(meter_max)
        sql = f"SELECT * FROM image_index WHERE {' AND '.join(where)} ORDER BY meter_center LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Bucket registry ──

    def create_bucket(self, data: dict) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO bucket_registry (bucket_id, run_id, camera_id, bucket_type, "
            "bucket_path, max_image_count, max_size_mb, created_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')",
            (data["bucket_id"], data["run_id"], data["camera_id"],
             data["bucket_type"], data["bucket_path"],
             data.get("max_image_count"), data.get("max_size_mb"),
             data["created_at"]),
        )
        conn.commit()
        conn.close()

    def close_bucket(self, bucket_id: str, image_count: int, total_size_mb: float) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE bucket_registry SET status='closed', closed_at=datetime('now','localtime'), "
            "image_count=?, total_size_mb=? WHERE bucket_id=?",
            (image_count, total_size_mb, bucket_id),
        )
        conn.commit()
        conn.close()

    def get_open_bucket(self, run_id: str, camera_id: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM bucket_registry WHERE run_id=? AND camera_id=? AND status='open' ORDER BY created_at DESC LIMIT 1",
            (run_id, camera_id),
        ).fetchone()
        conn.close()
        return dict(row) if row else None
```

- [ ] **Step 2: 运行测试确认通过**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_image_index.py -v
```

- [ ] **Step 3: Commit**

```bash
git add storage_v8/__init__.py storage_v8/image_index.py tests/test_image_index.py
git commit -m "feat: add ImageIndexDB with image_index.db schema and bucket registry"
```

---

### Task 3.2: SavePolicyManager

**Files:**
- Create: `storage_v8/save_policy.py`
- Test: `tests/test_save_policy.py`

- [ ] **Step 1: 实现 SavePolicyManager**

```python
"""Save policy manager — controls which tiles get saved to disk."""
from __future__ import annotations

import random
import time
from enum import Enum
from gpu_scheduler.stats import TileResult


class SaveMode(str, Enum):
    SAVE_ALL = "save_all"
    SAVE_NG_ONLY = "save_ng_only"
    SAVE_NG_OK_SAMPLING = "save_ng_ok_sampling"
    RESULT_ONLY = "result_only"


class OkSampler:
    """Sampling controller for OK tiles."""

    def __init__(
        self,
        every_n_tiles: int = 100,
        every_n_meters: float = 10.0,
        every_n_seconds: int = 30,
    ):
        self._every_n_tiles = every_n_tiles
        self._every_n_meters = every_n_meters
        self._every_n_seconds = every_n_seconds

        self._tile_count = 0
        self._last_meter: float | None = None
        self._last_sample_time: float = 0.0

    def should_keep(self, result: TileResult) -> bool:
        self._tile_count += 1

        if self._tile_count % self._every_n_tiles == 0:
            return True

        if self._last_meter is not None:
            if abs(result.meter_start - self._last_meter) >= self._every_n_meters:
                self._last_meter = result.meter_start
                return True
        else:
            self._last_meter = result.meter_start

        now = time.time()
        if now - self._last_sample_time >= self._every_n_seconds:
            self._last_sample_time = now
            return True

        return False


class SavePolicyManager:
    """Determines whether a tile result should be saved to disk.

    NG and UNKNOWN results are always saved (unless RESULT_ONLY mode).
    OK results are handled per the current SaveMode.
    """

    def __init__(self, mode: SaveMode = SaveMode.SAVE_NG_ONLY):
        self._mode = mode
        self._ok_sampler = OkSampler()
        self._stats = {"total_saved": 0, "total_skipped": 0}

    @property
    def mode(self) -> SaveMode:
        return self._mode

    def switch_mode(self, new_mode: SaveMode) -> None:
        self._mode = new_mode

    def should_save_image(self, result: TileResult) -> bool:
        """Decide whether to save the image file. Result JSON is always saved."""
        if self._mode == SaveMode.RESULT_ONLY:
            self._stats["total_skipped"] += 1
            return False

        if result.result_type in ("NG", "UNKNOWN"):
            self._stats["total_saved"] += 1
            return True

        if self._mode == SaveMode.SAVE_ALL:
            self._stats["total_saved"] += 1
            return True

        if self._mode == SaveMode.SAVE_NG_OK_SAMPLING:
            if self._ok_sampler.should_keep(result):
                self._stats["total_saved"] += 1
                return True
            self._stats["total_skipped"] += 1
            return False

        # SAVE_NG_ONLY: OK tiles are NOT saved
        self._stats["total_skipped"] += 1
        return False

    def get_stats(self) -> dict:
        return dict(self._stats)
```

- [ ] **Step 2: 运行测试确认通过**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_save_policy.py -v
```

- [ ] **Step 3: Commit**

```bash
git add storage_v8/save_policy.py tests/test_save_policy.py
git commit -m "feat: add SavePolicyManager with 4 modes and OK sampling strategies"
```

---

### Task 3.3: StorageBucketManager

**Files:**
- Create: `storage_v8/bucket_manager.py`
- Test: `tests/test_bucket_manager.py`

- [ ] **Step 1: 实现 StorageBucketManager**

```python
"""Storage bucket manager — automatic bucket rotation for disk folders."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime

from storage_v8.image_index import ImageIndexDB


@dataclass
class BucketConfig:
    max_images: int = 3000
    max_size_mb: int = 500
    max_duration_min: int = 60


@dataclass
class Bucket:
    bucket_id: str
    run_id: str
    camera_id: str
    bucket_type: str
    bucket_path: str
    max_images: int = 3000
    max_size_mb: int = 500
    max_duration_min: int = 60
    image_count: int = 0
    total_size_bytes: int = 0
    created_time: float = field(default_factory=time.time)

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 * 1024)

    def should_rotate(self) -> bool:
        if self.image_count >= self.max_images:
            return True
        if self.total_size_mb >= self.max_size_mb:
            return True
        elapsed_min = (time.time() - self.created_time) / 60
        if elapsed_min >= self.max_duration_min:
            return True
        return False


class StorageBucketManager:
    """Manages bucket rotation for disk storage.

    Creates new buckets when any threshold (count/size/time) is met.
    Maintains bucket state in image_index.db.
    """

    def __init__(self, base_dir: str, index_db: ImageIndexDB | None = None):
        self._base_dir = base_dir
        self._index_db = index_db or ImageIndexDB()
        self._active_buckets: dict[tuple[str, str], Bucket] = {}  # (run_id, camera_id) → Bucket

    def get_or_create_bucket(
        self,
        run_id: str,
        camera_id: str,
        bucket_type: str = "ng",
        config: BucketConfig | None = None,
    ) -> Bucket:
        cfg = config or BucketConfig()
        key = (run_id, camera_id)

        bucket = self._active_buckets.get(key)
        if bucket is not None and not bucket.should_rotate():
            return bucket

        # Close existing bucket
        if bucket is not None:
            self._index_db.close_bucket(
                bucket.bucket_id, bucket.image_count, bucket.total_size_mb
            )

        # Find next index
        next_idx = 1
        existing = self._index_db.get_open_bucket(run_id, camera_id)
        # Count closed buckets in path
        cam_dir = os.path.join(self._base_dir, run_id, camera_id)
        if os.path.isdir(cam_dir):
            existing_dirs = [d for d in os.listdir(cam_dir) if d.startswith("bucket_")]
            if existing_dirs:
                indices = [int(d.split("_")[1]) for d in existing_dirs]
                next_idx = max(indices) + 1

        bucket_id = f"bucket_{next_idx:06d}"
        bucket_path = os.path.join(cam_dir, bucket_id)
        os.makedirs(bucket_path, exist_ok=True)

        bucket = Bucket(
            bucket_id=bucket_id,
            run_id=run_id,
            camera_id=camera_id,
            bucket_type=bucket_type,
            bucket_path=bucket_path,
            max_images=cfg.max_images,
            max_size_mb=cfg.max_size_mb,
            max_duration_min=cfg.max_duration_min,
        )

        self._index_db.create_bucket({
            "bucket_id": bucket_id,
            "run_id": run_id,
            "camera_id": camera_id,
            "bucket_type": bucket_type,
            "bucket_path": bucket_path,
            "max_image_count": cfg.max_images,
            "max_size_mb": cfg.max_size_mb,
            "created_at": datetime.now().isoformat(),
        })

        self._active_buckets[key] = bucket
        return bucket

    def record_save(self, bucket: Bucket, file_size_bytes: int) -> None:
        bucket.image_count += 1
        bucket.total_size_bytes += file_size_bytes

    def close_all(self) -> None:
        for bucket in self._active_buckets.values():
            self._index_db.close_bucket(
                bucket.bucket_id, bucket.image_count, bucket.total_size_mb
            )
        self._active_buckets.clear()
```

- [ ] **Step 2: 运行测试确认通过**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_bucket_manager.py -v
```

- [ ] **Step 3: Commit**

```bash
git add storage_v8/bucket_manager.py tests/test_bucket_manager.py
git commit -m "feat: add StorageBucketManager with size/count/time rotation triggers"
```

---

### Task 3.4: AsyncDiskWriter

**Files:**
- Create: `storage_v8/async_writer.py`
- Test: `tests/test_async_writer.py`

- [ ] **Step 1: 实现 AsyncDiskWriter**

```python
"""Async disk writer — non-blocking image save via background thread."""
from __future__ import annotations

import logging
import os
import queue
import threading
from datetime import datetime
from typing import Callable

import cv2

from gpu_scheduler.stats import TileResult
from runtime.unified_image_pool import TileEntry
from storage_v8.save_policy import SavePolicyManager
from storage_v8.bucket_manager import StorageBucketManager
from storage_v8.image_index import ImageIndexDB

logger = logging.getLogger(__name__)


class AsyncDiskWriter:
    """Non-blocking disk writer with save policy and bucket management.

    Write requests are queued and processed by a background thread.
    Main detection loop never blocks on disk I/O.
    """

    def __init__(
        self,
        base_dir: str,
        policy: SavePolicyManager,
        bucket_mgr: StorageBucketManager | None = None,
        index_db: ImageIndexDB | None = None,
        queue_size: int = 500,
    ):
        self._base_dir = base_dir
        self._policy = policy
        self._bucket_mgr = bucket_mgr or StorageBucketManager(base_dir, index_db)
        self._index_db = index_db or ImageIndexDB()

        self._queue: queue.Queue[tuple[TileEntry, TileResult]] = queue.Queue(maxsize=queue_size)
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._stats = {"written": 0, "skipped": 0, "failed": 0, "queue_full_drops": 0}

        self._on_write_complete: Callable | None = None

    def set_on_write_complete(self, callback: Callable) -> None:
        self._on_write_complete = callback

    def write(self, tile: TileEntry, result: TileResult) -> bool:
        """Non-blocking write. Returns False if queue is full (tile dropped)."""
        if not self._policy.should_save_image(result):
            self._stats["skipped"] += 1
            return True  # intentionally skipped, not a failure

        try:
            self._queue.put_nowait((tile, result))
            return True
        except queue.Full:
            self._stats["queue_full_drops"] += 1
            logger.warning("Save queue full — dropping tile %s", result.tile_id)
            return False

    def start(self) -> None:
        self._running.set()
        self._thread = threading.Thread(target=self._write_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        # Write any remaining items
        self._drain_queue()
        self._bucket_mgr.close_all()
        if self._thread:
            self._thread.join(timeout=5)

    def _drain_queue(self) -> None:
        count = 0
        while True:
            try:
                item = self._queue.get_nowait()
                self._do_write(*item)
                count += 1
            except queue.Empty:
                break
        if count:
            logger.info("Drained %d pending writes on shutdown", count)

    def _write_loop(self) -> None:
        while self._running.is_set():
            try:
                item = self._queue.get(timeout=0.5)
                self._do_write(*item)
            except queue.Empty:
                continue

    def _do_write(self, tile: TileEntry, result: TileResult) -> None:
        try:
            bucket = self._bucket_mgr.get_or_create_bucket(
                run_id=result.run_id,
                camera_id=result.camera_id,
                bucket_type="ng" if result.result_type == "NG" else "ok",
            )

            # Build filename per spec: cam01_m000123.456_tile0008_model_v003_NG_20260520_203012_123.png
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = (
                f"{result.camera_id}_"
                f"m{result.meter_start:09.3f}_"
                f"tile{tile.tile_index:04d}_"
                f"model_{result.model_version}_"
                f"{result.result_type}_"
                f"{ts}.png"
            )
            filepath = os.path.join(bucket.bucket_path, filename)

            # Save image
            img = tile.image
            if img.ndim == 3 and img.shape[0] == 3:
                img = img.transpose(1, 2, 0)  # CHW → HWC
            cv2.imwrite(filepath, img)

            file_size = os.path.getsize(filepath)
            self._bucket_mgr.record_save(bucket, file_size)

            # Insert into index
            self._index_db.insert_image({
                "image_id": result.tile_id,
                "run_id": result.run_id,
                "customer_id": result.product_id,  # will be enriched upstream
                "product_id": result.product_id,
                "camera_id": result.camera_id,
                "bucket_id": bucket.bucket_id,
                "file_path": filepath,
                "result_type": result.result_type,
                "defect_type": result.defect_type,
                "model_version": result.model_version,
                "model_type": result.model_type,
                "tile_id": result.tile_id,
                "block_id": tile.block_id,
                "meter_start": result.meter_start,
                "meter_end": result.meter_end,
                "meter_center": (result.meter_start + result.meter_end) / 2,
                "tile_x": tile.tile_x,
                "tile_y": tile.tile_y,
                "confidence": result.confidence,
                "created_at": result.created_time,
            })

            self._stats["written"] += 1

            if self._on_write_complete:
                self._on_write_complete(filepath, result)

        except Exception:
            self._stats["failed"] += 1
            logger.exception("Failed to write tile %s", result.tile_id)

    def get_stats(self) -> dict:
        return dict(self._stats)
```

- [ ] **Step 2: 运行测试确认通过**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_async_writer.py -v
```

- [ ] **Step 3: Commit**

```bash
git add storage_v8/async_writer.py tests/test_async_writer.py
git commit -m "feat: add AsyncDiskWriter with non-blocking queue-based image save"
```

---

## Phase 4: 压测系统（Agent 4 核心）

### Task 4.1: MetricsCollector

**Files:**
- Create: `benchmark/__init__.py`
- Create: `benchmark/metrics_collector.py`

- [ ] **Step 1: 实现 MetricsCollector**

```python
"""Metrics collector — samples CPU, GPU, memory, disk, and pipeline stats."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class MetricSnapshot:
    timestamp: float = 0.0
    cpu_percent: float = 0.0
    gpu_percent: float = 0.0
    gpu_vram_used_mb: float = 0.0
    gpu_vram_total_mb: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    pool_usage_ratio: float = 0.0
    disk_write_mbps: float = 0.0
    disk_queue_len: int = 0
    tiles_per_sec: float = 0.0
    avg_inference_ms: float = 0.0
    p95_inference_ms: float = 0.0
    p99_inference_ms: float = 0.0
    acquire_queue_len: int = 0
    save_queue_len: int = 0
    dropped_tiles: int = 0


class MetricsCollector:
    """Samples system and pipeline metrics at configurable intervals.

    Uses psutil for CPU/RAM and nvidia-ml-py for GPU. Gracefully degrades
    if any library is unavailable.
    """

    def __init__(self, sample_interval_sec: float = 0.2):
        self._sample_interval_sec = sample_interval_sec
        self._history: list[MetricSnapshot] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        # Try to init GPU monitoring
        self._nvml_available = False
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml_available = True
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            self._nvml_available = False

        # External refs to be set by benchmark runner
        self._pool = None  # UnifiedImagePool
        self._scheduler = None  # GPUInferenceScheduler
        self._writer = None  # AsyncDiskWriter

    def set_sources(self, pool, scheduler, writer) -> None:
        self._pool = pool
        self._scheduler = scheduler
        self._writer = writer

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _sample_loop(self) -> None:
        last_tiles = 0
        last_time = time.time()
        while self._running:
            time.sleep(self._sample_interval_sec)

            snap = MetricSnapshot(timestamp=time.time())

            # CPU
            try:
                import psutil
                snap.cpu_percent = psutil.cpu_percent(interval=0)
                mem = psutil.virtual_memory()
                snap.ram_used_gb = mem.used / (1024**3)
                snap.ram_total_gb = mem.total / (1024**3)
            except Exception:
                pass

            # GPU
            if self._nvml_available:
                try:
                    import pynvml
                    util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                    snap.gpu_percent = util.gpu
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                    snap.gpu_vram_used_mb = mem_info.used / (1024**2)
                    snap.gpu_vram_total_mb = mem_info.total / (1024**2)
                except Exception:
                    pass

            # Pipeline
            if self._pool is not None:
                snap.pool_usage_ratio = self._pool.usage_ratio()
                snap.dropped_tiles = self._pool.stats().total_dropped
            if self._scheduler is not None:
                sched_stats = self._scheduler.get_stats()
                snap.avg_inference_ms = sched_stats.avg_inference_ms
                snap.p95_inference_ms = sched_stats.p95_inference_ms
                snap.p99_inference_ms = sched_stats.p99_inference_ms
            if self._writer is not None:
                ws = self._writer.get_stats()
                snap.save_queue_len = ws.get("queue_full_drops", 0)

            # Throughput
            if self._pool is not None:
                current_tiles = self._pool.stats().total_pops
                dt = time.time() - last_time
                snap.tiles_per_sec = (current_tiles - last_tiles) / max(dt, 0.001)
                last_tiles = current_tiles
                last_time = time.time()

            with self._lock:
                self._history.append(snap)

    def snapshot(self) -> MetricSnapshot:
        with self._lock:
            if self._history:
                return self._history[-1]
            return MetricSnapshot()

    def history(self) -> list[MetricSnapshot]:
        with self._lock:
            return list(self._history)

    def clear(self) -> None:
        with self._lock:
            self._history.clear()
```

- [ ] **Step 2: Commit**

```bash
git add benchmark/__init__.py benchmark/metrics_collector.py
git commit -m "feat: add MetricsCollector with CPU/GPU/memory/disk/pipeline sampling"
```

---

### Task 4.2: SpiCalculator + HardwareAdvisor

**Files:**
- Create: `benchmark/spi_calculator.py`
- Create: `benchmark/hardware_advisor.py`
- Test: `tests/test_spi_calculator.py`

- [ ] **Step 1: 实现 SpiCalculator**

```python
"""SPI (System Pressure Index) calculator."""
from __future__ import annotations

from benchmark.metrics_collector import MetricSnapshot


class SpiCalculator:
    DEFAULT_WEIGHTS = {
        "camera": 0.20,
        "cpu": 0.20,
        "gpu": 0.30,
        "memory": 0.15,
        "disk": 0.15,
    }

    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = weights or dict(self.DEFAULT_WEIGHTS)

    def compute(self, snapshot: MetricSnapshot) -> float:
        camera = min(snapshot.pool_usage_ratio * 100, 100)
        cpu = min(snapshot.cpu_percent, 100)
        vram_ratio = snapshot.gpu_vram_used_mb / max(snapshot.gpu_vram_total_mb, 1)
        gpu = max(snapshot.gpu_percent, vram_ratio * 100)
        memory = min(snapshot.pool_usage_ratio * 100, 100)
        disk = min(snapshot.disk_write_mbps / 200 * 100, 100)

        spi = (
            camera * self._weights["camera"]
            + cpu * self._weights["cpu"]
            + gpu * self._weights["gpu"]
            + memory * self._weights["memory"]
            + disk * self._weights["disk"]
        )
        return round(spi, 1)

    def pressure_level(self, spi: float) -> str:
        if spi < 40:
            return "low"
        elif spi < 70:
            return "medium"
        elif spi < 85:
            return "high"
        return "critical"

    def compute_from_history(self, history: list[MetricSnapshot]) -> dict:
        if not history:
            return {"avg_spi": 0, "peak_spi": 0, "pressure_level": "low"}
        spis = [self.compute(s) for s in history]
        avg = sum(spis) / len(spis)
        peak = max(spis)
        return {
            "avg_spi": round(avg, 1),
            "peak_spi": round(peak, 1),
            "pressure_level": self.pressure_level(avg),
        }
```

- [ ] **Step 2: 实现 HardwareAdvisor**

```python
"""Hardware advisor — recommends hardware tier based on benchmark results."""
from __future__ import annotations

from enum import Enum


class HardwareTier(str, Enum):
    L1_LIGHT = "L1"         # RK3588 / ARM
    L2_ENTRY = "L2"         # GTX 1650 / RTX 3050
    L3_STANDARD = "L3"      # RTX 4060 / 4060 Ti / 4070
    L4_HIGH = "L4"          # RTX 4080 / 4090 / RTX 5000 Ada


class HardwareAdvisor:
    def recommend(
        self,
        avg_spi: float,
        peak_spi: float,
        avg_tiles_per_sec: float,
        avg_inference_ms: float,
        total_dropped: int,
        gpu_vram_mb: float,
    ) -> dict:
        if avg_spi < 40 and total_dropped == 0:
            tier = HardwareTier.L1_LIGHT
        elif avg_spi < 70 and total_dropped < 10:
            tier = HardwareTier.L2_ENTRY
        elif avg_spi < 85:
            tier = HardwareTier.L3_STANDARD
        else:
            tier = HardwareTier.L4_HIGH

        return {
            "recommended_tier": tier.value,
            "spi_avg": avg_spi,
            "spi_peak": peak_spi,
            "tiles_per_sec": avg_tiles_per_sec,
            "avg_inference_ms": avg_inference_ms,
            "total_dropped": total_dropped,
            "notes": self._tier_notes(tier),
        }

    def _tier_notes(self, tier: HardwareTier) -> str:
        notes = {
            HardwareTier.L1_LIGHT: "轻量平台适用。1相机+低线速+Save NG Only。不适合多模型并行。",
            HardwareTier.L2_ENTRY: "入门独显平台适用。1-3相机+中等线速。建议主模型单独运行。",
            HardwareTier.L3_STANDARD: "标准工业检测平台。3相机+60-100 m/min+YOLO+PatchCore。推荐配置。",
            HardwareTier.L4_HIGH: "高性能平台。3-6相机+高线速+多模型并行+离线回放。",
        }
        return notes[tier]
```

- [ ] **Step 3: 运行测试确认通过**

```bash
cd D:/work/copper-defect-eval-tool && python -m pytest tests/test_spi_calculator.py -v
```

- [ ] **Step 4: Commit**

```bash
git add benchmark/spi_calculator.py benchmark/hardware_advisor.py tests/test_spi_calculator.py
git commit -m "feat: add SpiCalculator and HardwareAdvisor for system pressure evaluation"
```

---

### Task 4.3: InputSource + BenchmarkRunner

**Files:**
- Create: `benchmark/input_source.py`
- Create: `benchmark/benchmark_runner.py`
- Create: `benchmark/report_exporter.py`

- [ ] **Step 1: 实现 InputSource**

```python
"""Benchmark input sources — 4 types for feeding tiles into the pipeline."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator

import numpy as np

from runtime.unified_image_pool import TileEntry


class InputSource(ABC):
    @abstractmethod
    def next_batch(self, batch_size: int) -> list[TileEntry]: ...

    @abstractmethod
    def reset(self) -> None: ...


class SimulatedTileSource(InputSource):
    """Generates synthetic tiles at a configurable rate."""

    def __init__(
        self,
        camera_count: int = 3,
        width: int = 2048,
        line_speed_mpm: float = 80.0,
        defect_rate: float = 0.05,
    ):
        self._camera_count = camera_count
        self._width = width
        self._line_speed_mpm = line_speed_mpm
        self._defect_rate = defect_rate
        self._tile_idx = 0
        self._meter = 0.0
        self._cam_idx = 0

    def next_batch(self, batch_size: int) -> list[TileEntry]:
        tiles = []
        for _ in range(batch_size):
            self._cam_idx = (self._cam_idx % self._camera_count) + 1
            self._meter += 0.1
            self._tile_idx += 1

            is_defect = np.random.random() < self._defect_rate
            if is_defect:
                img = np.random.randint(0, 120, (3, 320, 320), dtype=np.uint8)
                img[:, 100:220, 100:220] = np.random.randint(180, 255, (3, 120, 120), dtype=np.uint8)
            else:
                img = np.random.randint(40, 80, (3, 320, 320), dtype=np.uint8)

            tiles.append(TileEntry(
                tile_id=f"sim_tile_{self._tile_idx:06d}",
                run_id="bench_run",
                customer_id="bench",
                product_id="bench",
                camera_id=f"Camera_{self._cam_idx:02d}",
                block_id=f"sim_block_{self._tile_idx // 20:06d}",
                tile_index=self._tile_idx % 20,
                tile_x=0,
                tile_y=0,
                meter_start=round(self._meter, 3),
                meter_end=round(self._meter + 0.1, 3),
                encoder_count_start=self._tile_idx * 100,
                encoder_count_end=(self._tile_idx + 1) * 100,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                image=img,
            ))
        return tiles

    def reset(self) -> None:
        self._tile_idx = 0
        self._meter = 0.0
        self._cam_idx = 0


class SpeedMultiplierSource(InputSource):
    """Wraps any InputSource and multiplies the tile rate (0.5x to 8x)."""

    def __init__(self, inner: InputSource, multiplier: float = 1.0):
        self._inner = inner
        self._multiplier = multiplier
        self._buffer: list[TileEntry] = []

    def next_batch(self, batch_size: int) -> list[TileEntry]:
        actual_batch = max(1, int(batch_size * self._multiplier))
        return self._inner.next_batch(actual_batch)

    def reset(self) -> None:
        self._inner.reset()
```

- [ ] **Step 2: 实现 BenchmarkRunner**

```python
"""Benchmark runner — orchestrates stress tests with configurable scenarios."""
from __future__ import annotations

import time
from dataclasses import dataclass

from benchmark.input_source import InputSource
from benchmark.metrics_collector import MetricsCollector
from benchmark.spi_calculator import SpiCalculator
from benchmark.hardware_advisor import HardwareAdvisor
from gpu_scheduler.scheduler import GPUInferenceScheduler
from gpu_scheduler.stats import SchedulerStats
from runtime.unified_image_pool import UnifiedImagePool
from storage_v8.async_writer import AsyncDiskWriter


@dataclass
class BenchmarkConfig:
    camera_count: int = 3
    line_speed_mpm: float = 80.0
    model_combo: str = "yolo+patchcore"  # yolo, patchcore, yolo+patchcore
    save_mode: str = "save_ng_only"
    batch_size: int = 4
    max_wait_ms: float = 10.0
    duration_sec: float = 1800  # 30 minutes
    source_type: str = "simulated"  # simulated, real_camera, history_replay
    speed_multiplier: float = 1.0  # 0.5x, 1x, 2x, 4x, 8x


@dataclass
class BenchmarkReport:
    config: BenchmarkConfig
    duration_sec: float
    avg_tiles_per_sec: float
    max_tiles_per_sec: float
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_cpu_pct: float
    peak_cpu_pct: float
    avg_gpu_pct: float
    peak_gpu_pct: float
    avg_vram_mb: float
    peak_vram_mb: float
    avg_ram_gb: float
    peak_ram_gb: float
    avg_spi: float
    peak_spi: float
    total_tiles: int
    total_dropped: int
    total_saved: int
    hardware_advice: dict


class BenchmarkRunner:
    def __init__(
        self,
        source: InputSource,
        pool: UnifiedImagePool,
        scheduler: GPUInferenceScheduler,
        writer: AsyncDiskWriter,
        collector: MetricsCollector | None = None,
    ):
        self._source = source
        self._pool = pool
        self._scheduler = scheduler
        self._writer = writer
        self._collector = collector or MetricsCollector()
        self._collector.set_sources(pool, scheduler, writer)
        self._spi = SpiCalculator()
        self._advisor = HardwareAdvisor()
        self._running = False

    def run(self, config: BenchmarkConfig, progress_callback=None) -> BenchmarkReport:
        self._pool.clear()
        self._collector.clear()
        self._source.reset()

        self._running = True
        self._scheduler.start()
        self._writer.start()
        self._collector.start()

        start_time = time.time()
        end_time = start_time + config.duration_sec

        while time.time() < end_time and self._running:
            tiles = self._source.next_batch(config.batch_size)
            for t in tiles:
                self._pool.push(t)

            if progress_callback:
                elapsed = time.time() - start_time
                progress_callback(elapsed / config.duration_sec, self._collector.snapshot())

            time.sleep(0.01)

        self._writer.stop()
        self._scheduler.stop()
        self._collector.stop()

        return self._build_report(config, time.time() - start_time)

    def stop(self) -> None:
        self._running = False

    def _build_report(self, config: BenchmarkConfig, elapsed: float) -> BenchmarkReport:
        history = self._collector.history()
        if not history:
            return BenchmarkReport(config=config, duration_sec=elapsed, ...)

        tiles_per_sec = [s.tiles_per_sec for s in history]
        spi_data = self._spi.compute_from_history(history)
        sched_stats = self._scheduler.get_stats()

        advice = self._advisor.recommend(
            avg_spi=spi_data["avg_spi"],
            peak_spi=spi_data["peak_spi"],
            avg_tiles_per_sec=sum(tiles_per_sec) / len(tiles_per_sec),
            avg_inference_ms=sched_stats.avg_inference_ms,
            total_dropped=sum(s.dropped_tiles for s in history),
            gpu_vram_mb=max((s.gpu_vram_used_mb for s in history), default=0),
        )

        return BenchmarkReport(
            config=config,
            duration_sec=elapsed,
            avg_tiles_per_sec=sum(tiles_per_sec) / len(tiles_per_sec),
            max_tiles_per_sec=max(tiles_per_sec),
            avg_latency_ms=sched_stats.avg_inference_ms,
            p95_latency_ms=sched_stats.p95_inference_ms,
            p99_latency_ms=sched_stats.p99_inference_ms,
            avg_cpu_pct=sum(s.cpu_percent for s in history) / len(history),
            peak_cpu_pct=max(s.cpu_percent for s in history),
            avg_gpu_pct=sum(s.gpu_percent for s in history) / len(history),
            peak_gpu_pct=max(s.gpu_percent for s in history),
            avg_vram_mb=sum(s.gpu_vram_used_mb for s in history) / len(history),
            peak_vram_mb=max(s.gpu_vram_used_mb for s in history),
            avg_ram_gb=sum(s.ram_used_gb for s in history) / len(history),
            peak_ram_gb=max(s.ram_used_gb for s in history),
            avg_spi=spi_data["avg_spi"],
            peak_spi=spi_data["peak_spi"],
            total_tiles=sched_stats.total_tiles_processed,
            total_dropped=sum(s.dropped_tiles for s in history),
            total_saved=self._writer.get_stats().get("written", 0),
            hardware_advice=advice,
        )
```

- [ ] **Step 3: 实现 report_exporter**

```python
"""Benchmark report exporter — Markdown, JSON, and HTML formats."""
from __future__ import annotations

import json
from datetime import datetime

from benchmark.benchmark_runner import BenchmarkReport


def export_markdown(report: BenchmarkReport) -> str:
    return f"""# Benchmark Report — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Configuration
| Parameter | Value |
|-----------|-------|
| Source | {report.config.source_type} |
| Cameras | {report.config.camera_count} |
| Line Speed | {report.config.line_speed_mpm} m/min |
| Models | {report.config.model_combo} |
| Save Mode | {report.config.save_mode} |
| Batch Size | {report.config.batch_size} |
| Duration | {report.duration_sec:.0f}s |
| Speed Multiplier | {report.config.speed_multiplier}x |

## Throughput
- **Avg Tile/s**: {report.avg_tiles_per_sec:.1f}
- **Max Tile/s**: {report.max_tiles_per_sec:.1f}
- **Total Tiles**: {report.total_tiles}
- **Total Dropped**: {report.total_dropped}
- **Total Saved**: {report.total_saved}

## Latency
- **Avg**: {report.avg_latency_ms:.2f} ms
- **P95**: {report.p95_latency_ms:.2f} ms
- **P99**: {report.p99_latency_ms:.2f} ms

## System Load
| Resource | Avg | Peak |
|----------|-----|------|
| CPU | {report.avg_cpu_pct:.1f}% | {report.peak_cpu_pct:.1f}% |
| GPU | {report.avg_gpu_pct:.1f}% | {report.peak_gpu_pct:.1f}% |
| VRAM | {report.avg_vram_mb:.0f} MB | {report.peak_vram_mb:.0f} MB |
| RAM | {report.avg_ram_gb:.1f} GB | {report.peak_ram_gb:.1f} GB |

## System Pressure Index
- **Avg SPI**: {report.avg_spi:.1f}
- **Peak SPI**: {report.peak_spi:.1f}

## Hardware Recommendation
- **Recommended Tier**: {report.hardware_advice.get('recommended_tier', 'N/A')}
- **Notes**: {report.hardware_advice.get('notes', 'N/A')}
"""


def export_json(report: BenchmarkReport) -> str:
    return json.dumps(report.__dict__, indent=2, default=str)
```

- [ ] **Step 4: Commit**

```bash
git add benchmark/input_source.py benchmark/benchmark_runner.py benchmark/report_exporter.py
git commit -m "feat: add BenchmarkRunner with simulated input source and report export"
```

---

## Phase 5: 集成 + UI

### Task 5.1: 更新 pyproject.toml

- [ ] **Step 1: 添加 nvidia-ml-py 和 psutil 依赖**

在 `pyproject.toml` 的 `dependencies` 中添加：
```toml
"psutil>=5.9.0",
"nvidia-ml-py>=12.560.30",
```

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add psutil and pynvml dependencies for V8 benchmark"
```

---

### Task 5.2: 集成 AcquisitionPipeline → UnifiedImagePool

**Files:**
- Modify: `runtime/acquisition_pipeline.py`

- [ ] **Step 1: 添加 UnifiedImagePool 推入逻辑**

在 `add_line_scan_camera` 的 `_on_block` 回调中，改为向 UnifiedImagePool 推入 tile（而非直接推 FrameBuffer）。添加 `set_image_pool()` 方法。

```python
# New method:
def set_image_pool(self, pool: UnifiedImagePool, tile_gen: TileGenerator) -> None:
    self._image_pool = pool
    self._tile_gen = tile_gen

# Modified on_block callback:
def _on_block(block: LineScanImageBlock) -> None:
    if block.image is not None and self._image_pool is not None:
        tiles = self._tile_gen.slice_block(block)
        for i, tile in enumerate(tiles):
            entry = TileEntry(
                tile_id=tile.tile_id,
                run_id=self._current_run_id,
                customer_id=self._current_customer_id,
                product_id=self._current_product_id,
                camera_id=camera_id,
                block_id=block.block_id,
                tile_index=i,
                tile_x=tile.x0, tile_y=tile.y0,
                meter_start=tile.meter_start, meter_end=tile.meter_end,
                encoder_count_start=block.start_encoder_count,
                encoder_count_end=block.end_encoder_count,
                timestamp=datetime.now().isoformat(),
                image=tile.image,
            )
            self._image_pool.push(entry)
```

- [ ] **Step 2: Commit**

```bash
git add runtime/acquisition_pipeline.py
git commit -m "feat: integrate AcquisitionPipeline with UnifiedImagePool for tile push"
```

---

### Task 5.3: Benchmark UI Page

**Files:**
- Create: `desktop_app/pages/benchmark_page.py`

- [ ] **Step 1: 实现 BenchmarkPage**

使用 PySide6 构建 UI（左侧配置面板 + 右侧实时指标面板 + 底部报告区）。

- [ ] **Step 2: 注册到 MainWindow 和 Navigation**

修改 `desktop_app/main_window.py`：注册 benchmark 页面到 QStackedWidget。
修改 `desktop_app/navigation.py`：添加"压测中心"导航项。

- [ ] **Step 3: Commit**

```bash
git add desktop_app/pages/benchmark_page.py desktop_app/main_window.py desktop_app/navigation.py
git commit -m "feat: add BenchmarkPage UI with real-time metrics and report panel"
```

---

## 优先级与依赖

```
Phase 1 (内存基础) ── 无依赖
    ↓
Phase 2 (GPU调度) ── 依赖 Phase 1
    ↓
Phase 3 (存储) ── 依赖 Phase 2 models (TileResult), 依赖 Phase 1 (TileEntry)
    ↓
Phase 4 (压测) ── 依赖 Phase 2 (SchedulerStats), Phase 3 (AsyncDiskWriter stats)
    ↓
Phase 5 (集成+UI) ── 依赖 Phase 1-4
```

**建议执行顺序**：1.1 → 1.2 → 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 3.1 → 3.2 → 3.3 → 3.4 → 4.1 → 4.2 → 4.3 → 5.1 → 5.2 → 5.3
