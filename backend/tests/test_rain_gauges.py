from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import rain as rain_router
from app.services import rain_gauges as rg


def page(times_values, stations=(("S1", "Ang Mo Kio", 1.37, 103.85), ("S2", "Changi", 1.36, 103.99))):
    return {
        "data": {
            "stations": [{"id": i, "name": n, "location": {"latitude": la, "longitude": lo}} for i, n, la, lo in stations],
            "readings": [{"timestamp": t, "data": [{"stationId": k, "value": v} for k, v in vals.items()]} for t, vals in times_values],
        }
    }


def test_parse_merges_pages_oldest_first_and_keeps_gaps():
    newer = page([("2026-10-26T22:40:00+08:00", {"S1": 0.4, "S2": 0}), ("2026-10-26T22:35:00+08:00", {"S1": 1.2})])
    older = page([("2026-10-26T22:30:00+08:00", {"S1": 0.0, "S2": 2.0, "S9": -1})])
    out = rg.parse_readings([newer, older])

    assert out["times"] == ["2026-10-26T22:30:00+08:00", "2026-10-26T22:35:00+08:00", "2026-10-26T22:40:00+08:00"]
    assert [s["id"] for s in out["stations"]] == ["S1", "S2"]
    assert out["values"]["S1"] == [0.0, 1.2, 0.4]
    assert out["values"]["S2"] == [2.0, None, 0.0]  # missing reading stays missing
    assert out["unit"] == "mm in 5 minutes"


class FakeService:
    def __init__(self, data):
        self.data = data

    async def gauges(self):
        return self.data


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(rain_router.router, prefix="/api")
    monkeypatch.setattr(rain_router, "latest_wind", lambda: {"speed_kn": 4.0, "dir_deg": 45, "stations": 3, "at": "x"})
    return TestClient(app), monkeypatch


def test_endpoint_returns_gauges_with_wind(client):
    c, mp = client
    data = rg.parse_readings([page([("2026-10-26T22:40:00+08:00", {"S1": 0.4})])])
    mp.setattr(rain_router, "get_rain_gauge_service", lambda: FakeService(data))
    body = c.get("/api/rain/gauges").json()

    assert body["values"]["S1"] == [0.4]
    assert body["wind"]["dir_deg"] == 45


def test_endpoint_says_when_gauges_are_down(client):
    c, mp = client
    mp.setattr(rain_router, "get_rain_gauge_service", lambda: FakeService(None))
    assert c.get("/api/rain/gauges").status_code == 503


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("x", request=None, response=None)
        return self

    def json(self):
        return self._body


class FakeClient:
    def __init__(self, statuses, body):
        self.statuses = list(statuses)
        self.body = body
        self.calls = 0

    async def get(self, url, params=None):
        self.calls += 1
        return FakeResponse(self.statuses.pop(0), self.body)


@pytest.mark.asyncio
async def test_a_rate_limit_is_retried_after_a_wait():
    body = page([(f"2026-10-26T22:{m:02d}:00+08:00", {"S1": 0}) for m in range(0, 60, 4)])
    client = FakeClient([429, 429, 200], body)
    waits = []

    async def sleep(s):
        waits.append(s)

    out = await rg.fetch_gauges(client, datetime(2026, 10, 26, 15, tzinfo=timezone.utc), sleep=sleep)
    assert client.calls == 3
    assert waits == list(rg.RETRY_WAITS)
    assert out["values"]["S1"][-1] == 0


@pytest.mark.asyncio
async def test_last_good_readings_are_kept_through_a_failure(monkeypatch):
    svc = rg.RainGaugeService()
    good = {"times": ["t"], "stations": [], "values": {}}

    async def ok(client, now):
        return dict(good)

    async def fail(client, now):
        import httpx

        raise httpx.HTTPError("429")

    monkeypatch.setattr(rg, "fetch_gauges", ok)
    assert (await svc.gauges())["times"] == ["t"]
    monkeypatch.setattr(rg, "fetch_gauges", fail)
    assert (await svc.gauges(force=True))["times"] == ["t"]
