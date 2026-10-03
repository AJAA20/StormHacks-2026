"""Load cached OSM graph and expose edges as GeoDataFrame geometries."""
from pathlib import Path
import osmnx as ox
import geopandas as gpd
import networkx as nx

GRAPH_PATH = Path(__file__).parent.parent / "data" / "graphs" / "demo_region.graphml"

_graph: nx.MultiDiGraph | None = None


def load_graph(path: Path = GRAPH_PATH) -> nx.MultiDiGraph:
    """Load the cached graph from disk once and reuse it (module-level cache)."""
    global _graph
    if _graph is None:
        _graph = ox.load_graphml(path)
    return _graph


def get_edges_gdf(G: nx.MultiDiGraph) -> gpd.GeoDataFrame:
    """Return road edges as a GeoDataFrame with LineString geometry (u, v, key index)."""
    _, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
    return edges