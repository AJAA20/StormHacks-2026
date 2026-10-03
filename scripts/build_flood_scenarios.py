"""Turn the saved MNDWI rasters into one flood-polygon GeoJSON per UI scenario (low / moderate / severe).

Each scenario is the SAME satellite observation thresholded at a different MNDWI
value: a lower threshold also counts shallower / muddier water, so more area floods.
Runs offline from the outputs of scripts/analyze_flood.py.

    python scripts/build_flood_scenarios.py
    python scripts/build_flood_scenarios.py --scenario low=0.3 --scenario severe=-0.05

Writes backend/data/flood/<scenario>.geojson (small, committed, read by the routing API).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from pyproj import CRS  # noqa: E402

from backend.gis import export_geojson, vectorize_flood_mask  # noqa: E402
from backend.satellite.bands import ReferenceGrid  # noqa: E402
from backend.satellite.mask import build_flood_mask  # noqa: E402
from backend.satellite.raster_io import write_flood_mask  # noqa: E402

DEFAULT_SCENARIOS = {"low": 0.3, "moderate": 0.15, "severe": 0.0}


def read_mndwi(path: Path) -> tuple[np.ndarray, ReferenceGrid]:
    with rasterio.open(path) as src:
        grid = ReferenceGrid(CRS.from_user_input(src.crs), src.transform, src.width, src.height)
        return src.read(1).astype("float32"), grid


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mndwi", default="data/processed/mndwi.tif")
    p.add_argument("--preflood", default="data/processed/mndwi_preflood.tif")
    p.add_argument("--out-dir", default="backend/data/flood")
    p.add_argument("--work-dir", default="data/processed/scenarios")
    p.add_argument("--scenario", action="append", metavar="NAME=THRESHOLD",
                   help=f"Override scenarios (repeatable). Default: {DEFAULT_SCENARIOS}")
    p.add_argument("--min-area", type=float, default=5000.0)
    a = p.parse_args()

    scenarios = dict(DEFAULT_SCENARIOS)
    if a.scenario:
        scenarios = {k: float(v) for k, v in (s.split("=") for s in a.scenario)}

    mndwi, grid = read_mndwi(Path(a.mndwi))
    pre = read_mndwi(Path(a.preflood))[0] if Path(a.preflood).exists() else None
    if pre is None:
        print(f"WARNING: {a.preflood} not found - permanent rivers/lakes will count as flooded")

    for name, threshold in scenarios.items():
        mask = build_flood_mask(mndwi, threshold, invalid=~np.isfinite(mndwi), preflood_mndwi=pre)
        mask_path = write_flood_mask(Path(a.work_dir) / f"flood_mask_{name}.tif", mask, grid)
        gdf = vectorize_flood_mask(mask_path, min_area=a.min_area, merge=True, merge_gap=10, simplify_tolerance=5)
        out = export_geojson(gdf, Path(a.out_dir) / f"{name}.geojson")
        print(f"{name:9s} MNDWI > {threshold:+.2f}: {len(gdf):4d} polygons, "
              f"{gdf['area_m2'].sum() / 1e6:6.2f} km^2 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
