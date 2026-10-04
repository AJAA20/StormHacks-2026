"""Tests for the Earth Search STAC fetcher. Offline by default.

The real-network test runs only with:  SATRELIEF_NETWORK_TESTS=1 pytest -m network
"""

import os
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.satellite import stac
from backend.satellite.stac import SceneCandidate, _bbox_key, boa_offset_from_item

ABBOTSFORD = (-122.32, 49.00, -122.10, 49.12)


def fake_item(scale=0.0001, offset=-0.1):
    band = SimpleNamespace(extra_fields={"raster:bands": [{"scale": scale, "offset": offset}]})
    return SimpleNamespace(id="X", assets={"green": band}, properties={},
                           datetime=datetime(2021, 11, 21, tzinfo=timezone.utc))


def test_boa_offset_from_stac_metadata():
    assert boa_offset_from_item(fake_item()) == -1000  # Collection 1: DN*0.0001 - 0.1
    assert boa_offset_from_item(fake_item(offset=0.0)) == 0


def test_bbox_key_is_stable():
    assert _bbox_key(ABBOTSFORD) == _bbox_key(tuple(ABBOTSFORD))
    assert _bbox_key(ABBOTSFORD) != _bbox_key((-122.3, 49.0, -122.1, 49.1))


def test_rank_sorts_clearest_first(monkeypatch):
    clear = {"a": 10.0, "b": 85.0, "c": 50.0}
    monkeypatch.setattr(stac, "score_scene", lambda it, bbox: SceneCandidate(it, "2021-11-21", 0, clear[it], 0))
    ranking = stac.rank_scenes(["a", "b", "c"], ABBOTSFORD, workers=1)
    assert [s.id for s in ranking] == ["b", "c", "a"]


def test_find_best_scene_rejects_cloudy(monkeypatch):
    monkeypatch.setattr(stac, "search_scenes", lambda bbox, dates: ["a"])
    monkeypatch.setattr(stac, "score_scene", lambda it, bbox: SceneCandidate(it, "2021-11-21", 99, 3.0, 0))
    with pytest.raises(LookupError, match="cloud-free"):
        stac.find_best_scene(ABBOTSFORD, "2021-11-01/2021-11-30", min_clear_pct=50)


@pytest.mark.network
@pytest.mark.skipif(os.environ.get("SATRELIEF_NETWORK_TESTS") != "1", reason="set SATRELIEF_NETWORK_TESTS=1")
def test_earth_search_finds_abbotsford_flood_scene():
    item, ranking = stac.find_best_scene(ABBOTSFORD, "2021-11-14/2021-12-10", min_clear_pct=50)
    assert item.id.startswith("S2")
    assert ranking[0].aoi_clear_pct >= 50
    assert boa_offset_from_item(item) == -1000
