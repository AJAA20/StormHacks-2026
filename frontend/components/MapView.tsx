"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import AnalysisSteps, { type Phase } from "./AnalysisSteps";
import AnalyzeAreaPanel from "./AnalyzeAreaPanel";
import AreaBoxLayer from "./AreaBoxLayer";
import FloodLayer from "./FloodLayer";
import FloodedRoadLayer from "./FloodedRoadLayer";
import LayerControls, { type LayerKey, type LayerVisibility } from "./LayerControls";
import OriginalRouteLayer from "./OriginalRouteLayer";
import PointControls, { type PickMode } from "./PointControls";
import RegionSelector from "./RegionSelector";
import SafeRouteLayer from "./SafeRouteLayer";
import SatelliteOverlayLayer from "./SatelliteOverlayLayer";
import ScenarioControls from "./ScenarioControls";
import StatusBanner from "./StatusBanner";
import StatusPanel from "./StatusPanel";
import { buildSteps, isRouteAffected, type AnalysisStep, type Reveal } from "@/lib/analysis";
import {
  getRoute,
  listRegions,
  USE_MOCK,
  type BBox,
  type Region,
  type RouteResponse,
  type Scenario,
} from "@/lib/api";
import {
  LAYER_SLOTS,
  MAP_CENTER,
  MAP_ZOOM,
  MAX_AREA_KM,
  SATELLITE_ATTRIBUTION,
  SATELLITE_TILES,
  type LngLat,
} from "@/lib/config";
import { clampBox, contains, sizeKm } from "@/lib/geo";
import { MAP_COLORS } from "@/lib/theme";
import styles from "./MapView.module.css";

