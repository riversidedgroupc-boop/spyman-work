"""Tests for TileGenerator."""
import numpy as np

from src.device.camera.line_scan.tile_generator import TileGenerator
from src.device.camera.line_scan.types import LineScanImageBlock


def make_block(width: int = 640, height: int = 640) -> LineScanImageBlock:
    img = np.random.randint(0, 255, (height, width), dtype=np.uint8)
    return LineScanImageBlock(
        block_id="BLK_000", camera_id="C1",
        start_frame_id=0, end_frame_id=height,
        width=width, height=height,
        image=img, start_meter=0.0, end_meter=1.0,
    )


def test_640_by_640_yields_4_tiles():
    gen = TileGenerator(tile_size=320)
    block = make_block(640, 640)
    tiles = gen.slice_block(block)
    assert len(tiles) == 4


def test_exact_fit_produces_one_tile():
    gen = TileGenerator(tile_size=320)
    block = make_block(320, 320)
    tiles = gen.slice_block(block)
    assert len(tiles) == 1
    assert tiles[0].x0 == 0
    assert tiles[0].y0 == 0


def test_small_image_still_produces_one_tile():
    gen = TileGenerator(tile_size=320)
    block = make_block(200, 200)
    tiles = gen.slice_block(block)
    assert len(tiles) == 1
    assert tiles[0].image.shape == (320, 320, 3)


def test_tile_image_is_3_channel():
    gen = TileGenerator(tile_size=320)
    block = make_block(320, 320)
    tiles = gen.slice_block(block)
    assert tiles[0].image.shape == (320, 320, 3)


def test_coordinate_conversion():
    gen = TileGenerator(tile_size=320)
    block = make_block(640, 640)
    tiles = gen.slice_block(block)
    tile = [t for t in tiles if t.x0 == 320 and t.y0 == 320][0]
    bx, by = gen.tile_to_original_coords(tile, 50, 100)
    assert bx == 370
    assert by == 420


def test_meter_position_monotonic():
    gen = TileGenerator(tile_size=320)
    block = make_block(640, 640)
    block.start_meter = 10.0
    block.end_meter = 12.0
    tiles = gen.slice_block(block)
    for t in tiles:
        assert t.meter_start <= t.meter_end
        assert 10.0 <= t.meter_start <= 12.0
