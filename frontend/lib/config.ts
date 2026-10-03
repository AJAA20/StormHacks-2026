// Demo region configuration.
// All coordinates are [longitude, latitude] (GeoJSON order), per architecture.md.

export type LngLat = [number, number];

// Placeholder start/destination taken from the POST /api/route example in
// docs/architecture.md (Sumas Prairie / Abbotsford, BC). Replace once the
// team settles on the final demo locations.
export const START_COORDS: LngLat = [-122.285, 49.102];
export const END_COORDS: LngLat = [-122.15, 49.12];

export const MAP_CENTER: LngLat = [-122.2175, 49.111];
export const MAP_ZOOM = 11.5;

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
} as const;
