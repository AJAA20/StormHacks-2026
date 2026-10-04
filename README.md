# StormHacks-2026 — SatRelief

Satellite-aware evacuation routing: Sentinel-2 imagery → MNDWI flood detection → flood polygons →
OpenStreetMap road blocking → A* safe route → interactive map.

- **Examples (instant, offline):** Abbotsford / Sumas Prairie, BC (Nov 2021) and Conselice, Emilia-Romagna, Italy (May 2023).
- **Analyze a new area:** search a place (or pan the map), pick the flood dates, and SatRelief finds the clearest
  Sentinel-2 image in the open archive, maps the water, downloads the roads and plans routes — about 15–40 s.

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

1. **Area**: pick an example from the dropdown. The dashed box is the analysed area; the image inside it is the
   real Sentinel-2 photo from the flood date.
2. **Route**: drag the blue (start) / green (destination) markers, or click *Move start* / *Move destination* and click the map.
3. **Run analysis**: steps through flood detected → flooded roads → route compromised → safe route.
4. **Low / Moderate / Severe**: the same satellite image thresholded more or less strictly (MNDWI 0.30 / 0.15 / 0.00).
5. **+ Analyze a new area**: search a place (or *Try an example*), frame the orange box (max 25 km), set the
   flood dates (2–4 weeks around the flood), *Analyze area*. When it finishes, click the map to place start and destination.

New areas need internet (Earth Search for Sentinel-2, OpenStreetMap for roads) and a mostly cloud-free image in
the chosen dates; otherwise you get a clear message (e.g. "too cloudy — widen the dates").

## Test

```bash
pytest -q                                # unit + API tests, offline (~3 s)
SATRELIEF_NETWORK_TESTS=1 pytest -q      # also real Earth Search / OSM builds
python scripts/smoke_test.py             # end-to-end against the running backend, incl. a live analysis
python scripts/smoke_test.py --skip-live # same, offline (examples only)
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/regions` | Analysed areas (examples first) |
| GET | `/api/regions/{id}` / `/api/regions/{id}/overlay` | Area details / Sentinel-2 image (WebP) |
| POST | `/api/analyze` | `{name, bbox:[w,s,e,n], flood_dates:"YYYY-MM-DD/YYYY-MM-DD", preflood_dates?}` → job |
| GET | `/api/analyze/{job_id}` | Job progress: `status`, `stage`, `progress`, `error`, `region_id` |
| POST | `/api/route` | `{region_id, start_coords, end_coords, scenario}` → routes, flood polygons, flooded roads |
| GET | `/api/geocode?q=` | Place search (OpenStreetMap Nominatim) |

## Data layout

`backend/data/regions/<id>/` holds `region.json`, `graph.graphml` (roads), `flood/{low,moderate,severe}.geojson`
and `overlay.webp`. Examples are committed; areas analysed at runtime stay local (gitignored).
Rebuild an example: `python scripts/build_region.py --help`.

Contains modified Copernicus Sentinel data. Road data © OpenStreetMap contributors (ODbL).
Place search © OpenStreetMap Nominatim.
