"use client";

import { useEffect } from "react";
import type { GeoJSONSource, Map } from "maplibre-gl";
import { EMPTY_COLLECTION, type RouteFeature } from "@/lib/api";
import { LAYER_SLOTS } from "@/lib/config";

const SOURCE_ID = "safe-route";
// Layer ids, bottom to top.
const LAYER_IDS = ["safe-route-casing", "safe-route-line"];

type Props = {
  map: Map;
  // null draws nothing (field missing from the response).
  data: RouteFeature | null;
  visible: boolean;
};

// Current safe evacuation route as a solid green line (architecture.md §9).
export default function SafeRouteLayer({ map, data, visible }: Props) {
  useEffect(() => {
    const geojson = data ?? EMPTY_COLLECTION;
    const source = map.getSource<GeoJSONSource>(SOURCE_ID);
    if (source) {
      source.setData(geojson);
      return;
    }

    map.addSource(SOURCE_ID, { type: "geojson", data: geojson });
    map.addLayer(
      {
        id: LAYER_IDS[0],
        type: "line",
        source: SOURCE_ID,
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#052e16", "line-width": 9, "line-opacity": 0.6 },
      },
      LAYER_SLOTS.safeRoute,
    );
    map.addLayer(
      {
        id: LAYER_IDS[1],
        type: "line",
        source: SOURCE_ID,
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#22c55e", "line-width": 5 },
      },
      LAYER_SLOTS.safeRoute,
    );
  }, [map, data]);

  useEffect(() => {
    for (const id of LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
  }, [map, visible]);

  return null;
}
