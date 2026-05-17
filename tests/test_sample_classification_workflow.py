"""Tests for the sample classification queue workflow."""
from desktop_app.pages.sample_classification_page import (
    BATCH_SIZE,
    batch_start_for_index,
    next_index_after_label,
)


def test_batch_start_uses_twelve_image_pages():
    assert BATCH_SIZE == 12
    assert batch_start_for_index(0) == 0
    assert batch_start_for_index(11) == 0
    assert batch_start_for_index(12) == 12
    assert batch_start_for_index(23) == 12


def test_labeling_advances_to_next_image_and_stops_at_end():
    assert next_index_after_label(0, 5) == 1
    assert next_index_after_label(10, 12) == 11
    assert next_index_after_label(11, 12) == 11
