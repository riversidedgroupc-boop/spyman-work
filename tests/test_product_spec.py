"""Tests for product spec model and CRUD."""
import os

import pytest

@pytest.fixture
def project():
    from core.customer import create_customer
    from core.project import create_project
    c = create_customer("Spec Test Corp", "STC")
    return create_project(c.customer_id, "Spec Test Project")

def test_create_product_spec(project):
    from core.product_spec import create_product_spec, get_product_spec
    s = create_product_spec(
        project.project_id,
        "Tube-25mm",
        material="铜",
        geometry_type="管",
        target_speed_mpm=80.0,
        camera_count=3,
    )
    assert s.spec_id.startswith("SPEC_")
    assert s.material == "铜"
    assert s.camera_count == 3
    fetched = get_product_spec(s.spec_id)
    assert fetched is not None

def test_validation_camera_count(project):
    from core.product_spec import create_product_spec
    with pytest.raises(ValueError, match="camera_count"):
        create_product_spec(
            project.project_id, "Bad", material="铜",
            geometry_type="管", camera_count=0,
        )
    with pytest.raises(ValueError, match="camera_count"):
        create_product_spec(
            project.project_id, "Bad", material="铜",
            geometry_type="管", camera_count=7,
        )

def test_validation_speed_range(project):
    from core.product_spec import create_product_spec
    with pytest.raises(ValueError):
        create_product_spec(
            project.project_id, "Bad Speed", material="铜",
            geometry_type="管",
            line_speed_min_mpm=150, line_speed_max_mpm=100, target_speed_mpm=120,
        )

def test_list_by_project(project):
    from core.product_spec import create_product_spec, list_product_specs
    create_product_spec(
        project.project_id, "Spec A", material="铜", geometry_type="管"
    )
    create_product_spec(
        project.project_id, "Spec B", material="铝", geometry_type="板"
    )
    specs = list_product_specs(project.project_id)
    assert len(specs) == 2
