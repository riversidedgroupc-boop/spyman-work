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


def test_move_label_reorders_options_and_keeps_values(tmp_path, monkeypatch):
    monkeypatch.setenv("COPPER_VISION_LABEL_CONFIG_PATH", str(tmp_path / "labels.json"))

    from desktop_app.label_config import LabelOption, move_label, save_label_options, load_label_options

    save_label_options(
        [
            LabelOption(value="OK", label="OK", color="#2E7D32"),
            LabelOption(value="NG_A", label="NG-A", color="#C62828"),
            LabelOption(value="OIL", label="油污", color="#607D8B"),
        ]
    )

    move_label("OIL", 1)

    assert [option.value for option in load_label_options()] == ["OK", "OIL", "NG_A"]


def test_rename_label_updates_display_text_without_changing_value(tmp_path, monkeypatch):
    monkeypatch.setenv("COPPER_VISION_LABEL_CONFIG_PATH", str(tmp_path / "labels.json"))

    from desktop_app.label_config import LabelOption, label_text, rename_label, save_label_options

    save_label_options([LabelOption(value="OIL", label="油污", color="#607D8B")])

    renamed = rename_label("OIL", "重油污")

    assert renamed == LabelOption(value="OIL", label="重油污", color="#607D8B")
    assert label_text("OIL") == "重油污"
