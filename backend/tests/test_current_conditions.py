from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import weather
from app.services.current_conditions import (
    describe_condition,
    is_daytime_sgt,
    parse_reading_time,
    pick_current_reading,
)

# 00:39 SGT on 26 Oct 2026, the time of the reported bug.
NOW = datetime(2026, 10, 25, 16, 39, tzinfo=timezone.utc)


def _row(ts, dist=0.001, temp=25.0, humidity=96.0, rainfall=0.0):
    return {
        "location": "Clementi Road",
        "temperature": temp,
        "humidity": humidity,
        "wind_speed": 1.0,
        "pressure": None,
        "rainfall": rainfall,
        "country": "singapore",
        "source_api": "api-open.data.gov.sg",
        "timestamp": ts,
        "approx_dist": dist,
    }


def test_parse_reading_time_treats_naive_as_utc():
    assert parse_reading_time("2026-10-25T16:00:00") == datetime(2026, 10, 25, 16, tzinfo=timezone.utc)
    assert parse_reading_time("2026-10-26T00:30:00+08:00") == datetime(2026, 10, 25, 16, 30, tzinfo=timezone.utc)
    assert parse_reading_time("garbage") is None


def test_afternoon_reading_is_stale_at_night():
    # 15:03 SGT passes a naive-UTC text cutoff but is 9.5 hours old.
    afternoon = _row("2026-10-25T15:03:00+08:00", temp=31.6, humidity=67.9)
    assert pick_current_reading([afternoon], NOW) is None


def test_newest_reading_of_nearest_station_wins_regardless_of_row_order():
    rows = [
        _row("2026-10-26T00:10:00+08:00", temp=25.6),
        _row("2026-10-26T00:30:00+08:00", temp=25.2),
        _row("2026-10-26T00:20:00+08:00", temp=25.4),
        _row("2026-10-26T00:35:00+08:00", dist=0.2, temp=27.0),
    ]
    for order in (rows, list(reversed(rows))):
        assert pick_current_reading(order, NOW)["temperature"] == 25.2


def test_future_readings_are_ignored():
    assert pick_current_reading([_row("2026-10-26T03:00:00+08:00")], NOW) is None


def test_daytime_window_in_singapore():
    assert not is_daytime_sgt(NOW)
    assert is_daytime_sgt(datetime(2026, 10, 26, 4, 0, tzinfo=timezone.utc))  # 12:00 SGT


@pytest.mark.parametrize(
    "rainfall,sky,is_day,expected",
    [
        (0, "Clear", True, "Sunny"),
        (0, "Clear", False, "Clear"),
        (0, "Mainly Clear", False, "Clear"),
        (0, "Overcast", False, "Overcast"),
        (0, None, False, "Fair (Night)"),
        (0, "Light Showers", True, "Fair"),
        (0.4, "Clear", True, "Light Rain"),
        (8, "Clear", False, "Rainy"),
    ],
)
def test_describe_condition(rainfall, sky, is_day, expected):
    assert describe_condition(rainfall, sky, is_day) == expected


def test_hot_temperature_alone_never_means_sunny():
    assert describe_condition(0, None, False) != "Sunny"


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(weather.router)

    class _Row:
        def __init__(self, m):
            self._mapping = m

    rows = [
        _Row(_row("2026-10-25T15:03:00+08:00", temp=31.6, humidity=67.9)),
        _Row(_row("2026-10-26T00:30:00+08:00", temp=25.2, humidity=95.5)),
    ]
    monkeypatch.setattr(weather, "fetch_all", lambda sql, params: rows)

    async def fake_open_meteo(lat, lng):
        return {"pressure": 1009.0, "visibility": 10.0, "uv_index": 0.0, "condition": "Clear", "is_day": 0}

    monkeypatch.setattr(weather, "fetch_from_open_meteo", fake_open_meteo)

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(weather, "datetime", _Clock)
    return TestClient(app)


def test_endpoint_returns_the_current_night_reading(client):
    body = client.get("/api/weather?lat=1.3329&lng=103.7764").json()
    assert body["temperature"] == 25.2
    assert body["humidity"] == 95.5
    assert body["condition"] == "Clear"
    assert body["is_day"] is False
    assert body["timestamp"] == "2026-10-26T00:30:00+08:00"
