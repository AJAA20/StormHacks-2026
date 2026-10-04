"use client";

import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import AnalysisSteps, { type Phase } from "./AnalysisSteps";
import FloodLayer from "./FloodLayer";
import FloodedRoadLayer from "./FloodedRoadLayer";
import LayerControls, { type LayerKey, type LayerVisibility } from "./LayerControls";
import OriginalRouteLayer from "./OriginalRouteLayer";
import SafeRouteLayer from "./SafeRouteLayer";
import ScenarioControls from "./ScenarioControls";
import StatusBanner from "./StatusBanner";
import StatusPanel from "./StatusPanel";
import { buildSteps, isRouteAffected, type AnalysisStep, type Reveal } from "@/lib/analysis";
import { getRoute, type RouteResponse, type Scenario } from "@/lib/api";
import { MAP_COLORS } from "@/lib/theme";
import styles from "./MapView.module.css";
import {
  type LngLat,
  END_COORDS,
  LAYER_SLOTS,
  MAP_CENTER,
  MAP_ZOOM,
  SATELLITE_ATTRIBUTION,
  SATELLITE_TILES,
  START_COORDS,
} from "@/lib/config";

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  // Set once the style has loaded, so data layers can be added safely.
  const [map, setMap] = useState<maplibregl.Map | null>(null);
  const [scenario, setScenario] = useState<Scenario>("severe");
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [visibility, setVisibility] = useState<LayerVisibility>({
    flood: true,
    floodedRoads: true,
    originalRoute: true,
    safeRoute: true,
  });

  // Request state. The previous route stays on screen while a new one loads.
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Bumped by Retry to re-run the request for the same scenario.
  const [attempt, setAttempt] = useState(0);

  // Demo sequence: "before" shows only the current route, "analysing" reveals
  // the loaded results step by step, "complete" shows everything.
  const [phase, setPhase] = useState<Phase>("before");
  const [steps, setSteps] = useState<AnalysisStep[]>([]);
  const [stepIndex, setStepIndex] = useState(0);

  const toggleLayer = (key: LayerKey) =>
    setVisibility((v) => ({ ...v, [key]: !v[key] }));

  const startRequest = () => {
    setLoading(true);
    setError(null);
  };

  const selectScenario = (next: Scenario) => {
    if (next === scenario) return;
    startRequest();
    setScenario(next);
  };

  const retry = () => {
    startRequest();
    setAttempt((n) => n + 1);
  };

  const runAnalysis = () => {
    if (!route) return;
    setSteps(buildSteps(route));
    setStepIndex(0);
    setPhase("analysing");
  };

  // Advance one step at a time; the last step completes the sequence.
  useEffect(() => {
    if (phase !== "analysing") return;
    const isLast = stepIndex === steps.length - 1;
    const timer = setTimeout(() => {
      if (isLast) setPhase("complete");
      else setStepIndex((i) => i + 1);
    }, steps[stepIndex].durationMs);
    return () => clearTimeout(timer);
  }, [phase, stepIndex, steps]);

  const reached = new Set(
    steps.slice(0, stepIndex + 1).flatMap((step) => (step.reveals ? [step.reveals] : [])),
  );
  const shows = (reveal: Reveal) =>
    phase === "complete" || (phase === "analysing" && reached.has(reveal));
  // After the sequence, follow the loaded data so scenario switches update instantly.
  const routeCompromised =
    route !== null && (phase === "complete" ? isRouteAffected(route) : shows("compromised"));

  useEffect(() => {
    let cancelled = false;
    getRoute({ start_coords: START_COORDS, end_coords: END_COORDS, scenario })
      .then((data) => {
        if (!cancelled) setRoute(data);
      })
      .catch((err: unknown) => {
        console.error(err);
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scenario, attempt]);

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      center: MAP_CENTER,
      zoom: MAP_ZOOM,
      style: {
        version: 8,
        sources: {
          satellite: {
            type: "raster",
            tiles: [SATELLITE_TILES],
            tileSize: 256,
            maxzoom: 19,
            attribution: SATELLITE_ATTRIBUTION,
          },
        },
        layers: [
          {
            id: "background",
            type: "background",
            paint: { "background-color": "#1b2430" },
          },
          { id: "satellite", type: "raster", source: "satellite" },
          // Draw-order slots: data layers are inserted beneath these.
          { id: LAYER_SLOTS.flood, type: "background", layout: { visibility: "none" } },
          { id: LAYER_SLOTS.route, type: "background", layout: { visibility: "none" } },
          { id: LAYER_SLOTS.floodedRoads, type: "background", layout: { visibility: "none" } },
          { id: LAYER_SLOTS.safeRoute, type: "background", layout: { visibility: "none" } },
        ],
      },
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

    addLabelledMarker(map, START_COORDS, MAP_COLORS.startMarker, "Start");
    addLabelledMarker(map, END_COORDS, MAP_COLORS.endMarker, "Evacuation point");

    map.on("load", () => setMap(map));

    return () => {
      setMap(null);
      map.remove();
    };
  }, []);

  return (
    <>
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />
      {map && route && (
        <>
          <FloodLayer
            map={map}
            data={route.flood_polygons_geojson}
            visible={visibility.flood && shows("flood")}
          />
          <OriginalRouteLayer
            map={map}
            data={route.original_route_geojson}
            visible={visibility.originalRoute}
            compromised={routeCompromised}
          />
          <FloodedRoadLayer
            map={map}
            data={route.flooded_roads_geojson}
            visible={visibility.floodedRoads && shows("floodedRoads")}
          />
          <SafeRouteLayer
            map={map}
            data={route.route_geojson}
            visible={visibility.safeRoute && shows("safeRoute")}
          />
        </>
      )}
      <StatusPanel
        scenario={scenario}
        data={route}
        showMetrics={phase === "complete"}
        legend={
          <LayerControls
            visibility={visibility}
            onToggle={toggleLayer}
            routeCompromised={routeCompromised}
          />
        }
      >
        <ScenarioControls
          value={scenario}
          onChange={selectScenario}
          disabled={loading || phase === "analysing"}
        />
        <AnalysisSteps
          phase={phase}
          steps={steps}
          current={stepIndex}
          canRun={route !== null && !loading}
          onRun={runAnalysis}
        />
      </StatusPanel>
      <StatusBanner loading={loading} error={error} onRetry={retry} />
    </>
  );
}

// A pin plus an always-visible label beside it, so start and destination
// are identifiable without clicking.
function addLabelledMarker(map: maplibregl.Map, at: LngLat, color: string, text: string) {
  new maplibregl.Marker({ color }).setLngLat(at).addTo(map);

  const label = document.createElement("div");
  label.className = styles.markerLabel;
  label.textContent = text;
  new maplibregl.Marker({ element: label, anchor: "left", offset: [14, -20] })
    .setLngLat(at)
    .addTo(map);
}
