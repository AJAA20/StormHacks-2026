"use client";

import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import FloodLayer from "./FloodLayer";
import FloodedRoadLayer from "./FloodedRoadLayer";
import OriginalRouteLayer from "./OriginalRouteLayer";
import {
  getFloodedRoads,
  getFloodPolygons,
  getOriginalRoute,
  type FloodedRoads,
  type FloodPolygons,
  type RouteFeature,
} from "@/lib/api";
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
  const [flood, setFlood] = useState<FloodPolygons | null>(null);
  const [originalRoute, setOriginalRoute] = useState<RouteFeature | null>(null);
  const [floodedRoads, setFloodedRoads] = useState<FloodedRoads | null>(null);

  useEffect(() => {
    let cancelled = false;
    getFloodPolygons()
      .then((data) => {
        if (!cancelled) setFlood(data);
      })
      .catch((err) => console.error(err));
    getOriginalRoute()
      .then((data) => {
        if (!cancelled) setOriginalRoute(data);
      })
      .catch((err) => console.error(err));
    getFloodedRoads()
      .then((data) => {
        if (!cancelled) setFloodedRoads(data);
      })
      .catch((err) => console.error(err));
    return () => {
      cancelled = true;
    };
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
          { id: LAYER_SLOTS.flood, type: "background", layout: { visibility: "none" } },
          { id: LAYER_SLOTS.route, type: "background", layout: { visibility: "none" } },
          { id: LAYER_SLOTS.floodedRoads, type: "background", layout: { visibility: "none" } },
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
      {map && flood && <FloodLayer map={map} data={flood} />}
      {map && originalRoute && <OriginalRouteLayer map={map} data={originalRoute} />}
      {map && floodedRoads && <FloodedRoadLayer map={map} data={floodedRoads} />}
    </>
  );
}
