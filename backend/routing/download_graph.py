"""One-off script: download OSM road network for the demo region and cache it to disk."""
import osmnx as ox
from pathlib import Path

# The demo graph now lives in the Abbotsford preset region folder (what graph_loader loads).
# New areas get their graph from backend/regions/builder.py.
GRAPH_DIR = Path(__file__).parent.parent / "data" / "regions" / "abbotsford-2021"
GRAPH_PATH = GRAPH_DIR / "graph.graphml"

# Demo region = Abbotsford / Sumas Prairie: the same bbox the Sentinel-2 flood
# polygons were computed for (Nov 2021 flood). osmnx v2 order: (west, south, east, north).
DEMO_BBOX = (-122.32, 49.00, -122.10, 49.12)

# Other candidate regions (not used by the demo)
DEMO_PLACES = {
    "burnaby": "Burnaby, British Columbia, Canada",
    "richmond": "Richmond, British Columbia, Canada",
    "surrey": "Surrey, British Columbia, Canada",
}


def download_demo_region(path: Path = GRAPH_PATH) -> None:
    """Download the demo bbox into the Abbotsford preset folder (what graph_loader loads)."""
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading road network for bbox: {DEMO_BBOX}")
    G = ox.graph_from_bbox(DEMO_BBOX, network_type="drive")
    ox.save_graphml(G, filepath=path)
    print(f"Saved graph to {path} ({len(G.nodes)} nodes, {len(G.edges)} edges)")


def download_and_cache(place: str, filename: str) -> None:
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    path = GRAPH_DIR / filename
    print(f"Downloading road network for: {place}")
    G = ox.graph_from_place(place, network_type="drive")
    ox.save_graphml(G, filepath=path)
    print(f"Saved graph to {path}")


if __name__ == "__main__":
    download_demo_region()
