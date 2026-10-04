"""End-to-end smoke test against a RUNNING backend (what the UI talks to).

Start the backend first (uvicorn backend.main:app), then:

    python scripts/smoke_test.py                 # full test, includes a live analysis (~30 s, needs internet)
    python scripts/smoke_test.py --skip-live     # presets only, works offline
    python scripts/smoke_test.py --url http://localhost:3000   # through the Next.js proxy instead

Prints PASS/FAIL per check and exits 1 if anything failed.
"""

from __future__ import annotations

import argparse
import sys
import time

import requests

# A real flood with a clear Sentinel-2 image (2019-03-31) that is NOT a preset,
# so this exercises the whole live pipeline: STAC search -> MNDWI -> polygons -> OSM -> routing.
LIVE_AREA = {
    "name": "Smoke test - Fremont, Nebraska",
    "bbox": [-96.55, 41.38, -96.40, 41.47],
    "flood_dates": "2019-03-16/2019-04-05",
}
UI_FIELDS = {
    "status", "scenario", "route_found", "start_coords", "end_coords", "distance_km", "detour_added_km",
    "flooded_edges", "flooded_edges_avoided", "route_status", "route_geojson", "original_route_geojson",
    "flood_polygons_geojson", "flooded_roads_geojson",
}

failures: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{f'  ({detail})' if detail else ''}")
    if not ok:
        failures.append(label)
    return ok


def route(base, region, start, end, scenario="severe"):
    return requests.post(f"{base}/api/route", json={
        "region_id": region, "start_coords": start, "end_coords": end, "scenario": scenario,
    }, timeout=60)


def test_presets(base: str) -> None:
    print("\n1. Preset areas")
    regions = requests.get(f"{base}/api/regions", timeout=10).json()
    ids = [r["id"] for r in regions]
    check("abbotsford-2021" in ids and "emilia-romagna-2023" in ids, "both presets listed", ", ".join(ids))
    check(ids[0] == "abbotsford-2021", "Abbotsford is the default (first) area")

    for region in (r for r in regions if r["preset"]):
        rid = region["id"]
        print(f"\n   {region['name']}")
        overlay = requests.get(f"{base}/api/regions/{rid}/overlay", timeout=10)
        check(overlay.ok and overlay.headers.get("content-type") == "image/webp",
              "Sentinel-2 overlay image served", f"{len(overlay.content) // 1024} KB")
        counts = []
        for scenario in ("low", "moderate", "severe"):
            r = route(base, rid, region["default_start"], region["default_end"], scenario)
            d = r.json() if r.ok else {}
            ok = r.ok and UI_FIELDS <= d.keys() and d["route_found"]
            check(ok, f"{scenario:8s} route", f"{d.get('distance_km')} km, +{d.get('detour_added_km')} km detour, "
                                             f"{d.get('flooded_edges')} flooded roads" if ok else r.text[:120])
            counts.append(d.get("flooded_edges") or 0)
        check(counts[0] < counts[1] < counts[2], "worse flood -> more flooded roads", str(counts))
        check((d.get("detour_added_km") or 0) > 0, "severe flood forces a detour", f"+{d.get('detour_added_km')} km")

    print("\n2. Error handling")
    r = route(base, "abbotsford-2021", [0, 0], [-122.2852, 49.0824])
    check(r.status_code == 400 and "outside" in r.json().get("detail", ""), "point outside area -> clear 400")
    r = route(base, "no-such-area", [0, 0], [0, 0])
    check(r.status_code == 404, "unknown area -> 404")
    r = requests.post(f"{base}/api/analyze", json={"bbox": [0, 0, 5, 5], "flood_dates": "2019-03-16/2019-04-05"}, timeout=10)
    check(r.status_code == 400 and "zoom in" in r.json().get("detail", ""), "area too big -> clear 400")


def test_live(base: str, timeout_s: int) -> None:
    print("\n3. Analyse a new area live (Fremont, Nebraska, March 2019 flood)")
    t0 = time.time()
    job = requests.post(f"{base}/api/analyze", json=LIVE_AREA, timeout=10).json()
    last_stage = None
    while job["status"] in ("queued", "running") and time.time() - t0 < timeout_s:
        if job["stage"] != last_stage:
            print(f"     [{job['progress']:4.0%}] {job['stage']}")
            last_stage = job["stage"]
        time.sleep(1)
        job = requests.get(f"{base}/api/analyze/{job['id']}", timeout=10).json()
    if not check(job["status"] == "done", "analysis finished", f"{time.time() - t0:.0f} s"
                 if job["status"] == "done" else (job.get("error") or job["status"])):
        return

    region = requests.get(f"{base}/api/regions/{job['region_id']}", timeout=10).json()
    check(region["flood_scene"]["date"].startswith("2019-0"), "picked a Sentinel-2 image in the flood window",
          f"{region['flood_scene']['date']}, {region['flood_scene']['aoi_clear_pct']}% clear")
    check(region["road_edges"] > 100, "downloaded the road network", f"{region['road_edges']} road segments")
    check(region["scenarios"]["severe"]["polygons"] > 0, "detected flood polygons",
          f"{region['scenarios']['severe']['polygons']} polygons, {region['scenarios']['severe']['area_km2']} km^2")

    w, s, e, n = region["bbox"]
    start = [w + (e - w) * 0.35, s + (n - s) * 0.75]  # north of the Platte River (town)
    end = [w + (e - w) * 0.75, s + (n - s) * 0.30]    # south-east
    r = route(base, region["id"], start, end)
    d = r.json() if r.ok else {}
    check(r.ok and UI_FIELDS <= d.keys(), "route in the new area returns every UI field",
          f"{d.get('route_status')}, {d.get('distance_km')} km" if r.ok else r.text[:120])

    again = requests.post(f"{base}/api/analyze", json=LIVE_AREA, timeout=10).json()
    check(again["status"] == "done" and again["stage"] == "Loaded from cache", "repeat request is instant (cache)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--skip-live", action="store_true", help="Skip the live analysis (offline)")
    p.add_argument("--timeout", type=int, default=240, help="Seconds to wait for the live analysis")
    a = p.parse_args()
    base = a.url.rstrip("/")

    try:
        requests.get(f"{base}/api/regions", timeout=5).raise_for_status()
    except requests.RequestException as exc:
        print(f"Backend not reachable at {base}: {exc}\nStart it with: uvicorn backend.main:app --reload")
        return 1

    print(f"SatRelief smoke test against {base}")
    test_presets(base)
    if not a.skip_live:
        test_live(base, a.timeout)

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
