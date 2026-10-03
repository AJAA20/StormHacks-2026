// Data access layer. Components get data from here and never fetch directly,
// so mock files can be swapped for FastAPI responses in one place.

import type {
  Feature,
  FeatureCollection,
  LineString,
  MultiPolygon,
  Polygon,
} from "geojson";
import type { LngLat } from "./config";

// Flood polygons in EPSG:4326, [longitude, latitude] (architecture.md §6).
export type FloodPolygons = FeatureCollection<Polygon | MultiPolygon>;

// A route as a single LineString Feature, matching `route_geojson` (§8).
export type RouteFeature = Feature<LineString>;

// Road edges that intersect flood polygons (§7 road state FLOODED).
export type FloodedRoads = FeatureCollection<LineString>;

export type Scenario = "low" | "moderate" | "severe";

// Request body for POST /api/route (§8).
export type RouteRequest = {
  start_coords: LngLat;
  end_coords: LngLat;
  scenario: Scenario;
};

// Response from POST /api/route: §8 plus the fields proposed to Person 3
// (start/end_coords, original_route_geojson, flooded_roads_geojson, and
// flood_mask_geojson renamed to flood_polygons_geojson). Not yet agreed.
export type RouteResponse = {
  status: string;
  scenario: Scenario;
  route_found: boolean;
  start_coords: LngLat;
  end_coords: LngLat;
  distance_km: number;
  detour_added_km: number;
  flooded_edges: number;
  flooded_edges_avoided: number;
  route_status: string;
  route_geojson: RouteFeature;
  original_route_geojson: RouteFeature;
  flood_polygons_geojson: FloodPolygons;
  flooded_roads_geojson: FloodedRoads;
};

const MOCK_ROUTE_URL = "/mock/mock_route.json";

// Mock: ignores the request and returns the static response.
// Backend: POST `request` as JSON to /api/route instead.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export async function getRoute(request: RouteRequest): Promise<RouteResponse> {
  const res = await fetch(MOCK_ROUTE_URL);
  if (!res.ok) {
    throw new Error(`Failed to load route (${res.status})`);
  }
  return res.json();
}
