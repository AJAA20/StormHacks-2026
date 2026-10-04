"""Latest-available vs. historical flood analysis (POST /api/flood-analysis).

Offline: the Sentinel-2 archive is replaced by a fake list of acquisitions, so these tests
check the SELECTION rules (latest, nearest-to-date, honest errors, offline fallback) and
that both modes end in the same shared region/routing pipeline. Real-archive runs are in
the opt-in network test at the bottom and in scripts/smoke_test.py.
"""

import os
import shutil
import time
import warnings
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from backend.regions import builder, observations, store
from backend.regions.observations import Location, NoObservation

ROOT = Path(__file__).resolve().parents[1]
PRESET = ROOT / "backend/data/regions/abbotsford-2021"
pytestmark = pytest.mark.skipif(not (PRESET / "region.json").exists(), reason="preset missing")

ABBOTSFORD = Location(49.05, -122.25, "Abbotsford, BC")
NOWHERE = Location(-28.81, 153.28, "Lismore, NSW")  # not a preset
PRESET_SCENE = "S2A_T10UEV_20211121T191716_L2A"


def item(scene_id, day):
    d = date.fromisoformat(day)
    return SimpleNamespace(id=scene_id, datetime=SimpleNamespace(date=lambda: d), _day=d)


def fake_archive(monkeypatch, acquisitions):
    """acquisitions: list of (scene_id, 'YYYY-MM-DD', cloud_free_pct), served by a fake STAC."""
    from backend.satellite import stac

    clear_by_id = {sid: clear for sid, _, clear in acquisitions}

    def search(bbox, date_range):
        start, end = (date.fromisoformat(d) for d in date_range.split("/"))
        return [item(sid, day) for sid, day, _ in acquisitions if start <= date.fromisoformat(day) <= end]

    monkeypatch.setattr(stac, "search_scenes", search)
    monkeypatch.setattr(stac, "score_scene", lambda it, bbox: SimpleNamespace(aoi_clear_pct=clear_by_id[it.id]))


@pytest.fixture
def temp_regions(tmp_path, monkeypatch):
    regions = tmp_path / "regions"
    shutil.copytree(PRESET, regions / "abbotsford-2021", ignore=shutil.ignore_patterns("raster"))
    for module in (store, builder):
        monkeypatch.setattr(module, "REGIONS_DIR", regions)
    return regions


@pytest.fixture
def fake_build(monkeypatch):
    """Instant stand-in for the satellite+OSM build: copies the preset under the new id."""
    built = []

    def build(region_id, name, bbox, flood_dates, preflood_dates=None, progress=lambda s, f: None, flood_item=None, **kw):
        target = store.REGIONS_DIR / region_id
        shutil.copytree(store.REGIONS_DIR / "abbotsford-2021", target)
        meta = store.load_region(region_id) | {
            "id": region_id, "name": name, "preset": False, "bbox": list(bbox), "created_at": time.time(),
            "flood_scene": {"id": flood_item.id, "date": flood_item._day.isoformat(), "aoi_clear_pct": 90.0},
        }
        store.save_region(meta, target)
        built.append(region_id)
        return meta

    monkeypatch.setattr(builder, "build_region", build)
    return built


# --- selection rules -------------------------------------------------------------------

def test_historical_uses_nearest_usable_and_says_so(temp_regions, monkeypatch, fake_build):
    """Test 3 + 7: Nov 15 has no image; the nearest usable one (Nov 21) is used and labelled."""
    fake_archive(monkeypatch, [
        ("S2B_T10UEV_20211116T191938_L2A", "2021-11-16", 17.0),   # nearest, but too cloudy
        (PRESET_SCENE, "2021-11-21", 84.5),
        ("S2B_T10UEV_20211126T191729_L2A", "2021-11-26", 48.3),
    ])
    d = observations.analyze("historical", ABBOTSFORD, date(2021, 11, 15))
    assert d["requested_date"] == "2021-11-15"
    assert d["observation_date"] == "2021-11-21"  # the real acquisition date, not the requested one
    assert "nearest usable" in d["note"]
    assert d["region_id"] == "abbotsford-2021"  # same area + same image -> cached analysis reused
    assert fake_build == []


def test_latest_picks_newest_usable_image(temp_regions, monkeypatch, fake_build):
    """Test 1: newest usable acquisition wins (a newer but cloudy one is skipped)."""
    today = date.today().isoformat()
    fake_archive(monkeypatch, [
        ("S2A_OLD", "2021-11-21", 90.0),
        ("S2C_RECENT", today, 95.0),
    ])
    monkeypatch.setattr(observations, "LATEST_LOOKBACK_DAYS", 100000)
    d = observations.analyze("latest", ABBOTSFORD)
    assert d["mode"] == "latest" and d["observation_date"] == today and d["requested_date"] is None
    assert d["note"] is None
    assert store.load_region(d["region_id"])["flood_scene"]["id"] == "S2C_RECENT"


