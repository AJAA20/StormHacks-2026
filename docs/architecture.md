# Architecture
# SatRelief Architecture

## 1. Project Overview

**SatRelief** is a satellite-aware emergency evacuation routing system.

The application uses Earth-observation satellite imagery to identify flooded areas, determine which roads are affected, and dynamically calculate an evacuation route that avoids flooded infrastructure.

The core system pipeline is:

```text
Sentinel-2 Satellite Imagery
        ↓
Multispectral Flood Detection
        ↓
Flood Raster Mask
        ↓
Flood Vector Polygons
        ↓
OpenStreetMap Road Network
        ↓
Flood / Road Intersection
        ↓
Road Graph Modification
        ↓
A* / Dijkstra Routing
        ↓
FastAPI Backend
        ↓
Interactive Web Map
```

The most important architectural principle is:

> Satellite data must directly affect routing decisions.

The satellite imagery is not simply a visual background. Flood regions derived from satellite observations determine which road edges are considered unsafe.

---

# 2. Primary Demo Scenario

SatRelief will initially support **one predefined historical flood region**.

The system should demonstrate the following sequence:

1. Load a geographic region.
2. Display satellite-derived flood areas.
3. Load the OpenStreetMap road network.
4. Calculate an initial evacuation route.
5. Apply a different flood scenario or flood classification.
6. Determine that one or more roads are flooded.
7. Mark those road edges as unavailable.
8. Recalculate the route.
9. Display the updated evacuation route.

The primary visual interaction is:

```text
Flood Area Changes
        ↓
Road Becomes Unsafe
        ↓
Previous Route Becomes Invalid
        ↓
Road Graph Updates
        ↓
New Route Appears
```

The initial system should optimize for a reliable hackathon demonstration rather than production-scale generality.

---

# 3. Technology Stack

## Backend / Scientific Processing

Language:

```text
Python
```

Primary libraries:

```text
NumPy
Rasterio
GeoPandas
Shapely
PyProj
OpenCV / scikit-image
OSMnx
NetworkX
FastAPI
```

---

## Frontend

Preferred stack:

```text
Next.js
React
TypeScript
```

Mapping library:

```text
MapLibre GL JS
```

Mapbox GL JS or Leaflet may be substituted if implementation speed is significantly better.

---

## Data Sources

### Satellite Data

Primary Earth-observation source:

```text
Sentinel-2
```

Important bands:

```text
B3  = Green
B11 = Short-Wave Infrared (SWIR)
```

These bands are used to calculate MNDWI.

---

### Road Network

Road data comes from:

```text
OpenStreetMap
```

and is downloaded / processed through:

```text
OSMnx
```

The road graph should be cached locally as GraphML before the final demo.

---

# 4. System Components

SatRelief is divided into four major technical modules.

```text
┌──────────────────────────────┐
│ 1. Satellite Processing      │
└──────────────┬───────────────┘
               ↓
        flood_mask.tif
               ↓
┌──────────────────────────────┐
│ 2. GIS Processing            │
└──────────────┬───────────────┘
               ↓
    flood_polygons.geojson
               ↓
┌──────────────────────────────┐
│ 3. Routing + Backend API     │
└──────────────┬───────────────┘
               ↓
       JSON / GeoJSON API
               ↓
┌──────────────────────────────┐
│ 4. Interactive Frontend      │
└──────────────────────────────┘
```

Each component must be independently testable.

---

# 5. Component 1 — Satellite Processing

## Responsibility

Convert Sentinel-2 multispectral imagery into a georeferenced binary flood / water raster.

This component performs the main Earth-observation image-processing work.

---

## Inputs

Sentinel-2 bands:

```text
B3  — Green
B11 — SWIR
```

---

## Processing

### Step 1 — Load Bands

Load B3 and B11 using Rasterio.

Inspect and preserve:

```text
CRS
Affine transform
Width
Height
Resolution
NoData
```

---

### Step 2 — Align Bands

Sentinel-2 bands may have different spatial resolutions.

Before performing pixel-wise calculations:

