# Field Exploration Hybrid Detection Spec

## 1. Product Positioning

This software is not only a defect model training tool. It is a field engineering tool for the first customer site visit.

Primary field workflow:

```text
collect small amount of site data
-> discover unknown defect/anomaly patterns
-> human review and define defect categories
-> generate first usable model
-> run production-line retest
-> export deployment package and field report
```

At the first visit, customer defect types and representative samples are often unknown. The software must therefore support an exploration-first workflow instead of assuming predefined classes.

## 2. Core Principle

Default mode: exploration first.

Do not force an early OK/NG production conclusion. First help the engineer discover, cluster, review, and name unknown surface anomalies.

Model roles:

- Unsupervised/anomaly model: primary model during unknown-defect exploration.
- YOLO: primary model after confirmed defect categories and labeled samples exist.
- Hybrid fusion: production retest mode, where YOLO detects known defects and anomaly detection catches unknown or missed defects.

## 3. Target User Flow

### Phase 1: OK Baseline Collection

Goal: build a reference set of customer-accepted normal material.

Required UI/workflow:

1. Create or select customer/project/product spec.
2. Configure camera, lighting, encoder, and acquisition settings.
3. Collect OK baseline samples.
4. Record sampling context:
   - product batch
   - line speed
   - camera/light setup
   - operator
   - material condition
5. Run baseline quality checks:
   - exposure range
   - blur
   - brightness variance
   - duplicate images
   - sample count

Output:

- OK baseline dataset
- baseline quality summary
- acquisition configuration snapshot

### Phase 2: Unknown Anomaly Exploration

Goal: find candidate abnormal regions without requiring predefined labels.

Required behavior:

1. Run anomaly model on unlabeled or mixed field samples.
2. Generate anomaly score and heatmap per image.
3. Produce candidate anomaly crops/regions.
4. Rank samples by anomaly score.
5. Group visually similar candidates into clusters if possible.

Do not classify directly as OK/NG in this phase.

Use exploration labels:

```text
normal
anomaly_candidate
known_defect
acceptable_texture
noise_or_reflection
unknown_pending
```

### Phase 3: Human Review and Defect Dictionary

Goal: convert unknown anomaly candidates into usable defect knowledge.

Required UI/workflow:

1. Show anomaly candidates with:
   - original image
   - anomaly heatmap
   - crop/region
   - anomaly score
   - cluster id if available
2. Human reviewer assigns one of:
   - confirmed defect
   - acceptable texture
   - noise/reflection
   - normal
   - unknown pending
3. For confirmed defects, reviewer can create or select a defect type.
4. Defect type record should include:
   - defect code
   - Chinese display name
   - English/internal name
   - severity level
   - description
   - sample images
   - whether it should trigger NG
5. The software builds a first defect dictionary.

Output:

- reviewed anomaly pool
- defect dictionary
- YOLO-ready labeled dataset for confirmed defects

### Phase 4: First YOLO Training

Goal: train YOLO only on confirmed and named defect categories.

Rules:

- Do not train YOLO on unknown_pending samples.
- Do not treat all anomaly candidates as defects.
- Keep acceptable_texture and noise_or_reflection as negative/ignore evidence, not defect classes unless explicitly configured.

Training output:

- `best.pt`
- `last.pt`
- metrics
- training config
- dataset snapshot
- class mapping

Model version should link back to:

- source dataset version
- defect dictionary version
- training job
- baseline acquisition snapshot

### Phase 5: Hybrid Production Retest

Goal: retest on real line or replayed historical samples using YOLO plus anomaly detection.

Recommended fusion logic:

```text
YOLO high-confidence known defect -> NG / Known Defect
YOLO no defect + anomaly normal -> OK
YOLO uncertain + anomaly abnormal -> Suspect
YOLO no defect + anomaly strong abnormal -> Unknown / Needs Review
YOLO defect + anomaly normal -> possible YOLO false positive, send to review if low confidence
```

Retest output states:

```text
OK
NG
Suspect
Unknown
Needs Review
```

Retest metrics should include:

- known defect count
- unknown anomaly count
- suspect count
- OK count
- inference latency
- throughput
- dropped frames
- samples sent to review
- manual confirmation result if available

## 4. Detection Strategy Modes

Add a strategy mode concept.

### `exploration_first`

Default for first customer visit.

- anomaly model primary
- YOLO optional if an existing model is available
- output focuses on anomaly candidates and review queue

### `few_shot_learning`

Used after first defect categories exist.

