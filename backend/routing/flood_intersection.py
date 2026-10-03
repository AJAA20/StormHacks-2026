"""Detect which road edges intersect flood polygons and mark them blocked."""
from pathlib import Path
import geopandas as gpd
import networkx as nx
from shapely.geometry import shape
import json

MOCK_FLOOD_PATH = Path(__file__).parent.parent / "data" / "mock_flood.json"
BLOCK_WEIGHT = 1e9  # infinite penalty, per spec


def load_flood_polygons(path: Path = MOCK_FLOOD_PATH, flood_level: float = 1.0) -> gpd.GeoDataFrame:
    with open(path) as f:
        gj = json.load(f)
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
    """
    flood_union = flood_gdf.geometry.unary_union
    flooded_count = 0

    for (u, v, k), geom in zip(edges_gdf.index, edges_gdf.geometry):
        intersects = geom.intersects(flood_union)
        data = G[u][v][k]
        data["blocked"] = bool(intersects)
        if intersects:
            data["weight"] = BLOCK_WEIGHT
            flooded_count += 1
        else:
            data["weight"] = data.get("length", 1.0)

    return flooded_count