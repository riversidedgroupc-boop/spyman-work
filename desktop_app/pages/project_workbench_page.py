"""Project workbench — guided testing flow navigator.

Four areas:
  1. Top overview bar — customer / project / spec / stage / progress
  2. Left — 8-step flow list (done / current / blocked / pending)
  3. Right — selected step detail (purpose, steps, criteria, enter button)
  4. Bottom — blocker hint + recommended next step
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QPushButton,
    QSizePolicy,
)

from core.project_workflow import derive_workflow_status, WorkflowState
from core.customer import get_customer
from core.project import get_project
from core.product_spec import get_product_spec
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, I18nManager
from desktop_app.theme_manager import ThemeManager


class _ClickableFrame(QFrame):
    """QFrame that emits clicked when pressed."""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)


# ── WorkflowState → step index (0–7) ───────────────────────────────

_STATE_TO_STEP: dict[WorkflowState, int] = {
    WorkflowState.NEW_PROJECT: 0,
    WorkflowState.DEVICE_CONFIG_REQUIRED: 1,
    WorkflowState.DEVICE_CONFIGURED: 2,
    WorkflowState.INITIAL_CAPTURE_READY: 3,
    WorkflowState.INITIAL_CAPTURE_DONE: 3,
    WorkflowState.MANUAL_TRIAGE_DONE: 4,
    WorkflowState.UNSUPERVISED_READY: 4,
    WorkflowState.UNSUPERVISED_TRAINED: 3,
    WorkflowState.ASSISTED_CAPTURE_READY: 5,
    WorkflowState.ANOMALY_REVIEW_PENDING: 3,
    WorkflowState.YOLO_ANNOTATION_READY: 3,
    WorkflowState.YOLO_TRAINING_READY: 4,
    WorkflowState.YOLO_TRAINED: 5,
    WorkflowState.HYBRID_CAPTURE_READY: 5,
    WorkflowState.ITERATION_ACTIVE: 6,
    WorkflowState.BENCHMARK_READY: 6,
    WorkflowState.ACCEPTANCE_READY: 7,
}

_STEP_NAMES = [
    "workbench.step_project_config",
    "workbench.step_device_config",
    "workbench.step_site_capture",
    "workbench.step_sample_review",
    "workbench.step_model_training",
    "workbench.step_hybrid_detection",
    "workbench.step_performance",
    "workbench.step_delivery",
]

_STEP_PAGE_IDS = [
    "workbench",
    "device_setup",
    "site_capture",
    "sample_review",
    "model_iteration",
    "hybrid_runtime",
    "performance",
    "delivery",
]

_PURPOSE_KEYS = [
    "workbench.purpose_project_config",
    "workbench.purpose_device_config",
    "workbench.purpose_site_capture",
    "workbench.purpose_sample_review",
    "workbench.purpose_model_training",
    "workbench.purpose_hybrid_detection",
    "workbench.purpose_performance",
    "workbench.purpose_delivery",
]

_CRITERIA_KEYS = [
    "workbench.criteria_project_config",
    "workbench.criteria_device_config",
    "workbench.criteria_site_capture",
    "workbench.criteria_sample_review",
    "workbench.criteria_model_training",
    "workbench.criteria_hybrid_detection",
    "workbench.criteria_performance",
    "workbench.criteria_delivery",
]

_OPS_KEYS = [
    "workbench.ops_project_config",
    "workbench.ops_device_config",
    "workbench.ops_site_capture",
    "workbench.ops_sample_review",
    "workbench.ops_model_training",
    "workbench.ops_hybrid_detection",
    "workbench.ops_performance",
    "workbench.ops_delivery",
]

_STEP_ICONS = {
    "done": "✓",        # ✓
    "current": "●",     # ●
    "blocked": "⚠",     # ⚠
    "pending": "○",     # ○
}

_OBJECT_NAMES = {
    "done": "workbenchStepItemDone",
    "current": "workbenchStepItemCurrent",
    "blocked": "workbenchStepItemBlocked",
    "pending": "workbenchStepItem",
}


class ProjectWorkbenchPage(QWidget):
    """Guided testing flow navigator replacing the old status dashboard."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._selected_step_idx: int = 0
        self._step_frames: list[_ClickableFrame] = []
        self._step_state_labels: list[QLabel] = []
        self._step_icon_labels: list[QLabel] = []
        self._step_name_labels: list[QLabel] = []
        self._step_purpose_labels: list[QLabel] = []

        self._build_ui()
        self._ctx.customer_changed.connect(self._on_context_changed)
        self._ctx.project_changed.connect(self._on_context_changed)
        self._ctx.spec_changed.connect(self._on_context_changed)
        I18nManager.instance().language_changed.connect(self._on_lang_changed)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    # ── Build UI ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(20, 16, 20, 16)
        self._content_layout.setSpacing(12)
        scroll.setWidget(content)

        # 1 ── Top overview bar ──
        self._build_overview()
        self._content_layout.addWidget(self._overview_frame)

        # 2 ── Main area: left steps + right detail ──
        main_row = QWidget()
        main_layout = QHBoxLayout(main_row)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        self._build_step_list(main_layout)
        self._build_detail_panel(main_layout)
        self._content_layout.addWidget(main_row, 1)

        # 3 ── Bottom hint bar ──
        self._build_hint_bar()
        self._content_layout.addWidget(self._hint_frame)

    def _build_overview(self) -> None:
        self._overview_frame = QFrame()
        self._overview_frame.setObjectName("workbenchOverview")
        self._overview_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout = QHBoxLayout(self._overview_frame)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(16)

        # Customer
        cust_col = self._make_overview_col(tr("selector.customer"))
        layout.addLayout(cust_col)
        self._overview_customer = cust_col.itemAt(1).widget()

        # Project
        proj_col = self._make_overview_col(tr("selector.project"))
        layout.addLayout(proj_col)
        self._overview_project = proj_col.itemAt(1).widget()

        # Spec
        spec_col = self._make_overview_col(tr("selector.spec"))
        layout.addLayout(spec_col)
        self._overview_spec = spec_col.itemAt(1).widget()

        layout.addStretch()

        # Stage
        stage_col = self._make_overview_col(tr("workbench.current_stage"))
        layout.addLayout(stage_col)
        self._overview_stage = stage_col.itemAt(1).widget()

        # Progress
        prog_col = self._make_overview_col(tr("workbench.progress"))
        layout.addLayout(prog_col)
        self._overview_progress = prog_col.itemAt(1).widget()

    @staticmethod
    def _make_overview_col(label_text: str) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(2)
        header = QLabel(label_text)
        header.setObjectName("secondaryLabel")
        col.addWidget(header)
        value = QLabel("—")
        value.setStyleSheet("font-size: 14px; font-weight: bold;")
        col.addWidget(value)
        return col

    def _build_step_list(self, parent_layout: QHBoxLayout) -> None:
        """Build left-side 8-step scrollable list."""
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        for i in range(8):
            frame = _ClickableFrame()
            frame.setObjectName("workbenchStepItem")
            frame.clicked.connect(lambda idx=i: self._on_step_clicked(idx))

            inner = QHBoxLayout(frame)
            inner.setContentsMargins(12, 10, 12, 10)
            inner.setSpacing(10)

            # Icon
            icon_label = QLabel(_STEP_ICONS["pending"])
            icon_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            icon_label.setFixedWidth(24)
            inner.addWidget(icon_label)
            self._step_icon_labels.append(icon_label)

            # Text column
            text_col = QVBoxLayout()
            text_col.setSpacing(2)

            name_row = QHBoxLayout()
            name_row.setSpacing(8)
            name_label = QLabel(tr(_STEP_NAMES[i]))
            name_label.setStyleSheet("font-size: 13px; font-weight: bold;")
            name_row.addWidget(name_label)
            self._step_name_labels.append(name_label)

            state_label = QLabel("")
            state_label.setObjectName("secondaryLabel")
            name_row.addWidget(state_label)
            name_row.addStretch()
            self._step_state_labels.append(state_label)
            text_col.addLayout(name_row)

            purpose_label = QLabel(tr(_PURPOSE_KEYS[i]))
            purpose_label.setObjectName("secondaryLabel")
            purpose_label.setWordWrap(True)
            text_col.addWidget(purpose_label)
            self._step_purpose_labels.append(purpose_label)

            inner.addLayout(text_col, 1)
            left_layout.addWidget(frame)
            self._step_frames.append(frame)

        left_layout.addStretch()
        parent_layout.addWidget(left_container, 7)

    def _build_detail_panel(self, parent_layout: QHBoxLayout) -> None:
        """Build right-side detail panel for selected step."""
        self._detail_frame = QFrame()
        self._detail_frame.setObjectName("workbenchStepDetail")
        self._detail_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        detail_layout = QVBoxLayout(self._detail_frame)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        detail_layout.setSpacing(12)

        # Step title
        self._detail_title = QLabel()
        self._detail_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        detail_layout.addWidget(self._detail_title)

        # Purpose
        purpose_header = QLabel(tr("workbench.step_purpose"))
        purpose_header.setStyleSheet("font-weight: bold; margin-top: 4px;")
        detail_layout.addWidget(purpose_header)
        self._detail_purpose = QLabel()
        self._detail_purpose.setWordWrap(True)
        c = ThemeManager.current()
        self._detail_purpose.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        detail_layout.addWidget(self._detail_purpose)

        # Operation steps
        ops_header = QLabel(tr("workbench.operation_steps"))
        ops_header.setStyleSheet("font-weight: bold; margin-top: 4px;")
        detail_layout.addWidget(ops_header)
        self._detail_ops = QLabel()
        self._detail_ops.setWordWrap(True)
        self._detail_ops.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        detail_layout.addWidget(self._detail_ops)

        # Completion criteria
        criteria_header = QLabel(tr("workbench.completion_criteria"))
        criteria_header.setStyleSheet("font-weight: bold; margin-top: 4px;")
        detail_layout.addWidget(criteria_header)
        self._detail_criteria = QLabel()
        self._detail_criteria.setWordWrap(True)
        self._detail_criteria.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        detail_layout.addWidget(self._detail_criteria)

        # Missing items
        self._detail_missing_header = QLabel(tr("workbench.missing_items"))
        self._detail_missing_header.setStyleSheet("font-weight: bold; margin-top: 4px;")
        detail_layout.addWidget(self._detail_missing_header)
        self._detail_missing = QLabel()
        self._detail_missing.setWordWrap(True)
        self._detail_missing.setStyleSheet(f"color: {c.WARNING};")
        detail_layout.addWidget(self._detail_missing)

        detail_layout.addStretch()

        # Enter button
        self._detail_enter_btn = QPushButton()
        self._detail_enter_btn.clicked.connect(self._on_enter_clicked)
        detail_layout.addWidget(self._detail_enter_btn)

        parent_layout.addWidget(self._detail_frame, 3)

    def _build_hint_bar(self) -> None:
        self._hint_frame = QFrame()
        self._hint_frame.setObjectName("workbenchNextHint")
        self._hint_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout = QHBoxLayout(self._hint_frame)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # Blocker
        blocker_label = QLabel(tr("workbench.blocker_label") + ":")
        blocker_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(blocker_label)
        self._hint_blocker = QLabel("—")
        self._hint_blocker.setWordWrap(True)
        layout.addWidget(self._hint_blocker)

        layout.addSpacing(16)

        # Recommended next
        next_label = QLabel(tr("workbench.recommended_next") + ":")
        next_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(next_label)
        self._hint_next = QLabel("—")
        self._hint_next.setWordWrap(True)
        layout.addWidget(self._hint_next, 1)

    # ── Public ─────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._refresh()

    # ── Internal: refresh ──────────────────────────────────────────

    def _refresh(self) -> None:
        c = ThemeManager.current()
        customer_id = self._ctx.current_customer_id
        project_id = self._ctx.current_project_id
        spec_id = self._ctx.current_spec_id

        # ── Resolve latest names from DB ──
        customer_name = "—"
        project_name = "—"
        spec_name = "—"

        if customer_id:
            cust = get_customer(customer_id)
            if cust:
                customer_name = cust.customer_name
        if project_id:
            proj = get_project(project_id)
            if proj:
                project_name = proj.project_name
        if spec_id:
            spec = get_product_spec(spec_id)
            if spec:
                spec_name = f"{spec.product_name} ({spec.material}/{spec.geometry_type})"

        self._overview_customer.setText(customer_name)
        self._overview_project.setText(project_name)
        self._overview_spec.setText(spec_name)

        # ── No project at all ──
        if not project_id:
            self._overview_stage.setText("—")
            self._overview_progress.setText("0/8")
            self._show_empty_state()
            return

        # ── Derive workflow status ──
        status = derive_workflow_status(project_id)
        details = status.details
        current_idx = _STATE_TO_STEP.get(status.state, 0)

        # Overview
        stage_name = tr(_STEP_NAMES[current_idx])
        self._overview_stage.setText(stage_name)
        completed = sum(
            1
            for i in range(current_idx)
            if self._is_step_complete(i, details, project_id, spec_id)
        )
        self._overview_progress.setText(f"{completed}/{len(_STEP_NAMES)}")

        # Determine step states
        has_spec = details.get("has_spec", False)
        step_states = self._compute_step_states(current_idx, project_id, has_spec)

        # Update each step frame
        for i in range(8):
            state = step_states[i]
            frame = self._step_frames[i]
            frame.setObjectName(_OBJECT_NAMES[state])
            frame.setStyleSheet("")  # force QSS re-apply
            # Re-apply object name triggers QSS cascade — but we need to
            # force a style refresh. unpolish + repolish is the safe way.
            self.style().unpolish(frame)
            self.style().polish(frame)

            icon = _STEP_ICONS[state]
            icon_color = {
                "done": c.SUCCESS,
                "current": c.PRIMARY,
                "blocked": c.WARNING,
                "pending": c.TEXT_SECONDARY,
            }[state]
            self._step_icon_labels[i].setText(icon)
            self._step_icon_labels[i].setStyleSheet(
                f"font-size: 16px; font-weight: bold; color: {icon_color};"
            )

            self._step_name_labels[i].setText(tr(_STEP_NAMES[i]))
            self._step_purpose_labels[i].setText(tr(_PURPOSE_KEYS[i]))

            state_text = tr(f"workbench.status_{state}")
            self._step_state_labels[i].setText(state_text)
            state_color = {
                "done": c.SUCCESS,
                "current": c.PRIMARY,
                "blocked": c.WARNING,
                "pending": c.TEXT_SECONDARY,
            }[state]
            self._step_state_labels[i].setStyleSheet(
                f"color: {state_color}; font-size: 11px; font-weight: bold;"
            )

        # Update detail panel for currently selected step
        self._selected_step_idx = current_idx
        self._update_detail_panel(current_idx, details, project_id, spec_id)

        # Update hint bar
        self._update_hint_bar(current_idx, details, project_id, spec_id)

    def _show_empty_state(self) -> None:
        """Render empty state when no project is selected."""
        c = ThemeManager.current()
        for i in range(8):
            frame = self._step_frames[i]
            state = "current" if i == 0 else "pending"
            frame.setObjectName(_OBJECT_NAMES[state])
            self.style().unpolish(frame)
            self.style().polish(frame)

            icon = _STEP_ICONS[state]
            icon_color = c.PRIMARY if state == "current" else c.TEXT_SECONDARY
            self._step_icon_labels[i].setText(icon)
            self._step_icon_labels[i].setStyleSheet(
                f"font-size: 16px; font-weight: bold; color: {icon_color};"
            )
            self._step_name_labels[i].setText(tr(_STEP_NAMES[i]))
            self._step_purpose_labels[i].setText(tr(_PURPOSE_KEYS[i]))
            state_text = tr(f"workbench.status_{state}")
            state_color = c.PRIMARY if state == "current" else c.TEXT_SECONDARY
            self._step_state_labels[i].setText(state_text)
            self._step_state_labels[i].setStyleSheet(
                f"color: {state_color}; font-size: 11px; font-weight: bold;"
            )

        self._selected_step_idx = 0
        self._update_detail_panel(0, {}, "", "")
        self._update_hint_bar(0, {}, "", "")

    def _compute_step_states(
        self, current_idx: int, project_id: str, has_spec: bool
    ) -> list[str]:
        """Determine done/current/blocked/pending for each step."""
        states: list[str] = []
        for i in range(8):
            if i < current_idx:
                states.append("done")
            elif i == current_idx:
                states.append("current")
            else:
                # Blocked if a hard prerequisite is missing at current step
                if current_idx == 0 and project_id and not has_spec:
                    states.append("blocked")
                else:
                    states.append("pending")
        return states

    @staticmethod
    def _is_step_complete(
        step_idx: int, details: dict, project_id: str, spec_id: str
    ) -> bool:
        """Check whether a step's completion criteria are met."""
        if step_idx == 0:
            return bool(project_id and details.get("has_spec"))
        elif step_idx == 1:
            return bool(details.get("has_device_config"))
        elif step_idx == 2:
            return bool(details.get("has_capture"))
        elif step_idx == 3:
            return bool(details.get("has_classifications"))
        elif step_idx == 4:
            return bool(
                details.get("has_unsupervised_model")
                or details.get("has_yolo_model")
            )
        elif step_idx == 5:
            return bool(details.get("has_hybrid_detection"))
        elif step_idx == 6:
            return False  # benchmark is optional / late-stage
        elif step_idx == 7:
            return False  # delivery is final
        return False

    # ── Detail panel ───────────────────────────────────────────────

    def _update_detail_panel(
        self, step_idx: int, details: dict, project_id: str, spec_id: str
    ) -> None:
        c = ThemeManager.current()
        step_name = tr(_STEP_NAMES[step_idx])
        self._detail_title.setText(step_name)
        self._detail_purpose.setText(tr(_PURPOSE_KEYS[step_idx]))
        self._detail_ops.setText(tr(_OPS_KEYS[step_idx]))
        self._detail_criteria.setText(tr(_CRITERIA_KEYS[step_idx]))

        # Missing items
        missing = self._get_missing_items(step_idx, details, project_id, spec_id)
        if missing:
            self._detail_missing_header.setVisible(True)
            self._detail_missing.setText("\n".join(f"• {m}" for m in missing))
            self._detail_missing.setStyleSheet(f"color: {c.WARNING};")
        else:
            self._detail_missing_header.setVisible(True)
            self._detail_missing.setText(tr("app.completed"))
            self._detail_missing.setStyleSheet(f"color: {c.SUCCESS};")

        # Enter button
        self._detail_enter_btn.setText(
            tr("workbench.enter_step", step=step_name)
        )

    def _get_missing_items(
        self, step_idx: int, details: dict, project_id: str, spec_id: str
    ) -> list[str]:
        """Collect human-readable missing items for a step."""
        missing: list[str] = []
        if step_idx == 0:
            if not project_id:
                missing.append(tr("workbench.project_missing"))
            elif not details.get("has_spec"):
                missing.append(tr("workbench.spec_missing"))
        elif step_idx == 1:
            if not details.get("has_device_config"):
                missing.append(tr("workbench.hint_no_device"))
        elif step_idx == 2:
            if not details.get("has_capture"):
                missing.append(tr("workbench.hint_no_capture"))
        elif step_idx == 3:
            if not details.get("has_classifications"):
                missing.append(tr("workbench.hint_no_capture"))
        elif step_idx == 4:
            if not details.get("has_unsupervised_model") and not details.get(
                "has_yolo_model"
            ):
                missing.append(tr("workbench.hint_no_model"))
        elif step_idx == 5:
            if not details.get("has_field_session"):
                missing.append(tr("workbench.hint_no_model"))
        elif step_idx in (6, 7):
            pass  # late-stage, criteria are aspirational
        return missing

    # ── Hint bar ───────────────────────────────────────────────────

    def _update_hint_bar(
        self, current_idx: int, details: dict, project_id: str, spec_id: str
    ) -> None:
        c = ThemeManager.current()
        has_spec = details.get("has_spec", False)
        has_device = details.get("has_device_config", False)
        has_capture = details.get("has_capture", False)
        has_model = details.get("has_unsupervised_model") or details.get(
            "has_yolo_model"
        )

        # Determine blocker
        if not project_id:
            blocker = tr("workbench.project_missing")
            hint = tr("workbench.hint_no_spec")
        elif not has_spec:
            blocker = tr("workbench.spec_missing")
            hint = tr("workbench.hint_no_spec")
        elif not has_device:
            blocker = tr("workbench.hint_no_device")
            hint = tr("workbench.hint_no_device")
        elif not has_capture:
            blocker = tr("workbench.hint_no_capture")
            hint = tr("workbench.hint_no_capture")
        elif not has_model:
            blocker = tr("workbench.hint_no_model")
            hint = tr("workbench.hint_no_model")
        else:
            blocker = "—"
            hint = tr(_STEP_NAMES[min(current_idx + 1, 7)])

        self._hint_blocker.setText(blocker)
        self._hint_blocker.setStyleSheet(f"color: {c.WARNING}; font-weight: bold;")
        self._hint_next.setText(hint)
        self._hint_next.setStyleSheet(f"color: {c.TEXT_SECONDARY};")

    # ── Slots ──────────────────────────────────────────────────────

    def _on_step_clicked(self, idx: int) -> None:
        """Select a step in the detail panel without navigating."""
        self._selected_step_idx = idx
        project_id = self._ctx.current_project_id
        spec_id = self._ctx.current_spec_id
        if project_id:
            status = derive_workflow_status(project_id)
            details = status.details
        else:
            details = {}
        self._update_detail_panel(idx, details, project_id, spec_id)

    def _on_enter_clicked(self) -> None:
        """Navigate to the page for the currently selected step."""
        idx = self._selected_step_idx
        page_id = _STEP_PAGE_IDS[idx]
        if page_id == "workbench":
            self._ctx.navigate_to_page.emit("workbench")
            # Signal MainWindow to switch to project-center tab
            self._ctx.navigate_to_project_center.emit()
        else:
            self._ctx.navigate_to_page.emit(page_id)

    def _on_context_changed(self, _value: str = "") -> None:
        self.refresh()

    def _on_lang_changed(self, _lang: str) -> None:
        self.refresh()

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._detail_purpose.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        self._detail_ops.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        self._detail_criteria.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        self._hint_next.setStyleSheet(f"color: {c.TEXT_SECONDARY};")
        self._hint_blocker.setStyleSheet(f"color: {c.WARNING}; font-weight: bold;")
        # Refresh to repaint step item styles
        self.refresh()
