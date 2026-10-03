"""Write GeoTIFFs that keep the CRS and affine transform of the reference grid.

This is the single most important thing for Person 2: without crs + transform,
flood_mask.tif is just a picture and can't be placed on a map.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from backend.satellite.bands import ReferenceGrid
from backend.satellite.mask import NODATA


def _write(path: str | Path, array: np.ndarray, grid: ReferenceGrid, dtype: str, nodata) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if array.shape != grid.shape:
        raise ValueError(f"array shape {array.shape} != grid shape {grid.shape}")
    with rasterio.open(
        path, "w", driver="GTiff", width=grid.width, height=grid.height, count=1,
        dtype=dtype, crs=grid.crs, transform=grid.transform, nodata=nodata, compress="deflate",
    ) as dst:
        dst.write(array.astype(dtype), 1)
    return path


def write_flood_mask(path: str | Path, mask: np.ndarray, grid: ReferenceGrid) -> Path:
    """uint8 GeoTIFF: 1 flooded, 0 dry, 255 nodata. This is the file Person 2 consumes."""
    return _write(path, mask, grid, "uint8", NODATA)


def write_mndwi(path: str | Path, mndwi: np.ndarray, grid: ReferenceGrid) -> Path:
    """float32 GeoTIFF of raw MNDWI (NaN = nodata). Keep it: re-thresholding it is how the
    backend's flood-severity slider can work without redoing the satellite processing."""
    return _write(path, mndwi, grid, "float32", np.nan)
