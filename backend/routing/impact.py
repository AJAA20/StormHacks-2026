"""Flood impact rating: how much new water the satellite observation shows in the analysed area.

This is SatRelief's own summary of the satellite result, not an official flood warning level
and not a water-depth measurement. It is based on the area of NEW water (permanent rivers and
lakes are already removed by comparing with a dry-weather baseline image).
"""

from __future__ import annotations

import geopandas as gpd

# Upper bounds in km^2 of new water; anything above the last bound is "severe".
IMPACT_LEVELS = (("none", 0.5), ("low", 5.0), ("moderate", 20.0))
BASIS = (
    "Rated by the area of new water Sentinel-2 detected in the analysed area: "
    "under 0.5 km² none, 0.5–5 low, 5–20 moderate, over 20 severe. "
    "SatRelief's own rating, not an official flood warning level."
)


def impact_level(new_water_km2: float) -> str:
    for level, upper in IMPACT_LEVELS:
        if new_water_km2 < upper:
            return level
    return "severe"


def new_water_km2(flood_gdf: gpd.GeoDataFrame, flood_geojson: dict) -> float:
    """Total flood area. Uses the area_m2 the GIS module computed in a metric CRS; if a file
    lacks it (e.g. hand-drawn mock data), measures in the local UTM zone, never in degrees."""
    features = flood_geojson.get("features", [])
    areas = [f.get("properties", {}).get("area_m2") for f in features]
    if features and all(isinstance(a, (int, float)) for a in areas):
        return sum(areas) / 1e6
    if flood_gdf.empty:
        return 0.0
    return float(flood_gdf.to_crs(flood_gdf.estimate_utm_crs()).area.sum()) / 1e6


def flood_impact(flood_gdf: gpd.GeoDataFrame, flood_geojson: dict, flooded_roads: int) -> dict:
    km2 = new_water_km2(flood_gdf, flood_geojson)
    return {
        "level": impact_level(km2),
        "new_water_km2": round(km2, 2),
        "flooded_roads": flooded_roads,
        "basis": BASIS,
    }
