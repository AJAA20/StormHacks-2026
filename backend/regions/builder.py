"""Build a region end to end: Sentinel-2 search -> MNDWI -> flood scenarios -> overlay -> OSM roads.

This is what runs (in a background job) when a user asks to analyse a new area.
"""

from __future__ import annotations

import shutil
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from pyproj import Geod

from backend.regions.store import REGIONS_DIR, save_region

MAX_SIDE_KM = 30.0  # keeps a build under ~1 minute and the road graph small
MIN_SIDE_KM = 1.0
MIN_CLEAR_PCT = 40.0  # flood scene must be at least this cloud-free over the area
STAC_CACHE = Path(__file__).resolve().parents[2] / "data" / "raw" / "stac"
# Where the imagery actually comes from (shown in the UI): ESA's Copernicus Sentinel-2,
# Level-2A Collection 1, served by Element 84's Earth Search catalogue on AWS Open Data.
SATELLITE_SOURCE = "Copernicus Sentinel-2 L2A via Earth Search (AWS Open Data)"

Progress = Callable[[str, float], None]


class RegionBuildError(Exception):
    """A user-facing reason the area could not be analysed (too cloudy, no roads, ...)."""


def bbox_size_km(bbox) -> tuple[float, float]:
    w, s, e, n = bbox
    geod = Geod(ellps="WGS84")
    mid = (s + n) / 2
    width = geod.inv(w, mid, e, mid)[2] / 1000
    height = geod.inv(w, s, w, n)[2] / 1000
    return width, height


def parse_range(text: str, label: str) -> tuple[date, date]:
    try:
        start_s, end_s = text.split("/")
        start, end = date.fromisoformat(start_s), date.fromisoformat(end_s)
    except ValueError:
        raise RegionBuildError(f"{label} must look like 2021-11-14/2021-12-10.") from None
    if end < start:
        raise RegionBuildError(f"{label}: end date is before start date.")
    if start < date(2015, 7, 1):
        raise RegionBuildError(f"{label}: Sentinel-2 data starts in mid-2015.")
    if start > date.today():
        raise RegionBuildError(f"{label} is in the future.")
    return start, end


def default_preflood_range(flood_dates: str) -> str:
    """Dry-weather baseline: the 4 months ending 2 weeks before the flood window."""
    start, _ = parse_range(flood_dates, "Flood dates")
    return f"{start - timedelta(days=120)}/{start - timedelta(days=14)}"


def validate_request(bbox, flood_dates: str, preflood_dates: str | None) -> tuple[tuple, str, str]:
    if len(bbox) != 4:
        raise RegionBuildError("Area must be [west, south, east, north].")
    w, s, e, n = (float(v) for v in bbox)
    if not (-180 <= w < e <= 180 and -85 <= s < n <= 85):
        raise RegionBuildError("Area must be [west, south, east, north] in degrees, west < east, south < north.")
    width, height = bbox_size_km((w, s, e, n))
    if max(width, height) > MAX_SIDE_KM:
        raise RegionBuildError(
            f"Area is {width:.0f} x {height:.0f} km; zoom in to at most {MAX_SIDE_KM:.0f} km per side."
        )
    if min(width, height) < MIN_SIDE_KM:
        raise RegionBuildError(f"Area is too small; make it at least {MIN_SIDE_KM:.0f} km per side.")
    parse_range(flood_dates, "Flood dates")
    preflood_dates = preflood_dates or default_preflood_range(flood_dates)
    parse_range(preflood_dates, "Pre-flood dates")
    return (w, s, e, n), flood_dates, preflood_dates


def _scene_info(scene, item) -> dict:
    """What we know about an image: real acquisition time (UTC), cloud-free share of the area."""
    return {
        "id": scene.id,
        "date": scene.date,
        "datetime": item.datetime.isoformat() if item.datetime else None,
        "aoi_clear_pct": scene.aoi_clear_pct,
        "mission": "Sentinel-2",
    }


