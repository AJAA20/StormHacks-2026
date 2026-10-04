from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from backend.regions.store import PRESET_ID, RegionNotFound
from backend.routing.routes import PointOutsideRegion, compute_route
from backend.audio.elevenlabs_engine import (
    DEFAULT_VOICE_ID,
    format_dispatch_script,
    generate_with_cache,
    load_fallback_audio,
)

router = APIRouter()

class RouteRequest(BaseModel):
    start_coords: list[float]  # [lng, lat]
    end_coords: list[float]    # [lng, lat]
    # Flood scenario from the UI; each maps to a satellite flood layer of the region
    scenario: Literal["low", "moderate", "severe"] = "severe"
    # Which analysed area to route in (GET /api/regions); default = Abbotsford preset
    region_id: str = PRESET_ID
    flood_level: float = 0.5
    custom_polygon_overrides: list = []


@router.post("/api/route")
def get_route(req: RouteRequest):
    try:
        return compute_route(tuple(req.start_coords), tuple(req.end_coords), req.scenario, req.region_id)
    except RegionNotFound:
        raise HTTPException(404, f"Unknown region '{req.region_id}'.") from None
    except PointOutsideRegion as exc:
        raise HTTPException(400, str(exc)) from None


class AudioAlertRequest(BaseModel):
    primary_blocked_road: str = "the primary route"
    safe_detour_road: str = "an alternate route"
    flooded_edges_count: int = 0
    detour_added_km: float | None = None
    eta_minutes: float | None = None
    voice_id: str = DEFAULT_VOICE_ID
    # Used for the pre-generated fallback file lookup if ElevenLabs is unreachable.
    fallback_scenario: Literal["low", "moderate", "severe"] = "severe"
    # Which region's fallback library to check first (location-aware fallback).
    region_id: str = PRESET_ID


@router.post("/api/audio-alert")
def audio_alert(req: AudioAlertRequest):
    """Generate a spoken emergency dispatch alert as MP3 bytes.

    Zero-crash guarantee: if ElevenLabs is unreachable or misconfigured, falls
    back to a pre-generated MP3 for this region+scenario (see
    generate_fallback_library). If even that is missing, returns 503 so the
    frontend can fall back to window.speechSynthesis.
    """
    script = format_dispatch_script(req.model_dump())
    audio_bytes = generate_with_cache(script, req.voice_id)

    if audio_bytes is None:
        audio_bytes = load_fallback_audio(req.fallback_scenario, req.region_id)

    if audio_bytes is None:
        raise HTTPException(
            503,
            "Audio generation unavailable (no ElevenLabs API key/connection and no fallback cached). "
            "Use client-side speech synthesis instead.",
        )

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"X-Dispatch-Script": script[:500]},
    )

