"""ElevenLabs text-to-speech wrapper for emergency evacuation voice alerts.

Zero-crash guarantee: any failure (missing API key, network error, rate limit)
is logged and results in `None` being returned, never an exception bubbling up
to the FastAPI endpoint. Callers must handle `None` by falling back to a
pre-cached MP3 or client-side speech synthesis.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import requests

log = logging.getLogger(__name__)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" - clear, calm, good for alerts
REQUEST_TIMEOUT_SEC = 8

AUDIO_CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "audio_cache"

# Tuned for emergency clarity: high stability (less emotional variance), strong
# similarity boost (consistent voice identity even under repeated calls).
VOICE_SETTINGS = {
    "stability": 0.75,
    "similarity_boost": 0.85,
}


def format_dispatch_script(scenario_data: dict) -> str:
    """Build a concise, judge/driver-friendly emergency dispatch script from route data.

    Expected keys (all optional, sensible defaults substituted so this never raises):
        flooded_edges_count, detour_added_km, eta_minutes,
        primary_blocked_road, safe_detour_road
    """
    flooded_edges_count = scenario_data.get("flooded_edges_count", 0)
    detour_added_km = scenario_data.get("detour_added_km")
    eta_minutes = scenario_data.get("eta_minutes")
    primary_blocked_road = scenario_data.get("primary_blocked_road") or "the primary route"
    safe_detour_road = scenario_data.get("safe_detour_road") or "an alternate route"

    detour_phrase = (
        f"Detour adds {detour_added_km:.1f} kilometers. "
        if isinstance(detour_added_km, (int, float))
        else ""
    )
    eta_phrase = (
        f"Estimated travel time is {eta_minutes:.0f} minutes."
        if isinstance(eta_minutes, (int, float))
        else ""
    )

    return (
        f"Emergency Dispatch Alert: Primary route via {primary_blocked_road} is blocked by "
        f"floodwaters, avoiding {flooded_edges_count} submerged road segments. "
        f"Rerouting via {safe_detour_road}. {detour_phrase}{eta_phrase}"
    ).strip()


def _cache_key(text: str, voice_id: str) -> str:
    digest = hashlib.sha1(f"{voice_id}:{text}".encode()).hexdigest()[:16]
    return digest


def generate_emergency_audio(text_prompt: str, voice_id: str = DEFAULT_VOICE_ID) -> bytes | None:
    """Call ElevenLabs TTS and return MP3 bytes, or None on any failure.

    Never raises: missing API key, network errors, non-200 responses, and
    unexpected exceptions are all caught and logged so the FastAPI app keeps
    running and the frontend can fall back gracefully.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        log.warning("ELEVENLABS_API_KEY not set; cannot generate live audio.")
        return None

    url = ELEVENLABS_API_URL.format(voice_id=voice_id)
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text_prompt,
        "model_id": "eleven_flash_v3",
        "voice_settings": VOICE_SETTINGS,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SEC)
        if resp.status_code != 200:
            log.error("ElevenLabs TTS failed (%s): %s", resp.status_code, resp.text[:300])
            return None
        return resp.content
    except requests.RequestException:
        log.exception("ElevenLabs TTS request failed (network error)")
        return None
    except Exception:
        log.exception("Unexpected error generating emergency audio")
        return None


def generate_with_cache(text_prompt: str, voice_id: str = DEFAULT_VOICE_ID) -> bytes | None:
    """Like generate_emergency_audio, but caches results to disk by content hash
    so repeated identical alerts (e.g. demo rehearsal) don't re-hit the API."""
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(text_prompt, voice_id)
    cached_path = AUDIO_CACHE_DIR / f"{key}.mp3"

    if cached_path.exists():
        return cached_path.read_bytes()

    audio_bytes = generate_emergency_audio(text_prompt, voice_id)
    if audio_bytes:
        try:
            cached_path.write_bytes(audio_bytes)
        except OSError:
            log.exception("Failed to write audio cache file %s", cached_path)
    return audio_bytes


def load_fallback_audio(scenario_key: str, region_id: str | None = None) -> bytes | None:
    """Pre-generated MP3 for a region+scenario, used when ElevenLabs is unreachable.

    Looks for a region-specific file first (e.g. "abbotsford-2021_severe.mp3",
    generated automatically from that region's real flood data by
    `generate_fallback_library()`), then falls back to a generic
    "fallback_<scenario_key>.mp3" if no region-specific one exists.
    """
    candidates = []
    if region_id:
        candidates.append(AUDIO_CACHE_DIR / f"{region_id}_{scenario_key}.mp3")
    candidates.append(AUDIO_CACHE_DIR / f"fallback_{scenario_key}.mp3")

    for path in candidates:
        if path.exists():
            return path.read_bytes()

    log.warning(
        "No fallback audio found for region '%s' scenario '%s' (checked: %s)",
        region_id, scenario_key, [str(p) for p in candidates],
    )
    return None


def generate_fallback_library(
    region_id: str,
    scenario_summaries: dict[str, dict],
    voice_id: str = DEFAULT_VOICE_ID,
) -> dict[str, bool]:
    """Pre-generate one fallback MP3 per scenario for a region, using real data
    (no manual scripting needed). Call this once per region after a build
    completes (or offline via a script) while the ElevenLabs API is reachable;
    the resulting files then serve as the offline-safe fallback during the demo.

    scenario_summaries: {scenario_key: {primary_blocked_road, safe_detour_road,
        flooded_edges_count, detour_added_km, eta_minutes}} — derived from a real
        compute_route() call for that region/scenario (e.g. a representative
        start/end pair), so the spoken script reflects actual local road names
        and flood stats instead of generic placeholder text.

    Returns {scenario_key: True/False} indicating which ones succeeded.
    """
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, bool] = {}

    for scenario_key, summary in scenario_summaries.items():
        script = format_dispatch_script(summary)
        audio_bytes = generate_emergency_audio(script, voice_id)
        path = AUDIO_CACHE_DIR / f"{region_id}_{scenario_key}.mp3"

        if audio_bytes:
            try:
                path.write_bytes(audio_bytes)
                results[scenario_key] = True
                continue
            except OSError:
                log.exception("Failed to write fallback audio file %s", path)

        results[scenario_key] = False
        log.warning(
            "Could not pre-generate fallback audio for %s/%s; "
            "demo will rely on generic fallback or speechSynthesis.",
            region_id, scenario_key,
        )

    return results

