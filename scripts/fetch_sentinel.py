"""Search Earth Search (AWS) for Sentinel-2 scenes and download the AOI bands. No API key needed.

List the clearest scenes over the AOI (no download):
    python scripts/fetch_sentinel.py --bbox -122.32 49.00 -122.10 49.12 --dates 2021-11-14/2021-12-10 --list

Download the clearest one (or a specific --scene-id):
    python scripts/fetch_sentinel.py --bbox -122.32 49.00 -122.10 49.12 --dates 2021-11-14/2021-12-10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.satellite.stac import download_scene, rank_scenes, search_scenes  # noqa: E402


def print_ranking(ranking, top: int) -> None:
    print(f"  {'date':10s}  {'AOI clear':>9s}  {'AOI water':>9s}  {'tile cloud':>10s}  scene")
    for s in ranking[:top]:
        print(f"  {s.date:10s}  {s.aoi_clear_pct:8.1f}%  {s.aoi_water_pct:8.1f}%  {s.tile_cloud_pct:9.1f}%  {s.id}")


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch Sentinel-2 L2A bands for an AOI from Earth Search STAC.")
    p.add_argument("--bbox", type=float, nargs=4, required=True, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    p.add_argument("--dates", required=True, help="Date range, e.g. 2021-11-14/2021-12-10")
    p.add_argument("--list", action="store_true", help="Only print the ranking, download nothing")
    p.add_argument("--scene-id", help="Download this scene instead of the clearest")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--out", default="data/raw/stac")
    a = p.parse_args()
    bbox = tuple(a.bbox)

    print(f"Searching Earth Search for {bbox} in {a.dates} ...")
    items = search_scenes(bbox, a.dates)
    print(f"  {len(items)} scenes found; scoring cloud cover over the AOI (SCL band)")
    if not items:
        return 1
    ranking = rank_scenes(items, bbox)
    print_ranking(ranking, a.top)
    if a.list:
        return 0

    chosen = a.scene_id or ranking[0].id
    item = next((it for it in items if it.id == chosen), None)
    if item is None:
        sys.exit(f"error: scene {chosen} not in search results")
    scene = download_scene(item, bbox, a.out)
    print(f"Downloaded {scene.id} ({scene.date}, {scene.aoi_clear_pct}% clear) -> {scene.dir}")
    print(f"  green {scene.green.name}, swir {scene.swir.name}, scl {scene.scl.name}, "
          f"true colour {scene.true_colour.name if scene.true_colour else '-'}; BOA offset {scene.boa_offset:g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
