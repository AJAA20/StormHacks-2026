"use client";

import { useEffect } from "react";
import type { GeoJSONSource, Map } from "maplibre-gl";
import type { FloodedRoads } from "@/lib/api";
import { LAYER_SLOTS } from "@/lib/config";

const SOURCE_ID = "flooded-roads";
// Layer ids, bottom to top.
const LAYER_IDS = ["flooded-roads-line"];

type Props = {
  map: Map;
  data: FloodedRoads;
  visible: boolean;
};

// Road segments classified as flooded, in solid red (architecture.md §9).
export default function FloodedRoadLayer({ map, data, visible }: Props) {
  useEffect(() => {
    const source = map.getSource<GeoJSONSource>(SOURCE_ID);
    if (source) {
      source.setData(data);
      return;
    }

    map.addSource(SOURCE_ID, { type: "geojson", data });
    map.addLayer(
      {
        id: LAYER_IDS[0],
        type: "line",
        source: SOURCE_ID,
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#ef4444", "line-width": 5 },
      },
      LAYER_SLOTS.floodedRoads,
    );
  }, [map, data]);

  useEffect(() => {
    for (const id of LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
  }, [map, visible]);

  return null;
}
