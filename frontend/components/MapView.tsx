"use client";

import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import FloodLayer from "./FloodLayer";
import FloodedRoadLayer from "./FloodedRoadLayer";
import LayerControls, { type LayerKey, type LayerVisibility } from "./LayerControls";
import OriginalRouteLayer from "./OriginalRouteLayer";
import SafeRouteLayer from "./SafeRouteLayer";
import ScenarioControls from "./ScenarioControls";
import StatusPanel from "./StatusPanel";
import { getRoute, type RouteResponse, type Scenario } from "@/lib/api";
import {
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

  const toggleLayer = (key: LayerKey) =>
    setVisibility((v) => ({ ...v, [key]: !v[key] }));

  useEffect(() => {
    let cancelled = false;
    getRoute({ start_coords: START_COORDS, end_coords: END_COORDS, scenario })
      .then((data) => {
        if (!cancelled) setRoute(data);
      })
      .catch((err) => console.error(err));
    return () => {
      cancelled = true;
    };
  }, [scenario]);

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

    new maplibregl.Marker({ color: "#2563eb" })
      .setLngLat(START_COORDS)
      .setPopup(new maplibregl.Popup({ offset: 24 }).setText("Start"))
      .addTo(map);

    new maplibregl.Marker({ color: "#16a34a" })
      .setLngLat(END_COORDS)
      .setPopup(new maplibregl.Popup({ offset: 24 }).setText("Evacuation destination"))
      .addTo(map);

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
            visible={visibility.flood}
          />
          <OriginalRouteLayer
            map={map}
            data={route.original_route_geojson}
            visible={visibility.originalRoute}
          />
          <FloodedRoadLayer
            map={map}
            data={route.flooded_roads_geojson}
            visible={visibility.floodedRoads}
          />
          <SafeRouteLayer
            map={map}
            data={route.route_geojson}
            visible={visibility.safeRoute}
          />
        </>
      )}
      {route && (
        <StatusPanel data={route}>
          <ScenarioControls value={scenario} onChange={setScenario} />
        </StatusPanel>
      )}
      <LayerControls visibility={visibility} onToggle={toggleLayer} />
    </>
  );
}
