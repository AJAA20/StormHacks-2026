"""One-off script: pre-generate ElevenLabs fallback audio for every cached region.

Run this while the ElevenLabs API is reachable (e.g. the night before the demo)
so that during judging, even if ElevenLabs is rate-limited or offline, every
region+scenario combination has a location-aware spoken fallback ready —
no manual recording needed.

Usage:
    python3 -m scripts.generate_fallback_audio
    python3 -m scripts.generate_fallback_audio --region abbotsford-2021
"""
from __future__ import annotations

import argparse
import logging

from dotenv import load_dotenv
load_dotenv()

from backend.audio.elevenlabs_engine import generate_fallback_library
from backend.regions.store import list_regions
from backend.routing.flood_intersection import SCENARIOS
from backend.routing.routes import compute_route

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def build_scenario_summary(region: dict, scenario: str) -> dict | None:
    """Run a real compute_route() for this region/scenario and shape the result
    into the fields format_dispatch_script() expects, using actual road names
    and flood stats instead of placeholder text."""
    start = region.get("default_start")
    end = region.get("default_end")
    if not start or not end:
        log.warning("Region '%s' has no default_start/default_end; skipping.", region["id"])
        return None

    try:
        result = compute_route(tuple(start), tuple(end), scenario, region["id"])
    except Exception:
        log.exception("compute_route failed for %s/%s", region["id"], scenario)
        return None

    flooded_roads = result.get("flooded_roads_geojson", {}).get("features", [])
    primary_blocked_road = None
    if flooded_roads:
        primary_blocked_road = flooded_roads[0].get("properties", {}).get("name")

    return {
        "primary_blocked_road": primary_blocked_road or "the primary route",
        "safe_detour_road": "the suggested detour" if result.get("route_found") else None,
        "flooded_edges_count": result.get("flooded_edges", 0),
        "detour_added_km": result.get("detour_added_km"),
        "eta_minutes": None,  # no travel-time model yet; omitted from the script
    }


def main(region_filter: str | None = None) -> None:
    regions = list_regions()
    if region_filter:
        regions = [r for r in regions if r["id"] == region_filter]
        if not regions:
            log.error("No cached region with id '%s'.", region_filter)
            return

    for region in regions:
        log.info("Generating fallback audio for region '%s'...", region["id"])
        summaries = {}
        for scenario in SCENARIOS:
            summary = build_scenario_summary(region, scenario)
            if summary:
                summaries[scenario] = summary

        if not summaries:
            log.warning("No usable scenarios for region '%s'; skipping.", region["id"])
            continue

        results = generate_fallback_library(region["id"], summaries)
        for scenario, ok in results.items():
            status = "OK" if ok else "FAILED"
            log.info("  %s/%s: %s", region["id"], scenario, status)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", help="Only generate for this region id (default: all cached regions)")
    args = parser.parse_args()
    main(args.region)
