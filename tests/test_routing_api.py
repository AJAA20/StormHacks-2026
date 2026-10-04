"""Integration tests: satellite flood scenarios -> Jethro's routing -> /api/route (what the UI calls).

Uses the committed Abbotsford preset (backend/data/regions/abbotsford-2021/);
skipped if it hasn't been generated.
"""

import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRESET = ROOT / "backend/data/regions/abbotsford-2021"
GRAPH = PRESET / "graph.graphml"
FLOOD = PRESET / "flood"
pytestmark = pytest.mark.skipif(
    not GRAPH.exists() or not (FLOOD / "severe.geojson").exists(),
    reason="preset missing: run scripts/build_region.py (see README)",
)

START = [-122.219, 49.024]  # south edge of Sumas Prairie (frontend/lib/config.ts)
END = [-122.2852, 49.0824]  # north Abbotsford

# Every field frontend/lib/api.ts reads from the response.
UI_FIELDS = {
    "status", "scenario", "route_found", "start_coords", "end_coords", "distance_km",
    "detour_added_km", "flooded_edges", "flooded_edges_avoided", "route_status", "route_geojson",
    "original_route_geojson", "flood_polygons_geojson", "flooded_roads_geojson",
}


@pytest.fixture(scope="module")
def client():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from fastapi.testclient import TestClient
    from backend.main import app

    return TestClient(app)


def post(client, scenario):
    r = client.post("/api/route", json={"start_coords": START, "end_coords": END, "scenario": scenario})
    assert r.status_code == 200
    return r.json()


@pytest.mark.parametrize("scenario", ["low", "moderate", "severe"])
def test_response_has_every_field_the_ui_reads(client, scenario):
    d = post(client, scenario)
    assert UI_FIELDS <= d.keys()
    assert d["scenario"] == scenario
    assert d["flood_polygons_geojson"]["type"] == "FeatureCollection"
    assert d["flooded_roads_geojson"]["type"] == "FeatureCollection"


def test_uses_satellite_flood_not_mock(client):
    d = post(client, "severe")
    assert d["flood_source"] == "severe.geojson"
    assert d["flood_polygons_geojson"]["features"][0]["properties"]["source"] == "satellite"


def test_worse_flood_blocks_more_roads_and_lengthens_route(client):
    low, moderate, severe = (post(client, s) for s in ("low", "moderate", "severe"))
    assert low["flooded_edges"] < moderate["flooded_edges"] < severe["flooded_edges"]
    assert all(d["route_found"] for d in (low, moderate, severe))
    assert low["distance_km"] <= moderate["distance_km"] <= severe["distance_km"]
    assert severe["detour_added_km"] > 0  # the flood forces a detour


def test_safe_route_never_uses_a_flooded_road(client):
    from shapely.geometry import shape

    d = post(client, "severe")
    route = shape(d["route_geojson"]["geometry"])
    flood = [shape(f["geometry"]) for f in d["flood_polygons_geojson"]["features"]]
    # Allow a touch at a polygon edge, but the route must not run through water.
    assert sum(route.intersection(p).length for p in flood) < 1e-4  # ~10 m in degrees


def test_highway_1_is_flooded_in_severe_scenario(client):
    """Sanity check against reality: Hwy 1 at Sumas Prairie was closed in Nov 2021."""
    d = post(client, "severe")
    names = " ".join(str(f["properties"].get("name")) for f in d["flooded_roads_geojson"]["features"])
    assert "Trans-Canada Highway" in names


def test_bad_scenario_is_rejected(client):
    r = client.post("/api/route", json={"start_coords": START, "end_coords": END, "scenario": "apocalyptic"})
    assert r.status_code == 422


def test_flood_impact_rating_is_reported(client):
    d = post(client, "severe")
    impact = d["flood_impact"]
    assert impact["level"] == "severe"  # ~27.6 km2 of new water on Sumas Prairie, Nov 2021
    assert 20 < impact["new_water_km2"] < 40
    assert impact["flooded_roads"] == d["flooded_edges"]
    assert "not an official" in impact["basis"]


def test_default_detection_level_is_the_standard_one(client):
    r = client.post("/api/route", json={"start_coords": START, "end_coords": END})
    assert r.json()["scenario"] == "severe" and r.json()["flood_source"] == "severe.geojson"
