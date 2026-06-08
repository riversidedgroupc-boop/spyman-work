# Phase F: Existing Module Map (Agent 0 Audit)

Generated: 2026-05-23. Covers all workflow nodes from the Phase F spec against current code.

## Legend

- **Reuse** — module already covers the workflow step; no changes needed
- **Extend** — module exists but needs new capabilities / API surface
- **New** — module does not exist; must be created
- **Integrate** — module exists but needs wiring into the workflow orchestration

---

## 1. Project Center → Device Configuration

| Workflow Node | Module(s) | Status | Notes |
|---|---|---|---|
| Project CRUD | `core/project.py` | **Extend** | `PROJECT_DATA_ROOT` hardcoded to repo; needs workspace path resolution |
| Customer CRUD | `core/storage.py` (customers table) | Reuse | Schema sufficient |
| Product spec | `core/product_spec.py`, `storage.py` (product_specs table) | Reuse | Fields cover material, geometry, surface, speed |
| Device config | `desktop_app/pages/device_config_page.py`, `core/camera_config.py` | **Extend** | Camera config schema v6 complete; needs device_readiness service |
| Camera config | `desktop_app/pages/camera_config_page.py`, `core/camera_config.py` | Reuse | 6-camera support, structured fields |
| Navigation / routing | `desktop_app/main_window.py`, `desktop_app/constants.py` | Reuse | All pages registered in NAV_ITEMS |

## 2. Capture / Baseline Collection

| Workflow Node | Module(s) | Status | Notes |
|---|---|---|---|
| Capture sessions | `core/capture_session.py` | **Extend** | `session_output_root()` depends on `PROJECT_DATA_ROOT`; needs workspace routing |
| Capture UI | `desktop_app/pages/capture_page.py` | **Extend** | FolderWatchWorker-based; needs integration with production runtime view |
| Image ingestion | `core/capture_session.py` (`add_captured_image`) | Reuse | Dedup logic present |
| Classification labels | `core/capture_session.py` (`set_image_classification`, `get_classification_counts`) | Reuse | OK/NG/Uncertain labels supported |

## 3. Manual Triage (OK / NG / Uncertain)

| Workflow Node | Module(s) | Status | Notes |
|---|---|---|---|
| Sample classification UI | `desktop_app/pages/sample_classification_page.py` | Reuse | Page exists |
| Label policy | `core/label_policy.py` | Reuse | `is_background_label()`, `is_review_label()` |
| Classification counts | `core/capture_session.py` (`get_classification_counts`) | Reuse | Already counts by label |

## 4. Unsupervised Training

| Workflow Node | Module(s) | Status | Notes |
|---|---|---|---|
| Anomaly dataset builder | `core/anomaly_dataset_builder.py` | **Extend** | Already filters OK-only for train; needs workspace output paths |
| Dataset quality check | `core/dataset_quality.py` | Reuse | Already integrated |
| Dataset version record | `core/dataset_version.py` | **Extend** | Needs `source_kind` field for provenance |
| PatchCore trainer | `trainers/patchcore_trainer.py` | **Extend** | Needs workspace model output path |
| Training page UI | `desktop_app/pages/training_page.py` | **Extend** | Needs workflow gating integration |

## 5. Anomaly-Assisted Capture

| Workflow Node | Module(s) | Status | Notes |
|---|---|---|---|
| Production runtime | `desktop_app/pages/production_run_page.py` | **Extend** | Currently requires model; needs `runtime_mode` concept for anomaly_assisted_capture |
| Acquisition pipeline | `runtime/acquisition_pipeline.py` | Reuse | Multi-camera + line-scan support |
| Inference pipeline | `runtime/inference_pipeline.py` | Reuse | Runner-per-camera architecture |
| Anomaly scoring | `model_runners/` | Reuse | PatchCore runner exists |

## 6. Anomaly Review / Defect Dictionary

| Workflow Node | Module(s) | Status | Notes |
|---|---|---|---|
| Field workflow page | `desktop_app/pages/field_workflow_page.py` | **Extend** | Stepper + review queue + defect dictionary exist; stepper uses fixed logic, needs data-derived states |
| Field sessions | `core/field_session.py` | Reuse | Session types: baseline_collection, anomaly_exploration, first_training, production_retest, deployment |
| Anomaly reviews | `core/anomaly_review.py` | Reuse | CRUD + status tracking |
| Defect dictionary | `core/defect_dictionary.py` | Reuse | Defect types with severity, is_ng flag |
| Bbox annotation | `desktop_app/pages/bbox_annotation_page.py` | Reuse | Page exists |