- YOLO trained on confirmed categories
- anomaly model still used heavily for unknowns
- output includes known defects and anomaly candidates

### `production_retest`

Used for customer line retest.

- YOLO and anomaly model run together
- fusion produces OK/NG/Suspect/Unknown
- review queue captures uncertain samples

### `stable_production`

Used after sufficient data and customer acceptance.

- YOLO primary
- TensorRT engine preferred if available
- anomaly model only catches unknown anomalies or drift

## 5. Suggested Architecture

### New Domain Modules

Create these modules under `core/`:

```text
core/defect_dictionary.py
core/anomaly_review.py
core/hybrid_strategy.py
core/field_session.py
core/deployment_package.py
```

Suggested responsibilities:

#### `core/field_session.py`

Represents one customer field visit or retest session.

Fields:

- `field_session_id`
- `customer_id`
- `project_id`
- `spec_id`
- `session_type`
- `status`
- `hardware_snapshot`
- `acquisition_config_snapshot`
- `created_at`
- `updated_at`
- `notes`

Session types:

```text
baseline_collection
anomaly_exploration
first_training
production_retest
deployment
```

#### `core/defect_dictionary.py`

Stores defect categories discovered at the customer site.

Fields:

- `defect_type_id`
- `project_id`
- `spec_id`
- `code`
- `display_name_zh`
- `display_name_en`
- `severity`
- `description`
- `is_ng`
- `sample_image_paths`
- `created_at`
- `updated_at`

#### `core/anomaly_review.py`

Stores anomaly candidate review records.

Fields:

- `review_id`
- `field_session_id`
- `image_path`
- `crop_path`
- `heatmap_path`
- `anomaly_score`
- `cluster_id`
- `review_status`
- `assigned_defect_type_id`
- `reviewer`
- `reviewed_at`
- `notes`

Review statuses:

```text
unreviewed
confirmed_defect
acceptable_texture
noise_or_reflection
normal
unknown_pending
```

#### `core/hybrid_strategy.py`

Contains deterministic fusion logic.

Inputs:

- YOLO detections
- anomaly scores
- anomaly regions
- confidence thresholds
- strategy mode

Outputs:

- final state
- reason code
- known defects
- unknown anomaly candidates
- review recommendation

Reason codes:

```text
yolo_known_defect
anomaly_unknown_candidate
yolo_uncertain_anomaly_confirmed
clean_by_both_models
possible_yolo_false_positive
needs_manual_review
```

#### `core/deployment_package.py`

Creates a portable deployment package after retest passes.

Package should contain:

```text
model.pt
model.engine optional
class_labels.json
defect_dictionary.json
training_config.json
dataset_summary.json
metrics.json
hardware_profile.json
camera_config.json
software_version.txt
field_report.md/html
```

TensorRT rule:

- `.pt` is the source model and must always be kept.
- `.engine` is a machine-specific acceleration artifact.
- If hardware, driver, CUDA, TensorRT, image size, or model hash changes, mark `.engine` stale.

## 6. UI Changes

Add a new top-level page:

```text
Field Workflow / 现场交付流程
```

This page should show a stepper/checklist:

```text
1. Hardware check
2. OK baseline collection
3. Unknown anomaly exploration
4. Human review and defect dictionary
5. First YOLO training
6. Hybrid production retest
7. Deployment package and report
```

Each step should show:

- status
- blocking issues
- next action
- link to related page

Add or extend pages:

```text
desktop_app/pages/field_workflow_page.py
desktop_app/pages/anomaly_exploration_page.py
desktop_app/pages/anomaly_review_page.py
desktop_app/pages/defect_dictionary_page.py
desktop_app/pages/hybrid_retest_page.py
```

For first implementation, these pages can be simple but must support the data flow.

## 7. Model Execution Order

Do not hard-code one global order such as YOLO-first or anomaly-first.

Use mode-based policy:

```text
exploration_first:
    run anomaly first
    optional YOLO if model exists
    output anomaly candidates

few_shot_learning:
    run YOLO and anomaly in parallel when possible
    YOLO handles known classes
    anomaly catches unknowns

production_retest:
    run YOLO and anomaly in parallel
    fusion emits OK/NG/Suspect/Unknown

stable_production:
    run TensorRT YOLO first if available
    run anomaly as drift/unknown monitor
```

Parallel execution is preferred for production retest if GPU/CPU resources allow it. If resources are limited, use:

```text
YOLO first for stable_production
anomaly first for exploration_first
```

## 8. TensorRT Integration Placement

TensorRT belongs to deployment, not exploration.

