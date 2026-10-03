"use client";

import { useEffect } from "react";
import type { GeoJSONSource, Map } from "maplibre-gl";
import { EMPTY_COLLECTION, type FloodPolygons } from "@/lib/api";
import { LAYER_SLOTS } from "@/lib/config";

const SOURCE_ID = "flood";
// Layer ids, bottom to top.
const LAYER_IDS = ["flood-fill", "flood-outline"];

type Props = {
  map: Map;
  // null draws nothing (field missing from the response).
  data: FloodPolygons | null;
  visible: boolean;
};

// Semi-transparent blue flood polygons (architecture.md §9).
export default function FloodLayer({ map, data, visible }: Props) {
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
        type: "fill",
        source: SOURCE_ID,
        paint: { "fill-color": "#3b82f6", "fill-opacity": 0.45 },
      },
      LAYER_SLOTS.flood,
    );
    map.addLayer(
      {
        id: LAYER_IDS[1],
        type: "line",
        source: SOURCE_ID,
        paint: { "line-color": "#93c5fd", "line-width": 2 },
      },
      LAYER_SLOTS.flood,
    );
  }, [map, data]);

  useEffect(() => {
    for (const id of LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
  }, [map, visible]);

  return null;
}
