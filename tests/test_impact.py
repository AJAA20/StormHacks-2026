"""Flood impact rating thresholds (backend/routing/impact.py)."""

import geopandas as gpd
import pytest
from shapely.geometry import box

from backend.routing.impact import flood_impact, impact_level


@pytest.mark.parametrize("km2, level", [
    (0.0, "none"), (0.02, "none"), (0.5, "low"), (4.99, "low"),
    (5.0, "moderate"), (7.09, "moderate"), (20.0, "severe"), (27.6, "severe"), (66, "severe"),
])
def test_levels(km2, level):
    assert impact_level(km2) == level


def test_uses_area_from_gis_module():
    gj = {"features": [{"properties": {"area_m2": 3_000_000}}, {"properties": {"area_m2": 4_000_000}}]}
    out = flood_impact(gpd.GeoDataFrame(geometry=[]), gj, 12)
    assert out == {"level": "moderate", "new_water_km2": 7.0, "flooded_roads": 12, "basis": out["basis"]}


def test_measures_in_metres_when_area_missing():
    # ~0.01 x 0.01 degree square near Abbotsford is ~0.8 km2 -- never "0.0001 square degrees".
    gdf = gpd.GeoDataFrame(geometry=[box(-122.25, 49.05, -122.24, 49.06)], crs="EPSG:4326")
    out = flood_impact(gdf, {"features": [{"properties": {}}]}, 0)
    assert 0.7 < out["new_water_km2"] < 0.9 and out["level"] == "low"
