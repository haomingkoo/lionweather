"""Open-Meteo collection under rate limiting: batching, Retry-After, and reporting failures."""

import logging
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services import data_collector as dc
from app.services.data_collector import DataCollector, RateLimitedError


def _batch_response(url, current_for=lambda i: {"temperature_2m": float(i)}):
    """Answer a multi-location request the way Open-Meteo does: one object per coordinate."""
    lats = parse_qs(urlparse(url).query)["latitude"][0].split(",")
    out = []
    for i in range(len(lats)):
        item = {"current": current_for(i)}
        if i:
            item["location_id"] = i
        out.append(item)
    return out


@pytest.fixture
def no_wait():
    with patch.object(dc, "_wait", new_callable=AsyncMock) as wait:
        yield wait


async def test_malaysia_cities_go_out_in_one_request_and_map_back_by_position(no_wait):
    collector = DataCollector()
    with patch.object(collector, "_fetch_json", new_callable=AsyncMock) as fetch:
        fetch.side_effect = lambda session, url: _batch_response(url)
        records = await collector.fetch_malaysia_data()

    assert fetch.call_count == 1
    assert len(records) == 30
    by_city = {r.location: r.temperature for r in records}
    assert by_city["Kuala Lumpur"] == 0.0
    assert by_city["Klang"] == 9.0
    assert by_city["Muar"] == 21.0
    assert by_city["Temerloh"] == 29.0


async def test_retry_after_is_waited_out_then_the_batch_succeeds(no_wait):
    collector = DataCollector()
    calls = []

    async def fetch(session, url):
        calls.append(url)
        if len(calls) == 1:
            raise RateLimitedError(url, retry_after=7.0)
        return _batch_response(url)

    with patch.object(collector, "_fetch_json", side_effect=fetch):
        records = await collector.fetch_indonesia_data()

    no_wait.assert_awaited_once_with(7.0)
    assert len(records) == 30
    report = collector.last_reports["indonesia"]
    assert (report.requested, report.ok, report.rate_limited, report.failed) == (30, 30, 0, 0)


async def test_persistent_429_stops_after_bounded_attempts_and_names_every_city(no_wait):
    collector = DataCollector()
    with patch.object(collector, "_fetch_json", new_callable=AsyncMock) as fetch:
        fetch.side_effect = RateLimitedError("u", retry_after=1.0)
        records = await collector.fetch_indonesia_data()

    assert fetch.call_count == dc.OPEN_METEO_MAX_ATTEMPTS == 3
    assert records == []
    report = collector.last_reports["indonesia"]
    assert (report.requested, report.ok, report.rate_limited, report.failed) == (30, 0, 30, 0)
    assert {"Jayapura", "Surakarta"} <= {c["city"] for c in report.failed_cities}


async def test_retry_after_longer_than_the_cap_is_not_slept_through(no_wait):
    collector = DataCollector()
    with patch.object(collector, "_fetch_json", new_callable=AsyncMock) as fetch:
        fetch.side_effect = RateLimitedError("u", retry_after=3600.0)
        await collector.fetch_malaysia_data()

    assert fetch.call_count == 1
    no_wait.assert_not_awaited()
    assert collector.last_reports["malaysia"].rate_limited == 30


async def test_city_without_current_data_in_the_batch_is_reported_failed(no_wait):
    collector = DataCollector()
    muar = 21
    with patch.object(collector, "_fetch_json", new_callable=AsyncMock) as fetch:
        fetch.side_effect = lambda session, url: _batch_response(
            url, current_for=lambda i: None if i == muar else {"temperature_2m": 30.0}
        )
        records = await collector.fetch_malaysia_data()

    assert len(records) == 29
    assert "Muar" not in {r.location for r in records}
    report = collector.last_reports["malaysia"]
    assert (report.ok, report.failed) == (29, 1)
    assert report.failed_cities == [{"country": "malaysia", "city": "Muar", "reason": "no current data in response"}]


class _FakeResponse:
    def __init__(self, status, headers):
        self.status = status
        self.headers = headers

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def text(self):
        return '{"error":true,"reason":"Minutely API request limit exceeded."}'

    def raise_for_status(self):
        raise AssertionError("429 must be turned into RateLimitedError before raise_for_status")


class _FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, url, headers=None):
        return self.response


async def test_http_429_becomes_rate_limited_error_carrying_retry_after():
    collector = DataCollector()
    session = _FakeSession(_FakeResponse(429, {"Retry-After": "12"}))

    with pytest.raises(RateLimitedError) as err:
        await collector._fetch_json(session, "https://api.open-meteo.com/v1/forecast?x=1")

    assert err.value.retry_after == 12.0
    assert "Minutely API request limit exceeded" in str(err.value)


async def test_run_summary_is_logged_and_kept_for_the_health_output(no_wait, caplog):
    collector = DataCollector()

    async def fetch(session, url):
        if "latitude=-6.2088" in url:
            raise RateLimitedError(url, retry_after=1.0)
        return _batch_response(url)

    caplog.set_level(logging.INFO, logger="app.services.data_collector")
    with patch.object(collector, "fetch_singapore_data", new_callable=AsyncMock, return_value=[]), \
         patch.object(collector, "_fetch_json", side_effect=fetch):
        records = await collector.collect_all_sources()

    assert len(records) == 30
    assert "Open-Meteo run summary: requested=60 ok=30 rate_limited=30 failed=0" in caplog.text
    summary = dc.get_last_collection_summary()
    assert (summary["requested"], summary["ok"], summary["rate_limited"], summary["failed"]) == (60, 30, 30, 0)
    failed = {(c["country"], c["city"]) for c in summary["failed_cities"]}
    assert ("indonesia", "Jayapura") in failed and len(failed) == 30


def test_status_is_degraded_and_lists_cities_missing_from_the_last_run(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr(dc, "_last_collection_summary", {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "requested": 60, "ok": 58, "rate_limited": 2, "failed": 0,
        "failed_cities": [
            {"country": "indonesia", "city": "Jayapura", "reason": "rate limited (HTTP 429)"},
            {"country": "malaysia", "city": "Klang", "reason": "rate limited (HTTP 429)"},
        ],
    })

    body = TestClient(app).get("/status").json()

    assert body["status"] == "degraded"
    assert {c["city"] for c in body["last_collection"]["failed_cities"]} == {"Jayapura", "Klang"}


def test_status_stays_healthy_when_the_last_run_got_every_city(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr(dc, "_last_collection_summary", {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "requested": 60, "ok": 60, "rate_limited": 0, "failed": 0, "failed_cities": [],
    })

    body = TestClient(app).get("/status").json()

    assert body["status"] == "healthy"
    assert body["last_collection"]["ok"] == 60


def test_data_gov_sg_429_on_uv_is_logged_not_swallowed(monkeypatch, caplog):
    from app.routers import environmental

    real_client = httpx.Client

    def client_with_429(**kwargs):
        transport = httpx.MockTransport(lambda request: httpx.Response(429, headers={"Retry-After": "30"}))
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(environmental.httpx, "Client", client_with_429)
    caplog.set_level(logging.WARNING, logger="app.routers.environmental")

    assert environmental.fetch_api_data("/v2/real-time/api/uv") is None
    warning = next(r for r in caplog.records if "/v2/real-time/api/uv" in r.getMessage())
    assert warning.levelno == logging.WARNING
    assert "429" in warning.getMessage() and "Retry-After 30" in warning.getMessage()
