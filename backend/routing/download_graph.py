"""One-off script: download OSM road network for the demo region and cache it to disk."""
import osmnx as ox
from pathlib import Path

GRAPH_DIR = Path(__file__).parent.parent / "data" / "graphs"
GRAPH_PATH = GRAPH_DIR / "demo_region.graphml"

# Pick a small, demo-friendly region (adjust to your demo area)
DEMO_PLACES = { 
    "burnaby": "Burnaby, British Columbia, Canada",
    "richmond": "Richmond, British Columbia, Canada",
    "surrey": "Surrey, British Columbia, Canada",
}

def download_and_cache(place: str, filename: str) -> None:
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    path = GRAPH_DIR / filename
    print(f"Downloading road network for: {place}")
    G = ox.graph_from_place(place, network_type="drive")
    ox.save_graphml(G, filepath=path)
    print(f"Saved graph to {path}")

if __name__ == "__main__":
    for key, place in DEMO_PLACES.items():
        download_and_cache(place, f"{key}.graphml")
