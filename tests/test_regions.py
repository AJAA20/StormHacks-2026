"""Tests for analysed regions: request validation, background jobs, and the region/analyze API.

Offline: the slow build (satellite download + OSM) is replaced by a fake that copies the
Abbotsford preset. The real end-to-end build is covered by the opt-in network test at the
bottom and by scripts/smoke_test.py.
"""

import os
import shutil
import time
import warnings
from pathlib import Path

import pytest

from backend.regions import builder, jobs, store
from backend.regions.builder import RegionBuildError, validate_request

ROOT = Path(__file__).resolve().parents[1]
PRESET = ROOT / "backend/data/regions/abbotsford-2021"
needs_preset = pytest.mark.skipif(not (PRESET / "region.json").exists(), reason="preset missing")
CONSELICE = [11.80, 44.40, 11.98, 44.52]  # Emilia-Romagna flood, May 2023 (clear Sentinel-2 on 2023-05-23)


@pytest.fixture
def client():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from fastapi.testclient import TestClient
    from backend.main import app

    return TestClient(app)


@pytest.fixture
def temp_regions(tmp_path, monkeypatch):
    """Point the region store at a temp folder holding a copy of the preset."""
    regions = tmp_path / "regions"
    shutil.copytree(PRESET, regions / "abbotsford-2021", ignore=shutil.ignore_patterns("raster"))
    for module in (store, builder):
        monkeypatch.setattr(module, "REGIONS_DIR", regions)
    return regions


# --- validation ----------------------------------------------------------------

def test_valid_request_fills_default_preflood_dates():
    bbox, flood, pre = validate_request(CONSELICE, "2023-05-17/2023-06-05", None)
    assert bbox == tuple(CONSELICE)
    assert pre == "2023-01-17/2023-05-03"  # 4 months ending 2 weeks before the flood window


@pytest.mark.parametrize("bbox, dates, message", [
    ([11.0, 44.0, 12.0, 45.0], "2023-05-17/2023-06-05", "zoom in"),           # ~80 km: too big
    ([11.80, 44.40, 11.801, 44.401], "2023-05-17/2023-06-05", "too small"),
    ([11.98, 44.40, 11.80, 44.52], "2023-05-17/2023-06-05", "west < east"),
    (CONSELICE, "2023-06-05/2023-05-17", "before start"),
    (CONSELICE, "May 2023", "must look like"),
    (CONSELICE, "2014-01-01/2014-02-01", "2015"),
])
def test_invalid_requests_get_clear_messages(bbox, dates, message):
    with pytest.raises(RegionBuildError, match=message):
        validate_request(bbox, dates, None)


def test_region_id_is_stable_and_safe():
    a = store.region_id_for("Conselice, Italy!", CONSELICE, "2023-05-17/2023-06-05")
    assert a == store.region_id_for("Conselice, Italy!", CONSELICE, "2023-05-17/2023-06-05")
    assert a.startswith("conselice-italy-")
    with pytest.raises(store.RegionNotFound):
        store.region_dir("../../etc")


# --- jobs + API (with a fake, instant build) -------------------------------------

def fake_build(region_id, name, bbox, flood_dates, preflood_dates=None, progress=lambda s, f: None, **kw):
    progress("Searching the Sentinel-2 archive", 0.1)
    target = store.REGIONS_DIR / region_id
    shutil.copytree(store.REGIONS_DIR / "abbotsford-2021", target)
    meta = store.load_region(region_id) | {"id": region_id, "name": name, "preset": False,
                                           "bbox": list(bbox), "created_at": time.time()}
    store.save_region(meta, target)
    return meta


def wait_for(client, job_id, timeout=10):
    for _ in range(int(timeout / 0.05)):
        job = client.get(f"/api/analyze/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


@needs_preset
def test_regions_list_starts_with_preset(client):
    regions = client.get("/api/regions").json()
    assert regions[0]["id"] == "abbotsford-2021" and regions[0]["preset"] is True
    assert regions[0]["default_start"] and regions[0]["overlay_corners"]
    assert client.get("/api/regions/abbotsford-2021/overlay").headers["content-type"] == "image/webp"


@needs_preset
def test_analyze_new_area_then_route_in_it(client, temp_regions, monkeypatch):
    monkeypatch.setattr(builder, "build_region", fake_build)
    abbotsford_bbox = [-122.32, 49.00, -122.10, 49.12]
    r = client.post("/api/analyze", json={"name": "Test area", "bbox": abbotsford_bbox,
                                          "flood_dates": "2021-11-14/2021-12-10"})
    assert r.status_code == 200
    job = wait_for(client, r.json()["id"])
    assert job["status"] == "done", job

    region_id = job["region_id"]
    assert region_id in [x["id"] for x in client.get("/api/regions").json()]
    route = client.post("/api/route", json={"start_coords": [-122.219, 49.024], "end_coords": [-122.2852, 49.0824],
                                            "scenario": "severe", "region_id": region_id}).json()
    assert route["region_id"] == region_id and route["route_found"]

    # Same request again comes straight from the cache.
    again = client.post("/api/analyze", json={"name": "Test area", "bbox": abbotsford_bbox,
                                              "flood_dates": "2021-11-14/2021-12-10"}).json()
    assert again["status"] == "done" and again["stage"] == "Loaded from cache"


def test_failed_build_reports_the_reason(client, temp_regions, monkeypatch):
    def cloudy(*a, **kw):
        raise RegionBuildError("No usable flood-date image: too cloudy")

    monkeypatch.setattr(builder, "build_region", cloudy)
    r = client.post("/api/analyze", json={"name": "Cloudy", "bbox": CONSELICE, "flood_dates": "2023-05-17/2023-06-05"})
    job = wait_for(client, r.json()["id"])
    assert job["status"] == "error" and "too cloudy" in job["error"]


def test_bad_analyze_request_is_400(client):
    r = client.post("/api/analyze", json={"bbox": [0, 0, 5, 5], "flood_dates": "2023-05-17/2023-06-05"})
    assert r.status_code == 400 and "zoom in" in r.json()["detail"]


@needs_preset
def test_route_errors_are_readable(client):
    outside = client.post("/api/route", json={"start_coords": [0, 0], "end_coords": [-122.2852, 49.0824]})
    assert outside.status_code == 400 and "outside the analysed area" in outside.json()["detail"]
    unknown = client.post("/api/route", json={"start_coords": [0, 0], "end_coords": [0, 0], "region_id": "nope"})
    assert unknown.status_code == 404


# --- real end-to-end build (internet) ---------------------------------------------

@pytest.mark.network
@pytest.mark.skipif(os.environ.get("SATRELIEF_NETWORK_TESTS") != "1", reason="set SATRELIEF_NETWORK_TESTS=1")
def test_real_build_emilia_romagna(temp_regions):
    meta = builder.build_region("conselice-test", "Conselice", CONSELICE, "2023-05-17/2023-06-05")
    assert meta["flood_scene"]["date"].startswith("2023-05")
    assert meta["road_edges"] > 100
    assert meta["scenarios"]["severe"]["polygons"] > 0
    assert (temp_regions / "conselice-test" / "overlay.webp").exists()
