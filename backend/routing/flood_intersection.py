"""Detect which road edges intersect flood polygons and mark them blocked."""
from pathlib import Path
import geopandas as gpd
import networkx as nx
from shapely.geometry import shape
import json

DATA_DIR = Path(__file__).parent.parent / "data"
MOCK_FLOOD_PATH = DATA_DIR / "mock_flood.json"
# Satellite-derived flood polygons, one file per UI scenario, per region
# (built by backend/regions/builder.py from Sentinel-2 MNDWI). Default = Abbotsford preset.
FLOOD_DIR = DATA_DIR / "regions" / "abbotsford-2021" / "flood"
SCENARIOS = ("low", "moderate", "severe")
BLOCK_WEIGHT = 1e9  # infinite penalty, per spec


def flood_path_for(scenario: str, flood_dir: Path = FLOOD_DIR) -> Path:
    """Real satellite flood file for the scenario, falling back to the mock if it's missing."""
    path = Path(flood_dir) / f"{scenario}.geojson"
    return path if path.exists() else MOCK_FLOOD_PATH


def load_flood_geojson(path: Path = MOCK_FLOOD_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def load_flood_polygons(path: Path = MOCK_FLOOD_PATH, flood_level: float = 1.0) -> gpd.GeoDataFrame:
    gj = load_flood_geojson(path)
    geoms = []
    for feat in gj["features"]:
        intensity = feat.get("properties", {}).get("intensity", 1.0)
        if intensity <= flood_level:
            geoms.append(shape(feat["geometry"]))
    return gpd.GeoDataFrame(geometry=geoms, crs="EPSG:4326")


def apply_flood_blocking(
    G: nx.MultiDiGraph,
    edges_gdf: gpd.GeoDataFrame,
    flood_gdf: gpd.GeoDataFrame,
) -> int:
    """
    Mutates G in place: sets edge['blocked'] = True and edge['weight'] = BLOCK_WEIGHT
    for any edge whose geometry intersects a flood polygon.
    Returns the count of flooded edges.

    intersects() is a topological test, so it is exact in EPSG:4326 (no distances involved).
    """
    if flood_gdf.empty:  # no flooding detected: every road is open
        for (u, v, k) in edges_gdf.index:
            data = G[u][v][k]
            data["blocked"] = False
            data["weight"] = data.get("length", 1.0)
        return 0

    flood_union = flood_gdf.geometry.union_all()
    # Vectorised test (one call for all edges) instead of a Python loop.
    flooded = edges_gdf.geometry.intersects(flood_union)

    for (u, v, k), intersects in zip(edges_gdf.index, flooded):
        data = G[u][v][k]
        data["blocked"] = bool(intersects)
        if intersects:
            data["weight"] = BLOCK_WEIGHT
        else:
            data["weight"] = data.get("length", 1.0)

    return int(flooded.sum())
