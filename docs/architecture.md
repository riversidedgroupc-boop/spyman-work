# Copper Defect Eval Tool — Architecture Overview

## 1. System Layers

```
┌─────────────────────────────────────────┐
│            Desktop App                   │  PySide6 UI, pages, dialogs, widgets
│          (desktop_app/)                  │  Human-in-the-loop review & control
├─────────────────────────────────────────┤
│              Core                        │  Domain models, evaluation metrics,
│            (core/)                       │  CRUD / SQLite storage, matchers
├─────────────────────────────────────────┤
│               Src                        │  Inference pipelines, fusion engines,
│             (src/)                       │  post-processing, visualisation, reports
├─────────────────────────────────────────┤
│            Runtime                       │  Acquisition / inference / encoder
│          (runtime/)                      │  orchestration (real-time loop)
├─────────────────────────────────────────┤
│         Camera Adapters                  │  Hikrobot MVS, Basler, folder monitor
│       (camera_adapters/)                 │  Hardware abstraction layer
└─────────────────────────────────────────┘
```

| Layer | Role | Key Dependencies |
|-------|------|-----------------|
| Desktop App | Operator-facing GUI, review queue, manual annotation | core + src (via workers) |
| Core | Domain model, evaluation, storage | No Qt, no PyTorch |
| Src | ML inference, fusion logic, report generation | core (via decision_types) |
| Runtime | Real-time acquisition + inference loop | src + camera_adapters |
| Camera Adapters | Hardware abstraction for industrial cameras | Vendor SDKs only |

Supporting packages: `model_runners/` (model wrappers), `trainers/` (training pipelines), `ui/` (Streamlit tools), `integration/` (TCP/HTTP), `benchmark/`, `retrieval/`.

## 2. The core/ vs src/ Split

Two top-level packages exist for a deliberate separation of concerns:

### core/ — Evaluation Domain

- **Purpose**: Data models, storage, and evaluation logic used across the entire system.
- **Key files**: `schema.py` (DetectionBox, ImagePrediction, ImageGroundTruth), `storage.py` (SQLite CRUD), `metrics.py` (precision/recall/mAP), `matcher.py` (IoU matching).
- **Constraint**: Zero dependency on Qt, PyTorch, or any UI framework. This keeps core/ lightweight and testable in CI without GPU hardware.

### src/ — Production Inference Domain

- **Purpose**: ML pipelines, fusion engines, post-processing, and report generation that run on the factory floor.
- **Key files**: `fusion/decision_types.py` (BBoxPrediction, FusionDecision, DefectCandidate), `fusion/hybrid_fusion.py`, `inference/` runners.
- **Constraint**: May depend on core/ for storage and shared utilities, but core/ must never depend on src/.

### Why Both Exist

The project evolved from a research prototype (single inference pipeline) into a production system with evaluation tooling. The research code lived in src/; evaluation tooling was added in core/ without refactoring the existing types. The two type systems converged but were never formally unified.

## 3. Dual Detection Box Models

| Aspect | core.schema.DetectionBox | src.fusion.decision_types.BBoxPrediction |
|--------|--------------------------|------------------------------------------|
| Package | `core/schema.py` | `src/fusion/decision_types.py` |
| Bbox field | `bbox` (list[float], [x1,y1,x2,y2]) | `bbox_xyxy` (list[float], [x1,y1,x2,y2]) |
| Extra fields | `image_name`, `class_id` | `type`, `mask`, `score` |
| Used by | Matcher, metrics, confusion matrix, evaluation | Fusion engines, inference runners, decision pipeline |
| Validation | `__post_init__` checks | None (unvalidated) |

**Adapters**: `core/schema_adapters.py` provides bidirectional conversion:
- `bbox_prediction_to_detection_box(pred, ...)`  fusion → core
- `detection_box_to_bbox_prediction(box)`        core → fusion

**Protocol**: `core/detection_protocol.py` defines `DetectionBoxProtocol` as the structural interface shared by both types.

**Pydantic**: `core/schema_pydantic.py` provides `DetectionBoxV2` for validated serialization at I/O boundaries.

## 4. Three Fusion Engines

| Engine | Location | Strategy | When Used |
|--------|----------|----------|-----------|
| HybridFusionEngine | `core/hybrid_strategy.py` | EXPLORATION_FIRST, FEW_SHOT, PRODUCTION_RETEST, STABLE_PRODUCTION | Batch retest and production evaluation |
| (Legacy) | `src/fusion/` | YOLO_ONLY, ANOMALY_ONLY, DOUBLE_CONFIRM | Original research pipeline |
| (Rule-based) | `src/fusion/` | RULE_BASED | Deterministic rule evaluation |

The three engines should be consolidated into a single engine in `core/` in v1.0, with strategy selection as a simple enum dispatch.

## 5. Recommended Consolidation Path for v1.0

1. **Unify detection box types** — Make `DetectionBox` the single canonical type. Deprecate `BBoxPrediction` with a type alias and migration period.
2. **Merge fusion engines** — Move the remaining src/fusion logic into `core/hybrid_strategy.py`. Keep strategy dispatch as an enum.
3. **Formalize the adapter layer** — Use `DetectionBoxV2` (Pydantic) at all I/O boundaries; use `DetectionBox` (dataclass) internally.
4. **Invert the dependency** — Eventually move `decision_types.py` enums (FinalDecision, FusionStrategy, etc.) into core/ so src/ depends on core/ for types, not the reverse.
5. **Add integration tests** — Cover the full path from camera capture through fusion to evaluation report without mocking.

### Migration Order (by risk)

| Step | Risk | Effort |
|------|------|--------|
| Add Pydantic models + adapters (this phase) | Low | Small |
| Unify box types | Medium | Medium |
| Merge fusion engines | Medium | Large |
| Move enums to core | Low | Small |
| Integration test suite | Low | Large |
