"""High-level orchestration: load graph, apply flood blocking, compute route."""
from backend.routing.graph_loader import load_graph, get_edges_gdf
from backend.routing.flood_intersection import load_flood_polygons, apply_flood_blocking
from backend.routing.router import find_route, route_length_km
from backend.routing.geojson import path_to_geojson


def compute_route(start_coords: tuple[float, float], end_coords: tuple[float, float]) -> dict:
    G = load_graph()
    edges_gdf = get_edges_gdf(G)
    flood_gdf = load_flood_polygons()
    flooded_count = apply_flood_blocking(G, edges_gdf, flood_gdf)

    path = find_route(G, start_coords, end_coords)

    if path is None:
        return {
            "route_found": False,
            "distance_km": 0,
            "flooded_edges": flooded_count,
            "route_status": "no_safe_route",
            "route_geojson": {},
        }

    return {
        "route_found": True,
        "distance_km": round(route_length_km(G, path), 2),
        "flooded_edges": flooded_count,
        "route_status": "safe",
        "route_geojson": path_to_geojson(G, path),
    }