def build_region(
    region_id: str,
    name: str,
    bbox,
    flood_dates: str,
    preflood_dates: str | None = None,
    progress: Progress = lambda stage, frac: None,
    preset: bool = False,
    default_start=None,
    default_end=None,
    flood_item=None,
) -> dict:
    """Build the region folder. Writes into a temp folder and renames at the end,
    so a half-finished build is never visible to the API.

    flood_item: an already-chosen Sentinel-2 item (e.g. the latest or the nearest-to-a-date
    observation, see observations.py). If None, the clearest image in flood_dates is used.
    """
    # Heavy imports here so importing the API stays fast.
    import osmnx as ox

    from backend.satellite.overlay import export_overlay
    from backend.satellite.pipeline import generate_flood_mask
    from backend.satellite.scenarios import build_flood_scenarios
    from backend.satellite.stac import download_scene, find_best_scene

    bbox, flood_dates, preflood_dates = validate_request(bbox, flood_dates, preflood_dates)
    final_dir = REGIONS_DIR / region_id
    tmp_dir = REGIONS_DIR / f".tmp-{region_id}"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    (tmp_dir / "raster").mkdir(parents=True)
    warnings: list[str] = []

    try:
        if flood_item is None:
            progress("Searching the Sentinel-2 archive", 0.05)
            try:
                flood_item, _ = find_best_scene(bbox, flood_dates, MIN_CLEAR_PCT)
            except LookupError as exc:
                raise RegionBuildError(f"No usable flood-date image: {exc}") from None

        progress("Downloading flood-date imagery", 0.2)
        flood = download_scene(flood_item, bbox, STAC_CACHE)

        progress("Finding a dry-weather baseline image", 0.3)
        pre = pre_item = None
        try:
            pre_item, _ = find_best_scene(bbox, preflood_dates, MIN_CLEAR_PCT)
            pre = download_scene(pre_item, bbox, STAC_CACHE)
        except LookupError:
            warnings.append("No clear pre-flood image; permanent rivers and lakes may show as flooded.")

        progress("Detecting water with MNDWI", 0.45)
        raster = tmp_dir / "raster"
        result = generate_flood_mask(
            flood.green, flood.swir, out_mask=raster / "flood_mask.tif", out_mndwi=raster / "mndwi.tif",
            out_preflood_mndwi=raster / "mndwi_preflood.tif", scl_path=flood.scl, bbox=bbox,
            boa_offset=flood.boa_offset,
            pre_green_path=pre.green if pre else None, pre_swir_path=pre.swir if pre else None,
            pre_scl_path=pre.scl if pre else None, pre_boa_offset=pre.boa_offset if pre else 0.0,
        )
        if result["stats"]["valid_pixels"] == 0:
            raise RegionBuildError("The whole area is cloud or outside the satellite image.")

        progress("Building flood scenarios", 0.6)
        scenarios = build_flood_scenarios(
            raster / "mndwi.tif", tmp_dir / "flood", raster,
            preflood_path=raster / "mndwi_preflood.tif" if pre else None,
        )
        for st in scenarios.values():
            st["path"] = Path(st["path"]).name

        progress("Rendering the satellite overlay", 0.7)
        corners = export_overlay(flood.true_colour, tmp_dir / "overlay.webp") if flood.true_colour else None

        progress("Downloading the road network (OpenStreetMap)", 0.8)
        try:
            G = ox.graph_from_bbox(bbox, network_type="drive")
        except (ValueError, ox._errors.InsufficientResponseError):
            raise RegionBuildError("No drivable roads found in this area.") from None
        ox.save_graphml(G, filepath=tmp_dir / "graph.graphml")

        meta = {
            "id": region_id,
            "name": name,
            "bbox": list(bbox),
            "center": [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
            "preset": preset,
            "flood_dates": flood_dates,
            "preflood_dates": preflood_dates,
            "flood_scene": _scene_info(flood, flood_item),
            "preflood_scene": _scene_info(pre, pre_item) if pre else None,
            "scenarios": scenarios,
            "overlay_corners": corners,
            "default_start": list(default_start) if default_start else None,
            "default_end": list(default_end) if default_end else None,
            "road_edges": len(G.edges),
            "warnings": warnings,
            "created_at": time.time(),
            "source": SATELLITE_SOURCE,
        }
        save_region(meta, tmp_dir)

        progress("Finalising", 0.95)
        shutil.rmtree(final_dir, ignore_errors=True)
        tmp_dir.rename(final_dir)
        progress("Done", 1.0)
        return meta
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
