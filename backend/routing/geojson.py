"""Convert a node-id path into route GeoJSON."""
import networkx as nx


def path_to_geojson(G: nx.MultiDiGraph, path: list[int]) -> dict:
    """LineString following each edge's road geometry (curves included), not just node-to-node."""
    coords = [[G.nodes[path[0]]["x"], G.nodes[path[0]]["y"]]]
    for u, v in zip(path[:-1], path[1:]):
        data = min(G[u][v].values(), key=lambda d: d.get("weight", d.get("length", 1)))
        if "geometry" in data:
            coords.extend([list(c) for c in data["geometry"].coords][1:])
        else:
            coords.append([G.nodes[v]["x"], G.nodes[v]["y"]])
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
        "properties": {},
    }
