"use client";

import { useEffect } from "react";
import type { GeoJSONSource, Map } from "maplibre-gl";
import { EMPTY_COLLECTION, type RouteFeature } from "@/lib/api";
import { LAYER_SLOTS } from "@/lib/config";
import { MAP_COLORS } from "@/lib/theme";

const SOURCE_ID = "original-route";
// Layer ids, bottom to top.
const LAYER_IDS = ["original-route-casing", "original-route-line"];

type Props = {
  map: Map;
  // null draws nothing (field missing from the response).
  data: RouteFeature | null;
  visible: boolean;
  // false: the active route before analysis (solid orange). true: blocked by flooding (grey dashed).
  compromised: boolean;
};

const COMPROMISED_DASH = [2, 1.5];
// An explicit solid pattern: resetting the dash to undefined is not reliably applied.
const SOLID = [1, 0];

// Pre-flood route: solid orange while it is the current route, dashed grey once
// flooding makes it unsafe (architecture.md §9). A dark casing underneath
// keeps it legible over satellite imagery.
export default function OriginalRouteLayer({ map, data, visible, compromised }: Props) {
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
        paint: { "line-color": MAP_COLORS.routeCasing, "line-width": 7, "line-opacity": 0.6 },
      },
      LAYER_SLOTS.route,
    );
    map.addLayer(
      {
        id: LAYER_IDS[1],
        type: "line",
        source: SOURCE_ID,
        layout: { "line-join": "round" },
        paint: { "line-color": MAP_COLORS.routeCurrent, "line-width": 4, "line-dasharray": SOLID },
      },
      LAYER_SLOTS.route,
    );
  }, [map, data]);

  useEffect(() => {
    const line = LAYER_IDS[1];
    map.setPaintProperty(line, "line-color", compromised ? MAP_COLORS.routeBlocked : MAP_COLORS.routeCurrent);
    map.setPaintProperty(line, "line-dasharray", compromised ? COMPROMISED_DASH : SOLID);
  }, [map, compromised]);

  useEffect(() => {
    for (const id of LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
  }, [map, visible]);

  return null;
}
