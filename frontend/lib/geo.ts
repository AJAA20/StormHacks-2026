// Small lon/lat helpers for area boxes. Approximate (spherical), which is plenty
// for sizing a box on screen; the backend re-checks sizes precisely.

import type { BBox } from "./api";
import type { LngLat } from "./config";

const KM_PER_DEG_LAT = 111.32;

const kmPerDegLng = (lat: number) => KM_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);

// [width, height] of a box in km.
export function sizeKm([w, s, e, n]: BBox): [number, number] {
  return [(e - w) * kmPerDegLng((s + n) / 2), (n - s) * KM_PER_DEG_LAT];
}

// Shrink a box around its centre so neither side exceeds maxKm.
export function clampBox(box: BBox, maxKm: number): BBox {
  const [w, s, e, n] = box;
  const [cx, cy] = [(w + e) / 2, (s + n) / 2];
  const halfW = Math.min((e - w) / 2, maxKm / 2 / kmPerDegLng(cy));
  const halfH = Math.min((n - s) / 2, maxKm / 2 / KM_PER_DEG_LAT);
  return [cx - halfW, cy - halfH, cx + halfW, cy + halfH];
}

export function contains([w, s, e, n]: BBox, [lng, lat]: LngLat): boolean {
  return lng >= w && lng <= e && lat >= s && lat <= n;
}

export function boxPolygon([w, s, e, n]: BBox): GeoJSON.Feature<GeoJSON.Polygon> {
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] },
  };
}
