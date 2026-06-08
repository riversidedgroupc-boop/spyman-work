# Phase F: Field Workflow, Sample Reuse, Runtime Capture, and Workspace Split Multi-Agent Brief

> **For Claude Code:** use multi-agent development. Do not rewrite existing modules. First inspect the current implementation, then connect and harden the existing pieces. Do not `git commit` or `git push` unless the owner explicitly asks.
>
> **Recommended agent skill:** use subagent-driven development. Each agent owns a narrow file set and reports findings before implementation.

## 1. Goal

Build the next product-level iteration around the real customer-site workflow:

```text
Project Center
-> Device Configuration
-> Production Runtime View based capture
-> Manual OK / NG / Uncertain triage
-> Unsupervised training v1
-> Assisted capture with unsupervised anomaly scoring
-> Historical same-type sample reuse when useful
-> YOLO annotation from reviewed NG/anomaly candidates
-> Unsupervised optimization + YOLO training
-> Production Runtime View with YOLO + unsupervised hybrid detection
-> Iterative model improvement
-> Benchmark / stress test / hardware recommendation
-> report export
```

The main change is not "add many new modules". The repository already has many modules. Phase F should add a workflow orchestration layer, externalize runtime assets, and put existing pages/services in the right business sequence.

## 2. Product Direction

This software is a field engineering tool for first customer-site defect evaluation.

At the first customer visit:

- there may be no defect samples;
- engineers first collect a small amount of site data;
- humans split samples into `OK`, `NG`, and `Uncertain`;
- unsupervised/anomaly training starts from confirmed `OK` samples;
- anomaly-assisted capture finds more suspicious samples;
- reviewed NG/anomaly candidates later become YOLO annotation candidates;
- YOLO detects known defects after enough labeled samples exist;
- unsupervised detection remains responsible for unknown anomaly discovery.

New project creation must also support reusing historical samples from similar projects. Historical samples can help cold start, but they must keep provenance and must not silently replace current-site samples.

## 3. Hard Constraints

- Do not duplicate existing modules such as project center, capture, production run, training, hybrid retest, benchmark, model export, or report pages.
- Do not delete or bulk move customer/project/sample/model files without explicit owner confirmation.
- Do not modify `.env`, secrets, certificates, CI/CD config, or git history.
- Do not `git commit`, `git push`, `git rebase`, or `git reset --hard` unless explicitly requested.
- Keep the current Python 3.12 + PySide6 + pytest + ruff style.
- Prefer new small core services over large UI-only logic.
- All large/generated/runtime assets must move toward an external workspace root, not the source repository.

## 4. Current Repository Facts

Relevant existing files:

```text
core/project.py                         # project CRUD; currently hard-codes project_data under repo
core/capture_session.py                 # capture sessions and captured_images
core/field_session.py                   # field visit/session workflow data
core/anomaly_dataset_builder.py         # anomaly dataset builder from capture sessions
core/field_training_dataset.py          # YOLO dataset from reviewed field anomalies
core/dataset_version.py                 # dataset version records
core/model_version.py                   # model version records
core/model_export.py                    # ONNX / TensorRT export artifacts
core/hybrid_retest.py                   # YOLO + anomaly retest flow
core/production_event.py                # production defect events
core/storage.py                         # SQLite schema and migrations
desktop_app/main_window.py              # existing page composition and navigation routing
desktop_app/constants.py                # NAV_ITEMS
desktop_app/pages/project_center_page.py
desktop_app/pages/device_config_page.py
desktop_app/pages/camera_config_page.py
desktop_app/pages/capture_page.py
desktop_app/pages/sample_classification_page.py
desktop_app/pages/bbox_annotation_page.py
desktop_app/pages/dataset_version_page.py
desktop_app/pages/field_workflow_page.py
desktop_app/pages/training_page.py
desktop_app/pages/model_version_page.py
desktop_app/pages/production_run_page.py
desktop_app/pages/hybrid_retest_page.py
desktop_app/pages/benchmark_page.py
desktop_app/pages/report_page.py
desktop_app/pages/system_settings_page.py
benchmark/benchmark_runner.py
benchmark/hardware_advisor.py
runtime/acquisition_pipeline.py
runtime/inference_pipeline.py
```

Important current issue:

```text
core/project.py uses PROJECT_DATA_ROOT = <repo>/project_data
core/storage.py defaults DB to <repo>/data/app.db
many outputs still go to outputs/, data/, models/, benchmark/, or project_data/ inside the repo
```

Phase F must introduce a consistent workspace root and gradually route runtime data there.

## 5. Target Folder Policy

Use three sibling roots:

```text
D:\work\copper-defect-eval-tool\              # source code repository
D:\work\copper-defect-eval-tool_external\     # SDKs, runtimes, wheels, downloaded dependencies
D:\work\copper-defect-eval-tool_workspace\    # projects, samples, datasets, models, reports, benchmark outputs
```

`copper-defect-eval-tool_external` already exists and should remain for environment/download/dependency artifacts.

Create or support `copper-defect-eval-tool_workspace` for business/runtime assets:

```text
copper-defect-eval-tool_workspace/
  app_data/
    app.db
    config.json
  projects/
    customer_<customer_id>/
      project_<project_id>/
        project.json
        device_configs/
        sample_sessions/
        captures/
        reviews/
        datasets/
        annotations/
        models/
        predictions/
        production_records/
        benchmark/
        stress_tests/
        reports/
  sample_library/
    manifests/
    assets/
  model_registry/
    unsupervised/
    yolo/
    exported/
      onnx/
      tensorrt/
  benchmarks/
  stress_tests/
  reports/
  temp/
```

Repository may keep:

```text
tests/fixtures/
configs/
docs/
scripts/
small deterministic test assets
```

Repository should not keep customer data, generated project folders, real model weights, benchmark outputs, or training outputs.

## 6. Data Provenance Rules

Every sample used by a project must be traceable.

Required metadata for imported/reused historical samples:

```text
sample_id
current_project_id
current_dataset_version_id
source_kind = current_capture | historical_import | historical_reference
source_project_id
source_dataset_version_id
source_capture_session_id
source_image_id
source_image_path
current_image_path
original_label
current_label
human_review_status
device_config_id or device_config_snapshot
import_reason
created_at
```

Recommended rule:

- `historical_reference`: points to an existing asset; does not copy the image unless needed for training export.
- `historical_import`: copies the image into the current workspace dataset and records provenance.

Historical samples must be visually and semantically reviewed before they become training-critical data for a new project.

## 7. Workflow State Model

Add a project workflow status service. It should derive state from existing data rather than require fragile manual flags.

Recommended states:

```text
new_project
device_config_required
device_configured
initial_capture_ready
initial_capture_done
manual_triage_done
unsupervised_ready
unsupervised_trained
assisted_capture_ready
anomaly_review_pending
yolo_annotation_ready
yolo_training_ready
yolo_trained
hybrid_capture_ready
iteration_active
benchmark_ready
acceptance_ready
```

Gating rules:

- A project without product spec or device config cannot enter real capture.
- A project without confirmed OK samples cannot train unsupervised baseline.
- A project without reviewed and labeled NG/anomaly candidates cannot train YOLO.
- Benchmark and hardware recommendation require selected project, dataset version, and model version.
- Production runtime can open in every capture phase, but enabled overlays depend on available models.

## 8. Production Runtime Placement

`desktop_app/pages/production_run_page.py` is not only a final production page. It should become the shared live runtime view for capture, retest, and production validation.

Target modes:

```text
runtime_mode = setup_capture
runtime_mode = baseline_capture
runtime_mode = anomaly_assisted_capture
runtime_mode = hybrid_capture
runtime_mode = stable_production
runtime_mode = benchmark_replay
```

Expected behavior:

- First capture: live camera/image view + manual OK/NG/Uncertain entry, no model required.
- After unsupervised v1: live view + anomaly score + anomaly candidate routing.
- After YOLO training: live view + YOLO boxes + anomaly score + fused decision.
- Every capture session should be able to launch or embed the production runtime view.

Do not build a second live camera UI if `ProductionRunPage` can be parameterized and reused.

## 9. Multi-Agent Plan

Use the following agents. They may run in parallel only when their file ownership does not overlap.

### Agent 0: Architecture Audit and Contract Lock

Purpose: verify current modules, prevent duplicate development, and write the implementation contract for other agents.

Primary files:

