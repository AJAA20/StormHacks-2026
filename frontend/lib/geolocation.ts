// Browser location, requested ONLY after the user clicks "Use my location".
// This is genuinely where the user is now (unlike satellite images, which are snapshots).
// No imports, so it can be unit-tested with plain Node (lib/geolocation.test.ts).

export type GeoPoint = { latitude: number; longitude: number };

export class LocationError extends Error {}

// GeolocationPositionError codes.
const PERMISSION_DENIED = 1;
const POSITION_UNAVAILABLE = 2;
const TIMEOUT = 3;

export function locationErrorMessage(code: number): string {
  if (code === PERMISSION_DENIED) return "Location access was denied. Search for a location instead.";
  if (code === POSITION_UNAVAILABLE) return "Unable to determine your location. Search for a location instead.";
  if (code === TIMEOUT) return "Finding your location took too long. Try again, or search for a location.";
  return "Unable to determine your location. Search for a location instead.";
}

export function getCurrentLocation(
  geolocation: Geolocation | undefined = typeof navigator === "undefined" ? undefined : navigator.geolocation,
  timeoutMs = 10000,
): Promise<GeoPoint> {
  return new Promise((resolve, reject) => {
    if (!geolocation) {
      reject(new LocationError("This browser can't share its location. Search for a location instead."));
      return;
    }
    geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      (err) => reject(new LocationError(locationErrorMessage(err.code))),
      { enableHighAccuracy: false, timeout: timeoutMs, maximumAge: 60000 },
    );
  });
}
