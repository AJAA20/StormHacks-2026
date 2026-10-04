"""Analysed areas: list presets/regions, analyse a new area (background job), geocode a place name."""

import threading
import time
from datetime import date
from typing import Literal

import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.regions import jobs, observations
from backend.regions.builder import RegionBuildError, validate_request
from backend.regions.store import (
    RegionNotFound,
    list_regions,
    load_region,
    public_summary,
    region_dir,
    region_id_for,
)

router = APIRouter()


@router.get("/api/regions")
def get_regions():
    return [public_summary(r) for r in list_regions()]


@router.get("/api/regions/{region_id}")
def get_region(region_id: str):
    try:
        return public_summary(load_region(region_id))
    except RegionNotFound:
        raise HTTPException(404, f"Unknown region '{region_id}'.") from None


@router.get("/api/regions/{region_id}/overlay")
def get_overlay(region_id: str):
    """Sentinel-2 true-colour image of the flood date, for draping over the map."""
    try:
        path = region_dir(region_id) / "overlay.webp"
    except RegionNotFound:
        path = None
    if path is None or not path.exists():
        raise HTTPException(404, "No satellite overlay for this region.")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "max-age=86400"})


class AnalyzeRequest(BaseModel):
    name: str = Field("Custom area", max_length=80)
    bbox: list[float] = Field(..., description="[west, south, east, north] in degrees")
    flood_dates: str = Field(..., description="YYYY-MM-DD/YYYY-MM-DD around the flood")
    preflood_dates: str | None = Field(None, description="Dry-weather baseline; default: 4 months before")


@router.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    """Start analysing an area. Poll GET /api/analyze/{job_id} until status is done or error."""
    try:
        bbox, flood_dates, preflood_dates = validate_request(req.bbox, req.flood_dates, req.preflood_dates)
    except RegionBuildError as exc:
        raise HTTPException(400, str(exc)) from None
    region_id = region_id_for(req.name, bbox, flood_dates)
    return jobs.submit(region_id, req.name.strip() or "Custom area", bbox, flood_dates, preflood_dates).public()


class FloodAnalysisRequest(BaseModel):
    """One request shape for both exploration modes; only the image selection differs."""
    mode: Literal["latest", "historical"]
    latitude: float = Field(..., ge=-85, le=85)
    longitude: float = Field(..., ge=-180, le=180)
    location_name: str = Field("Selected location", max_length=120)
    requested_date: date | None = Field(None, description="Required for historical mode")


@router.post("/api/flood-analysis")
def flood_analysis(req: FloodAnalysisRequest):
    """Latest-available or historical flood analysis around a location.

    Returns a job; poll GET /api/flood-analysis/{job_id}. When done, `details` holds the mode,
    requested date, actual satellite observation date and any note, and `region_id` is what
    POST /api/route takes.
    """
    if req.mode == "historical":
        if req.requested_date is None:
            raise HTTPException(400, "Choose a date for the historical view.")
        if req.requested_date < date(2015, 7, 1):
            raise HTTPException(400, "Sentinel-2 observations start in mid-2015; choose a later date.")
        if req.requested_date > date.today():
            raise HTTPException(400, "The historical date can't be in the future.")
    requested = req.requested_date if req.mode == "historical" else None
    location = observations.Location(req.latitude, req.longitude, req.location_name.strip() or "Selected location")
    key = f"{req.mode}:{req.latitude:.3f}:{req.longitude:.3f}:{requested or date.today()}"
    job = jobs.submit_task(key, location.name,
                           lambda progress: observations.analyze(req.mode, location, requested, progress))
    return job.public()


@router.get("/api/flood-analysis/{job_id}")
@router.get("/api/analyze/{job_id}")
def analyze_status(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job (the server may have restarted). Start the analysis again.")
    return job.public()


# --- place search (OpenStreetMap Nominatim) -----------------------------------
# Proxied through the backend so we can send the identifying User-Agent the
# Nominatim usage policy asks for, and keep to its 1 request/second limit.
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
USER_AGENT = "SatRelief/0.1 (StormHacks 2026 hackathon flood-routing demo)"
_geocode_lock = threading.Lock()
_last_geocode = 0.0


def _nominatim(path: str, params: dict) -> object:
    """GET from Nominatim with its required User-Agent, at most one request per second."""
    global _last_geocode
    with _geocode_lock:
        wait = 1.0 - (time.time() - _last_geocode)
        if wait > 0:
            time.sleep(wait)
        try:
            r = requests.get(f"{NOMINATIM_BASE}/{path}", params={**params, "format": "jsonv2"},
                             headers={"User-Agent": USER_AGENT}, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            raise HTTPException(502, "Place search is unavailable right now. Pan the map to the area instead.") from None
        finally:
            _last_geocode = time.time()


@router.get("/api/geocode")
def geocode(q: str):
    q = q.strip()
    if not q:
        return []
    results = []
    for item in _nominatim("search", {"q": q, "limit": 5}):
        s, n, w, e = (float(v) for v in item["boundingbox"])
        results.append({
            "name": item["display_name"],
            "center": [float(item["lon"]), float(item["lat"])],
            "bbox": [w, s, e, n],
        })
    return results


@router.get("/api/geocode/reverse")
def reverse_geocode(lat: float, lon: float):
    """Readable name for coordinates (e.g. the user's browser location)."""
    item = _nominatim("reverse", {"lat": lat, "lon": lon, "zoom": 12})
    name = item.get("display_name") if isinstance(item, dict) else None
    return {"name": name}
