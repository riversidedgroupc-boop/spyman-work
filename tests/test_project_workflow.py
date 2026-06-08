"""Tests for project workflow state derivation."""
from __future__ import annotations

import os

import pytest

from core.project_workflow import (
    WorkflowState,
    WorkflowStatus,
    derive_workflow_status,
)

@pytest.fixture
def customer():
    from core.customer import create_customer
    return create_customer("Test Corp", "TC")

class TestWorkflowStateEnum:
    def test_all_states_have_display_keys(self) -> None:
        from core.project_workflow import _STATE_DISPLAY
        for state in WorkflowState:
            assert state in _STATE_DISPLAY, f"Missing display key for {state}"

class TestDeriveEmptyProject:
    """No data at all — should be NEW_PROJECT."""

    def test_empty_project_id_returns_new_project(self) -> None:
        status = derive_workflow_status("")
        assert status.state == WorkflowState.NEW_PROJECT

    def test_nonexistent_project_returns_new_project(self) -> None:
        status = derive_workflow_status("PROJ_nonexistent_99999")
        assert status.state == WorkflowState.NEW_PROJECT

    def test_new_project_blocks_capture(self) -> None:
        status = derive_workflow_status("")
        assert "start_capture" in status.blocked_actions

class TestDeviceConfigGate:
    """Project with spec but no device config."""

    def test_spec_only_is_device_config_required(self, customer, make_project_with_spec) -> None:
        project_id = make_project_with_spec(customer.customer_id)
        status = derive_workflow_status(project_id)
        assert status.state == WorkflowState.DEVICE_CONFIG_REQUIRED

    def test_device_configured(self, customer, make_project_with_spec, make_camera_config) -> None:
        project_id, spec_id = make_project_with_spec(customer.customer_id, return_spec=True)
        make_camera_config(spec_id)
        status = derive_workflow_status(project_id)
        assert status.state == WorkflowState.DEVICE_CONFIGURED

class TestCaptureGates:
    """Capture session + classification states."""

    def test_with_capture_session(self, customer, make_project_with_spec, make_camera_config,
                                   make_capture_session) -> None:
        project_id, spec_id = make_project_with_spec(customer.customer_id, return_spec=True)
        make_camera_config(spec_id)
        make_capture_session(project_id, spec_id)
        status = derive_workflow_status(project_id)
        assert status.state == WorkflowState.INITIAL_CAPTURE_READY

    def test_with_classifications_no_ok(self, customer, make_project_with_spec, make_camera_config,
                                         make_capture_session, add_classified_image) -> None:
        project_id, spec_id = make_project_with_spec(customer.customer_id, return_spec=True)
        make_camera_config(spec_id)
        sess_id = make_capture_session(project_id, spec_id)
        add_classified_image(sess_id, project_id, "NG")
        status = derive_workflow_status(project_id)
        assert status.state == WorkflowState.INITIAL_CAPTURE_DONE
        assert "train_unsupervised" in status.blocked_actions

    def test_with_ok_samples_no_model(self, customer, make_project_with_spec, make_camera_config,
                                       make_capture_session, add_classified_image) -> None:
        project_id, spec_id = make_project_with_spec(customer.customer_id, return_spec=True)
        make_camera_config(spec_id)
        sess_id = make_capture_session(project_id, spec_id)
        add_classified_image(sess_id, project_id, "OK")
        status = derive_workflow_status(project_id)
        assert status.state == WorkflowState.MANUAL_TRIAGE_DONE
        assert "train_unsupervised" in status.available_actions

class TestUnsupervisedAndFieldGates:
    """States after unsupervised training."""

    def test_unsupervised_trained(self, customer, make_project_with_spec, make_camera_config,
                                   make_capture_session, add_classified_image,
                                   make_model_version) -> None:
        project_id, spec_id = make_project_with_spec(customer.customer_id, return_spec=True)
        make_camera_config(spec_id)
        sess_id = make_capture_session(project_id, spec_id)
        add_classified_image(sess_id, project_id, "OK")
        make_model_version(project_id, model_type="patchcore", status="completed")
        status = derive_workflow_status(project_id)
        assert status.state == WorkflowState.UNSUPERVISED_TRAINED

