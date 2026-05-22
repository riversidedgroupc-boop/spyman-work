"""Tests for camera binding store."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.device.camera.binding_store import BindingStore, CameraBinding, SLOT_IDS


class TestCameraBinding:
    """Unit tests for CameraBinding dataclass."""

    def test_default_construction(self) -> None:
        b = CameraBinding(camera_slot="camera_01")
        assert b.camera_slot == "camera_01"
        assert b.enabled is True
        assert b.role == "spare"
        assert b.serial_number == ""
        assert b.mac_address == ""
        assert b.ip_address == ""
        assert b.model == ""
        assert b.param_profile == ""

    def test_invalid_slot_raises(self) -> None:
        try:
            CameraBinding(camera_slot="camera_07")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_all_valid_slots(self) -> None:
        for sid in SLOT_IDS:
            b = CameraBinding(camera_slot=sid)
            assert b.camera_slot == sid

    def test_to_dict(self) -> None:
        b = CameraBinding(
            camera_slot="camera_01",
            enabled=True,
            role="top",
            serial_number="SN001",
            mac_address="AA:BB:CC:DD:EE:FF",
            ip_address="192.168.1.100",
            model="MV-CL022-91GC",
        )
        d = b.to_dict()
        assert d["camera_slot"] == "camera_01"
        assert d["serial_number"] == "SN001"
        assert d["role"] == "top"

    def test_from_dict(self) -> None:
        data = {
            "camera_slot": "camera_03",
            "enabled": False,
            "role": "left",
            "serial_number": "SN003",
            "mac_address": "11:22:33:44:55:66",
        }
        b = CameraBinding.from_dict(data)
        assert b.camera_slot == "camera_03"
        assert b.enabled is False
        assert b.role == "left"
        assert b.serial_number == "SN003"

    def test_roundtrip(self) -> None:
        b1 = CameraBinding(
            camera_slot="camera_02",
            serial_number="SN-RT-001",
            mac_address="DE:AD:BE:EF:00:01",
            ip_address="10.0.0.1",
            model="TestCam",
            role="right",
        )
        b2 = CameraBinding.from_dict(b1.to_dict())
        assert b2 == b1


class TestBindingStore:
    """Tests for BindingStore persistence."""

    def test_empty_store_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BindingStore(config_dir=tmpdir)
            bindings = store.load_all()
            assert bindings == []

    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BindingStore(config_dir=tmpdir)
            b1 = CameraBinding(camera_slot="camera_01", serial_number="SN-A")
            b2 = CameraBinding(camera_slot="camera_02", serial_number="SN-B")
            store.set_binding(b1)
            store.set_binding(b2)
            store.save_all()

            # Reload from disk
            store2 = BindingStore(config_dir=tmpdir)
            loaded = store2.load_all()
            assert len(loaded) == 2
            sns = {b.serial_number for b in loaded}
            assert sns == {"SN-A", "SN-B"}

    def test_get_serial_map(self) -> None:
        store = BindingStore(config_dir="/nonexistent")
        b1 = CameraBinding(camera_slot="camera_01", serial_number="SN10", enabled=True)
        b2 = CameraBinding(camera_slot="camera_02", serial_number="SN20", enabled=True)
        b3 = CameraBinding(camera_slot="camera_03", serial_number="SN30", enabled=False)
        b4 = CameraBinding(camera_slot="camera_04", serial_number="", enabled=True)
        store.set_binding(b1)
        store.set_binding(b2)
        store.set_binding(b3)
        store.set_binding(b4)

        smap = store.get_serial_map()
        assert smap == {"camera_01": "SN10", "camera_02": "SN20"}
        # camera_03 is disabled, camera_04 has no serial

    def test_find_by_serial(self) -> None:
        store = BindingStore(config_dir="/nonexistent")
        store.set_binding(CameraBinding(camera_slot="camera_01", serial_number="FINDME"))
        store.set_binding(CameraBinding(camera_slot="camera_02", serial_number="OTHER"))

        found = store.find_by_serial("FINDME")
        assert found is not None
        assert found.camera_slot == "camera_01"

        not_found = store.find_by_serial("NOPE")
        assert not_found is None

    def test_find_by_mac(self) -> None:
        store = BindingStore(config_dir="/nonexistent")
        store.set_binding(CameraBinding(
            camera_slot="camera_01", serial_number="S1", mac_address="AA:BB:CC:DD:EE:FF"
        ))

        found = store.find_by_mac("aa:bb:cc:dd:ee:ff")  # case-insensitive
        assert found is not None
        assert found.camera_slot == "camera_01"

    def test_remove_binding(self) -> None:
        store = BindingStore(config_dir="/nonexistent")
        store.set_binding(CameraBinding(camera_slot="camera_01", serial_number="S1"))
        assert store.get_binding("camera_01") is not None

        store.remove_binding("camera_01")
        assert store.get_binding("camera_01") is None

    def test_json_file_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BindingStore(config_dir=tmpdir)
            store.set_binding(CameraBinding(
                camera_slot="camera_01",
                serial_number="DA5172955",
                mac_address="34:BD:20:56:4E:68",
                ip_address="169.254.54.253",
                model="MV-CL022-91GC",
                role="top",
            ))
            store.save_all()

            file_path = Path(tmpdir) / "camera_binding.json"
            assert file_path.exists()

            raw = json.loads(file_path.read_text(encoding="utf-8"))
            assert raw["version"] == "1.0"
            assert len(raw["cameras"]) == 1
            assert raw["cameras"][0]["serial_number"] == "DA5172955"

    def test_save_overwrites_same_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BindingStore(config_dir=tmpdir)
            store.set_binding(CameraBinding(camera_slot="camera_01", serial_number="OLD"))
            store.save_all()

            # Overwrite same slot
            store.set_binding(CameraBinding(camera_slot="camera_01", serial_number="NEW"))
            store.save_all()

            store2 = BindingStore(config_dir=tmpdir)
            loaded = store2.load_all()
            assert len(loaded) == 1
            assert loaded[0].serial_number == "NEW"
