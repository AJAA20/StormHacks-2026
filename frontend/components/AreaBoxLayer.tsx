"use client";

import { useEffect } from "react";
import type { GeoJSONSource, Map } from "maplibre-gl";
import { EMPTY_COLLECTION, type BBox } from "@/lib/api";
import { LAYER_SLOTS } from "@/lib/config";
import { boxPolygon } from "@/lib/geo";

type Props = {
  map: Map;
  // Unique per box, e.g. "region-bounds" or "analysis-area".
  id: string;
  box: BBox | null;
  color: string;
  // Light fill, e.g. to highlight the area about to be analysed.
  fillOpacity?: number;
};

// Dashed rectangle: the analysed area (roads and flood data exist only inside it),
// or the area the user is about to analyse.
export default function AreaBoxLayer({ map, id, box, color, fillOpacity = 0 }: Props) {
  useEffect(() => {
    const data = box ? boxPolygon(box) : EMPTY_COLLECTION;
    const source = map.getSource<GeoJSONSource>(id);
    if (source) {
      source.setData(data);
      return;
    }
    map.addSource(id, { type: "geojson", data });
    map.addLayer(
      { id: `${id}-fill`, type: "fill", source: id, paint: { "fill-color": color, "fill-opacity": fillOpacity } },
      LAYER_SLOTS.areas,
    );
    map.addLayer(
      {
        id: `${id}-line`,
        type: "line",
        source: id,
        paint: { "line-color": color, "line-width": 2, "line-dasharray": [3, 2] },
      },
      LAYER_SLOTS.areas,
    );
  }, [map, id, box, color, fillOpacity]);

  return null;
}
