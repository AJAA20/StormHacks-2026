"use client";

import { useEffect } from "react";
import type { GeoJSONSource, Map } from "maplibre-gl";
import type { FloodPolygons } from "@/lib/api";

const SOURCE_ID = "flood";

type Props = {
  map: Map;
  data: FloodPolygons;
};

// Semi-transparent blue flood polygons (architecture.md §9).
export default function FloodLayer({ map, data }: Props) {
  useEffect(() => {
    const source = map.getSource<GeoJSONSource>(SOURCE_ID);
    if (source) {
      source.setData(data);
      return;
    }

    map.addSource(SOURCE_ID, { type: "geojson", data });
    map.addLayer({
      id: "flood-fill",
      type: "fill",
      source: SOURCE_ID,
      paint: { "fill-color": "#3b82f6", "fill-opacity": 0.45 },
    });
    map.addLayer({
      id: "flood-outline",
      type: "line",
      source: SOURCE_ID,
      paint: { "line-color": "#93c5fd", "line-width": 2 },
    });
  }, [map, data]);

  return null;
}
