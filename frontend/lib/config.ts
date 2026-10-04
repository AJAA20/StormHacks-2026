// Demo region configuration.
// All coordinates are [longitude, latitude] (GeoJSON order), per architecture.md.

export type LngLat = [number, number];

// Start/destination for mock mode. With the backend, each region supplies its
// own defaults (region.json) and users can click the map to move them.
// South edge of Sumas Prairie -> north Abbotsford (Abbotsford preset).
export const START_COORDS: LngLat = [-122.219, 49.024];
export const END_COORDS: LngLat = [-122.2852, 49.0824];

export const MAP_CENTER: LngLat = [-122.235, 49.055];
export const MAP_ZOOM = 12;

// Side of the square analysed around a chosen location (matches backend AOI_KM).
export const AOI_KM = 12;

// Satellite basemap (requires internet). If tiles fail to load, the map still
// renders over the background colour so data layers remain visible.
export const SATELLITE_TILES =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
export const SATELLITE_ATTRIBUTION =
  "Imagery © Esri, Maxar, Earthstar Geographics";

// Hidden placeholder layers that fix draw order regardless of which data
// loads first. Each data layer is inserted beneath its slot (bottom to top).
export const LAYER_SLOTS = {
  overlay: "slot-overlay",
  areas: "slot-areas",
  flood: "slot-flood",
  route: "slot-route",
  floodedRoads: "slot-flooded-roads",
  safeRoute: "slot-safe-route",
} as const;
