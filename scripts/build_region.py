"""Build (or rebuild) an analysed region from the command line, e.g. a committed preset.

    python scripts/build_region.py --id abbotsford-2021 --name "Abbotsford / Sumas Prairie, BC (Nov 2021)" \
        --bbox -122.32 49.00 -122.10 49.12 --flood-dates 2021-11-14/2021-12-10 \
        --preflood-dates 2021-08-01/2021-10-31 --preset \
        --start -122.219 49.024 --end -122.2852 49.0824
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.regions.builder import RegionBuildError, build_region  # noqa: E402
from backend.regions.store import region_id_for  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Analyse an area and save it as a region.")
    p.add_argument("--name", required=True)
    p.add_argument("--bbox", type=float, nargs=4, required=True, metavar=("W", "S", "E", "N"))
    p.add_argument("--flood-dates", required=True)
    p.add_argument("--preflood-dates")
    p.add_argument("--id", help="Region id (default: derived from name + area + dates)")
    p.add_argument("--preset", action="store_true", help="Mark as a committed demo preset")
    p.add_argument("--start", type=float, nargs=2, metavar=("LON", "LAT"))
    p.add_argument("--end", type=float, nargs=2, metavar=("LON", "LAT"))
    a = p.parse_args()

    region_id = a.id or region_id_for(a.name, a.bbox, a.flood_dates)
    t0 = time.time()
    try:
        meta = build_region(
            region_id, a.name, a.bbox, a.flood_dates, a.preflood_dates,
            progress=lambda stage, frac: print(f"  [{frac:4.0%}] {stage}", flush=True),
            preset=a.preset, default_start=a.start, default_end=a.end,
        )
    except RegionBuildError as exc:
        print(f"Could not analyse area: {exc}")
        return 1
    print(f"Region {region_id}: flood scene {meta['flood_scene']['date']}, "
          f"{meta['road_edges']} road segments, {time.time() - t0:.1f} s")
    for name, st in meta["scenarios"].items():
        print(f"  {name:9s} {st['polygons']:4d} polygons, {st['area_km2']:6.2f} km^2")
    for w in meta["warnings"]:
        print(f"  warning: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