```text
B3[x, y]
```

must represent the same geographic location as:

```text
B11[x, y]
```

Resampling should be performed where necessary.

---

### Step 3 — Calculate MNDWI

Use:

```text
MNDWI = (Green - SWIR) / (Green + SWIR)
```

Equivalent:

```python
mndwi = (green - swir) / (green + swir)
```

The implementation must safely handle:

```text
division by zero
NaN values
NoData pixels
invalid values
```

---

### Step 4 — Threshold

Generate a binary raster:

```text
1 = water / flooded
0 = not flooded
```

Conceptually:

```python
water_mask = mndwi > threshold
```

The threshold must remain configurable.

---

### Step 5 — Optional Cleanup

If required, apply simple image-processing cleanup:

```text
morphological opening
morphological closing
small-component removal
```

Avoid adding unnecessary ML models during the MVP.

---

## Output

Primary output:

```text
data/processed/flood_mask.tif
```

Optional debugging output:

```text
data/processed/mndwi.tif
```

`flood_mask.tif` must preserve valid geospatial metadata.

---

# 6. Component 2 — GIS / Flood Geometry Processing

## Responsibility

Convert the georeferenced flood raster into clean geographic vector polygons.

This module is the bridge between satellite image processing and road-network routing.

---

## Input

```text
data/processed/flood_mask.tif
```

---

## Processing

### Step 1 — Raster Vectorization

Use:

```python
rasterio.features.shapes
```

to convert connected flooded raster cells into vector geometries.

Convert geometries into Shapely polygons.

---

### Step 2 — Geometry Cleanup

Possible processing includes:

```text
remove tiny regions
repair invalid geometry
merge overlapping areas
simplify overly complex boundaries
```

Possible Shapely operations:

```python
make_valid()
buffer(0)
unary_union()
simplify()
```

Geometry simplification must preserve topology where practical.

---

### Step 3 — CRS Handling

The component must explicitly track:

```text
Source raster CRS
Processing CRS
Output CRS
```

Physical distance / area operations should not be performed directly in latitude / longitude degrees.

Projected coordinates should be used where physical measurement matters.

---

### Step 4 — GeoJSON Conversion

The final data passed between backend modules and the frontend should use:

```text
EPSG:4326
```

GeoJSON coordinate order:

```text
[longitude, latitude]
```

NOT:

```text
[latitude, longitude]
```

---

## Output

```text
data/processed/flood_polygons.geojson
```

Expected structure:

```json
{
  "type": "FeatureCollection",
  "features": []
}
```

Flood polygons should contain only minimal useful metadata.

Example:

```json
{
  "flooded": true,
  "source": "sentinel-2"
}
```

---

# 7. Component 3 — Road Network, Routing & Backend API

## Responsibility

Use flood polygons to determine which OpenStreetMap roads are unsafe and calculate evacuation routes that avoid them.

This module also exposes routing results to the frontend through FastAPI.

---

## Inputs

```text
data/processed/flood_polygons.geojson
```

and:

```text
OpenStreetMap road network
```

---

## Road Graph

Use OSMnx to obtain the road network for the selected demo region.

The graph should be cached before judging.

Example:

```text
data/graphs/demo_region.graphml
```

This avoids depending on OpenStreetMap network availability during the final demo.

---

## Flood / Road Intersection

Road edges must be represented using geographic LineString geometry.

For each road edge:

```python
road_geometry.intersects(flood_geometry)
```

determines whether the road overlaps a flooded region.

---

## Road States

MVP states:

```text
SAFE
FLOODED
```

Safe road:

```text
weight = road length
```

Flooded road:

```text
unavailable for routing
```

Do not initially implement a complicated flood-risk scoring system.

---

## Routing

Use:

```text
A*
```

or:

```text
Dijkstra
```

to calculate the shortest available safe route.

The calculated route must never contain an edge marked as flooded.

---

## Stretch Goal — Risk-Aware Routing

Later, road cost may become:

```text
cost(edge)
=
distance(edge)
+
λ × floodRisk(edge)
```

