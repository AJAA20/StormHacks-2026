# StormHacks-2026 — SatRelief

Satellite-aware evacuation routing: Sentinel-2 imagery → MNDWI flood detection → flood polygons →
OpenStreetMap road blocking → A* safe route → interactive map.

- **Latest available:** for any place (searched, or your browser location), the most recent usable Sentinel-2
  observation — with its real acquisition date — mapped for flooding, with a flood-aware route.
- **Historical:** the same for a chosen date; SatRelief uses the nearest usable observation and shows both dates.
- **Examples (instant, offline):** Abbotsford / Sumas Prairie, BC (Nov 2021) and Conselice, Emilia-Romagna, Italy (May 2023).

Satellite images are snapshots (Sentinel-2 revisits every few days), not a live feed. SatRelief is a
demonstration, not a certified emergency navigation system.

## Setup (once)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install
```

## Run the app (two terminals)

Terminal 1 — backend (repo root):
```bash
source .venv/bin/activate && uvicorn backend.main:app --reload
```

Terminal 2 — frontend (`frontend/`):
```bash
npm run dev
```

Open http://localhost:3000.

## Using it

1. **Latest available / Historical**: pick the mode at the top of the panel.
2. **Location**: search any place, or click *Use my location* (your browser asks for permission).
3. **Date** (historical only), then **Analyze flood conditions**. New areas take ~15–40 s (internet needed);
   repeats and the examples are instant.
4. The header says which view you are looking at (LATEST AVAILABLE / HISTORICAL), the satellite observation
   date/time, and for historical views the date you asked for.
5. **Route**: drag the start / destination markers or click *Move start* / *Move destination* and click the map.
   **Run analysis** steps through flood → flooded roads → compromised route → safe route.
6. **Flood impact** (in the results): SatRelief rates each observation by the area of new water Sentinel-2
   detected — under 0.5 km² *None*, 0.5–5 *Low*, 5–20 *Moderate*, over 20 *Severe*. It is SatRelief's own
   summary, not an official warning level or a water-depth measurement. Water is detected with the standard
   MNDWI > 0 threshold.

## Test

```bash
pytest -q                                # unit + API tests, offline (~3 s)
cd frontend && npm test                  # browser-geolocation handling (Node test runner)
SATRELIEF_NETWORK_TESTS=1 pytest -q      # also real Earth Search / OSM builds
python scripts/smoke_test.py             # end-to-end against the running backend, incl. a live analysis
python scripts/smoke_test.py --skip-live # same, offline (examples only)
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/flood-analysis` | `{mode: "latest"\|"historical", latitude, longitude, location_name, requested_date?}` → job |
| GET | `/api/flood-analysis/{job_id}` | Progress; when done: `region_id` and `details` (requested vs. observation date, note) |
| GET | `/api/regions` | Analysed areas (examples first) |
| GET | `/api/regions/{id}` / `/api/regions/{id}/overlay` | Area details / Sentinel-2 image (WebP) |
| POST | `/api/analyze` | `{name, bbox:[w,s,e,n], flood_dates:"YYYY-MM-DD/YYYY-MM-DD", preflood_dates?}` → job |
| GET | `/api/analyze/{job_id}` | Job progress: `status`, `stage`, `progress`, `error`, `region_id` |
| POST | `/api/route` | `{region_id, start_coords, end_coords, scenario}` → routes, flood polygons, flooded roads |
| GET | `/api/geocode?q=` / `/api/geocode/reverse?lat=&lon=` | Place search / name for coordinates (OpenStreetMap Nominatim) |

## Data layout

`backend/data/regions/<id>/` holds `region.json`, `graph.graphml` (roads), `flood/{low,moderate,severe}.geojson`
and `overlay.webp`. Examples are committed; areas analysed at runtime stay local (gitignored).
Rebuild an example: `python scripts/build_region.py --help`.

Contains modified Copernicus Sentinel data. Road data © OpenStreetMap contributors (ODbL).
Place search © OpenStreetMap Nominatim.
