"""Full automatic run: Earth Search -> clearest flood + pre-flood scenes -> MNDWI -> flood polygons GeoJSON.

Abbotsford / Sumas Prairie, Nov 2021:
    python scripts/analyze_flood.py --bbox -122.32 49.00 -122.10 49.12 \\
        --flood-dates 2021-11-14/2021-12-10 --preflood-dates 2021-08-01/2021-10-31 \\
        --preview data/processed/mndwi_preview.png
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.satellite.analyze import analyze_flood_event  # noqa: E402
from scripts.calculate_mndwi import save_preview  # noqa: E402
from scripts.fetch_sentinel import print_ranking  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Automatically fetch Sentinel-2 data and map a flood.")
    p.add_argument("--bbox", type=float, nargs=4, required=True, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    p.add_argument("--flood-dates", required=True, help="e.g. 2021-11-14/2021-12-10")
    p.add_argument("--preflood-dates", help="e.g. 2021-08-01/2021-10-31 (removes permanent water)")
    p.add_argument("--threshold", type=float, default=0.0)
    p.add_argument("--min-clear", type=float, default=50.0, help="Min %% of AOI that must be cloud-free")
    p.add_argument("--min-area", type=float, default=5000.0, help="Drop flood polygons smaller than this (m^2)")
    p.add_argument("--out-dir", default="data/processed")
    p.add_argument("--preview", help="Optional PNG preview path")
    a = p.parse_args()

    t0 = time.time()
    r = analyze_flood_event(
        tuple(a.bbox), a.flood_dates, a.preflood_dates, threshold=a.threshold,
        out_dir=a.out_dir, min_clear_pct=a.min_clear, min_area=a.min_area,
    )
    print("Flood-date candidates (clearest first):")
    print_ranking(r.flood_ranking, 5)
    if r.preflood_ranking:
        print("Pre-flood candidates:")
        print_ranking(r.preflood_ranking, 5)

    s = r.stats
    print(f"Chosen flood scene    : {r.flood_scene.id} ({r.flood_scene.date}, {r.flood_scene.aoi_clear_pct}% clear)")
    if r.preflood_scene:
        print(f"Chosen pre-flood scene: {r.preflood_scene.id} ({r.preflood_scene.date}, {r.preflood_scene.aoi_clear_pct}% clear)")
    print(f"MNDWI > {a.threshold:g}: {s['flooded_pixels']} new-water px = {s['flooded_area_km2']:.2f} km^2 "
          f"({s['flooded_pct_of_valid']:.1f}% of valid AOI); masked {s['invalid_pixels']} px")
    print(f"Outputs: {r.mask_path}, {r.mndwi_path}, {r.geojson_path} ({r.polygon_count} polygons)")
    if r.flood_scene.true_colour:
        print(f"True-colour overlay: {r.flood_scene.true_colour}")
    if a.preview:
        save_preview(r.result, Path(a.preview), a.threshold)
        print(f"Preview: {a.preview}")
    print(f"Done in {time.time() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
