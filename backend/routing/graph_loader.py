"""Load cached OSM graphs and expose edges as GeoDataFrame geometries."""
from pathlib import Path
import osmnx as ox
import geopandas as gpd
import networkx as nx

# Default = the Abbotsford preset region; other regions pass their own graph path.
GRAPH_PATH = Path(__file__).parent.parent / "data" / "regions" / "abbotsford-2021" / "graph.graphml"

_graphs: dict[Path, nx.MultiDiGraph] = {}
_edges: dict[int, gpd.GeoDataFrame] = {}


def load_graph(path: Path = GRAPH_PATH) -> nx.MultiDiGraph:
    """Load a cached graph from disk once per file and reuse it (module-level cache)."""
    path = Path(path)
    if path not in _graphs:
        _graphs[path] = ox.load_graphml(path)
    return _graphs[path]


def get_edges_gdf(G: nx.MultiDiGraph) -> gpd.GeoDataFrame:
    """Return road edges as a GeoDataFrame with LineString geometry (u, v, key index).

    Cached per graph: edge geometry never changes, only the weights we set on G.
    """
    if id(G) not in _edges:
        _, _edges[id(G)] = ox.graph_to_gdfs(G, nodes=True, edges=True)
    return _edges[id(G)]
