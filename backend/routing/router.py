"""Compute shortest safe route avoiding blocked (flooded) edges."""
import networkx as nx
import osmnx as ox
from typing import Optional

BLOCK_WEIGHT = 1e9


def haversine_heuristic(G: nx.MultiDiGraph):
    def h(u, v):
        y1, x1 = G.nodes[u]["y"], G.nodes[u]["x"]
        y2, x2 = G.nodes[v]["y"], G.nodes[v]["x"]
        return ox.distance.great_circle(y1, x1, y2, x2)
    return h


def find_route(
    G: nx.MultiDiGraph,
    start_coords: tuple[float, float],
    end_coords: tuple[float, float],
) -> Optional[list[int]]:
    """
    start_coords / end_coords are (lng, lat). Returns list of node ids or None if unreachable.
    """
    start_lng, start_lat = start_coords
    end_lng, end_lat = end_coords

    orig_node = ox.distance.nearest_nodes(G, start_lng, start_lat)
    dest_node = ox.distance.nearest_nodes(G, end_lng, end_lat)

    try:
        path = nx.astar_path(
            G,
            orig_node,
            dest_node,
            heuristic=haversine_heuristic(G),
            weight="weight",
        )
    except nx.NetworkXNoPath:
        return None

    # Safety check: ensure no blocked edge made it through (shouldn't, given BLOCK_WEIGHT)
    for u, v in zip(path[:-1], path[1:]):
        edge_data = min(G[u][v].values(), key=lambda d: d.get("weight", 1))
        if edge_data.get("weight", 0) >= BLOCK_WEIGHT:
            return None

    return path


def route_length_km(G: nx.MultiDiGraph, path: list[int]) -> float:
    length_m = sum(
        min(G[u][v].values(), key=lambda d: d.get("length", 1))["length"]
        for u, v in zip(path[:-1], path[1:])
    )
    return length_m / 1000.0