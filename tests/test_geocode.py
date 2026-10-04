"""Place search proxy (GET /api/geocode): English names and place types, no real network."""

import warnings

import pytest

from backend.api import regions as api


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "_last_geocode", 0.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from fastapi.testclient import TestClient
    from backend.main import app

    return TestClient(app)


def test_search_asks_for_english_and_returns_place_type(client, monkeypatch):
    seen = {}

    def fake_get(url, params, headers, timeout):
        seen.update(params)
        return FakeResponse([
            {"display_name": "Palamas, Domokos Municipality, Phthiotis Regional Unit, Central Greece, Greece",
             "lat": "39.029", "lon": "22.400", "boundingbox": ["39.0", "39.1", "22.3", "22.5"], "addresstype": "village"},
            {"display_name": "Palamas, Palamas Municipality, Karditsa Regional Unit, Thessaly, Greece",
             "lat": "39.467", "lon": "22.083", "boundingbox": ["39.4", "39.5", "22.0", "22.2"], "addresstype": "town"},
        ])

    monkeypatch.setattr(api.requests, "get", fake_get)
    results = client.get("/api/geocode", params={"q": "Palamas, Greece"}).json()
    assert seen["accept-language"] == "en"
    assert [r["kind"] for r in results] == ["village", "town"]
    assert results[1]["center"] == [22.083, 39.467]
