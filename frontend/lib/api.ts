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
// The backend may not send every field yet, so anything missing is null.
export type RouteResponse = {
  status: string | null;
  scenario: Scenario;
  route_found: boolean;
  start_coords: LngLat | null;
  end_coords: LngLat | null;
  distance_km: number | null;
  detour_added_km: number | null;
  flooded_edges: number | null;
  flooded_edges_avoided: number | null;
  route_status: string | null;
  route_geojson: RouteFeature | null;
  original_route_geojson: RouteFeature | null;
  flood_polygons_geojson: FloodPolygons | null;
  flooded_roads_geojson: FloodedRoads | null;
};

// Drawn by a layer whose data is null, so stale shapes are cleared.
export const EMPTY_COLLECTION: FeatureCollection = { type: "FeatureCollection", features: [] };

// Defaults to mock data; set NEXT_PUBLIC_USE_MOCK=false to call FastAPI.
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== "false";

// mock_route.json is the severe case (the file shared with Person 3).
const MOCK_ROUTE_URLS: Record<Scenario, string> = {
  low: "/mock/mock_route_low.json",
  moderate: "/mock/mock_route_moderate.json",
  severe: "/mock/mock_route.json",
};

export async function getRoute(request: RouteRequest): Promise<RouteResponse> {
  const res = USE_MOCK
    ? await fetch(MOCK_ROUTE_URLS[request.scenario])
    : await fetch("/api/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
  if (!res.ok) {
    throw new Error(`Failed to load route (${res.status})`);
  }
  const raw = await res.json();
  if (raw?.status === "error") {
    throw new Error(raw.message ?? "Backend returned an error");
  }
  return normalizeRoute(raw, request);
}

// Fill gaps in a possibly partial response so components can rely on its shape.
function normalizeRoute(raw: Record<string, unknown>, request: RouteRequest): RouteResponse {
  const route = geojson<RouteFeature>(raw.route_geojson);
  return {
    status: typeof raw.status === "string" ? raw.status : null,
    scenario: (raw.scenario as Scenario | undefined) ?? request.scenario,
    route_found: typeof raw.route_found === "boolean" ? raw.route_found : route !== null,
    start_coords: lngLat(raw.start_coords),
    end_coords: lngLat(raw.end_coords),
    distance_km: num(raw.distance_km),
    detour_added_km: num(raw.detour_added_km),
    flooded_edges: num(raw.flooded_edges),
    flooded_edges_avoided: num(raw.flooded_edges_avoided),
    route_status: typeof raw.route_status === "string" ? raw.route_status : null,
    route_geojson: route,
    original_route_geojson: geojson<RouteFeature>(raw.original_route_geojson),
    flood_polygons_geojson: geojson<FloodPolygons>(raw.flood_polygons_geojson),
    flooded_roads_geojson: geojson<FloodedRoads>(raw.flooded_roads_geojson),
  };
}

function num(v: unknown): number | null {
  return typeof v === "number" ? v : null;
}

function lngLat(v: unknown): LngLat | null {
  return Array.isArray(v) && v.length === 2 && v.every((n) => typeof n === "number")
    ? (v as LngLat)
    : null;
}

// Treats null, {} and other non-GeoJSON values as missing.
function geojson<T>(v: unknown): T | null {
  return v && typeof v === "object" && typeof (v as { type?: unknown }).type === "string"
    ? (v as T)
    : null;
}
