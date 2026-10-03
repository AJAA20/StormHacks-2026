"""End-to-end Person 1 pipeline: band files -> MNDWI -> flood_mask.tif (-> polygons via Person 2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from backend.satellite.bands import ReferenceGrid, load_bands_on_grid, reference_grid
from backend.satellite.mask import FLOODED, NODATA, build_flood_mask, cloud_mask_from_scl
from backend.satellite.mndwi import compute_mndwi, to_reflectance
from backend.satellite.raster_io import write_flood_mask, write_mndwi

BBox = tuple[float, float, float, float]  # (min_lon, min_lat, max_lon, max_lat), EPSG:4326


@dataclass
class SceneMNDWI:
    mndwi: np.ndarray  # float32, NaN where invalid
    invalid: np.ndarray  # bool, True = cloud / shadow / nodata
    grid: ReferenceGrid


def scene_mndwi(
    green_path: str | Path,
    swir_path: str | Path,
    grid: ReferenceGrid,
    scl_path: str | Path | None = None,
    boa_offset: float = 0.0,
    cloud_buffer_px: int = 2,
) -> SceneMNDWI:
    """Align one scene's bands onto `grid`, convert to reflectance and compute MNDWI."""
    bands = load_bands_on_grid(green_path, swir_path, grid, scl_path)
    green = to_reflectance(bands["green"], boa_offset)
    swir = to_reflectance(bands["swir"], boa_offset)
    mndwi = compute_mndwi(green, swir)
    invalid = ~np.isfinite(mndwi)
    if "scl" in bands:
        invalid |= cloud_mask_from_scl(bands["scl"], buffer_px=cloud_buffer_px)
    mndwi[invalid] = np.nan
    return SceneMNDWI(mndwi=mndwi, invalid=invalid, grid=grid)


def generate_flood_mask(
    green_path: str | Path,
    swir_path: str | Path,
    out_mask: str | Path = "data/processed/flood_mask.tif",
    threshold: float = 0.0,
    scl_path: str | Path | None = None,
    bbox: BBox | None = None,
    boa_offset: float = 0.0,
    pre_green_path: str | Path | None = None,
    pre_swir_path: str | Path | None = None,
    pre_scl_path: str | Path | None = None,
    pre_boa_offset: float = 0.0,
    out_mndwi: str | Path | None = "data/processed/mndwi.tif",
    cloud_buffer_px: int = 2,
) -> dict:
    """Run the whole satellite step and write flood_mask.tif (and mndwi.tif).

    Returns a dict with arrays + stats for printing/plotting.
    """
    grid = reference_grid(green_path, bbox)
    flood = scene_mndwi(green_path, swir_path, grid, scl_path, boa_offset, cloud_buffer_px)

    pre = None
    if pre_green_path and pre_swir_path:
        # The pre-flood scene is warped onto the SAME grid, so pixels line up 1:1.
        pre = scene_mndwi(pre_green_path, pre_swir_path, grid, pre_scl_path, pre_boa_offset, cloud_buffer_px)

    mask = build_flood_mask(
        flood.mndwi, threshold, invalid=flood.invalid,
        preflood_mndwi=pre.mndwi if pre else None,
    )
    write_flood_mask(out_mask, mask, grid)
    if out_mndwi:
        write_mndwi(out_mndwi, flood.mndwi, grid)

    px_area_m2 = abs(grid.transform.a * grid.transform.e)
    valid = mask != NODATA
    return {
        "grid": grid,
        "mndwi": flood.mndwi,
        "preflood_mndwi": pre.mndwi if pre else None,
        "mask": mask,
        "out_mask": Path(out_mask),
        "out_mndwi": Path(out_mndwi) if out_mndwi else None,
        "stats": {
            "pixels": mask.size,
            "valid_pixels": int(valid.sum()),
            "invalid_pixels": int((~valid).sum()),
            "flooded_pixels": int((mask == FLOODED).sum()),
            "flooded_pct_of_valid": float(100 * (mask == FLOODED).sum() / max(valid.sum(), 1)),
            "flooded_area_km2": float((mask == FLOODED).sum() * px_area_m2 / 1e6),
            "mndwi_min": float(np.nanmin(flood.mndwi)) if valid.any() else float("nan"),
            "mndwi_max": float(np.nanmax(flood.mndwi)) if valid.any() else float("nan"),
        },
    }


def generate_flood_polygons(green_path, swir_path, threshold: float = 0.0, **kwargs):
    """Convenience wrapper for the backend: bands -> flood_mask.tif -> polygons (Person 2's code).

    Returns a GeoDataFrame in a metric CRS; use backend.gis.export_geojson for EPSG:4326 output.
    Extra keyword args go to generate_flood_mask (scl_path, bbox, pre_*...).
    """
    from backend.gis import vectorize_flood_mask

    result = generate_flood_mask(green_path, swir_path, threshold=threshold, **kwargs)
    return vectorize_flood_mask(result["out_mask"], min_area=1000, simplify_tolerance=5)
