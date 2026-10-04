// Small lon/lat helpers for area boxes. Approximate (spherical), which is plenty
// for sizing a box on screen; the backend re-checks sizes precisely.

import type { BBox } from "./api";
import type { LngLat } from "./config";

const KM_PER_DEG_LAT = 111.32;

const kmPerDegLng = (lat: number) => KM_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);

// Square of sideKm around a point (preview of the area the backend will analyse).
export function boxAround([lng, lat]: LngLat, sideKm: number): BBox {
  const halfW = sideKm / 2 / kmPerDegLng(lat);
  const halfH = sideKm / 2 / KM_PER_DEG_LAT;
  return [lng - halfW, lat - halfH, lng + halfW, lat + halfH];
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
