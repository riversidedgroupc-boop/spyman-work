"""Tests for LineScanBlockBuilder."""
import numpy as np

from src.device.camera.line_scan.block_builder import LineScanBlockBuilder
from src.device.camera.line_scan.types import FramePacket


def make_packet(frame_id: int, width: int = 100) -> FramePacket:
    data = np.full((1, width), fill_value=frame_id % 256, dtype=np.uint8)
    return FramePacket(
        camera_id="TEST",
        frame_id=frame_id,
        encoder_count=frame_id,
        width=width,
        height=1,
        line_data=data,
    )


def test_block_emitted_at_correct_height():
    builder = LineScanBlockBuilder(camera_id="C1", block_height=10)
    blocks: list = []
    builder.set_on_block(lambda b: blocks.append(b))
    for i in range(25):
        builder.push_line(make_packet(i, width=80))
    assert len(blocks) == 2
    assert blocks[0].height == 10
    assert blocks[0].start_frame_id == 0
    assert blocks[0].end_frame_id == 9
    assert blocks[1].start_frame_id == 10


def test_buffer_shape_correct():
    builder = LineScanBlockBuilder(camera_id="C1", block_height=50)
    blocks: list = []
    builder.set_on_block(lambda b: blocks.append(b))
    for i in range(50):
        builder.push_line(make_packet(i, width=200))
    assert len(blocks) == 1
    assert blocks[0].image.shape == (50, 200)
    assert blocks[0].image.dtype == np.uint8


def test_flush_returns_partial_block():
    builder = LineScanBlockBuilder(camera_id="C1", block_height=20)
    for i in range(5):
        builder.push_line(make_packet(i, width=50))
    partial = builder.flush()
    assert partial is not None
    assert partial.height == 5
    assert partial.image.shape == (5, 50)


def test_flush_returns_none_when_empty():
    builder = LineScanBlockBuilder(camera_id="C1", block_height=20)
    assert builder.flush() is None


def test_reset_clears_buffer():
    builder = LineScanBlockBuilder(camera_id="C1", block_height=20)
    for i in range(8):
        builder.push_line(make_packet(i))
    builder.reset()
    assert builder.current_row == 0
    assert builder.flush() is None
