// Location selection shared by both exploration modes. The rest of the app works with
// SelectedLocation (coordinates + a name) and never with a geocoding provider directly;
// today the backend proxies OpenStreetMap Nominatim (GET /api/geocode).

import { reverseGeocodeApi, searchPlaces, type BBox } from "./api";
import { getCurrentLocation } from "./geolocation";

export type SelectedLocation = {
  latitude: number;
  longitude: number;
  displayName: string;
  // "device": the user's own position from the browser; "search": a place they looked up.
  source: "search" | "device";
  bbox?: BBox;
  // Geocoder place type for search results, e.g. "town" or "village".
  kind?: string | null;
};

export async function searchLocation(query: string): Promise<SelectedLocation[]> {
  const places = await searchPlaces(query);
  return places.map((p) => ({
    latitude: p.center[1],
    longitude: p.center[0],
    displayName: p.name,
    source: "search",
    bbox: p.bbox,
    kind: p.kind ?? null,
  }));
}

export async function reverseGeocode(latitude: number, longitude: number): Promise<string | null> {
  try {
    return await reverseGeocodeApi(latitude, longitude);
  } catch {
    return null; // a name is nice to have; the coordinates are what matter
  }
}

// Browser permission prompt -> coordinates -> readable name (if available).
export async function locateUser(): Promise<SelectedLocation> {
  const { latitude, longitude } = await getCurrentLocation();
  const name = await reverseGeocode(latitude, longitude);
  return {
    latitude,
    longitude,
    displayName: name ?? `Your location (${latitude.toFixed(4)}, ${longitude.toFixed(4)})`,
    source: "device",
  };
}

// Where a search result is, for telling look-alike places apart: "town · Karditsa Regional Unit, Thessaly".
export function placeContext(location: SelectedLocation): string {
  const parts = location.displayName.split(",").map((p) => p.trim()).filter(Boolean);
  // Skip the name itself, municipality-level repeats and postcodes; keep the next two areas.
  const areas = parts.slice(1).filter((p) => !/^\d[\d\s-]*$/.test(p) && !p.startsWith(parts[0]));
  const where = areas.slice(0, 2).join(", ");
  return [location.kind, where].filter(Boolean).join(" · ");
}

// First part of a long geocoder name, e.g. "Abbotsford, Fraser Valley, BC, Canada" -> "Abbotsford, Fraser Valley".
export function shortName(displayName: string): string {
  return displayName.split(",").slice(0, 2).join(",").trim();
}
