import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import database
from app.routers import air_quality as router_module
from app.services import air_quality as aq

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "_database_url", f"sqlite:///{tmp_path / 'aq.db'}")
    monkeypatch.setattr(database, "_engine", None)
    aq.init_air_quality_table()
    yield
    database._engine.dispose()


@pytest.fixture
def service(monkeypatch):
    svc = aq.AirQualityService()
    monkeypatch.setattr(aq, "_service", svc)
    return svc


def fake_fetch(responses: dict):
    async def _fetch(client, path, date=None):
        result = responses[path]
        if isinstance(result, Exception):
            raise result
        return result

    return _fetch


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router_module.router, prefix="/api")
    return TestClient(app)


# --- parsing ---------------------------------------------------------------

def test_parse_series_psi_fixture_returns_regional_24h_psi():
    series = aq.parse_series(load("air_quality_psi_latest.json"), "psi_twenty_four_hourly")

    assert series == {
        "2026-10-25T07:00:00+00:00": {"north": 97, "south": 96, "east": 105, "west": 119, "central": 102}
    }


def test_parse_series_pm25_fixture_returns_regional_1h_pm25():
    series = aq.parse_series(load("air_quality_pm25_latest.json"), "pm25_one_hourly")

    assert series["2026-10-25T07:00:00+00:00"]["central"] == 27


def test_parse_series_day_fixture_returns_every_hour():
    series = aq.parse_series(load("air_quality_pm25_day.json"), "pm25_one_hourly")

    assert len(series) == 16
    assert min(series) == "2026-10-24T16:00:00+00:00"


def test_parse_series_error_payload_raises():
    payload = {"code": 4, "name": "ERROR_PARAMS", "data": None, "errorMsg": "Invalid date format."}

    with pytest.raises(aq.AirQualityError, match="Invalid date format"):
        aq.parse_series(payload, "psi_twenty_four_hourly")


def test_parse_series_empty_items_raises():
    payload = {"code": 0, "data": {"items": []}, "errorMsg": ""}

    with pytest.raises(aq.AirQualityError):
        aq.parse_series(payload, "pm25_one_hourly")


def test_parse_region_locations_reads_label_points():
    regions = aq.parse_region_locations(load("air_quality_psi_latest.json"))

    assert regions["east"] == {"lat": 1.35735, "lng": 103.94}
    assert set(regions) == set(aq.REGIONS)


# --- bands -----------------------------------------------------------------

@pytest.mark.parametrize(
    "value,key",
    [
        (0, "good"), (50, "good"), (51, "moderate"), (100, "moderate"),
        (101, "unhealthy"), (200, "unhealthy"), (201, "very_unhealthy"),
        (300, "very_unhealthy"), (301, "hazardous"), (500, "hazardous"),
    ],
)
def test_psi_band_edges(value, key):
    assert aq.psi_band(value)["key"] == key


@pytest.mark.parametrize(
    "value,key",
    [
        (0, "normal"), (55, "normal"), (56, "elevated"), (150, "elevated"),
        (151, "high"), (250, "high"), (251, "very_high"),
    ],
)
def test_pm25_band_edges(value, key):
    assert aq.pm25_band(value)["key"] == key


def test_band_of_none_is_none():
    assert aq.psi_band(None) is None
    assert aq.pm25_band(None) is None


def test_psi_band_carries_nea_advice():
    assert aq.psi_band(150)["advice"] == "Reduce prolonged or strenuous outdoor physical exertion"


# --- latest / failure path -------------------------------------------------

def snapshot_from_fixtures() -> aq.Snapshot:
    psi_raw = load("air_quality_psi_latest.json")
    return aq.Snapshot(
        psi=aq.parse_series(psi_raw, "psi_twenty_four_hourly"),
        pm25=aq.parse_series(load("air_quality_pm25_latest.json"), "pm25_one_hourly"),
        regions=aq.parse_region_locations(psi_raw),
        fetched_at=datetime(2026, 10, 25, 7, 20, tzinfo=timezone.utc),
    )


def test_build_latest_national_is_regional_range_banded_by_max():
    result = aq.build_latest(snapshot_from_fixtures(), datetime(2026, 10, 25, 7, 30, tzinfo=timezone.utc))

    assert result["status"] == "ok"
    assert result["observed_at"] == "2026-10-25T15:00:00+08:00"
    assert result["national"]["psi_24h_min"] == 96
    assert result["national"]["psi_24h_max"] == 119
    assert result["national"]["psi_band"]["key"] == "unhealthy"


def test_build_latest_old_reading_is_marked_stale():
    result = aq.build_latest(snapshot_from_fixtures(), datetime(2026, 10, 25, 10, 0, tzinfo=timezone.utc))

    assert result["status"] == "stale"


@pytest.mark.asyncio
async def test_refresh_failure_reports_unavailable_with_last_good_timestamp(temp_db, service, monkeypatch):
    aq.store_readings({"2026-10-25T06:00:00+00:00": {"central": 90}}, {}, "2026-10-25T06:10:00+00:00")
    monkeypatch.setattr(
        aq, "fetch_payload", fake_fetch({aq.PSI_PATH: aq.AirQualityError("boom"), aq.PM25_PATH: {}})
    )

    await service.refresh(force=True)
    result = service.latest()

    assert result["status"] == "unavailable"
    assert result["regions"] == [] and result["national"] is None
    assert result["last_good_observed_at"] == "2026-10-25T14:00:00+08:00"
    assert "boom" in result["error"]


