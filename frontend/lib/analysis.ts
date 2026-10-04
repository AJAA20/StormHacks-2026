// Steps of the "Run analysis" demo sequence. Each step presents part of an
// already-loaded /api/route response; nothing here computes new results.
// The pacing is presentation only.

import type { RouteResponse } from "./api";

// What becomes visible when a step starts.
export type Reveal = "flood" | "floodedRoads" | "compromised" | "safeRoute";

export type AnalysisStep = {
  label: string;
  detail: string | null;
  reveals: Reveal | null;
  durationMs: number;
};

// True when the original route crosses flooded roads. Falls back to the
// detour, and assumes affected if the backend sends neither field.
export function isRouteAffected(r: RouteResponse): boolean {
  if (r.flooded_edges_avoided !== null) return r.flooded_edges_avoided > 0;
  if (r.detour_added_km !== null) return r.detour_added_km > 0;
  return true;
}

export function buildSteps(r: RouteResponse): AnalysisStep[] {
  const floodAreas = r.flood_polygons_geojson?.features.length ?? null;
  const affected = isRouteAffected(r);

  const steps: AnalysisStep[] = [
    { label: "Loading Sentinel-2 flood extent", detail: null, reveals: null, durationMs: 1400 },
    {
      label: "Flood detected",
      detail: floodDetail(r, floodAreas),
      reveals: "flood",
      durationMs: 1000,
    },
    {
      label: "Identifying affected roads",
      detail: r.flooded_edges === null ? null : `${plural(r.flooded_edges, "road segment")} flooded`,
      reveals: "floodedRoads",
      durationMs: 1000,
    },
  ];

  if (!affected) {
    steps.push(
      { label: "Primary route unaffected", detail: null, reveals: null, durationMs: 1000 },
      { label: "Original route remains safe", detail: distance(r), reveals: "safeRoute", durationMs: 0 },
    );
    return steps;
  }

  steps.push({
    label: "Primary route compromised",
    detail:
      r.flooded_edges_avoided === null
        ? null
        : `crosses ${plural(r.flooded_edges_avoided, "flooded segment")}`,
    reveals: "compromised",
    durationMs: 1000,
  });

  if (!r.route_found) {
    steps.push({ label: "No safe evacuation route found", detail: null, reveals: null, durationMs: 0 });
    return steps;
  }

  steps.push(
    { label: "Calculating safe evacuation route", detail: null, reveals: null, durationMs: 1200 },
    { label: "Evacuation route updated", detail: distance(r), reveals: "safeRoute", durationMs: 0 },
  );
  return steps;
}

// e.g. "166 flood areas · 27.6 km², severe impact"
function floodDetail(r: RouteResponse, floodAreas: number | null) {
  const parts = [];
  if (floodAreas !== null) parts.push(plural(floodAreas, "flood area"));
  if (r.flood_impact) {
    parts.push(`${r.flood_impact.new_water_km2.toFixed(1)} km², ${r.flood_impact.level} impact`);
  }
  return parts.length ? parts.join(" · ") : null;
}

function plural(n: number, noun: string) {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

function distance(r: RouteResponse) {
  if (r.distance_km === null) return null;
  const detour = r.detour_added_km ? `, +${r.detour_added_km.toFixed(1)} km detour` : "";
  return `${r.distance_km.toFixed(1)} km${detour}`;
}
