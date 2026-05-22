# Phase B: Field Workflow UI Implementation Brief

This document is for Claude Code. Implement Phase B only.

## Context

The project is a desktop tool for first customer-site defect evaluation:

```text
collect small site data
-> discover unknown anomaly patterns
-> human review and define defect categories
-> generate first usable model
-> production-line retest
```

Phase A is already implemented:

- `core/field_session.py`
- `core/defect_dictionary.py`
- `core/anomaly_review.py`
- `core/hybrid_strategy.py`
- schema support in `core/storage.py`
- tests for Phase A core modules

Phase B must add the exploration workflow UI. Do not implement training integration, hybrid retest, deployment packaging, or TensorRT in this phase.

## Confirmed Product Direction

Use layout option C:

```text
Workflow Hub + Embedded Review
```

The UI should keep the field workflow visible while embedding:

- anomaly review queue
- anomaly candidate details
- review decision controls
- defect dictionary list and creation/edit controls

This is intended for first customer visits where defect classes are not known yet.

## Scope

Implement these files:

```text
desktop_app/pages/field_workflow_page.py
desktop_app/navigation.py
desktop_app/main_window.py
desktop_app/constants.py
desktop_app/i18n.py
tests/test_field_workflow_page.py
```

If the existing app already has a better place for navigation registration, follow the existing pattern.

Do not modify unrelated pages except where required for navigation and imports.

## UI Requirements

Add a new top-level navigation item:

```text
Field Workflow / 现场交付流程
```

Recommended page structure:

```text
FieldWorkflowPage
├── left workflow stepper/checklist
│   ├── Hardware check
│   ├── OK baseline collection
│   ├── Unknown anomaly exploration
│   ├── Human review and defect dictionary
│   ├── First YOLO training
│   ├── Hybrid production retest
│   └── Deployment package and report
└── right work area
    ├── summary/status cards
    ├── anomaly review queue
    ├── candidate detail panel
    └── defect dictionary panel
```

The page can be simple but must be usable. Avoid placeholder-only implementation.

## Data Requirements

Use Phase A APIs:

```python
from core.field_session import (
    create_field_session,
    list_field_sessions,
    update_field_session,
)

from core.anomaly_review import (
    list_anomaly_reviews,
    update_anomaly_review,
    confirm_as_defect,
)

from core.defect_dictionary import (
    create_defect_type,
    list_defect_types,
    get_active_defect_types,
)
```

Use `desktop_app.app_context.AppContext` to get the current project/spec context where existing pages do so.

If no current project/spec is selected, show a clear disabled/empty state:

```text
Please select a customer, project, and product spec first.
```

## Field Session Behavior

The page should support at least:

1. Refresh current project/spec context.
2. Create a field session for the current project/spec.
3. List existing field sessions for the current project.
4. Select a field session.
5. Show session status and notes.

Allowed session types:

```text
baseline_collection
anomaly_exploration
first_training
production_retest
deployment
```

For Phase B, default new sessions to:

```text
anomaly_exploration
```

## Workflow Stepper Requirements

Show these steps with status text:

```text
1. Hardware check
2. OK baseline collection
3. Unknown anomaly exploration
4. Human review and defect dictionary
5. First YOLO training
6. Hybrid production retest
7. Deployment package and report
```

Use deterministic status derived from current data:

- no project/spec selected: blocked
- no field session: blocked
- field session exists: anomaly exploration available
- unreviewed anomaly reviews exist: review pending
- confirmed defect reviews or defect types exist: defect dictionary available

Do not invent completion states that are not backed by data.

## Anomaly Review Queue

Show a table/list of anomaly candidates for the selected field session.

Minimum columns:

```text
review_id
review_status
anomaly_score
cluster_id
image_path
assigned_defect_type_id
reviewer
reviewed_at
```

When a candidate is selected, show details:

```text
image_path
crop_path
heatmap_path
anomaly_score
cluster_id
review_status
notes
```

If image/crop/heatmap paths exist, display paths as text at minimum. Image preview is optional for this phase.

