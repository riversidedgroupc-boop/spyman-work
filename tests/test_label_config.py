"""Tests for configurable classification labels."""
from __future__ import annotations


def test_add_custom_label_persists_and_can_be_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("COPPER_VISION_LABEL_CONFIG_PATH", str(tmp_path / "labels.json"))

    from desktop_app.label_config import add_label, label_text, load_label_options, remove_label

    option = add_label("划伤")

    assert label_text(option.value) == "划伤"
    assert any(item.value == option.value for item in load_label_options())

    remove_label(option.value)

    assert all(item.value != option.value for item in load_label_options())
