"""FloodDataProvider: choose the satellite observation for a location, then reuse the shared pipeline.

The two exploration modes differ ONLY in how the Sentinel-2 observation is chosen:

    latest      the most recent usable (mostly cloud-free) image of the area
    historical  the usable image closest to a requested date

Everything downstream -- MNDWI flood detection, flood polygons, road graph, routing -- is the
same code path (builder.build_region -> /api/route).

Honesty rules this module enforces:
  * Satellite images are snapshots, not a live feed. We return the real acquisition date/time.
  * A requested historical date rarely has its own image; we return the nearest usable one and
    say so. We never relabel an image with the requested date.
  * If no usable image exists (or the archive can't be reached and nothing is cached),
    we raise an error instead of reusing another place's or another time's data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import requests

from backend.regions import builder
from backend.regions.builder import MIN_CLEAR_PCT, Progress, RegionBuildError
from backend.regions.store import list_regions, region_id_for

AOI_KM = 12.0  # side of the square analysed around a point location
LATEST_LOOKBACK_DAYS = 120
HISTORICAL_WINDOW_DAYS = 21  # look this far either side of a requested date


class NoObservation(RegionBuildError):
    """No usable satellite observation for this place/time (a user-facing message)."""


@dataclass
class Location:
    latitude: float
    longitude: float
    name: str


@dataclass
class Observation:
    item: object  # pystac Item
    date: date
    clear_pct: float


# ---- area of interest ----------------------------------------------------------------

def box_around(lat: float, lon: float, side_km: float = AOI_KM) -> tuple[float, float, float, float]:
    from pyproj import Geod

    geod = Geod(ellps="WGS84")
    half = side_km * 1000 / 2
    east = geod.fwd(lon, lat, 90, half)[0]
    west = geod.fwd(lon, lat, 270, half)[0]
    north = geod.fwd(lon, lat, 0, half)[1]
    south = geod.fwd(lon, lat, 180, half)[1]
    return (round(west, 5), round(south, 5), round(east, 5), round(north, 5))


def _inside(bbox, lat: float, lon: float) -> bool:
    w, s, e, n = bbox
    return w <= lon <= e and s <= lat <= n


def area_for(location: Location) -> tuple[tuple, dict | None]:
    """A point inside a preset uses the preset's area (so its cached analysis can be reused);
    anywhere else gets a square around the point."""
    for region in list_regions():
        if region.get("preset") and _inside(region["bbox"], location.latitude, location.longitude):
            return tuple(region["bbox"]), region
    return box_around(location.latitude, location.longitude), None


# ---- choosing the observation -----------------------------------------------------------

def _first_usable(bbox, date_range: str, order) -> tuple[object, float, date] | None:
    """Score images in `order` (best candidate first) and stop at the first one that is at
    least MIN_CLEAR_PCT cloud-free over the area. Scoring reads each image's cloud mask, so
    stopping early keeps "latest" and "nearest to a date" fast."""
    from backend.satellite.stac import score_scene, search_scenes

    items = sorted(search_scenes(bbox, date_range), key=lambda it: order(it.datetime.date()))
    for it in items:
        clear = score_scene(it, bbox).aoi_clear_pct
        if clear >= MIN_CLEAR_PCT:
            return it, clear, it.datetime.date()
    return None


def select_latest(bbox, today: date | None = None) -> Observation:
    today = today or date.today()
    start = today - timedelta(days=LATEST_LOOKBACK_DAYS)
    found = _first_usable(bbox, f"{start}/{today}", order=lambda d: -d.toordinal())  # newest first
    if not found:
        raise NoObservation(
            "No recent usable satellite observation is available for this location "
            f"(no Sentinel-2 image in the last {LATEST_LOOKBACK_DAYS} days was at least "
            f"{MIN_CLEAR_PCT:.0f}% cloud-free over the area)."
        )
    item, clear, day = found
    return Observation(item, day, clear)


def select_historical(bbox, requested: date, today: date | None = None) -> Observation:
    today = today or date.today()
    start = requested - timedelta(days=HISTORICAL_WINDOW_DAYS)
    end = min(requested + timedelta(days=HISTORICAL_WINDOW_DAYS), today)
    found = _first_usable(bbox, f"{start}/{end}", order=lambda d: abs((d - requested).days))  # nearest first
    if not found:
        raise NoObservation(
            f"No usable satellite observation within {HISTORICAL_WINDOW_DAYS} days of "
            f"{requested:%B %-d, %Y} for this location (images were too cloudy or none exist)."
        )
    item, clear, day = found
    return Observation(item, day, clear)


# ---- the provider -----------------------------------------------------------------------

ARCHIVE_ERRORS = (requests.RequestException, OSError)  # network down, S3/STAC unreachable


def _find_region(scene_id: str, bbox) -> str | None:
    for region in list_regions():
        scene = region.get("flood_scene") or {}
        if scene.get("id") == scene_id and [round(v, 4) for v in region["bbox"]] == [round(v, 4) for v in bbox]:
            return region["id"]
    return None


def analyze(mode: str, location: Location, requested_date: date | None = None,
            progress: Progress = lambda stage, frac: None) -> dict:
    """Choose the observation, (re)use or build the region, and describe what was used.

    Returns per-request details for the UI; routing then uses /api/route with region_id.
    """
    if mode not in ("latest", "historical"):
        raise RegionBuildError("mode must be 'latest' or 'historical'.")
    if mode == "historical" and requested_date is None:
        raise RegionBuildError("Historical mode needs a date.")

    bbox, preset = area_for(location)
    details = {
        "mode": mode,
        "requested_date": requested_date.isoformat() if requested_date else None,
        "location": {"name": location.name, "latitude": location.latitude, "longitude": location.longitude},
        "note": None,
    }

    progress("Searching the Sentinel-2 archive" + (" for the latest usable image" if mode == "latest"
             else f" near {requested_date:%b %-d, %Y}"), 0.05)
    try:
        obs = select_latest(bbox) if mode == "latest" else select_historical(bbox, requested_date)
    except NoObservation:
        raise
    except ARCHIVE_ERRORS:
        return _offline_fallback(mode, preset, requested_date, details)

    details["observation_date"] = obs.date.isoformat()
    if mode == "historical" and obs.date != requested_date:
        details["note"] = "Using the nearest usable satellite observation to your selected date."

    region_id = _find_region(obs.item.id, bbox)
    if region_id is None:
        name = f"{location.name} · Sentinel-2 {obs.date:%b %-d, %Y}"
        region_id = region_id_for(location.name, bbox, obs.item.id)
        start = obs.date - timedelta(days=120)
        end = obs.date - timedelta(days=14)
        builder.build_region(
            region_id, name, bbox, f"{obs.date}/{obs.date}", f"{start}/{end}",
            progress=progress, flood_item=obs.item,
        )
    else:
        progress("Loaded from cache", 1.0)
    details["region_id"] = region_id
    return details


def _offline_fallback(mode: str, preset: dict | None, requested_date: date | None, details: dict) -> dict:
    """Archive unreachable: only a cached analysis of the SAME area and period may be shown."""
    scene_day = date.fromisoformat(preset["flood_scene"]["date"]) if preset else None
    if (mode == "historical" and preset and requested_date
            and abs((scene_day - requested_date).days) <= HISTORICAL_WINDOW_DAYS):
        details.update(
            region_id=preset["id"],
            observation_date=scene_day.isoformat(),
            note="The satellite archive could not be reached, so this is SatRelief's cached analysis "
                 "of this flood event (the closest cached observation to your date).",
        )
        return details
    raise RegionBuildError(
        "Satellite flood analysis is not available for this location right now: the satellite "
        "archive can't be reached and no cached analysis covers this place and time."
    )