Add TensorRT export after:

```text
defect dictionary is stable
YOLO model exists
production retest passes
```

Do not block exploration on TensorRT.

Required TensorRT metadata:

- source `.pt` model hash
- engine path
- GPU name
- compute capability
- driver version
- CUDA version
- TensorRT version
- image size
- FP16/INT8 mode
- export time

Runtime loading rule:

```text
if compatible engine exists:
    use engine
else:
    use .pt and show "TensorRT needs rebuild"
```

## 9. Database / Storage

Prefer SQLite tables consistent with the existing `core/storage.py` pattern.

Add tables:

```text
field_sessions
defect_types
anomaly_reviews
hybrid_retest_runs
deployment_packages
```

Keep file artifacts under project data:

```text
project_data/<customer>/<project>/
  field_sessions/
  anomaly_candidates/
  heatmaps/
  review_crops/
  defect_dictionary/
  retest_runs/
  deployment_packages/
```

## 10. Minimum Implementation Slice

Implement this in small phases.

### Phase A: Data Model and Strategy Core

Files:

- `core/field_session.py`
- `core/defect_dictionary.py`
- `core/anomaly_review.py`
- `core/hybrid_strategy.py`
- tests for all core logic

Acceptance:

- Can create a field session.
- Can create defect types.
- Can store anomaly review records.
- Can run fusion logic on synthetic YOLO/anomaly inputs.

### Phase B: Exploration Workflow UI

Files:

- `desktop_app/pages/field_workflow_page.py`
- `desktop_app/pages/anomaly_review_page.py`
- navigation registration

Acceptance:

- User can see field workflow steps.
- User can review anomaly candidates.
- User can assign candidate to defect type or mark as normal/noise/unknown.

### Phase C: Training Integration

Files:

- `core/dataset_builder.py`
- `desktop_app/workers/training_worker.py`
- `core/model_version.py`

Acceptance:

- YOLO training uses only confirmed defect records.
- Model version links to defect dictionary and field session.
- Unknown pending samples are excluded from YOLO training.

### Phase D: Hybrid Retest

Files:

- `core/hybrid_strategy.py`
- `desktop_app/pages/hybrid_retest_page.py`
- model runner integration

Acceptance:

- Retest emits OK/NG/Suspect/Unknown.
- Unknown anomaly samples go back into review queue.
- Retest summary is saved.

### Phase E: Deployment Package and TensorRT

Files:

- `core/deployment_package.py`
- TensorRT export helper
- model version/deployment metadata

Acceptance:

- Deployment package includes source `.pt`.
- Optional `.engine` can be generated if TensorRT is available.
- Engine compatibility is checked before use.
- Runtime falls back to `.pt` if engine is missing or stale.

## 11. Testing Requirements

Use pytest.

Required tests:

- defect dictionary CRUD
- anomaly review status transitions
- hybrid strategy decision matrix
- unknown samples excluded from YOLO dataset
- deployment package manifest generation
- TensorRT compatibility check with mocked metadata
- field workflow state transitions

Important fusion test cases:

```text
YOLO high confidence + anomaly normal -> NG known defect
YOLO none + anomaly normal -> OK
YOLO none + anomaly high -> Unknown / Needs Review
YOLO low confidence + anomaly high -> Suspect
YOLO high confidence + anomaly high -> NG known defect, anomaly supports
YOLO low confidence + anomaly normal -> possible false positive / review
```

## 12. Non-Goals for First Slice

Do not implement these in the first slice:

- fully automatic defect naming
- fully automatic clustering UI polish
- INT8 TensorRT calibration
- cloud sync
- multi-site model governance
- replacing `.pt` with `.engine`

## 13. Engineering Notes

- Keep `.pt` as the canonical model asset.
- Treat `.engine` as local deployment cache.
- Avoid direct dependency on TensorRT in core modules; use optional imports.
- If TensorRT is unavailable, UI should show a clear disabled state, not fail.
- Keep review decisions auditable.
- Every automatic model decision should have a reason code.
- Exploration mode should avoid overconfident OK/NG wording.

## 14. Recommended First Prompt for Claude Code

Use this prompt to start implementation:

```text
Read docs/field_exploration_hybrid_detection_spec.md and implement Phase A only.

Constraints:
- Do not change unrelated UI pages.
- Follow existing core/storage.py patterns.
- Add pytest coverage for new core modules.
- Keep TensorRT as metadata only in Phase A; do not install TensorRT.
- Do not delete existing project data.
- Run pytest for the new tests and any touched existing tests.
```

