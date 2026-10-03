"""Find, crop, resample and align Sentinel-2 bands onto one pixel grid.

Sentinel-2 bands have different resolutions: B03 (Green) is 10 m, B11 (SWIR)
and SCL (scene classification) are 20 m. MNDWI compares the two pixel by pixel,
so pixel [r, c] must cover the *same ground* in every array. We pick the
cropped 10 m Green band as the reference grid and reproject every other band
onto exactly that grid (same CRS, transform, width, height).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds


@dataclass
class ReferenceGrid:
    """The pixel grid every band is aligned to (taken from the cropped Green band)."""

    crs: CRS
    transform: Affine
    width: int
    height: int

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width


def find_safe_bands(safe_dir: str | Path) -> dict[str, Path]:
    """Locate B03 (10 m), B11 (20 m) and SCL (20 m) inside an unzipped L2A .SAFE folder.

    Layout: <name>.SAFE/GRANULE/<granule>/IMG_DATA/R10m/*_B03_10m.jp2 etc.
    """
    safe_dir = Path(safe_dir)
    patterns = {"green": "*_B03_10m.jp2", "swir": "*_B11_20m.jp2", "scl": "*_SCL_20m.jp2"}
    found: dict[str, Path] = {}
    for key, pattern in patterns.items():
        matches = sorted(safe_dir.rglob(pattern))
        if matches:
            found[key] = matches[0]
    missing = {"green", "swir"} - found.keys()
    if missing:
        raise FileNotFoundError(f"Could not find {missing} bands under {safe_dir}")
    return found


def boa_offset_from_name(path: str | Path) -> float:
    """Guess the L2A reflectance offset from the processing baseline in the product name.

    Since processing baseline 04.00 (products from 25 Jan 2022 on), L2A pixel
    values include an offset: reflectance = (DN - 1000) / 10000. Older products
    have no offset. Names contain the baseline as e.g. "_N0400_" or "_N0301_".
    Returns 0.0 if the name has no baseline (e.g. a GeoTIFF from Copernicus Browser,
    which is already offset-corrected) - override with --boa-offset if needed.
    """
    m = re.search(r"_N(\d{4})_", str(path))
    if m and int(m.group(1)) >= 400:
        return -1000.0
    return 0.0


def reference_grid(green_path: str | Path, bbox_lonlat: tuple[float, float, float, float] | None) -> ReferenceGrid:
    """Build the reference grid: the Green band, cropped to `bbox_lonlat` if given.

    bbox_lonlat is (min_lon, min_lat, max_lon, max_lat) in EPSG:4326. It is
    converted into the band's own CRS (UTM metres for Sentinel-2) before
    cropping, because the raster's pixel grid is defined in that CRS.
    """
    with rasterio.open(green_path) as src:
        if src.crs is None:
            raise ValueError(f"{green_path} has no CRS; cannot georeference the output.")
        if bbox_lonlat is None:
            return ReferenceGrid(CRS.from_user_input(src.crs), src.transform, src.width, src.height)

        left, bottom, right, top = transform_bounds("EPSG:4326", src.crs, *bbox_lonlat)
        window = from_bounds(left, bottom, right, top, transform=src.transform)
        # Snap to whole pixels and clip to the image so the grid stays aligned with B03.
        window = window.round_offsets().round_lengths()
        window = window.intersection(Window(0, 0, src.width, src.height))
        if window.width < 1 or window.height < 1:
            raise ValueError(f"bbox {bbox_lonlat} does not overlap {green_path}")
        return ReferenceGrid(
            crs=CRS.from_user_input(src.crs),
            transform=src.window_transform(window),
            width=int(window.width),
            height=int(window.height),
        )


def read_onto_grid(
    path: str | Path,
    grid: ReferenceGrid,
    resampling: Resampling,
    dtype: str = "float32",
    src_nodata: float | None = 0,
) -> np.ndarray:
    """Read band 1 of `path` and warp it onto `grid` (crop + resample + reproject in one step).

    Pixels with no source data come back as NaN (float) so they can be masked later.
    Works even if the file is in a different CRS or tile (e.g. a pre-flood scene).
    """
    dst = np.full(grid.shape, np.nan, dtype=dtype)
    with rasterio.open(path) as src:
        if src.crs is None:
            raise ValueError(f"{path} has no CRS.")
        nodata = src.nodata if src.nodata is not None else src_nodata
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_nodata=nodata,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            dst_nodata=np.nan,
            resampling=resampling,
        )
    return dst


def load_bands_on_grid(
    green_path: str | Path,
    swir_path: str | Path,
    grid: ReferenceGrid,
    scl_path: str | Path | None = None,
) -> dict[str, np.ndarray]:
    """Return {"green", "swir", "scl"?} as float32 DN arrays aligned to `grid`.

    Resampling choices:
      * Green -> nearest (it already IS the grid, nothing is interpolated).
      * SWIR 20 m -> 10 m: bilinear, a smooth estimate for a continuous quantity.
      * SCL: nearest, because it holds class codes (averaging "cloud" and "water"
        codes would produce a meaningless code).
    """
    bands = {
        "green": read_onto_grid(green_path, grid, Resampling.nearest),
        "swir": read_onto_grid(swir_path, grid, Resampling.bilinear),
    }
    if scl_path is not None:
        bands["scl"] = read_onto_grid(scl_path, grid, Resampling.nearest, src_nodata=None)
    return bands
