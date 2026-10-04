// Data access layer. Components get data from here and never fetch directly,
// so mock files can be swapped for FastAPI responses in one place.

import type {
  Feature,
  FeatureCollection,
  LineString,
  MultiPolygon,
  Polygon,
} from "geojson";
import { END_COORDS, START_COORDS, type LngLat } from "./config";

// Flood polygons in EPSG:4326, [longitude, latitude] (architecture.md §6).
export type FloodPolygons = FeatureCollection<Polygon | MultiPolygon>;

// A route as a single LineString Feature, matching `route_geojson` (§8).
export type RouteFeature = Feature<LineString>;

// SatRelief's rating of the observed flood, from the area of new water (backend/routing/impact.py).
export type ImpactLevel = "none" | "low" | "moderate" | "severe";
export type FloodImpact = {
  level: ImpactLevel;
  new_water_km2: number;
  flooded_roads: number;
  basis: string;
};

// Road edges that intersect flood polygons (§7 road state FLOODED).
export type FloodedRoads = FeatureCollection<LineString>;

// Water-detection level sent to the backend. The app always uses the standard one
// ("severe" = MNDWI > 0.0); the impact rating, not the user, says how bad a flood is.
export type Scenario = "low" | "moderate" | "severe";
export const DETECTION_LEVEL: Scenario = "severe";

// [west, south, east, north] in degrees.
export type BBox = [number, number, number, number];

// Request body for POST /api/route (§8).
export type RouteRequest = {
  start_coords: LngLat;
  end_coords: LngLat;
  scenario: Scenario;
  // Analysed area to route in (GET /api/regions).
  region_id: string;
};

// A real Sentinel-2 acquisition: date/time are when the satellite took the image (UTC).
export type SceneInfo = {
  id: string;
  date: string;
  datetime?: string | null;
  aoi_clear_pct: number;
  mission?: string;
};
export type ScenarioStats = { threshold: number; polygons: number; area_km2: number };

// An analysed area: a preset (e.g. Abbotsford) or one a user asked for.
export type Region = {
  id: string;
  name: string;
  bbox: BBox;
  center: LngLat;
  preset: boolean;
  flood_dates: string;
  preflood_dates: string | null;
  flood_scene: SceneInfo | null;
  preflood_scene: SceneInfo | null;
  scenarios: Record<Scenario, ScenarioStats> | null;
  // Corners of the Sentinel-2 overlay image: TL, TR, BR, BL.
  overlay_corners: [LngLat, LngLat, LngLat, LngLat] | null;
  default_start: LngLat | null;
  default_end: LngLat | null;
  warnings: string[] | null;
  road_edges: number | null;
  source?: string | null;
};

// Latest available observation vs. a chosen historical date (architecture.md §8b).
export type ExplorationMode = "latest" | "historical";

export type FloodAnalysisRequest = {
  mode: ExplorationMode;
  latitude: number;
  longitude: number;
  location_name: string;
  // Historical mode only, YYYY-MM-DD.
  requested_date?: string;
};

// Facts about one analysis request, returned with the finished job.
export type AnalysisDetails = {
  region_id: string;
  mode?: ExplorationMode;
  requested_date?: string | null;
  observation_date?: string;
  location?: { name: string; latitude: number; longitude: number };
  note?: string | null;
};

// Background analysis of a new area (POST /api/analyze, then poll).
export type Job = {
  id: string;
  region_id: string | null;
  name: string;
  status: "queued" | "running" | "done" | "error";
  stage: string;
  progress: number;
  error: string | null;
  details: AnalysisDetails | null;
};

// Place search result (GET /api/geocode).
export type Place = { name: string; center: LngLat; bbox: BBox };

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
  flood_impact: FloodImpact | null;
};

// Drawn by a layer whose data is null, so stale shapes are cleared.
export const EMPTY_COLLECTION: FeatureCollection = { type: "FeatureCollection", features: [] };

// Calls the FastAPI backend by default; set NEXT_PUBLIC_USE_MOCK=true for the
// static files in public/mock (no backend needed, but no new-area analysis).
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

const BACKEND_DOWN = "Can't reach the SatRelief backend. Is it running on port 8000?";

// fetch + JSON with readable errors: FastAPI's {"detail": "..."} becomes the message.
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new Error(BACKEND_DOWN);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    if (typeof body?.detail === "string") throw new Error(body.detail);
    // The Next.js proxy answers 500 with no JSON when the backend is not running.
    throw new Error(res.status >= 500 ? BACKEND_DOWN : `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

const post = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

// Stand-in region for mock mode, matching the mock route files (Abbotsford).
const MOCK_REGION: Region = {
  id: "mock",
  name: "Abbotsford / Sumas Prairie, BC (mock data)",
  bbox: [-122.32, 49.0, -122.1, 49.12],
  center: [-122.21, 49.06],
  preset: true,
  flood_dates: "2021-11-14/2021-12-10",
  preflood_dates: null,
  flood_scene: null,
  preflood_scene: null,
  scenarios: null,
  overlay_corners: null,
  default_start: START_COORDS,
  default_end: END_COORDS,
  warnings: null,
  road_edges: null,
};

export async function listRegions(): Promise<Region[]> {
  return USE_MOCK ? [MOCK_REGION] : request<Region[]>("/api/regions");
}

export function overlayUrl(regionId: string): string {
  return `/api/regions/${encodeURIComponent(regionId)}/overlay`;
}

export function startFloodAnalysis(body: FloodAnalysisRequest): Promise<Job> {
  return request<Job>("/api/flood-analysis", post(body));
}

export function getAnalysisJob(jobId: string): Promise<Job> {
  return request<Job>(`/api/flood-analysis/${encodeURIComponent(jobId)}`);
}

// Geocoding endpoints: use lib/location.ts rather than calling these directly.
export function searchPlaces(query: string): Promise<Place[]> {
  return request<Place[]>(`/api/geocode?q=${encodeURIComponent(query)}`);
}

export async function reverseGeocodeApi(latitude: number, longitude: number): Promise<string | null> {
  const res = await request<{ name: string | null }>(`/api/geocode/reverse?lat=${latitude}&lon=${longitude}`);
  return res.name;
}

// mock_route.json is the severe case (the file shared with Person 3).
const MOCK_ROUTE_URLS: Record<Scenario, string> = {
  low: "/mock/mock_route_low.json",
  moderate: "/mock/mock_route_moderate.json",
  severe: "/mock/mock_route.json",
};

export async function getRoute(body: RouteRequest): Promise<RouteResponse> {
  const raw = USE_MOCK
    ? await request<Record<string, unknown>>(MOCK_ROUTE_URLS[body.scenario])
    : await request<Record<string, unknown>>("/api/route", post(body));
  if (raw?.status === "error") {
    throw new Error(typeof raw.message === "string" ? raw.message : "Backend returned an error");
  }
  return normalizeRoute(raw, body);
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
    flood_impact: impact(raw.flood_impact),
  };
}

function impact(v: unknown): FloodImpact | null {
  const i = v as Partial<FloodImpact> | null;
  return i && typeof i.level === "string" && typeof i.new_water_km2 === "number" ? (i as FloodImpact) : null;
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
