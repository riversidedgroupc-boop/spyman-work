"""Image tile generator — slices LineScanImageBlock into fixed-size model-input tiles."""
from __future__ import annotations

import numpy as np

from src.device.camera.line_scan.types import ImageTile, LineScanImageBlock


class TileGenerator:
    """Slices a LineScanImageBlock into fixed-size tiles with optional overlap."""

    def __init__(self, tile_size: int = 320, stride: int | None = None) -> None:
        if tile_size < 1:
            raise ValueError(f"tile_size must be >= 1, got {tile_size}")
        self._tile_size = tile_size
        self._stride = stride if stride is not None else tile_size
        if self._stride < 1:
            raise ValueError(f"stride must be >= 1, got {self._stride}")

    @property
    def tile_size(self) -> int:
        return self._tile_size

    @property
    def stride(self) -> int:
        return self._stride

    def slice_block(self, block: LineScanImageBlock) -> list[ImageTile]:
        """Slice a single block into tiles. Returns list of ImageTile."""
        if block.image is None:
            return []
        img = block.image
        if img.ndim == 2:
            h, w = img.shape
            img = np.stack([img] * 3, axis=-1)
        elif img.ndim == 3:
            h, w = img.shape[:2]
        else:
            raise ValueError(f"block image must be 2D or 3D, got shape={img.shape}")
        tiles: list[ImageTile] = []
        y_positions = list(range(0, h - self._tile_size + 1, self._stride))
        x_positions = list(range(0, w - self._tile_size + 1, self._stride))
        if not y_positions or y_positions[-1] + self._tile_size < h:
            y_positions.append(max(0, h - self._tile_size))
        if not x_positions or x_positions[-1] + self._tile_size < w:
            x_positions.append(max(0, w - self._tile_size))
        block_meter_range = block.end_meter - block.start_meter
        for y0 in y_positions:
            for x0 in x_positions:
                tile_img = img[y0 : y0 + self._tile_size, x0 : x0 + self._tile_size].copy()
                if tile_img.shape[0] != self._tile_size or tile_img.shape[1] != self._tile_size:
                    padded = np.zeros((self._tile_size, self._tile_size, img.shape[2]), dtype=img.dtype)
                    padded[: tile_img.shape[0], : tile_img.shape[1], :] = tile_img
                    tile_img = padded
                meter_start = block.start_meter + (y0 / max(h, 1)) * block_meter_range
                meter_end = block.start_meter + ((y0 + self._tile_size) / max(h, 1)) * block_meter_range
                tile_id = f"{block.block_id}_T_{y0:04d}_{x0:04d}"
                tiles.append(ImageTile(
                    tile_id=tile_id,
                    block_id=block.block_id,
                    camera_id=block.camera_id,
                    x0=x0, y0=y0,
                    width=self._tile_size, height=self._tile_size,
                    image=tile_img,
                    meter_start=round(meter_start, 3),
                    meter_end=round(meter_end, 3),
                ))
        return tiles

    def tile_to_original_coords(self, tile: ImageTile, det_x: int, det_y: int) -> tuple[int, int]:
        """Convert detection point in tile coords back to block coords."""
        return (tile.x0 + det_x, tile.y0 + det_y)
