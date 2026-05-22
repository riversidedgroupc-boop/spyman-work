# V8 实时性能调度与硬件选型评估 — 架构设计

> 项目: copper-defect-eval-tool (v0.7.0 → v0.8.0)
> 来源: 第八版 Claude Code 开发任务书

## 核心架构决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 模块组织 | 方案 B：分散增强 | 各模块独立演进，不创建 `v8/` 临时包 |
| 推理路由 | 策略可切换（cold_start / hybrid_yolo_first / patchcore_first） | 支持首次客户现场零样本冷启动 |
| 消费者模型 | 单消费者串行 + batch | 避免多 stream 竞争，结果有序，显存可控 |
| 图像索引数据库 | 独立 `data/image_index.db` | 与 `app.db` 分离，避免锁竞争 |
| 内存管理 | 预分配 numpy 槽位 + 无锁环形队列 | 1000+ tile/s 场景零 GC 抖动 |

## 新增模块

```
runtime/
  unified_image_pool.py          # 统一图像池（预分配+无锁）
  ring_buffer.py                  # RAM环形缓冲区升级

gpu_scheduler/
  scheduler.py                    # GPUInferenceScheduler 主调度器
  model_pool.py                   # ModelEnginePool 模型加载/显存管理
  micro_batch.py                  # MicroBatchAccumulator 批次累积
  priority_router.py              # PriorityRouter 策略路由
  stats.py                        # 推理统计

storage_v8/
  save_policy.py                  # SavePolicyManager 4模式+冷启动
  bucket_manager.py               # StorageBucketManager 分桶
  async_writer.py                 # AsyncDiskWriter 队列+后台线程
  image_index.py                  # ImageIndexDB CRUD+schema

benchmark/
  benchmark_runner.py             # BenchmarkRunner 压测引擎
  input_source.py                 # 4种输入源
  metrics_collector.py            # MetricsCollector 系统指标采集
  spi_calculator.py               # SpiCalculator SPI计算
  hardware_advisor.py             # HardwareAdvisor 硬件推荐
  report_exporter.py              # 报告导出

desktop_app/pages/
  benchmark_page.py               # Benchmark UI

tests/                            # 对应各模块的测试文件
```

## 数据流

```
Camera 1..6 → BlockBuilder → TileGenerator
                                    ↓
                            UnifiedImagePool
                                    ↓
                    GPUInferenceScheduler (单消费者)
                        ├─ MicroBatchAccumulator
                        └─ PriorityRouter
                                    ↓
                            ModelEnginePool
                              ├─ YOLO Engine (P0, 常驻)
                              ├─ PatchCore Engine (P0, 常驻)
                              └─ Classification Engine (P2, 按需)
                                    ↓
                            ResultFusion
                              ├─ OK  → SavePolicy → 释放/抽样
                              └─ NG  → AsyncDiskWriter → StorageBucketManager
                                                ↓
                                          image_index.db
```

## 路由策略

| 策略 | P0 | P1 | P2 | 适用 |
|------|----|----|----|------|
| cold_start | patchcore | (人工复判) | - | 首次客户现场，零样本 |
| hybrid_yolo_first | yolo | patchcore | classification | 生产默认 |
| patchcore_first | patchcore | yolo | classification | YOLO 未成熟 |

## SavePolicy 模式

- `save_all` — 调试/样本采集/冷启动
- `save_ng_only` — 生产默认
- `save_ng_ok_sampling` — 模型持续优化
- `result_only` — 压力测试

NG/UNKNOWN 始终优先保存。策略运行时热切换。

## SPI 系统压力指数

SPI = Camera(20%) + CPU(20%) + GPU(30%) + Memory(15%) + Disk(15%)

- 0-40: 低压力，低端平台可用
- 40-70: 中压力，需独显
- 70-85: 高压力，需较强 NVIDIA GPU
- 85-100: 极高压力，有丢帧风险

## 硬件等级

- L1: RK3588 / ARM 工控（1相机, 低线速, 轻量模型）
- L2: GTX 1650 / RTX 3050（1-3相机, 中等线速）
- L3: RTX 4060 / 4060 Ti / 4070（3相机, 60-100 m/min）
- L4: RTX 4080 / 4090（3-6相机, 高线速, 多模型）

## 修改的现有文件

- `runtime/acquisition_pipeline.py` — 适配 UnifiedImagePool
- `runtime/inference_pipeline.py` — 适配 GPUInferenceScheduler
- `desktop_app/main_window.py` — 注册 benchmark 页
- `desktop_app/navigation.py` — 添加导航项
- `pyproject.toml` — 添加 nvidia-ml-py 依赖

## P0/P1 优先级

P0: UnifiedImagePool, RAMRingBuffer, GPUInferenceScheduler, ModelEnginePool, MicroBatch, SavePolicyManager, StorageBucketManager, AsyncDiskWriter, image_index.db, BenchmarkMode基础版, SPI基础版

P1: 条件触发 PatchCore, 模型优先级调度, OK Sampling 多种策略, 磁盘降级策略, 历史图像倍率回放, GPU P95/P99 延迟统计, 压测报告导出, 硬件等级推荐
