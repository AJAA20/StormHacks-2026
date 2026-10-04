// Run: npm test  (Node's built-in test runner; Node strips the TypeScript types).
import { test } from "node:test";
import assert from "node:assert/strict";
import { getCurrentLocation, LocationError } from "./geolocation.ts";

// Minimal stand-ins for the browser Geolocation API.
const granted = (latitude: number, longitude: number) =>
  ({ getCurrentPosition: (ok: PositionCallback) => ok({ coords: { latitude, longitude } } as GeolocationPosition) }) as Geolocation;
const failing = (code: number) =>
  ({ getCurrentPosition: (_ok: PositionCallback, fail?: PositionErrorCallback | null) => fail?.({ code } as GeolocationPositionError) }) as Geolocation;

test("returns the browser coordinates", async () => {
  assert.deepEqual(await getCurrentLocation(granted(49.05, -122.3)), { latitude: 49.05, longitude: -122.3 });
});

test("permission denied gives a clear message", async () => {
  await assert.rejects(getCurrentLocation(failing(1)), (e: unknown) =>
    e instanceof LocationError && e.message === "Location access was denied. Search for a location instead.");
});

test("position unavailable and timeout are explained", async () => {
  await assert.rejects(getCurrentLocation(failing(2)), /Unable to determine your location/);
  await assert.rejects(getCurrentLocation(failing(3)), /took too long/);
});

test("unsupported browser is handled", async () => {
  await assert.rejects(getCurrentLocation(undefined), /can't share its location/);
});
