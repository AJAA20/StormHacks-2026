"""Convert a node-id path into route GeoJSON."""
import networkx as nx


def path_to_geojson(G: nx.MultiDiGraph, path: list[int]) -> dict:
    coords = [[G.nodes[n]["x"], G.nodes[n]["y"]] for n in path]
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
        "properties": {},
    }