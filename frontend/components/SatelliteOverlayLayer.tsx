"use client";

import { useEffect } from "react";
import type { ImageSource, Map } from "maplibre-gl";
import { overlayUrl } from "@/lib/api";
import type { LngLat } from "@/lib/config";
import { LAYER_SLOTS } from "@/lib/config";

const SOURCE_ID = "sentinel-overlay";
const LAYER_ID = "sentinel-overlay-image";

type Props = {
  map: Map;
  regionId: string | null;
  // Image corners from the region (TL, TR, BR, BL); null = no overlay.
  corners: [LngLat, LngLat, LngLat, LngLat] | null;
  visible: boolean;
};

// The actual Sentinel-2 true-colour image from the flood date, draped over the
// basemap, so viewers see the satellite observation the flood polygons came from.
export default function SatelliteOverlayLayer({ map, regionId, corners, visible }: Props) {
  useEffect(() => {
    if (!regionId || !corners) {
      if (map.getLayer(LAYER_ID)) map.removeLayer(LAYER_ID);
      if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
      return;
    }
    const url = overlayUrl(regionId);
    const source = map.getSource<ImageSource>(SOURCE_ID);
    if (source) {
      source.updateImage({ url, coordinates: corners });
      return;
    }
    map.addSource(SOURCE_ID, { type: "image", url, coordinates: corners });
    map.addLayer(
      { id: LAYER_ID, type: "raster", source: SOURCE_ID, paint: { "raster-opacity": 0.9, "raster-fade-duration": 0 } },
      LAYER_SLOTS.overlay,
    );
  }, [map, regionId, corners]);

  useEffect(() => {
    if (map.getLayer(LAYER_ID)) {
      map.setLayoutProperty(LAYER_ID, "visibility", visible ? "visible" : "none");
    }
  }, [map, visible, regionId, corners]);

  return null;
}