This is not required for the MVP.

---

## Route Output

Routes must be converted from NetworkX nodes into a GeoJSON LineString.

Example:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "LineString",
    "coordinates": []
  }
}
```

---

# 8. FastAPI Interface

The routing system is exposed to the frontend through FastAPI.

Initial route endpoint:

```text
POST /api/route
```

Example request:

```json
{
  "start_coords": [-122.285, 49.102],
  "end_coords": [-122.150, 49.120],
  "scenario": "severe"
}
```

All geographic coordinates sent through the API use:

```text
[longitude, latitude]
```

---

## Example Response

```json
{
  "status": "success",

  "scenario": "severe",

  "route_found": true,

  "distance_km": 12.45,

  "detour_added_km": 2.7,

  "flooded_edges": 18,

  "flooded_edges_avoided": 5,

  "route_status": "safe",

  "route_geojson": {
    "type": "Feature",
    "geometry": {
      "type": "LineString",
      "coordinates": []
    }
  },

  "flood_mask_geojson": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

---

# 8b. Regions and Exploration Modes

SatRelief is no longer limited to one predefined region. Every analysed area is a **region**
(`backend/data/regions/<id>/`: `region.json`, `graph.graphml`, `flood/{low,moderate,severe}.geojson`,
`overlay.webp`). Two examples are committed (Abbotsford 2021, Emilia-Romagna 2023); others are
built on demand from the Sentinel-2 archive (Earth Search STAC) and OpenStreetMap, and cached.

## Two user-facing modes, one pipeline

```text
          Search location  /  Use my location (browser, on click only)
                         ↓
                 Selected location (lat, lon)
            ┌────────────┴────────────┐
      Latest available            Historical (date)
   newest usable image         usable image nearest the date
            └────────────┬────────────┘
             Sentinel-2 observation (real acquisition date/time)
                         ↓
   MNDWI → flood polygons → affected roads → graph update → A* route   (shared code)
```

The modes differ **only** in how the observation is chosen
(`backend/regions/observations.py`, the FloodDataProvider):

| Mode | Selection | Window |
|---|---|---|
| `latest` | newest image ≥ 40% cloud-free over the area | last 120 days |
| `historical` | image ≥ 40% cloud-free closest to the requested date | ±21 days |

Rules:

* Satellite imagery is a snapshot, never "live". The UI always shows the real acquisition date/time (UTC).
* A historical request shows **both** the requested date and the actual observation date.
* No usable image → an error. Another place's or another time's data is never substituted.
  If the archive is unreachable, only a cached analysis of the same area and period may be shown, with a note.
* The area is a 12 km square around the point, or a committed example's area if the point lies inside it.
* The user's browser location is only requested after clicking "Use my location".

## API

```text
POST /api/flood-analysis   {mode, latitude, longitude, location_name, requested_date?}  → job
GET  /api/flood-analysis/{job_id}   → {status, stage, progress, error, region_id,
                                       details: {mode, requested_date, observation_date, location, note}}
GET  /api/regions[/{id}[/overlay]]  → region metadata incl. flood_scene {date, datetime, aoi_clear_pct}
POST /api/route                     → as §8, plus "region_id"
GET  /api/geocode?q=  ·  GET /api/geocode/reverse?lat=&lon=   (OpenStreetMap Nominatim proxy)
POST /api/analyze  {name, bbox, flood_dates}  → job   (lower-level: analyse an explicit box + date range)
```

---

# 9. Component 4 — Frontend / Interactive Map

## Responsibility

Provide the user-facing visualization for the entire SatRelief system.

The frontend should make the relationship between flooding and routing immediately understandable.

---

## Required Map Layers

### Flood Layer

```text
Blue / semi-transparent
```

Source:

```text
flood_polygons.geojson
```

---

### Flooded Road Layer

```text
Red
```

Shows roads classified as unsafe.

---

### Previous Route

```text
Grey or red dashed line
```

Represents the route before conditions changed.

---

### Safe Route

```text
Green
```

Represents the current calculated evacuation route.

---

## Controls

Initial scenario controls:

```text
Low
Moderate
Severe
```

These should be described as flood scenarios unless the system is actually modeling physical water depth.

---

## Route Metrics

Display:

```text
Route Status
Route Distance
Detour Added
Flooded Roads
Flooded Roads Avoided
```

Example:

```text
ROUTE STATUS
SAFE

DISTANCE
12.4 km

DETOUR ADDED
+2.3 km

FLOODED ROADS
18

ROADS AVOIDED
5
```

---

# 10. Shared Data Contracts

The four components communicate through explicitly defined interfaces.

## Component 1 → Component 2

```text
flood_mask.tif
```

Requirements:

```text
georeferenced
valid CRS
valid affine transform
binary flood classification
```

---

## Component 2 → Component 3

```text
flood_polygons.geojson
```

Requirements:

```text
valid GeoJSON FeatureCollection
valid Polygon / MultiPolygon geometry
EPSG:4326
[longitude, latitude]
```

---

## Component 3 → Component 4

Communication:

```text
REST API
```

Payload:

```text
JSON + GeoJSON
```

The frontend must not depend directly on Python objects, Shapely geometry, GeoDataFrames, or NetworkX structures.

---

# 11. Parallel Development Strategy

No component should initially depend on another teammate finishing their work.

Each component must support mock data.

---

## Satellite Component

Works against:

```text
real Sentinel-2 imagery
```

---

## GIS Component

Initially works against:

```text
data/mock/mock_flood_mask.tif
```

Later replace with:

```text
data/processed/flood_mask.tif
```

No GIS code should need to change.

---

## Routing Component

Initially works against:

```text
data/mock/mock_flood_polygons.geojson
```

Later replace with:

```text
data/processed/flood_polygons.geojson
```

---

## Frontend

Initially works against:

```text
mock_route.json
mock_flood.geojson
```

Later replace mock responses with the FastAPI endpoints.

---

# 12. Integration Sequence

Integration should happen incrementally.

## Phase 1

```text
Satellite
    ↓
GIS
```

Success condition:

```text
Real Sentinel imagery
→ real flood GeoJSON
```

Verify that polygons appear in the correct geographic location.

---

## Phase 2

```text
GIS
    ↓
Routing
```

Success condition:

```text
Real satellite-derived flood polygon
→ real OSM road marked flooded
```

---

## Phase 3

```text
Routing
    ↓
FastAPI
    ↓
Frontend
```

Success condition:

```text
Backend route
→ rendered correctly on interactive map
```

---

## Phase 4

Full pipeline:

```text
Sentinel-2
    ↓
MNDWI
    ↓
Flood Mask
    ↓
Flood Polygons
    ↓
Flooded Roads
    ↓
Graph Modification
    ↓
A*
    ↓
FastAPI
    ↓
Web Map
```

---

# 13. Repository Structure

Recommended project structure:

```text
satrelief/
│
├── backend/
│   ├── main.py
│   │
│   ├── satellite/
│   │   ├── __init__.py
│   │   ├── sentinel_loader.py
│   │   ├── resample.py
│   │   ├── mndwi.py
│   │   └── flood_mask.py
│   │
│   ├── gis/
│   │   ├── __init__.py
│   │   ├── vectorize.py
│   │   ├── geometry_cleaner.py
│   │   ├── crs_utils.py
│   │   └── geojson_export.py
│   │
│   ├── routing/
│   │   ├── __init__.py
│   │   ├── graph_loader.py
│   │   ├── flood_intersection.py
│   │   ├── router.py
│   │   └── geojson.py
│   │
│   └── api/
│       ├── __init__.py
│       └── routes.py
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── public/
│
├── data/
│   ├── raw/
│   │   └── sentinel/
│   ├── processed/
│   ├── graphs/
│   ├── mock/
│   └── samples/
│
├── scripts/
│
├── tests/
│
├── architecture.md
├── README.md
├── requirements.txt
├── .env.example
└── .gitignore
```

---

# 14. Module Ownership

For the current four-person team:

```text
Person 1
Satellite processing
backend/satellite/

Person 2
GIS / flood geometry
backend/gis/

Person 3
Road graph, routing and FastAPI
backend/routing/
backend/api/
backend/main.py

Person 4
Frontend
frontend/
```

Team members should avoid unnecessarily modifying folders owned by other modules.

---

# 15. Git Branches

Recommended feature branches:

```text
feature/satellite
feature/gis
feature/routing-api
feature/frontend
```

Integration branch:

```text
develop
```

Stable demo branch:

```text
main
```

Typical flow:

```text
feature/*
    ↓
develop
    ↓
integration testing
    ↓
main
```

---

# 16. MVP Definition

SatRelief's MVP is complete when all of the following work:

1. A real Sentinel-2 scene can be loaded.
2. B3 and B11 are processed.
3. MNDWI is calculated.
4. A binary flood mask is generated.
5. Flood pixels are converted into geographic polygons.
6. Real OpenStreetMap roads are loaded.
7. Roads intersecting flood polygons are identified.
8. Flooded road edges are unavailable to routing.
9. A* or Dijkstra calculates an alternate route.
10. Flood polygons appear on the map.
11. The route appears on the map.
12. A scenario change causes the route to change.

Anything beyond this is considered a stretch goal.

---

# 17. Stretch Goals

Only add these after the MVP is reliable:

```text
Low / Moderate / Severe scenarios
old vs new route visualization
route statistics
nearest reachable shelter
ElevenLabs warning
before / after satellite comparison
animations
additional regions
risk-weighted routing
```

---

# 18. Non-Goals

The hackathon version is NOT intended to provide:

```text
nationwide routing
arbitrary geographic regions
production flood forecasting
real-time satellite video
live disaster-response guarantees
user accounts
authentication
production databases
custom deep-learning flood models
multiple satellite systems
production infrastructure
```

The project prioritizes one reliable demonstration scenario.

---

# 19. Offline / Demo Reliability

The final demo must not depend on external services for core functionality.

Cache locally:

```text
Sentinel imagery
flood_mask.tif
flood_polygons.geojson
OSM road graph
mock API responses
```

The following services may be unavailable during judging without breaking the core demo:

```text
Sentinel download service
OpenStreetMap download API
ElevenLabs
```

Earth-observation processing should operate on predownloaded Sentinel data during the final demonstration.

---

# 20. Optional ElevenLabs Integration

Voice functionality is not part of the core architecture.

If implemented:

```text
Route becomes invalid
        ↓
Backend generates warning text
        ↓
ElevenLabs generates speech
        ↓
Frontend plays warning
```

Example message:

```text
Warning. The previous evacuation route crosses a flooded roadway.
A safer route has been calculated.
```

This must remain optional.

---

# 21. Core Engineering Rules

### Rule 1 — Preserve geospatial metadata

Raster CRS and affine transforms must never be discarded during processing.

### Rule 2 — Never silently guess a missing CRS

Missing CRS should result in a clear error.

### Rule 3 — GeoJSON uses longitude first

```text
[longitude, latitude]
```

### Rule 4 — Use projected coordinates for physical measurements

Do not calculate meaningful area or distance directly in degrees.

### Rule 5 — Components communicate through files or APIs

Avoid tight coupling between modules.

### Rule 6 — Mock data must be supported

Every developer should be able to work without waiting for another component.

### Rule 7 — Cache external data

The final demonstration should not depend on remote services.

### Rule 8 — Reliability over feature count

If a new feature threatens the core pipeline, do not add it.

---

# 22. Core System Invariant

Any future feature or architectural decision should preserve the central SatRelief relationship:

```text
SATELLITE OBSERVATION
        ↓
FLOOD DETECTION
        ↓
GEOGRAPHIC FLOOD GEOMETRY
        ↓
ROAD NETWORK IMPACT
        ↓
GRAPH MODIFICATION
        ↓
EVACUATION REROUTING
```

If a feature does not strengthen this pipeline or the user's ability to understand it, it is secondary to the MVP.