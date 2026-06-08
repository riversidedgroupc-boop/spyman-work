"""Tests for camera_config model and CRUD."""

import pytest


@pytest.fixture
def ctx():
    """Create prerequisite customer -> project -> spec."""
    from core.customer import create_customer
    from core.project import create_project
    from core.product_spec import create_product_spec
    c = create_customer("TestCorp", "TC")
    p = create_project(c.customer_id, "TestProject")
    s = create_product_spec(p.project_id, "TestSpec", "铜", "管", camera_count=3)
    return {"customer": c, "project": p, "spec": s}


def test_create_camera_config(ctx):
    from core.camera_config import create_camera_config, get_camera_config
    spec = ctx["spec"]
    cfg = create_camera_config(spec.spec_id, camera_index=1, adapter_type="folder_watcher")
    assert cfg.config_id.startswith("CAMCONF_")
    assert cfg.camera_index == 1
    assert cfg.adapter_type == "folder_watcher"
    fetched = get_camera_config(cfg.config_id)
    assert fetched is not None
    assert fetched.spec_id == spec.spec_id


def test_camera_index_out_of_range():
    from core.camera_config import CameraConfig
    with pytest.raises(ValueError, match="camera_index"):
        CameraConfig(config_id="x", spec_id="x", camera_index=0)
    with pytest.raises(ValueError, match="camera_index"):
        CameraConfig(config_id="x", spec_id="x", camera_index=7)


def test_list_camera_configs(ctx):
    from core.camera_config import create_camera_config, list_camera_configs
    spec = ctx["spec"]
    create_camera_config(spec.spec_id, camera_index=1)
    create_camera_config(spec.spec_id, camera_index=2)
    cfgs = list_camera_configs(spec.spec_id)
    assert len(cfgs) == 2
    assert cfgs[0].camera_index == 1
    assert cfgs[1].camera_index == 2


def test_update_camera_config(ctx):
    from core.camera_config import create_camera_config, update_camera_config, get_camera_config
    spec = ctx["spec"]
    cfg = create_camera_config(spec.spec_id, camera_index=1, exposure_us=100.0)
    update_camera_config(cfg.config_id, exposure_us=200.0, gain_db=3.5)
    updated = get_camera_config(cfg.config_id)
    assert updated.exposure_us == 200.0
    assert updated.gain_db == 3.5


def test_delete_camera_config(ctx):
    from core.camera_config import create_camera_config, delete_camera_config, get_camera_config
    spec = ctx["spec"]
    cfg = create_camera_config(spec.spec_id, camera_index=1)
    delete_camera_config(cfg.config_id)
    assert get_camera_config(cfg.config_id) is None


def test_roundtrip_dict(ctx):
    from core.camera_config import CameraConfig
    spec = ctx["spec"]
    cfg = CameraConfig(
        config_id="CAMCONF_test", spec_id=spec.spec_id, camera_index=2,
        adapter_type="hikvision_mvs", trigger_mode="external",
        exposure_us=50.0, gain_db=6.0, model_binding="model_v1",
    )
    d = cfg.to_dict()
    cfg2 = CameraConfig.from_dict(d)
    assert cfg2.config_id == cfg.config_id
    assert cfg2.camera_index == 2
    assert cfg2.adapter_type == "hikvision_mvs"
    assert cfg2.trigger_mode == "external"
    assert cfg2.exposure_us == 50.0
    assert cfg2.gain_db == 6.0
    assert cfg2.model_binding == "model_v1"


def test_camera_config_v6_structured_fields(ctx):
    from core.camera_config import create_camera_config, get_camera_config

    spec = ctx["spec"]
    cfg = create_camera_config(
        spec.spec_id,
        camera_index=2,
        camera_id="CAM_02",
        camera_name="side camera",
        camera_type="line_scan",
        brand="Hikvision",
        serial_number="SN002",
        ip_address="192.168.1.12",
        resolution_width=4096,
        resolution_height=1,
        pixel_size_um=5.0,
        position_desc="right",
        save_ng_image=False,
    )

    fetched = get_camera_config(cfg.config_id)
    assert fetched.camera_id == "CAM_02"
    assert fetched.camera_name == "side camera"
    assert fetched.camera_type == "line_scan"
    assert fetched.brand == "Hikvision"
    assert fetched.serial_number == "SN002"
    assert fetched.ip_address == "192.168.1.12"
    assert fetched.resolution_width == 4096
    assert fetched.resolution_height == 1
    assert fetched.pixel_size_um == 5.0
    assert fetched.position_desc == "right"
    assert fetched.save_ng_image is False


def test_camera_config_v7_line_scan_fields_persist(ctx):
    from core.camera_config import create_camera_config, get_camera_config

    spec = ctx["spec"]
    cfg = create_camera_config(
        spec.spec_id,
        camera_index=1,
        adapter_type="hikrobot_line_scan",
        line_rate=20000,
        image_block_height=1024,
        pixel_format="Mono8",
    )

    fetched = get_camera_config(cfg.config_id)
    assert fetched.adapter_type == "hikrobot_line_scan"
    assert fetched.line_rate == 20000
    assert fetched.image_block_height == 1024
    assert fetched.pixel_format == "Mono8"