```text
docs/phase_f_field_workflow_workspace_multi_agent_claudecode.md
docs/phase_f_existing_module_map.md
```

Tasks:

- Read current core/UI/runtime/benchmark modules listed in section 4.
- Produce `docs/phase_f_existing_module_map.md`.
- Map each business workflow step to existing modules.
- Identify missing services only where current modules cannot cover the flow.
- Define shared names for workflow states, runtime modes, and workspace paths.

Acceptance:

- The module map clearly says "reuse", "extend", or "new small service" for every workflow node.
- No agent starts broad UI rewrites before this contract is accepted.

### Agent A: Workspace Root and Path Policy

Purpose: move the application toward external business data storage without destructive migration.

Primary files:

```text
core/workspace_paths.py                 # new
core/project.py
core/capture_session.py
core/storage.py
core/production_event.py
core/review.py
trainers/patchcore_trainer.py
trainers/yolo_trainer.py
desktop_app/pages/benchmark_page.py
benchmark/benchmark_runner.py or benchmark services as needed
desktop_app/pages/system_settings_page.py
tests/test_workspace_paths.py           # new
tests/test_project.py
tests/test_capture_session.py
```

Required behavior:

- Default workspace root:

```text
D:\work\copper-defect-eval-tool_workspace
```

- Allow override by env var:

```text
COPPER_VISION_WORKSPACE_ROOT
COPPER_VISION_DB_PATH
```

- Keep existing `COPPER_VISION_DB_PATH` behavior.
- Add a central path service so new code does not call `os.getcwd()` or hard-code `project_data`, `outputs`, `models`, or `data/benchmark`.
- Do not physically move old files in this phase.
- New projects and new runtime outputs should use the workspace root.
- System settings should show:

```text
workspace_root
external_root
db_path
project_data_root
model_registry_root
sample_library_root
benchmark_root
```

Acceptance:

- New project directory creation happens under workspace by default.
- Existing tests can override workspace root with a temp directory.
- Existing old project paths remain readable.

### Agent B: Project Workflow State and Gating

Purpose: make the project center and workflow page reflect the real site sequence.

Primary files:

```text
core/project_workflow.py                # new
core/device_readiness.py                # new if needed
core/project.py
core/camera_config.py
core/capture_session.py
core/dataset_version.py
core/model_version.py
desktop_app/pages/project_center_page.py
desktop_app/pages/field_workflow_page.py
desktop_app/pages/help_page.py
desktop_app/i18n.py
tests/test_project_workflow.py          # new
tests/test_field_workflow_page.py
```

Required behavior:

- Derive workflow state from:

```text
project exists
product spec exists
camera/device config exists
capture session exists
classification counts
dataset versions
field sessions
model versions
anomaly reviews
defect types
benchmark reports if available
```

- Project center should make device configuration the next required step after project/spec creation.
- Field workflow stepper should use derived states and show blocked/available/current without inventing unsupported completion.
- Do not block users from opening pages for inspection; block only destructive or invalid actions.

Acceptance:

- Tests cover no project, project without device config, device configured, initial capture done, OK triage done, unsupervised trained, YOLO trained, and benchmark-ready states.
- UI shows clear next action.

### Agent C: Historical Sample Library and Cross-Project Reuse

Purpose: allow new projects to reuse same-type historical samples safely.

Primary files:

```text
core/sample_library.py                  # new
core/sample_provenance.py               # new if separate
core/dataset_version.py
core/capture_session.py
core/storage.py
desktop_app/pages/dataset_version_page.py
desktop_app/pages/sample_classification_page.py
desktop_app/pages/project_center_page.py
desktop_app/i18n.py
tests/test_sample_library.py            # new
tests/test_dataset_version_integration.py
```

Required behavior:

- Support searching historical samples by:

```text
material
surface_type
geometry_type
product spec
defect type
label
source project
device config snapshot
```

- Support importing or referencing selected samples into current project datasets.
- Preserve provenance fields listed in section 6.
- Distinguish current-site samples from historical samples in UI and dataset summary.
- Historical OK samples may help unsupervised cold start.
- Historical NG samples may help YOLO cold start only after human confirmation.

Acceptance:

- A new project can create a dataset version containing current samples plus selected historical samples.
- Dataset summary shows counts by source kind.
- Training readiness can distinguish current-site evidence from imported evidence.

