"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import AnalysisSteps, { type Phase } from "./AnalysisSteps";
import AreaBoxLayer from "./AreaBoxLayer";
import ExplorePanel from "./ExplorePanel";
import FloodLayer from "./FloodLayer";
import FloodedRoadLayer from "./FloodedRoadLayer";
import FloodViewHeader, { type FloodView } from "./FloodViewHeader";
import LayerControls, { type LayerKey, type LayerVisibility } from "./LayerControls";
import OriginalRouteLayer from "./OriginalRouteLayer";
import PointControls, { type PickMode } from "./PointControls";
import SafeRouteLayer from "./SafeRouteLayer";
import SatelliteOverlayLayer from "./SatelliteOverlayLayer";
import StatusBanner from "./StatusBanner";
import StatusPanel from "./StatusPanel";
import { buildSteps, isRouteAffected, type AnalysisStep, type Reveal } from "@/lib/analysis";
import {
  DETECTION_LEVEL,
  getRoute,
  listRegions,
  USE_MOCK,
  type BBox,
  type ExplorationMode,
  type Job,
  type Region,
  type RouteResponse,
} from "@/lib/api";
import {
  LAYER_SLOTS,
  MAP_CENTER,
  AOI_KM,
  MAP_ZOOM,
  SATELLITE_ATTRIBUTION,
  SATELLITE_TILES,
  type LngLat,
} from "@/lib/config";
import { boxAround, contains } from "@/lib/geo";
import { shortName, type SelectedLocation } from "@/lib/location";
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

  // Exploration inputs: mode, where (searched or device location) and, for history, when.
  const [mode, setMode] = useState<ExplorationMode>("latest");
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation | null>(null);
  const [requestedDate, setRequestedDate] = useState("");
  // What the map currently shows (mode, place, real observation date).
  const [view, setView] = useState<FloodView | null>(null);
  // Orange preview of the area a new analysis will cover.
  const [previewBox, setPreviewBox] = useState<BBox | null>(null);

  // Analysed areas (presets + user-analysed) and the one on screen.
  const [regions, setRegions] = useState<Region[]>([]);
  const [regionId, setRegionId] = useState<string | null>(null);
  const region = regions.find((r) => r.id === regionId) ?? null;

  // Route end points; users can click the map or drag the markers.
  const [start, setStart] = useState<LngLat | null>(null);
  const [end, setEnd] = useState<LngLat | null>(null);
  const [pickMode, setPickMode] = useState<PickMode>(null);

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

  const runAnalysis = () => {
    if (!route) return;
    setSteps(buildSteps(route));
    setStepIndex(0);
    setPhase("analysing");
  };

  // ---- regions -------------------------------------------------------------

  const showRegion = useCallback((next: Region, startPoint: LngLat | null, endPoint: LngLat | null) => {
    setRegionId(next.id);
    setStart(startPoint);
    setEnd(endPoint);
    setPickMode(startPoint && endPoint ? null : startPoint ? "end" : "start");
    setRoute(null);
    setPhase("before");
    setPreviewBox(null);
  }, []);

  const loadRegions = useCallback(
    () =>
      listRegions().then((list) => {
        setRegions(list);
        return list;
      }),
    [],
  );

  // Committed example event: a cached historical analysis, shown without a request.
  const showExample = useCallback(
    (region: Region) => {
      setView({
        mode: "historical",
        example: true,
        locationName: region.name,
        requestedDate: null,
        observation: region.flood_scene,
        source: region.source ?? null,
        note: "Example flood event: a cached analysis of this Sentinel-2 observation.",
        warnings: region.warnings ?? [],
      });
      showRegion(region, region.default_start, region.default_end);
    },
    [showRegion],
  );

  const loadInitial = useCallback(() => {
    loadRegions()
      .then((list) => {
        const first = list.find((r) => r.preset) ?? list[0];
        if (first) showExample(first);
      })
      .catch((err: unknown) => {
        console.error(err);
        setError(`Couldn't load flood data: ${err instanceof Error ? err.message : String(err)}`);
      });
  }, [loadRegions, showExample]);

  useEffect(() => {
    loadInitial();
  }, [loadInitial]);

  // A finished latest/historical analysis: show its region with the facts of this request.
  const onAnalysisDone = useCallback(
    (job: Job, doneMode: ExplorationMode, location: SelectedLocation, date: string | null) => {
      loadRegions()
        .then((list) => {
          const region = list.find((r) => r.id === job.region_id);
          if (!region) throw new Error("The analysed area could not be loaded.");
          setView({
            mode: doneMode,
            example: false,
            locationName: shortName(location.displayName),
            requestedDate: date,
            observation: region.flood_scene,
            source: region.source ?? null,
            note: job.details?.note ?? null,
            warnings: region.warnings ?? [],
          });
          // Start at the user's own position, or at the searched place unless the area
          // has a demo route; the destination is picked on the map if there is no default.
          const point: LngLat = [location.longitude, location.latitude];
          const inside = contains(region.bbox, point);
          const startPoint =
            location.source === "device" && inside ? point : (region.default_start ?? (inside ? point : null));
          showRegion(region, startPoint, region.default_end);
        })
        .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
    },
    [loadRegions, showRegion],
  );

  const retry = () => {
    setError(null);
    if (regions.length === 0) loadInitial();
    else setAttempt((n) => n + 1);
  };

  // Frame the selected area (only when the area changes, not on every render).
  const regionKey = region?.id;
  useEffect(() => {
    if (map && region) {
      map.fitBounds(region.bbox, { padding: fitPadding(map), duration: 800 });
    }
  }, [map, regionKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // A newly chosen location: centre the map and preview the area that will be analysed.
  const selectLocation = (location: SelectedLocation) => {
    setSelectedLocation(location);
    setError(null);
    const point: LngLat = [location.longitude, location.latitude];
    const preset = regions.find((r) => r.preset && contains(r.bbox, point));
    const box = preset ? preset.bbox : boxAround(point, AOI_KM);
    setPreviewBox(box);
    map?.fitBounds(box, { padding: fitPadding(map), duration: 1000 });
  };

  // ---- route ---------------------------------------------------------------

  // Each distinct request has a key; it is loading until a result with that key
  // arrives. The previous route stays on screen meanwhile.
  const routeKey = regionId && start && end ? JSON.stringify([regionId, start, end, attempt]) : null;
  const [result, setResult] = useState<{ key: string; error: string | null } | null>(null);
  const loading = routeKey !== null && result?.key !== routeKey;
  const routeError = routeKey !== null && result?.key === routeKey ? result.error : null;

  useEffect(() => {
    if (!routeKey || !regionId || !start || !end) return;
    let cancelled = false;
    getRoute({ start_coords: start, end_coords: end, scenario: DETECTION_LEVEL, region_id: regionId })
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
  }, [routeKey, regionId, start, end]);

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
  // After the sequence, follow the loaded data so new results update instantly.
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
      if (point) marker.setLngLat(point).addTo(map);
      else marker.remove();
    }
  }, [map, start, end, error]);

  // Crosshair while picking a point.
  useEffect(() => {
    if (map) map.getCanvas().style.cursor = pickMode ? "crosshair" : "";
  }, [map, pickMode]);

  return (
    <>
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />
      {map && (
        <>
          <SatelliteOverlayLayer
            map={map}
            regionId={regionId}
            corners={region?.overlay_corners ?? null}
            visible={visibility.satellite}
          />
          <AreaBoxLayer
            map={map}
            id="analysis-area"
            box={previewBox}
            color={MAP_COLORS.analysisArea}
            fillOpacity={0.08}
          />
          <FloodLayer
            map={map}
            data={route?.flood_polygons_geojson ?? null}
            visible={visibility.flood && shows("flood")}
          />
          <OriginalRouteLayer
            map={map}
            data={route?.original_route_geojson ?? null}
            visible={visibility.originalRoute}
            compromised={routeCompromised}
          />
          <FloodedRoadLayer
            map={map}
            data={route?.flooded_roads_geojson ?? null}
            visible={visibility.floodedRoads && shows("floodedRoads")}
          />
          <SafeRouteLayer
            map={map}
            data={route?.route_geojson ?? null}
            visible={visibility.safeRoute && shows("safeRoute")}
          />
        </>
      )}
      <StatusPanel
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
        <ExplorePanel
          mode={mode}
          onModeChange={setMode}
          location={selectedLocation}
          onLocationChange={selectLocation}
          requestedDate={requestedDate}
          onDateChange={setRequestedDate}
          onDone={onAnalysisDone}
          examples={regions.filter((r) => r.preset)}
          onExample={showExample}
          canAnalyze={!USE_MOCK}
        />
        {view && <FloodViewHeader view={view} />}
        {region && (
          <>
            <PointControls mode={pickMode} onModeChange={setPickMode} hasStart={start !== null} hasEnd={end !== null} />
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
