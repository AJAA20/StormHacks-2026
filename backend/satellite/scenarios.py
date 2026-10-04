"""Flood scenarios: the same satellite observation thresholded at different MNDWI values.

A lower threshold also counts shallower / muddier water, so more area floods. The UI
labels these low / moderate / severe.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS

from backend.satellite.bands import ReferenceGrid
from backend.satellite.mask import build_flood_mask
from backend.satellite.raster_io import write_flood_mask

SCENARIO_THRESHOLDS = {"low": 0.3, "moderate": 0.15, "severe": 0.0}


def read_mndwi(path: str | Path) -> tuple[np.ndarray, ReferenceGrid]:
    with rasterio.open(path) as src:
        grid = ReferenceGrid(CRS.from_user_input(src.crs), src.transform, src.width, src.height)
        return src.read(1).astype("float32"), grid


def build_flood_scenarios(
    mndwi_path: str | Path,
    out_dir: str | Path,
    work_dir: str | Path,
    preflood_path: str | Path | None = None,
    thresholds: dict[str, float] | None = None,
    min_area: float = 5000.0,
) -> dict[str, dict]:
    """Write <out_dir>/<scenario>.geojson for each threshold. Returns per-scenario stats."""
    from backend.gis import export_geojson, vectorize_flood_mask

    thresholds = thresholds or SCENARIO_THRESHOLDS
    mndwi, grid = read_mndwi(mndwi_path)
    pre = read_mndwi(preflood_path)[0] if preflood_path and Path(preflood_path).exists() else None

    stats = {}
    for name, threshold in thresholds.items():
        mask = build_flood_mask(mndwi, threshold, invalid=~np.isfinite(mndwi), preflood_mndwi=pre)
        mask_path = write_flood_mask(Path(work_dir) / f"flood_mask_{name}.tif", mask, grid)
        gdf = vectorize_flood_mask(mask_path, min_area=min_area, merge=True, merge_gap=10, simplify_tolerance=5)
        path = export_geojson(gdf, Path(out_dir) / f"{name}.geojson")
        stats[name] = {
            "threshold": threshold,
            "polygons": len(gdf),
            "area_km2": round(float(gdf["area_m2"].sum()) / 1e6, 2) if len(gdf) else 0.0,
            "path": str(path),
        }
    return stats
