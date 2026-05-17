"""Tests for desktop enum display labels."""
from desktop_app.display import (
    MODEL_STATUS_OPTIONS,
    PROJECT_TYPE_OPTIONS,
    SESSION_STATUS_OPTIONS,
    label_for,
    model_status_label,
    project_type_label,
    session_status_label,
)


def test_session_statuses_display_as_chinese_labels():
    assert session_status_label("created") == "已创建"
    assert session_status_label("running") == "运行中"
    assert label_for(SESSION_STATUS_OPTIONS, "unknown_value") == "unknown_value"


def test_project_type_preserves_internal_value_with_chinese_label():
    assert project_type_label("surface_inspection") == "表面检测"
    assert dict(PROJECT_TYPE_OPTIONS)["dimensional"] == "尺寸检测"


def test_model_status_display_labels_cover_common_values():
    assert model_status_label("active") == "已启用"
    assert dict(MODEL_STATUS_OPTIONS)["archived"] == "已归档"