@pytest.mark.asyncio
async def test_refresh_failure_after_success_drops_old_readings(temp_db, service, monkeypatch):
    good = {aq.PSI_PATH: load("air_quality_psi_latest.json"), aq.PM25_PATH: load("air_quality_pm25_latest.json")}
    monkeypatch.setattr(aq, "fetch_payload", fake_fetch(good))
    await service.refresh(force=True)
    monkeypatch.setattr(aq, "fetch_payload", fake_fetch({**good, aq.PM25_PATH: aq.AirQualityError("down")}))

    await service.refresh(force=True)

    assert service.latest()["status"] == "unavailable"
    assert service.latest()["last_good_observed_at"] == "2026-10-25T15:00:00+08:00"


@pytest.mark.asyncio
async def test_refresh_success_stores_readings(temp_db, service, monkeypatch):
    monkeypatch.setattr(
        aq,
        "fetch_payload",
        fake_fetch({aq.PSI_PATH: load("air_quality_psi_latest.json"), aq.PM25_PATH: load("air_quality_pm25_latest.json")}),
    )

    await service.refresh(force=True)

    row = database.fetch_one(
        "SELECT psi_24h, pm25_1h FROM air_quality_readings WHERE region = 'west'"
    )
    assert (row[0], row[1]) == (119, 20)


def test_store_readings_upsert_does_not_null_existing_values(temp_db):
    ts = "2026-10-25T07:00:00+00:00"
    aq.store_readings({ts: {"north": 97}}, {ts: {"north": 22}}, ts)

    aq.store_readings({ts: {"north": 98}}, {}, ts)

    row = database.fetch_one("SELECT psi_24h, pm25_1h FROM air_quality_readings WHERE region = 'north'")
    assert (row[0], row[1]) == (98, 22)


# --- endpoints -------------------------------------------------------------

def test_latest_endpoint_returns_regions_and_bands(temp_db, service, client, monkeypatch):
    monkeypatch.setattr(
        aq,
        "fetch_payload",
        fake_fetch({aq.PSI_PATH: load("air_quality_psi_latest.json"), aq.PM25_PATH: load("air_quality_pm25_latest.json")}),
    )

    response = client.get("/api/air-quality/latest")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] in ("ok", "stale")
    central = next(r for r in body["regions"] if r["region"] == "central")
    assert central["psi_24h"] == 102 and central["psi_band"]["label"] == "Unhealthy"
    assert central["pm25_1h"] == 27 and central["pm25_band"]["label"] == "Normal"
    assert body["links"]["haze"] == "https://www.haze.gov.sg/"


def test_latest_endpoint_upstream_down_returns_200_unavailable(temp_db, service, client, monkeypatch):
    monkeypatch.setattr(
        aq, "fetch_payload", fake_fetch({aq.PSI_PATH: aq.AirQualityError("x"), aq.PM25_PATH: aq.AirQualityError("y")})
    )

    body = client.get("/api/air-quality/latest").json()

    assert body["status"] == "unavailable"
    assert body["last_good_observed_at"] is None


def test_history_endpoint_returns_recent_points_oldest_first(temp_db, client):
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    old, recent = (now - timedelta(hours=30)).isoformat(), (now - timedelta(hours=1)).isoformat()
    latest = now.isoformat()
    aq.store_readings(
        {old: {"central": 40}, recent: {"central": 60}, latest: {"central": 70}}, {latest: {"central": 15}}, latest
    )

    body = client.get("/api/air-quality/history?hours=24&region=central").json()

    assert [p["regions"]["central"]["psi_24h"] for p in body["points"]] == [60, 70]
    assert body["points"][-1]["timestamp"].endswith("+08:00")


def test_history_endpoint_rejects_unknown_region(temp_db, client):
    assert client.get("/api/air-quality/history?region=johor").status_code == 400


@pytest.mark.parametrize("hours", [0, 169])
def test_history_endpoint_bounds_hours(temp_db, client, hours):
    assert client.get(f"/api/air-quality/history?hours={hours}").status_code == 422


# --- upstream HTTP handling ------------------------------------------------

def _client_with(handler):
    import httpx

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_fetch_payload_retries_once_after_rate_limit(monkeypatch):
    import httpx

    monkeypatch.setattr(aq, "RATE_LIMIT_WAIT_SECONDS", 0)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={"code": 24})
        return httpx.Response(200, json=load("air_quality_pm25_latest.json"))

    async with _client_with(handler) as client:
        payload = await aq.fetch_payload(client, aq.PM25_PATH)

    assert len(calls) == 2 and payload["code"] == 0


@pytest.mark.asyncio
async def test_fetch_payload_http_error_names_status(monkeypatch):
    import httpx

    monkeypatch.setattr(aq, "RATE_LIMIT_WAIT_SECONDS", 0)

    async with _client_with(lambda r: httpx.Response(503)) as client:
        with pytest.raises(aq.AirQualityError, match="HTTP 503"):
            await aq.fetch_payload(client, aq.PSI_PATH)
