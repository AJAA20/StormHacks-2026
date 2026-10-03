// Data access layer. Components get data from here and never fetch directly,
// so mock files can be swapped for FastAPI responses in one place.

import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";

// Flood polygons in EPSG:4326, [longitude, latitude] (architecture.md §6).
export type FloodPolygons = FeatureCollection<Polygon | MultiPolygon>;

const MOCK_FLOOD_URL = "/mock/mock_flood.geojson";

export async function getFloodPolygons(): Promise<FloodPolygons> {
  const res = await fetch(MOCK_FLOOD_URL);
  if (!res.ok) {
    throw new Error(`Failed to load flood polygons (${res.status})`);
  }
  return res.json();
}