## Review Actions

The user must be able to mark a selected anomaly review as:

```text
confirmed_defect
acceptable_texture
noise_or_reflection
normal
unknown_pending
```

For `confirmed_defect`, user must be able to choose an existing defect type or create a new one first.

When confirming a defect, store:

```text
review_status = confirmed_defect
assigned_defect_type_id = selected defect type
reviewer = text input value, default empty string allowed
reviewed_at = current timestamp
```

For non-defect statuses, update status and reviewer/reviewed timestamp where supported by existing API.

Keep the implementation auditable: do not silently change other fields.

## Defect Dictionary Panel

Show defect types for the current project.

Minimum columns:

```text
code
display_name_zh
display_name_en
severity
is_ng
sample_image_paths
```

Add a small create form:

```text
code
display_name_zh
display_name_en
severity
description
is_ng
```

Severity options:

```text
critical
high
medium
low
info
```

After creating a defect type:

- refresh dictionary list
- allow it to be selected in the review action panel

Editing existing defect types is optional in Phase B. If implemented, keep it minimal.

## Navigation Integration

Add a nav item:

```python
{"id": "field_workflow", "label": "现场交付流程", "icon": "..."}
```

Use an existing simple icon style from `desktop_app/constants.py`.

Register the page in `MainWindow`:

- import `FieldWorkflowPage`
- instantiate once
- add to `QStackedWidget`
- route `page_id == "field_workflow"` to the page
- refresh translated tab/title text if needed

## i18n

Add keys for:

```text
nav.field_workflow
field_workflow.title
field_workflow.create_session
field_workflow.refresh
field_workflow.no_context
field_workflow.steps
field_workflow.review_queue
field_workflow.defect_dictionary
field_workflow.confirm_defect
field_workflow.mark_normal
field_workflow.mark_noise
field_workflow.mark_texture
field_workflow.mark_unknown
```

Chinese and English strings are both required.

Important: keep files encoded as UTF-8.

## Testing Requirements

Add `tests/test_field_workflow_page.py`.

Minimum tests:

1. `FieldWorkflowPage` can be constructed under `QApplication`.
2. No project/spec selected shows empty/blocked state without crashing.
3. Creating/listing a field session path works with a temporary SQLite DB.
4. Defect type list/create helper path works.
5. Anomaly review status update path works.
6. Navigation item and page id are registered.

Follow existing test style for PySide pages in the repository.

Run at least:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_field_workflow_page.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_field_session.py tests\test_defect_dictionary.py tests\test_anomaly_review.py tests\test_hybrid_strategy.py tests\test_fusion.py -q
.\.venv\Scripts\python.exe -m ruff check desktop_app\pages\field_workflow_page.py desktop_app\navigation.py desktop_app\main_window.py desktop_app\constants.py desktop_app\i18n.py tests\test_field_workflow_page.py
```

If time permits, run full pytest:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Non-Goals

Do not implement in Phase B:

- real anomaly model execution
- automatic clustering
- YOLO dataset generation from confirmed defects
- training worker changes
- hybrid retest runtime
- deployment package
- TensorRT export or runtime loading
- new database tables beyond Phase A tables

## Acceptance Criteria

Phase B is accepted when:

- The app has a visible `Field Workflow / 现场交付流程` navigation entry.
- User can create/select a field session for the current project/spec.
- User can see anomaly review candidates for the selected field session.
- User can mark anomaly candidates as defect/texture/noise/normal/unknown.
- User can create/select defect types and assign confirmed anomalies to them.
- The workflow stepper shows data-backed status and blockers.
- Existing Phase A tests still pass.
- New page tests pass.
- Targeted ruff passes.

## Implementation Notes

- Keep UI simple and dense. This is an engineering field tool, not a marketing page.
- Prefer tables, split panels, forms, and explicit status labels.
- Avoid destructive operations.
- Do not delete project data.
- Do not commit or push.
- Keep changes tightly scoped to Phase B.
