"""High-level orchestration: load graph, apply flood blocking, compute route."""
import json
import threading

from backend.regions.store import PRESET_ID, load_region, region_dir
from backend.routing.graph_loader import load_graph, get_edges_gdf
from backend.routing.flood_intersection import (
    apply_flood_blocking,
    flood_path_for,
    load_flood_geojson,
    load_flood_polygons,
)
from backend.routing.router import find_route, route_length_km
from backend.routing.geojson import path_to_geojson

# Graphs are shared and apply_flood_blocking mutates their weights, so two requests
# must not interleave.
_lock = threading.Lock()


class PointOutsideRegion(ValueError):
    pass


def _check_inside(bbox, point, label: str) -> None:
    w, s, e, n = bbox
    lng, lat = point
    if not (w <= lng <= e and s <= lat <= n):
        raise PointOutsideRegion(f"{label} is outside the analysed area. Pick a point inside the dashed box.")


def _flooded_roads_geojson(edges_gdf, flooded_mask) -> dict:
    roads = edges_gdf.loc[flooded_mask, ["name", "highway", "length", "geometry"]].copy()
    for col in ("name", "highway"):  # OSM tags can be lists; keep the GeoJSON simple
        roads[col] = roads[col].apply(lambda v: ", ".join(v) if isinstance(v, list) else v)
    return json.loads(roads.reset_index(drop=True).to_json(drop_id=True))


def _flooded_edges_on(G, path) -> int:
    """How many edges of `path` are blocked (on every parallel edge between the two nodes)."""
    return sum(
        all(d.get("blocked", False) for d in G[u][v].values())
        for u, v in zip(path[:-1], path[1:])
    )


def compute_route(
    start_coords: tuple[float, float],
    end_coords: tuple[float, float],
    scenario: str = "severe",
    region_id: str = PRESET_ID,
) -> dict:
    """Raises RegionNotFound (unknown region) or PointOutsideRegion (bad start/end)."""
    region = load_region(region_id)
    _check_inside(region["bbox"], start_coords, "Start")
    _check_inside(region["bbox"], end_coords, "Destination")
    folder = region_dir(region_id)

    with _lock:
        G = load_graph(folder / "graph.graphml")
        edges_gdf = get_edges_gdf(G)
        flood_path = flood_path_for(scenario, folder / "flood")
        flood_geojson = load_flood_geojson(flood_path)
        flood_gdf = load_flood_polygons(flood_path)
        flooded_count = apply_flood_blocking(G, edges_gdf, flood_gdf)
        flooded_mask = [G[u][v][k]["blocked"] for u, v, k in edges_gdf.index]

        # Route a driver would take with no flood information, for comparison.
        original = find_route(G, start_coords, end_coords, weight="length")
        path = find_route(G, start_coords, end_coords)

        original_km = round(route_length_km(G, original), 2) if original else None
        result = {
            "status": "success",
            "scenario": scenario,
            "region_id": region_id,
            "start_coords": list(start_coords),
            "end_coords": list(end_coords),
            "flooded_edges": flooded_count,
            "flooded_edges_avoided": _flooded_edges_on(G, original) if original else None,
            "original_route_geojson": path_to_geojson(G, original) if original else None,
            "flood_polygons_geojson": flood_geojson,
            "flooded_roads_geojson": _flooded_roads_geojson(edges_gdf, flooded_mask),
            "flood_source": flood_path.name,
        }

        if path is None:
            return result | {
                "route_found": False,
                "distance_km": None,
                "detour_added_km": None,
                "route_status": "no_safe_route",
                "route_geojson": None,
            }

        distance_km = round(route_length_km(G, path), 2)
        return result | {
            "route_found": True,
            "distance_km": distance_km,
            "detour_added_km": round(distance_km - original_km, 2) if original_km is not None else None,
            "route_status": "safe",
            "route_geojson": path_to_geojson(G, path),
        }
