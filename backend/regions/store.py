"""Analysed regions on disk.

Each region is a folder:
    backend/data/regions/<region_id>/
        region.json          metadata (name, bbox, dates, scenes, scenario stats, overlay corners)
        graph.graphml        OSM drive network for the bbox
        flood/<scenario>.geojson
        overlay.webp         Sentinel-2 true colour on the flood date (Web Mercator)
        raster/              MNDWI + masks (gitignored)

Presets (e.g. Abbotsford) are committed so the demo works offline; regions users
analyse are created at runtime and gitignored.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REGIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "regions"
PRESET_ID = "abbotsford-2021"


class RegionNotFound(LookupError):
    pass


def region_dir(region_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", region_id):  # also blocks path tricks like ../
        raise RegionNotFound(region_id)
    return REGIONS_DIR / region_id


def region_id_for(name: str, bbox, flood_dates: str) -> str:
    """Stable id: same area + dates -> same id, so repeat requests reuse the cached result."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "area"
    key = json.dumps([[round(v, 4) for v in bbox], flood_dates])
    return f"{slug}-{hashlib.sha1(key.encode()).hexdigest()[:6]}"


def region_exists(region_id: str) -> bool:
    try:
        return (region_dir(region_id) / "region.json").exists()
    except RegionNotFound:
        return False


def load_region(region_id: str) -> dict:
    path = region_dir(region_id) / "region.json"
    if not path.exists():
        raise RegionNotFound(region_id)
    return json.loads(path.read_text())


def save_region(meta: dict, directory: Path) -> None:
    (directory / "region.json").write_text(json.dumps(meta, indent=2))


def list_regions() -> list[dict]:
    """Presets first (oldest first, so the main demo stays on top), then user regions newest first."""
    regions = []
    if REGIONS_DIR.exists():
        for meta_path in REGIONS_DIR.glob("*/region.json"):
            try:
                regions.append(json.loads(meta_path.read_text()))
            except (OSError, json.JSONDecodeError):
                continue
    def order(r: dict):
        created = r.get("created_at", 0)
        return (0, created) if r.get("preset") else (1, -created)

    return sorted(regions, key=order)


def public_summary(meta: dict) -> dict:
    """What the frontend needs (no local file paths)."""
    keys = ("id", "name", "bbox", "center", "preset", "flood_dates", "preflood_dates", "flood_scene",
            "preflood_scene", "scenarios", "overlay_corners", "default_start", "default_end",
            "warnings", "created_at", "road_edges", "source")
    return {k: meta.get(k) for k in keys}