### Agent D: Production Runtime as Shared Capture View

Purpose: reposition `ProductionRunPage` so every capture round can actually use the live runtime view.

Primary files:

```text
desktop_app/pages/production_run_page.py
desktop_app/pages/capture_page.py
desktop_app/pages/field_workflow_page.py
desktop_app/main_window.py
desktop_app/i18n.py
runtime/acquisition_pipeline.py
runtime/inference_pipeline.py
core/capture_session.py
core/production_event.py
tests/test_production_runtime_modes.py   # new
tests/test_capture_session.py
tests/test_field_workflow_page.py
```

Required behavior:

- Add a runtime mode concept without duplicating production UI.
- From capture session and field workflow, user can open runtime in a mode matched to current workflow state.
- Runtime mode controls overlays and model requirements:

```text
baseline_capture: no model required, manual triage available
anomaly_assisted_capture: unsupervised model required for anomaly score
hybrid_capture: YOLO optional, anomaly model optional, fusion if both exist
stable_production: active production model required unless explicitly dry-run
```

- Capture-generated images/events must be linked to the selected capture session and project.
- Manual OK/NG/Uncertain classification should remain available through existing classification flow or a minimal runtime action path.

Acceptance:

- Tests verify that baseline runtime can start without model version.
- Tests verify hybrid mode chooses YOLO/anomaly model versions when available.
- UI no longer feels like capture and production are unrelated workflows.

### Agent E: Training Flow Alignment

Purpose: align unsupervised and YOLO training with the real data lifecycle.

Primary files:

```text
core/anomaly_dataset_builder.py
core/field_training_dataset.py
core/dataset_validation.py
core/training_job.py
core/model_version.py
desktop_app/pages/training_page.py
desktop_app/pages/field_workflow_page.py
desktop_app/pages/bbox_annotation_page.py
tests/test_anomaly_dataset_builder.py
tests/test_field_training_dataset.py
tests/test_training_page.py
tests/test_field_workflow_training_integration.py
```

Required behavior:

- Unsupervised training must primarily use confirmed OK samples.
- NG and Uncertain samples are validation/review candidates, not unsupervised baseline training data.
- YOLO training is available only for confirmed defect candidates with bbox labels and defect type mapping.
- Unknown/pending anomalies must not become YOLO positive samples.
- The UI should name the stage clearly:

```text
Unsupervised baseline training
Anomaly-assisted capture
YOLO dataset from reviewed defects
Hybrid model iteration
```

Acceptance:

- Tests prove NG samples do not pollute the unsupervised OK baseline dataset.
- Tests prove `unknown_pending` is excluded from YOLO training dataset.
- Model versions link to dataset version, training job, and class mapping.

### Agent F: Benchmark, Stress Test, Hardware Recommendation, and Reports

Purpose: make attached tasks project/model-version aware instead of standalone demos.

Primary files:

```text
benchmark/benchmark_runner.py
benchmark/hardware_advisor.py
benchmark/report_exporter.py
desktop_app/pages/benchmark_page.py
desktop_app/pages/report_page.py
core/deployment_metrics.py
core/report.py
core/model_version.py
core/dataset_version.py
tests/test_benchmark_runner.py
tests/test_report_exporter.py
tests/test_deployment_metrics.py
```

Required behavior:

- Benchmark requires selected project and should allow choosing:

```text
dataset_version
model_version
backend = pytorch | onnx | tensorrt | auto
source_type = simulated | history_replay | real_camera
```

- Results should be saved under workspace project benchmark folders.
- Hardware recommendation should cite measured throughput, latency, dropped frames, CPU/GPU/RAM/VRAM, and selected model combination.
- Reports should include workflow stage, device config, dataset version, model version, benchmark result, and recommendation.

Acceptance:

- Benchmark output is no longer written into repo `data/benchmark` by default.
- Hardware recommendation is based on measured benchmark report, not a free-text guess.
- Project report can include Phase F workflow summary.

### Agent G: Tests, Documentation, and Migration Safety

Purpose: keep the work verifiable and prevent accidental asset loss.

Primary files:

```text
docs/phase_f_migration_guide.md         # new
docs/phase_f_operator_workflow.md       # new or update help docs
README.md
USER_GUIDE.md
tests/
```

Required behavior:

- Add a migration guide for old repo-local data:

```text
old: D:\work\copper-defect-eval-tool\project_data
new: D:\work\copper-defect-eval-tool_workspace\projects
```

- Migration guide must be read-only by default. It may provide copy commands, but no automatic delete.
- Document how to back up before any migration.
- Add a full workflow smoke test checklist:

```text
new project
device config
baseline capture
manual triage
unsupervised training
assisted capture
historical sample import
YOLO annotation
YOLO training
hybrid runtime
benchmark
report
```

Acceptance:

- Docs explain the external workspace split clearly.
- Tests pass for all touched modules.
- No generated large files are added to git.

## 10. Suggested Execution Order

### Phase 0: Read-only audit

- Agent 0 writes `docs/phase_f_existing_module_map.md`.
- Other agents read their owned modules and report risks.
- No code changes except docs.

### Phase 1: Foundation

- Agent A implements workspace path service.
- Agent B implements workflow state derivation.
- Agent G starts migration guide.

Dependency:

```text
Agent C/D/E/F must use Agent A path APIs once available.
Agent D/E/F should use Agent B workflow states once available.
```

### Phase 2: Product workflow features

- Agent C implements sample library and provenance.
- Agent D integrates production runtime into capture/field workflow.
- Agent E aligns training gates and dataset builders.

### Phase 3: Validation and attached tasks

- Agent F aligns benchmark, stress, hardware recommendation, and report export.
- Agent G expands docs and smoke checklist.

### Phase 4: Integration pass

- Run focused tests for changed modules.
- Run broader pytest excluding known hardware-only tests if needed.
- Run ruff on touched files.
- Verify no generated runtime assets were added to git.
- Present change summary before any commit.

## 11. Test Commands

Use focused commands first:

```powershell
python -m pytest tests/test_workspace_paths.py -q
python -m pytest tests/test_project_workflow.py -q
python -m pytest tests/test_sample_library.py -q
python -m pytest tests/test_production_runtime_modes.py -q
python -m pytest tests/test_anomaly_dataset_builder.py tests/test_field_training_dataset.py -q
python -m pytest tests/test_benchmark_runner.py tests/test_report_exporter.py -q
```

Then run the relevant existing integration tests:

```powershell
python -m pytest tests/test_project.py tests/test_capture_session.py tests/test_dataset_version.py tests/test_field_workflow_page.py tests/test_training_page.py -q
```

Full suite only after focused tests pass:

```powershell
python -m pytest tests -q
```

If `tests/device/` requires missing hardware SDK or `src` import setup, report it explicitly rather than hiding the failure.

## 12. Definition of Done

Phase F is done when:

- New project flow pushes the user to device configuration first.
- Capture can launch or use the production runtime view in the correct mode.
- Initial no-defect scenario works with OK baseline and unsupervised training.
- Historical same-type samples can be added with provenance.
- YOLO training is gated behind reviewed and bbox-labeled defect candidates.
- Hybrid runtime supports known defect detection plus unknown anomaly discovery.
- Benchmark/stress/hardware recommendation are tied to project, dataset, and model version.
- New runtime assets default to `D:\work\copper-defect-eval-tool_workspace`.
- Existing repo-local data is not deleted and remains readable.
- Tests and docs cover the new workflow.

## 13. Risks to Watch

- Historical sample reuse can create distribution drift. Keep provenance visible and do not mix samples silently.
- Moving paths too aggressively can break old project records. Use path abstraction and compatibility fallback first.
- Production runtime integration can become a UI rewrite. Parameterize existing `ProductionRunPage` instead.
- YOLO can be trained too early if anomaly candidates are treated as ground truth. Only confirmed, labeled defects are positive samples.
- Unsupervised baseline can be poisoned if NG samples enter OK training. Validate this with tests.
- Benchmark results are not useful unless tied to project/model/dataset/backend.

## 14. Developer Notes for Claude Code

- Start every agent by reading existing tests for its module.
- Prefer small services in `core/` and thin UI calls from `desktop_app/pages/`.
- Use temp directories in tests for workspace root.
- Keep generated project/sample/model artifacts out of git.
- Before any migration script, make it dry-run/read-only by default.
- After each agent finishes, show:

```text
files changed
tests run
known risks
follow-up needed
```