class TestYoloGates:
    """States after YOLO training."""

    def test_yolo_trained(self, customer, make_project_with_spec, make_camera_config,
                           make_capture_session, add_classified_image,
                           make_model_version, make_field_session,
                           add_anomaly_review) -> None:
        project_id, spec_id = make_project_with_spec(customer.customer_id, return_spec=True)
        make_camera_config(spec_id)
        sess_id = make_capture_session(project_id, spec_id)
        add_classified_image(sess_id, project_id, "OK")
        make_model_version(project_id, model_type="patchcore", status="completed")
        field_session_id = make_field_session(project_id, spec_id)
        from core.defect_dictionary import create_defect_type
        dt = create_defect_type(project_id=project_id, spec_id=spec_id,
                                code="scratch", display_name_zh="scratch")
        add_anomaly_review(field_session_id, review_status="confirmed_defect",
                           assigned_defect_type_id=dt.defect_type_id)
        make_model_version(project_id, model_type="yolo", status="completed")
        status = derive_workflow_status(project_id)
        assert status.state == WorkflowState.YOLO_TRAINED
        assert "hybrid_capture" in status.available_actions

class TestWorkflowStatusDataclass:
    def test_is_blocked(self) -> None:
        s = WorkflowStatus(state=WorkflowState.NEW_PROJECT, display_key="k",
                           next_action="a")
        assert s.is_blocked

    def test_not_blocked(self) -> None:
        s = WorkflowStatus(state=WorkflowState.DEVICE_CONFIGURED, display_key="k",
                           next_action="a")
        assert not s.is_blocked

# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def make_project_with_spec():
    from core.project import create_project
    from core.product_spec import create_product_spec

    def _make(customer_id: str, return_spec: bool = False):
        proj = create_project(customer_id=customer_id, project_name="wf_test_proj")
        spec = create_product_spec(
            project_id=proj.project_id,
            product_name="test_product",
            material="copper",
            geometry_type="strip",
            surface_type="smooth",
        )
        if return_spec:
            return proj.project_id, spec.spec_id
        return proj.project_id

    return _make

@pytest.fixture
def make_camera_config():
    from core.camera_config import CameraConfig
    from core.storage import insert

    def _make(spec_id: str) -> str:
        from core.id_utils import generate_id
        cid = generate_id("CAMCFG")
        cfg = CameraConfig(
            config_id=cid, spec_id=spec_id, camera_index=1,
            adapter_type="folder_watcher", connection_params="{}",
        )
        insert("camera_configs", cfg.to_dict())
        return cid

    return _make

@pytest.fixture
def make_capture_session():
    from core.capture_session import create_capture_session

    def _make(project_id: str, spec_id: str) -> str:
        sess = create_capture_session(
            project_id=project_id, spec_id=spec_id,
            session_name="test_session",
        )
        return sess.session_id

    return _make

@pytest.fixture
def add_classified_image():
    from core.storage import insert
    from core.id_utils import generate_id

    def _add(session_id: str, project_id: str, label: str) -> str:
        img_id = generate_id("IMG")
        insert("captured_images", {
            "image_id": img_id,
            "session_id": session_id,
            "project_id": project_id,
            "image_path": f"/fake/path/{img_id}.jpg",
            "image_name": f"{img_id}.jpg",
            "classification_label": label,
        })
        return img_id

    return _add

@pytest.fixture
def make_model_version():
    from core.model_version import create_model_version

    def _make(project_id: str, model_type: str = "patchcore", status: str = "completed") -> str:
        m = create_model_version(
            project_id=project_id,
            model_name=f"test_{model_type}",
            model_type=model_type,
            model_path="/fake/model.pt",
            status=status,
        )
        return m.model_id

    return _make

@pytest.fixture
def make_field_session():
    from core.field_session import create_field_session

    def _make(project_id: str, spec_id: str) -> str:
        s = create_field_session(
            project_id=project_id,
            spec_id=spec_id,
            session_type="anomaly_exploration",
        )
        return s.field_session_id

    return _make

@pytest.fixture
def add_anomaly_review():
    from core.storage import insert
    from core.id_utils import generate_id

    def _add(field_session_id: str, review_status: str = "confirmed_defect",
             assigned_defect_type_id: str = "", anomaly_score: float = 0.85) -> str:
        rid = generate_id("REV")
        insert("anomaly_reviews", {
            "review_id": rid,
            "field_session_id": field_session_id,
            "image_path": "/fake/path/img.jpg",
            "crop_path": "",
            "heatmap_path": "",
            "anomaly_score": anomaly_score,
            "cluster_id": "",
            "review_status": review_status,
            "assigned_defect_type_id": assigned_defect_type_id,
            "reviewer": "",
            "reviewed_at": "",
            "notes": "",
        })
        return rid

    return _add
