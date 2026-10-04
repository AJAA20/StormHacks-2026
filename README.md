# StormHacks-2026 — SatRelief

Satellite-aware evacuation routing: Sentinel-2 imagery → MNDWI flood detection → flood polygons →
OpenStreetMap road blocking → A* safe route → interactive map.
Demo: Abbotsford / Sumas Prairie flood, November 2021.

## Setup (once)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install
```

The demo data is committed (`backend/data/graphs/demo_region.graphml`, `backend/data/flood/*.geojson`),
so the app runs offline without the steps below.

## Run the app

start backend (repo root):
```
uvicorn backend.main:app --reload
```

start frontend against the real backend (`frontend/`):
```
NEXT_PUBLIC_USE_MOCK=false npm run dev
```
Open http://localhost:3000. Without `NEXT_PUBLIC_USE_MOCK=false` the UI uses the mock files in `frontend/public/mock`.

## Regenerate the data (optional, needs internet)

```bash
# Sentinel-2 from Earth Search (no API key) -> MNDWI -> flood polygons
python scripts/analyze_flood.py --bbox -122.32 49.00 -122.10 49.12 \
    --flood-dates 2021-11-14/2021-12-10 --preflood-dates 2021-08-01/2021-10-31
# One flood layer per UI scenario (low / moderate / severe)
python scripts/build_flood_scenarios.py
# OSM road network for the same bbox
python -m backend.routing.download_graph
```

## Tests

```bash
pytest -q                                   # offline
SATRELIEF_NETWORK_TESTS=1 pytest -q         # also hits Earth Search
```

Contains modified Copernicus Sentinel data 2021. Road data © OpenStreetMap contributors (ODbL).
