// Demo region configuration.
// All coordinates are [longitude, latitude] (GeoJSON order), per architecture.md.

export type LngLat = [number, number];

// Demo start/destination (Sumas Prairie / Abbotsford, BC). Chosen so the route
// changes with each satellite flood scenario: south edge of Sumas Prairie ->
// north Abbotsford. Roads only exist inside the demo bbox
// (-122.32, 49.00, -122.10, 49.12), see backend/routing/download_graph.py.
export const START_COORDS: LngLat = [-122.219, 49.024];
export const END_COORDS: LngLat = [-122.2852, 49.0824];

export const MAP_CENTER: LngLat = [-122.235, 49.055];
export const MAP_ZOOM = 12;

// Satellite basemap (requires internet). If tiles fail to load, the map still
// renders over the background colour so data layers remain visible.
export const SATELLITE_TILES =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
export const SATELLITE_ATTRIBUTION =
  "Imagery © Esri, Maxar, Earthstar Geographics";

// Hidden placeholder layers that fix draw order regardless of which data
// loads first. Each data layer is inserted beneath its slot (bottom to top).
export const LAYER_SLOTS = {
  flood: "slot-flood",
  route: "slot-route",
  floodedRoads: "slot-flooded-roads",
  safeRoute: "slot-safe-route",
} as const;

// Shown in the map's title block. The imagery line is only shown when the app
// is running on the backend's satellite-derived data, not on mock files.
export const DEMO_PLACE = "Sumas Prairie, Abbotsford, BC";
export const IMAGERY_SOURCE = "Sentinel-2 MNDWI, Nov–Dec 2021";
