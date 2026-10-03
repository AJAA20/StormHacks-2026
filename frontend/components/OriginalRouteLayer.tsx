"use client";

import { useEffect } from "react";
import type { GeoJSONSource, Map } from "maplibre-gl";
import { EMPTY_COLLECTION, type RouteFeature } from "@/lib/api";
import { LAYER_SLOTS } from "@/lib/config";

const SOURCE_ID = "original-route";
// Layer ids, bottom to top.
const LAYER_IDS = ["original-route-casing", "original-route-line"];

type Props = {
  map: Map;
  // null draws nothing (field missing from the response).
  data: RouteFeature | null;
  visible: boolean;
};

// Pre-flood route as a dashed grey line (architecture.md §9). A dark casing
// underneath keeps it legible over satellite imagery.
export default function OriginalRouteLayer({ map, data, visible }: Props) {
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
        paint: { "line-color": "#111827", "line-width": 7, "line-opacity": 0.6 },
      },
      LAYER_SLOTS.route,
    );
    map.addLayer(
      {
        id: LAYER_IDS[1],
        type: "line",
        source: SOURCE_ID,
        layout: { "line-join": "round" },
        paint: {
          "line-color": "#d1d5db",
          "line-width": 4,
          "line-dasharray": [2, 1.5],
        },
      },
      LAYER_SLOTS.route,
    );
  }, [map, data]);

  useEffect(() => {
    for (const id of LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
  }, [map, visible]);

  return null;
}