// Keep framed areas clear of the left control panel (280px + margins) on wide screens.
function fitPadding(map: maplibregl.Map) {
  const wide = map.getContainer().clientWidth > 760;
  return { top: 40, bottom: 40, right: 40, left: wide ? 330 : 40 };
}

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
    // Off by default: the 10 m image reads as a blurry box over the basemap.
    // Tick it in the legend to show the flood-date observation.
    satellite: false,
  });

  // Analysed areas (presets + user-analysed) and the one on screen.
  const [regions, setRegions] = useState<Region[]>([]);
  const [regionId, setRegionId] = useState<string | null>(null);
  const region = regions.find((r) => r.id === regionId) ?? null;

  // Route end points; users can click the map or drag the markers.
  const [start, setStart] = useState<LngLat | null>(null);
  const [end, setEnd] = useState<LngLat | null>(null);
  const [pickMode, setPickMode] = useState<PickMode>(null);

  // "Analyze a new area" form, and the area it would analyse (current view, capped).
  const [analyzing, setAnalyzing] = useState(false);
  const [areaBox, setAreaBox] = useState<BBox | null>(null);

  // UI errors (bad click, areas failed to load). Route errors come from the request below.
  const [error, setError] = useState<string | null>(null);
  // Bumped by Retry to re-run the last request.
  const [attempt, setAttempt] = useState(0);

  // Demo sequence: "before" shows only the current route, "analysing" reveals
  // the loaded results step by step, "complete" shows everything.
  const [phase, setPhase] = useState<Phase>("before");
  const [steps, setSteps] = useState<AnalysisStep[]>([]);
  const [stepIndex, setStepIndex] = useState(0);

  const toggleLayer = (key: LayerKey) =>
    setVisibility((v) => ({ ...v, [key]: !v[key] }));

  const selectScenario = (next: Scenario) => {
    if (next === scenario) return;
    setScenario(next);
  };

  const runAnalysis = () => {
    if (!route) return;
    setSteps(buildSteps(route));
    setStepIndex(0);
    setPhase("analysing");
  };

  // ---- regions -------------------------------------------------------------

  const showRegion = useCallback((next: Region) => {
    setRegionId(next.id);
    setStart(next.default_start);
    setEnd(next.default_end);
    setPickMode(next.default_start && next.default_end ? null : "start");
    setRoute(null);
    setPhase("before");
  }, []);

  const refreshRegions = useCallback(
    (selectId?: string) => {
      listRegions()
        .then((list) => {
          setRegions(list);
          const target = list.find((r) => r.id === selectId) ?? (selectId ? null : list[0]);
          if (target) showRegion(target);
        })
        .catch((err: unknown) => {
          console.error(err);
          setError(`Couldn't load areas: ${err instanceof Error ? err.message : String(err)}`);
        });
    },
    [showRegion],
  );

  useEffect(() => {
    refreshRegions();
  }, [refreshRegions]);

  const selectRegion = (id: string) => {
    const next = regions.find((r) => r.id === id);
    if (next) showRegion(next);
  };

  const retry = () => {
    setError(null);
    if (regions.length === 0) refreshRegions();
    else setAttempt((n) => n + 1);
  };

  // Frame the selected area (only when the area changes, not on every render).
  const regionKey = region?.id;
  useEffect(() => {
    if (map && region && !analyzing) {
      map.fitBounds(region.bbox, { padding: fitPadding(map), duration: 800 });
    }
  }, [map, regionKey, analyzing]); // eslint-disable-line react-hooks/exhaustive-deps

  const onAnalyzed = useCallback(
    (newRegionId: string) => {
      setAnalyzing(false);
      refreshRegions(newRegionId);
    },
    [refreshRegions],
  );

  // ---- route ---------------------------------------------------------------

  // Each distinct request has a key; it is loading until a result with that key
  // arrives. The previous route stays on screen meanwhile.
  const routeKey = regionId && start && end ? JSON.stringify([regionId, start, end, scenario, attempt]) : null;
  const [result, setResult] = useState<{ key: string; error: string | null } | null>(null);
  const loading = routeKey !== null && result?.key !== routeKey;
  const routeError = routeKey !== null && result?.key === routeKey ? result.error : null;

  useEffect(() => {
    if (!routeKey || !regionId || !start || !end) return;
    let cancelled = false;
    getRoute({ start_coords: start, end_coords: end, scenario, region_id: regionId })
      .then((data) => {
        if (cancelled) return;
        setRoute(data);
        setResult({ key: routeKey, error: null });
      })
      .catch((err: unknown) => {
        console.error(err);
        if (cancelled) return;
        setResult({
          key: routeKey,
          error: `Couldn't load evacuation route: ${err instanceof Error ? err.message : String(err)}`,
        });
      });
    return () => {
      cancelled = true;
    };
  }, [routeKey, regionId, start, end, scenario]);

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

  // ---- map + markers ---------------------------------------------------------

  // Map event handlers are bound once, so they read the latest state through refs.
  const pickRef = useRef<PickMode>(null);
  const regionRef = useRef<Region | null>(null);
  const endRef = useRef<LngLat | null>(null);
  useEffect(() => {
    pickRef.current = pickMode;
    regionRef.current = region;
    endRef.current = end;
  });

  const startMarker = useRef<maplibregl.Marker | null>(null);
  const endMarker = useRef<maplibregl.Marker | null>(null);

  // Returns false (and explains why) for points outside the analysed area.
  const placePoint = useCallback((which: "start" | "end", point: LngLat) => {
    const current = regionRef.current;
    if (current && !contains(current.bbox, point)) {
      setError("That point is outside the analysed area, where there is no road or flood data.");
      return false;
    }
    setError(null);
    if (which === "start") setStart(point);
    else setEnd(point);
    return true;
  }, []);

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
          { id: LAYER_SLOTS.overlay, type: "background", layout: { visibility: "none" } },
          { id: LAYER_SLOTS.areas, type: "background", layout: { visibility: "none" } },
          { id: LAYER_SLOTS.flood, type: "background", layout: { visibility: "none" } },
          { id: LAYER_SLOTS.route, type: "background", layout: { visibility: "none" } },
          { id: LAYER_SLOTS.floodedRoads, type: "background", layout: { visibility: "none" } },
          { id: LAYER_SLOTS.safeRoute, type: "background", layout: { visibility: "none" } },
        ],
      },
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

    // Draggable markers, added to the map once their point is set. The label is
    // part of the marker element, so it stays visible and moves with a drag.
    const makeMarker = (color: string, label: string, which: "start" | "end") => {
      const marker = new maplibregl.Marker({ color, draggable: true }).setLngLat(MAP_CENTER);
      const tag = document.createElement("span");
      tag.className = styles.markerLabel;
      tag.textContent = label;
      marker.getElement().appendChild(tag);
      marker.on("dragend", () => {
        const { lng, lat } = marker.getLngLat();
        placePoint(which, [lng, lat]);
      });
      return marker;
    };
    startMarker.current = makeMarker(MAP_COLORS.startMarker, "Start", "start");
    endMarker.current = makeMarker(MAP_COLORS.endMarker, "Evacuation point", "end");

    map.on("click", (e) => {
      const mode = pickRef.current;
      if (!mode) return;
      if (!placePoint(mode, [e.lngLat.lng, e.lngLat.lat])) return;
      // After the start, go straight on to the destination if it is still missing.
      setPickMode(mode === "start" && !endRef.current ? "end" : null);
    });

    map.on("load", () => setMap(map));

    return () => {
      setMap(null);
      map.remove();
    };
  }, [placePoint]);

  // Keep markers in sync with state (this also reverts a rejected drag).
  useEffect(() => {
    if (!map) return;
    const pairs: [maplibregl.Marker | null, LngLat | null][] = [
      [startMarker.current, start],
      [endMarker.current, end],
    ];
    for (const [marker, point] of pairs) {
      if (!marker) continue;
      if (point && !analyzing) marker.setLngLat(point).addTo(map);
      else marker.remove();
    }
  }, [map, start, end, analyzing, error]);

  // Crosshair while picking a point.
  useEffect(() => {
    if (map) map.getCanvas().style.cursor = pickMode ? "crosshair" : "";
  }, [map, pickMode]);

  // While the "Analyze a new area" form is open, the area is the visible map, capped.
  useEffect(() => {
    if (!map || !analyzing) return;
    const update = () => {
      // The part of the map not covered by the panel, minus the same margins fitBounds uses.
      const { clientWidth: w, clientHeight: h } = map.getContainer();
      const pad = fitPadding(map);
      const nw = map.unproject([pad.left, pad.top]);
      const se = map.unproject([w - pad.right, h - pad.bottom]);
      setAreaBox(clampBox([nw.lng, se.lat, se.lng, nw.lat], MAX_AREA_KM));
    };
    update();
    map.on("moveend", update);
    return () => {
      map.off("moveend", update);
      setAreaBox(null);
    };
  }, [map, analyzing]);

  const flyToBox = useCallback(
    (box: BBox) => map?.fitBounds(clampBox(box, MAX_AREA_KM), { padding: fitPadding(map), duration: 1000 }),
    [map],
  );

  const openAnalyze = () => {
    setPickMode(null);
    setAnalyzing(true);
  };

  const shown = !analyzing ? route : null;

  return (
    <>
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />
      {map && (
        <>
          <SatelliteOverlayLayer
            map={map}
            regionId={analyzing ? null : regionId}
            corners={analyzing ? null : (region?.overlay_corners ?? null)}
            visible={visibility.satellite}
          />
          <AreaBoxLayer
            map={map}
            id="analysis-area"
            box={areaBox}
            color={MAP_COLORS.analysisArea}
            fillOpacity={0.08}
          />
          <FloodLayer
            map={map}
            data={shown?.flood_polygons_geojson ?? null}
            visible={visibility.flood && shows("flood")}
          />
          <OriginalRouteLayer
            map={map}
            data={shown?.original_route_geojson ?? null}
            visible={visibility.originalRoute}
            compromised={routeCompromised}
          />
          <FloodedRoadLayer
            map={map}
            data={shown?.flooded_roads_geojson ?? null}
            visible={visibility.floodedRoads && shows("floodedRoads")}
          />
          <SafeRouteLayer
            map={map}
            data={shown?.route_geojson ?? null}
            visible={visibility.safeRoute && shows("safeRoute")}
          />
        </>
      )}
      <StatusPanel
        data={shown}
        scenario={scenario}
        showMetrics={phase === "complete"}
        legend={
          <LayerControls
            visibility={visibility}
            onToggle={toggleLayer}
            routeCompromised={routeCompromised}
          />
        }
      >
        {analyzing ? (
          <AnalyzeAreaPanel
            areaBox={areaBox}
            areaKm={areaBox ? sizeKm(areaBox) : null}
            onFlyTo={flyToBox}
            onCancel={() => setAnalyzing(false)}
            onDone={onAnalyzed}
          />
        ) : (
          <>
            <RegionSelector
              regions={regions}
              value={regionId}
              onChange={selectRegion}
              onAnalyzeNew={openAnalyze}
              canAnalyze={!USE_MOCK}
              disabled={phase === "analysing"}
            />
            <PointControls mode={pickMode} onModeChange={setPickMode} hasStart={start !== null} hasEnd={end !== null} />
            <ScenarioControls
              value={scenario}
              onChange={selectScenario}
              disabled={loading || phase === "analysing"}
            />
            {route && (
              <AnalysisSteps
                phase={phase}
                steps={phase === "complete" ? buildSteps(route) : steps}
                current={stepIndex}
                canRun={!loading}
                onRun={runAnalysis}
              />
            )}
          </>
        )}
      </StatusPanel>
      <StatusBanner loading={loading} error={error ?? routeError} onRetry={retry} />
    </>
  );
}
