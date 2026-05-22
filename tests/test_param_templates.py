"""Tests for camera parameter template management."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from src.device.camera.param_templates import CameraParams, ParamTemplateManager


class TestCameraParams:
    """Unit tests for CameraParams dataclass."""

    def test_defaults(self) -> None:
        p = CameraParams.defaults()
        assert p.pixel_format == "Mono8"
        assert p.exposure_time == 100.0
        assert p.gain == 1.0
        assert p.trigger_mode == "Off"
        assert p.width == 2048
        assert p.block_height == 1024
        assert p.line_rate == 20000

    def test_defaults_with_slot(self) -> None:
        p = CameraParams.defaults("camera_03")
        assert p.camera_slot == "camera_03"

    def test_to_dict_and_back(self) -> None:
        p1 = CameraParams(
            camera_slot="camera_01",
            pixel_format="BayerRG8",
            exposure_time=500.0,
            gain=2.5,
            trigger_mode="On",
            trigger_source="Line1",
            width=4096,
            block_height=512,
            line_rate=50000,
            reverse_y=True,
        )
        d = p1.to_dict()
        p2 = CameraParams.from_dict(d)
        assert p2 == p1

    def test_from_partial_dict(self) -> None:
        p = CameraParams.from_dict({"exposure_time": 42.0, "trigger_mode": "On"})
        assert p.exposure_time == 42.0
        assert p.trigger_mode == "On"
        # Other fields should use defaults
        assert p.gain == 1.0
        assert p.width == 2048


class TestParamTemplateManager:
    """Tests for ParamTemplateManager persistence."""

    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ParamTemplateManager(templates_dir=tmpdir)
            params = CameraParams(
                camera_slot="camera_01",
                exposure_time=200.0,
                gain=3.0,
            )
            path = mgr.save("test_template", params)
            assert os.path.exists(path)
            assert path.endswith(".json")

            loaded = mgr.load("test_template")
            assert loaded is not None
            assert loaded.camera_slot == "camera_01"
            assert loaded.exposure_time == 200.0
            assert loaded.gain == 3.0

    def test_load_nonexistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ParamTemplateManager(templates_dir=tmpdir)
            assert mgr.load("no_such_template") is None

    def test_list_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ParamTemplateManager(templates_dir=tmpdir)
            assert mgr.list_templates() == []

            mgr.save("tpl_a", CameraParams())
            mgr.save("tpl_b", CameraParams())
            mgr.save("tpl_c", CameraParams())

            names = mgr.list_templates()
            assert sorted(names) == ["tpl_a", "tpl_b", "tpl_c"]

    def test_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ParamTemplateManager(templates_dir=tmpdir)
            mgr.save("to_delete", CameraParams())
            assert mgr.load("to_delete") is not None

            assert mgr.delete("to_delete") is True
            assert mgr.load("to_delete") is None

            # Delete nonexistent returns False
            assert mgr.delete("no_such") is False

    def test_export_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ParamTemplateManager(templates_dir=tmpdir)
            params = CameraParams(
                camera_slot="camera_02",
                exposure_time=999.0,
                line_rate=12345,
            )
            mgr.save("export_test", params)

            # Export
            dst = os.path.join(tmpdir, "exported.json")
            mgr.export_to("export_test", dst)
            assert os.path.exists(dst)

            # Import into a new manager
            tmpdir2 = tempfile.mkdtemp()
            try:
                mgr2 = ParamTemplateManager(templates_dir=tmpdir2)
                name = mgr2.import_from(dst)
                assert name == "export_test"

                loaded = mgr2.load("export_test")
                assert loaded is not None
                assert loaded.exposure_time == 999.0
                assert loaded.line_rate == 12345
            finally:
                import shutil
                shutil.rmtree(tmpdir2, ignore_errors=True)

    def test_name_sanitization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ParamTemplateManager(templates_dir=tmpdir)
            mgr.save("CustomerA/Product01:Camera01", CameraParams())
            # Should be saved with sanitized name
            names = mgr.list_templates()
            assert len(names) == 1
            assert "/" not in names[0]
            assert ":" not in names[0]

    def test_get_defaults_class_method(self) -> None:
        p = ParamTemplateManager.get_defaults("camera_05")
        assert p.camera_slot == "camera_05"
        assert p.pixel_format == "Mono8"