def test_user_location_is_the_area_but_data_is_historical(temp_regions, monkeypatch, fake_build):
    """Test 4: coordinates from the browser define the area; the image comes from the past."""
    fake_archive(monkeypatch, [("S2X_FAR", "2021-11-20", 80.0)])
    me = Location(-28.81, 153.28, "My location")
    d = observations.analyze("historical", me, date(2021, 11, 18))
    region = store.load_region(d["region_id"])
    w, s, e, n = region["bbox"]
    assert w < me.longitude < e and s < me.latitude < n  # area is centred on the user
    assert d["observation_date"] == "2021-11-20"


def test_no_usable_image_is_an_honest_error(temp_regions, monkeypatch, fake_build):
    """Test 5: nothing usable -> error, never someone else's flood data."""
    fake_archive(monkeypatch, [("S2_CLOUDY", "2022-03-01", 5.0)])
    with pytest.raises(NoObservation, match="No usable satellite observation"):
        observations.analyze("historical", NOWHERE, date(2022, 3, 1))
    with pytest.raises(NoObservation, match="No recent usable satellite observation"):
        observations.analyze("latest", NOWHERE)
    assert fake_build == []


def test_offline_only_falls_back_to_same_place_and_period(temp_regions, monkeypatch):
    def offline(*a, **kw):
        raise requests.ConnectionError("no internet")

    monkeypatch.setattr(observations, "_first_usable", offline)
    d = observations.analyze("historical", ABBOTSFORD, date(2021, 11, 18))
    assert d["region_id"] == "abbotsford-2021" and d["observation_date"] == "2021-11-21"
    assert "could not be reached" in d["note"]
    with pytest.raises(builder.RegionBuildError, match="not available for this location"):
        observations.analyze("historical", NOWHERE, date(2022, 3, 1))  # other place: no reuse
    with pytest.raises(builder.RegionBuildError, match="not available"):
        observations.analyze("historical", ABBOTSFORD, date(2019, 6, 1))  # other period: no reuse
    with pytest.raises(builder.RegionBuildError, match="not available"):
        observations.analyze("latest", ABBOTSFORD)  # cached 2021 data is never "latest"


# --- API: both modes end in the shared routing -----------------------------------------

@pytest.fixture
def client():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from fastapi.testclient import TestClient
    from backend.main import app

    return TestClient(app)


def wait_for(client, job_id):
    for _ in range(200):
        job = client.get(f"/api/flood-analysis/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_api_historical_then_route(client, temp_regions, monkeypatch, fake_build):
    fake_archive(monkeypatch, [(PRESET_SCENE, "2021-11-21", 84.5)])
    r = client.post("/api/flood-analysis", json={"mode": "historical", "latitude": 49.05, "longitude": -122.25,
                                                 "location_name": "Abbotsford, BC", "requested_date": "2021-11-15"})
    job = wait_for(client, r.json()["id"])
    assert job["status"] == "done", job
    assert job["details"]["requested_date"] == "2021-11-15" and job["details"]["observation_date"] == "2021-11-21"
    route = client.post("/api/route", json={"region_id": job["region_id"], "scenario": "severe",
                                            "start_coords": [-122.219, 49.024], "end_coords": [-122.2852, 49.0824]})
    assert route.status_code == 200 and route.json()["route_found"]


def test_api_validation(client):
    base = {"latitude": 49.05, "longitude": -122.25}
    assert client.post("/api/flood-analysis", json=base | {"mode": "historical"}).status_code == 400
    assert client.post("/api/flood-analysis", json=base | {"mode": "historical", "requested_date": "2014-01-01"}).status_code == 400
    assert client.post("/api/flood-analysis", json=base | {"mode": "historical", "requested_date": "2999-01-01"}).status_code == 400
    assert client.post("/api/flood-analysis", json=base | {"mode": "live"}).status_code == 422
    assert client.post("/api/flood-analysis", json={"mode": "latest", "latitude": 99, "longitude": 0}).status_code == 422


def test_api_reports_no_observation(client, temp_regions, monkeypatch, fake_build):
    fake_archive(monkeypatch, [])
    r = client.post("/api/flood-analysis", json={"mode": "latest", "latitude": -28.81, "longitude": 153.28})
    job = wait_for(client, r.json()["id"])
    assert job["status"] == "error" and "No recent usable satellite observation" in job["error"]


# --- real archive (internet) -------------------------------------------------------------

@pytest.mark.network
@pytest.mark.skipif(os.environ.get("SATRELIEF_NETWORK_TESTS") != "1", reason="set SATRELIEF_NETWORK_TESTS=1")
def test_real_historical_selection_abbotsford():
    bbox, _ = observations.area_for(ABBOTSFORD)
    obs = observations.select_historical(bbox, date(2021, 11, 15))
    assert obs.item.id == PRESET_SCENE and obs.date == date(2021, 11, 21)