## 7. YOLO Training

| Workflow Node | Module(s) | Status | Notes |
|---|---|---|---|
| YOLO dataset builder | `core/field_training_dataset.py` | **Extend** | Already excludes `unreviewed`/`unknown_pending`; needs workspace paths |
| Training job | `core/training_job.py` | Reuse | Schema exists |
| YOLO trainer | `trainers/yolo_trainer.py` | **Extend** | Needs workspace model output path |
| Model version | `core/model_version.py` | Reuse | Links to dataset_version_id, training_job_id |
| Training page | `desktop_app/pages/training_page.py` | Reuse | Already exists |

## 8. Hybrid Detection (YOLO + Unsupervised)

| Workflow Node | Module(s) | Status | Notes |
|---|---|---|---|
| Hybrid retest flow | `core/hybrid_retest.py` | Reuse | Schema v7 has hybrid_retest_runs/items tables |
| Hybrid retest page | `desktop_app/pages/hybrid_retest_page.py` | Reuse | Page exists |
| Production runtime (hybrid mode) | `desktop_app/pages/production_run_page.py` | **Extend** | Needs hybrid_capture runtime mode |

## 9. Benchmark / Stress Test / Hardware Recommendation

| Workflow Node | Module(s) | Status | Notes |
|---|---|---|---|
| Benchmark runner | `benchmark/benchmark_runner.py` | **Extend** | Needs project/model/dataset version linkage; output to workspace |
| Hardware advisor | `benchmark/hardware_advisor.py` | **Extend** | Needs measured metrics input |
| Report exporter | `benchmark/report_exporter.py` | **Extend** | Needs workspace output path |
| Benchmark UI | `desktop_app/pages/benchmark_page.py` | **Extend** | No project/model-version/dataset-version selectors |

## 10. Report Export

| Workflow Node | Module(s) | Status | Notes |
|---|---|---|---|
| Report page | `desktop_app/pages/report_page.py` | **Extend** | Needs workflow summary, benchmark results integration |
| Core report | `core/report.py` | **Extend** | Needs project/model/dataset linkage |

---

## New Modules Required

| Module | Agent | Purpose |
|---|---|---|
| `core/workspace_paths.py` | A | Central path resolution; env var overrides; three-root strategy |
| `core/project_workflow.py` | B | Derive workflow state from existing data; gating rules |
| `core/device_readiness.py` | B | Check device/camera config completeness |
| `core/sample_library.py` | C | Search, import, reference historical samples |
| `core/sample_provenance.py` | C | Provenance metadata model and tracking |

---

## Path Hardcoding Summary

All locations that currently write inside the repo and need workspace routing:

| File | Current Path | Target |
|---|---|---|
| `core/project.py:12-14` | `<repo>/project_data` | `<workspace>/projects` |
| `core/storage.py:9-16` | `<repo>/data/app.db` | `<workspace>/app_data/app.db` (with env override) |
| `desktop_app/pages/production_run_page.py:313-317` | `outputs/<spec_id>/run_*` | `<workspace>/projects/.../production_records/` |
| `desktop_app/pages/field_workflow_page.py:682-685` | `outputs/datasets/...` | `<workspace>/projects/.../datasets/` |
| `benchmark/benchmark_runner.py` | in-memory / repo paths | `<workspace>/benchmarks/` or `<workspace>/projects/.../benchmark/` |

---

## Risk Items Confirmed

1. **ProductionRunPage hard-depends on model**: `_start()` at line 296 returns early if `model_id` is empty. Blocking for baseline_capture mode.
2. **`field_training_dataset.py` already has exclusion logic**: `_EXCLUDED_STATUSES = {"unreviewed", "unknown_pending"}` — training alignment is partially in place.
3. **FieldWorkflowPage stepper is fixed**: `_update_stepper()` uses hardcoded step transitions, not data-derived states.
4. **No sample_library or provenance tables exist in schema v8** — Agent C needs schema migration v9.
5. **`_workspace` and `_external` directories**: `_external` exists; `_workspace` does not exist yet.
