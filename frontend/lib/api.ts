// Data access layer. Components get data from here and never fetch directly,
// so mock files can be swapped for FastAPI responses in one place.

import type {
  Feature,
  FeatureCollection,
  LineString,
  MultiPolygon,
  Polygon,
} from "geojson";

// Flood polygons in EPSG:4326, [longitude, latitude] (architecture.md §6).
export type FloodPolygons = FeatureCollection<Polygon | MultiPolygon>;

// A route as a single LineString Feature, matching `route_geojson` (§8).
export type RouteFeature = Feature<LineString>;

const MOCK_FLOOD_URL = "/mock/mock_flood.geojson";
const MOCK_ORIGINAL_ROUTE_URL = "/mock/mock_original_route.geojson";

export async function getFloodPolygons(): Promise<FloodPolygons> {
  const res = await fetch(MOCK_FLOOD_URL);
  if (!res.ok) {
    throw new Error(`Failed to load flood polygons (${res.status})`);
  }
  return res.json();
}

// Pre-flood route. Not in the §8 response yet; needs agreeing with Person 3.
export async function getOriginalRoute(): Promise<RouteFeature> {
  const res = await fetch(MOCK_ORIGINAL_ROUTE_URL);
  if (!res.ok) {
    throw new Error(`Failed to load original route (${res.status})`);
  }
  return res.json();
}
