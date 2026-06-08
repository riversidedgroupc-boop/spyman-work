"""Tests for historical sample library and cross-project reuse."""
from __future__ import annotations

import os
import tempfile

import pytest

from core.sample_library import (
    add_to_library,
    get_entry,
    list_entries,
    search_samples,
    SampleSearchFilter,
    import_samples,
    reference_samples,
    SOURCE_KIND_CURRENT,
    SOURCE_KIND_IMPORT,
    SOURCE_KIND_REFERENCE,
)

@pytest.fixture
def customer():
    from core.customer import create_customer
    return create_customer("Sample Library Corp", "SLC")

@pytest.fixture
def project1(customer):
    from core.project import create_project
    return create_project(customer.customer_id, "Source Project")

@pytest.fixture
def project2(customer):
    from core.project import create_project
    return create_project(customer.customer_id, "Target Project")

@pytest.fixture
def spec1(project1):
    from core.product_spec import create_product_spec
    return create_product_spec(
        project_id=project1.project_id, product_name="copper_strip_a",
        material="copper", geometry_type="strip", surface_type="smooth",
    )

@pytest.fixture
def spec2(project2):
    from core.product_spec import create_product_spec
    return create_product_spec(
        project_id=project2.project_id, product_name="copper_strip_b",
        material="copper", geometry_type="strip", surface_type="rough",
    )

class TestLibraryCRUD:
    def test_add_and_get_entry(self, project1):
        entry = add_to_library(
            current_project_id=project1.project_id,
            current_image_path="/data/img1.jpg",
            source_kind=SOURCE_KIND_CURRENT,
            original_label="OK",
        )
        fetched = get_entry(entry.entry_id)
        assert fetched is not None
        assert fetched.current_project_id == project1.project_id
        assert fetched.source_kind == SOURCE_KIND_CURRENT
        assert fetched.original_label == "OK"

    def test_list_entries_by_project(self, project1, project2):
        add_to_library(current_project_id=project1.project_id, current_image_path="/a.jpg")
        add_to_library(current_project_id=project2.project_id, current_image_path="/b.jpg")
        assert len(list_entries(project1.project_id)) == 1
        assert len(list_entries(project2.project_id)) == 1
        assert len(list_entries()) == 2

    def test_invalid_source_kind(self, project1):
        with pytest.raises(ValueError, match="Invalid source_kind"):
            add_to_library(current_project_id=project1.project_id,
                           current_image_path="/x.jpg", source_kind="bad_kind")

class TestSearch:
    def test_search_by_label(self, project1, spec1):
        add_to_library(current_project_id=project1.project_id,
                       current_image_path="/ng1.jpg",
                       source_project_id=project1.project_id,
                       original_label="NG", current_label="NG")
        add_to_library(current_project_id=project1.project_id,
                       current_image_path="/ok1.jpg",
                       source_project_id=project1.project_id,
                       original_label="OK", current_label="OK")
        results = search_samples(SampleSearchFilter(label="NG"))
        assert len(results) == 1
        assert results[0].current_label == "NG"

    def test_search_by_material(self, project1, spec1, project2, spec2):
        add_to_library(current_project_id=project1.project_id,
                       current_image_path="/c1.jpg",
                       source_project_id=project1.project_id,
                       original_label="OK")
        add_to_library(current_project_id=project2.project_id,
                       current_image_path="/c2.jpg",
                       source_project_id=project2.project_id,
                       original_label="OK")
        # spec1 material=copper, spec2 material=copper (same), so both match
        results = search_samples(SampleSearchFilter(material="copper"))
        assert len(results) == 2

    def test_search_by_surface_type(self, project1, spec1, project2, spec2):
        add_to_library(current_project_id=project1.project_id,
                       current_image_path="/s1.jpg",
                       source_project_id=project1.project_id)
        add_to_library(current_project_id=project2.project_id,
                       current_image_path="/s2.jpg",
                       source_project_id=project2.project_id)
        # spec1 surface=smooth, spec2 surface=rough
        results = search_samples(SampleSearchFilter(surface_type="smooth"))
        assert len(results) == 1

    def test_search_exclude_project(self, project1, project2, spec1, spec2):
        add_to_library(current_project_id=project1.project_id,
                       current_image_path="/e1.jpg",
                       source_project_id=project1.project_id)
        add_to_library(current_project_id=project2.project_id,
                       current_image_path="/e2.jpg",
                       source_project_id=project2.project_id)
        results = search_samples(SampleSearchFilter(exclude_project_id=project1.project_id))
        assert len(results) == 1
        assert results[0].current_project_id == project2.project_id

class TestImport:
    def test_import_copies_provenance(self, project1, project2):
        with tempfile.TemporaryDirectory() as td:
            src_path = os.path.join(td, "src.jpg")
            with open(src_path, "w") as f:
                f.write("fake image")
            src_entry = add_to_library(
                current_project_id=project1.project_id,
                current_image_path=src_path,
                source_kind=SOURCE_KIND_CURRENT,
                source_project_id=project1.project_id,
                original_label="NG",
                current_label="NG",
                human_review_status="confirmed_defect",
            )
            dest_dir = os.path.join(td, "imported")
            result = import_samples(
                [src_entry.entry_id], project2.project_id, dest_dir,
                import_reason="cold start",
            )
            assert result.imported_count == 1
            assert result.skipped_count == 0
            imported = result.entries[0]
            assert imported.source_kind == SOURCE_KIND_IMPORT
            assert imported.current_project_id == project2.project_id
            assert imported.source_project_id == project1.project_id
            assert imported.original_label == "NG"
            assert os.path.isfile(imported.current_image_path)

    def test_import_missing_source_skips(self, project1, project2):
        entry = add_to_library(
            current_project_id=project1.project_id,
            current_image_path="/nonexistent/file.jpg",
            source_kind=SOURCE_KIND_CURRENT,
        )
        with tempfile.TemporaryDirectory() as td:
            result = import_samples([entry.entry_id], project2.project_id,
                                   os.path.join(td, "dest"))
            assert result.imported_count == 0
            assert result.skipped_count == 1
            assert len(result.errors) == 1

class TestReference:
    def test_reference_no_copy(self, project1, project2):
        src_entry = add_to_library(
            current_project_id=project1.project_id,
            current_image_path="/data/ref.jpg",
            source_kind=SOURCE_KIND_CURRENT,
            original_label="OK",
        )
        result = reference_samples(
            [src_entry.entry_id], project2.project_id,
            import_reason="for reference",
        )
        assert result.referenced_count == 1
        assert result.imported_count == 0
        ref = result.entries[0]
        assert ref.source_kind == SOURCE_KIND_REFERENCE
        assert ref.current_project_id == project2.project_id
        assert ref.source_project_id == project1.project_id

class TestSourceKindCounts:
    def test_counts_by_kind(self, project1, spec1):
        from core.sample_library import get_source_kind_counts
        add_to_library(current_project_id=project1.project_id,
                       current_image_path="/a.jpg", source_kind=SOURCE_KIND_CURRENT)
        add_to_library(current_project_id=project1.project_id,
                       current_image_path="/b.jpg", source_kind=SOURCE_KIND_IMPORT,
                       source_project_id="PROJ_other")
        counts = get_source_kind_counts(project1.project_id)
        assert counts.get(SOURCE_KIND_CURRENT, 0) == 1
        assert counts.get(SOURCE_KIND_IMPORT, 0) == 1
        assert counts.get(SOURCE_KIND_REFERENCE, 0) == 0
