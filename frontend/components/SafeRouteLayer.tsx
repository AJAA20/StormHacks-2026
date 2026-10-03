"use client";

import { useEffect } from "react";
import type { GeoJSONSource, Map } from "maplibre-gl";
import type { RouteFeature } from "@/lib/api";
import { LAYER_SLOTS } from "@/lib/config";

const SOURCE_ID = "safe-route";

type Props = {
  map: Map;
  data: RouteFeature;
};

// Current safe evacuation route as a solid green line (architecture.md §9).
export default function SafeRouteLayer({ map, data }: Props) {
  useEffect(() => {
    const source = map.getSource<GeoJSONSource>(SOURCE_ID);
    if (source) {
      source.setData(data);
      return;
    }

    map.addSource(SOURCE_ID, { type: "geojson", data });
    map.addLayer(
      {
        id: "safe-route-casing",
        type: "line",
        source: SOURCE_ID,
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#052e16", "line-width": 9, "line-opacity": 0.6 },
      },
      LAYER_SLOTS.safeRoute,
    );
    map.addLayer(
      {
        id: "safe-route-line",
        type: "line",
        source: SOURCE_ID,
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#22c55e", "line-width": 5 },
      },
      LAYER_SLOTS.safeRoute,
    );
  }, [map, data]);

  return null;
}
