from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import database
from app.db.database import execute_sql
from app.routers import haze as router_module
from app.services import air_quality as aq
from app.services import haze_scene as hs
from app.services import wind_grid as wg

SGT = timezone(timedelta(hours=8))
END = datetime(2026, 10, 25, 12, 30, tzinfo=SGT)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "_database_url", f"sqlite:///{tmp_path / 'haze.db'}")
    monkeypatch.setattr(database, "_engine", None)
    aq.init_air_quality_table()
    execute_sql("""
        CREATE TABLE weather_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, country TEXT NOT NULL, location TEXT NOT NULL,
            latitude REAL, longitude REAL, temperature REAL, rainfall REAL, humidity REAL,
            wind_speed REAL NOT NULL, wind_direction REAL, pressure REAL, source_api TEXT,
            created_at TEXT
        )
    """)
    yield
    database._engine.dispose()


@pytest.fixture
def service(monkeypatch):
    svc = hs.HazeSceneService()
    monkeypatch.setattr(hs, "_service", svc)
    return svc


class FakeWind:
    """A uniform south-westerly over the whole grid, covering the last 8 days."""

    def __init__(self, grid=None):
        self._grid = grid

    async def grid(self):
        return self._grid


def uniform_grid(u=4.0, v=4.0):
    import numpy as np

    now = int(datetime.now(timezone.utc).timestamp()) // 3600 * 3600
    times = np.arange(now - 8 * 86400, now + 2 * 86400, 3600)
    grid = wg.WindGrid(times=times, lats=wg.LATS.copy(), lons=wg.LONS.copy())
    shape = (len(times), len(wg.LATS), len(wg.LONS))
    for level in wg.LEVELS:
        grid.u[level] = np.full(shape, u)
        grid.v[level] = np.full(shape, v)
    return grid


@pytest.fixture(autouse=True)
def wind(monkeypatch):
    fake = FakeWind(uniform_grid())
    monkeypatch.setattr(wg, "get_wind_grid_service", lambda: fake)
    return fake


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router_module.router, prefix="/api")
    return TestClient(app)


def wind_row(ts, speed, direction, location="Changi", source="api-open.data.gov.sg"):
    return {
        "timestamp": ts, "location": location, "latitude": 1.36, "longitude": 103.98,
        "wind_speed": speed, "wind_direction": direction, "source_api": source,
    }


# --- wind maths --------------------------------------------------------------

def test_wind_from_north_blows_south():
    u, v = hs.to_uv(10, 0)
    assert u == pytest.approx(0, abs=1e-9)
    assert v == pytest.approx(-10)


@pytest.mark.parametrize("direction", [0, 45, 135, 270, 359])
def test_uv_round_trip(direction):
    speed, back = hs.from_uv(*hs.to_uv(5, direction))
    assert speed == pytest.approx(5)
    assert back == pytest.approx(direction % 360, abs=1e-6)


def test_aggregate_wind_averages_vectors_not_angles():
    grid = hs.hour_grid(END, 2)
    rows = [
        wind_row("2026-10-25T12:10:00+08:00", 4, 350),
        wind_row("2026-10-25T12:20:00+08:00", 4, 10),
    ]
    wind = hs.aggregate_wind(rows, grid)

    assert wind["mean"][1]["dir_deg"] in (0, 360)
    assert wind["mean"][1]["speed_kn"] == pytest.approx(3.94, abs=0.01)
    assert wind["mean"][0] is None
    assert wind["station_hourly"]["Changi"][1][1] in (0, 360)


def test_aggregate_wind_reads_naive_timestamps_as_sgt_and_drops_out_of_window():
    grid = hs.hour_grid(END, 1)
    rows = [
        wind_row("2026-10-25T12:05:00", 3, 90),
        wind_row("2026-10-25T09:05:00+08:00", 9, 270),
        wind_row("2026-10-25T12:06:00+08:00", 2, None),
    ]
    wind = hs.aggregate_wind(rows, grid)

    assert wind["mean"] == [{"speed_kn": 3.0, "dir_deg": 90, "stations": 1}]


# --- air quality alignment ---------------------------------------------------

def test_align_air_places_readings_on_the_hour_grid():
    grid = hs.hour_grid(END, 3)
    points = [
        {"timestamp": "2026-10-25T11:00:00+08:00", "regions": {"west": {"psi_24h": 150, "pm25_1h": 61}}},
        {"timestamp": "2026-10-24T11:00:00+08:00", "regions": {"west": {"psi_24h": 1, "pm25_1h": 1}}},
    ]
    air = hs.align_air(points, grid)

    assert air["psi"]["west"] == [None, 150, None]
    assert air["pm25"]["west"] == [None, 61, None]
    assert air["psi"]["east"] == [None, None, None]


def test_missing_air_dates_lists_sgt_days_with_gaps():
    grid = hs.hour_grid(datetime(2026, 10, 25, 1, tzinfo=SGT), 3)  # 23:00, 00:00, 01:00
    air = {"psi": {r: [None, None, 80] for r in aq.REGIONS}}

    assert hs.missing_air_dates(air, grid) == ["2026-10-25", "2026-10-24"]


# --- FIRMS ----------------------------------------------------------------------

FIRMS_CSV = """latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
-0.51,102.1,330.1,0.4,0.4,2026-10-25,0612,N,VIIRS,n,2.0NRT,290.1,12.5,D
-1.2,103.4,340.2,0.4,0.4,2026-10-25,618,N,VIIRS,h,2.0NRT,295.3,40.0,D
-2.0,113.9,300.0,0.4,0.4,2026-10-25,0618,N,VIIRS,l,2.0NRT,280.0,99.0,D
"""


def test_parse_firms_csv_drops_low_confidence():
    rows = hs.parse_firms_csv(FIRMS_CSV)

    assert [r[2] for r in rows] == [12.5, 40.0]
    assert datetime.fromtimestamp(rows[1][3], SGT).isoformat() == "2026-10-25T14:18:00+08:00"


def test_merge_hotspots_joins_one_pass_in_one_cell_and_sorts_by_power():
    t = 1_792_000_000
    rows = [
        [-1.200, 103.400, 10.0, t],
        [-1.203, 103.404, 5.0, t],  # same ~2 km cell, same pass
        [-1.203, 103.404, 7.0, t + 3600],  # next pass: kept apart
        [-2.000, 113.900, 30.0, t],
        [-3.000, 113.000, 99.0, t - 90000],  # before the window
    ]
    points = hs.merge_hotspots(rows, since=t - 86400)

    assert [p[2] for p in points] == [30.0, 15.0, 7.0]
    assert points[1][4] == 2
    assert points[1][:2] == [-1.2015, 103.402]
    assert sum(p[4] for p in points) == 4


def test_parse_firms_csv_rejects_error_text():
    with pytest.raises(ValueError):
        hs.parse_firms_csv("Invalid MAP_KEY.")


# --- endpoint -------------------------------------------------------------------

def seed(now):
    hour = hs.hour_floor(now)
    psi = {(hour - timedelta(hours=h)).isoformat(): {r: 100 + h for r in aq.REGIONS} for h in range(30)}
    pm25 = {(hour - timedelta(hours=h)).isoformat(): {r: 40 + h for r in aq.REGIONS} for h in range(30)}
    aq.store_readings(psi, pm25, now.isoformat())
    for h in range(80):
        ts = (hour - timedelta(hours=h) + timedelta(minutes=10)).astimezone(SGT).isoformat()
        execute_sql(
            """INSERT INTO weather_records (timestamp, country, location, latitude, longitude,
               wind_speed, wind_direction, source_api)
               VALUES (:ts, 'singapore', 'Changi', 1.36, 103.98, 5, 225, 'api-open.data.gov.sg')""",
            {"ts": ts},
        )
    execute_sql(
        """INSERT INTO weather_records (timestamp, country, location, latitude, longitude,
           wind_speed, wind_direction, source_api)
           VALUES (:ts, 'malaysia', 'Johor Bahru', 1.46, 103.76, 50, 0, 'open-meteo.com')""",
        {"ts": hour.astimezone(SGT).isoformat()},
    )


def test_scene_endpoint_shapes_data_and_flags_missing_firms_key(temp_db, service, client, monkeypatch):
    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)
    backfilled = []

    async def fake_backfill(dates):
        backfilled.extend(dates)
        return 0

    monkeypatch.setattr(hs, "backfill_air", fake_backfill)
    seed(datetime.now(timezone.utc))

    body = client.get("/api/haze/scene?hours=24").json()

    assert len(body["hours"]) == 24
    assert body["hours"][-1].endswith("+08:00")
    assert set(body["psi"]) == set(aq.REGIONS)
    assert body["psi"]["west"][-1] == 100 and body["psi"]["west"][0] == 123
    assert body["coverage"] == {"hours": 24, "air_hours": 24, "wind_hours": 24}
    assert body["wind"]["mean"][-1] == {"speed_kn": 5.0, "dir_deg": 225, "stations": 1}
    assert [s["name"] for s in body["wind"]["stations"]] == ["Changi"]
    air = body["air_path"]
    assert air["status"] == "ok"
    assert set(air["paths"]) == {"850hPa", "925hPa"}
    assert len(air["paths"]["850hPa"]) == 24
    path = air["paths"]["850hPa"][-1]
    # Air moving north-east at 5.7 m/s came from the south-west.
    origin = path["points"][-1]
    assert origin[0] < wg.SINGAPORE[0] and origin[1] < wg.SINGAPORE[1]
    assert path["points"][0][:2] == [round(wg.SINGAPORE[0], 3), round(wg.SINGAPORE[1], 3)]
    speed, direction = air["sg_wind"]["850hPa"][-1]
    assert speed == pytest.approx(5.7, abs=0.1) and direction == pytest.approx(225, abs=0.5)
    assert body["hotspots"]["status"] == "unavailable"
    assert body["hotspots"]["signup"].startswith("https://firms.modaps.eosdis.nasa.gov")
    assert body["bands"]["pm25"][0] == {
        "max": 55, "key": "normal", "label": "Normal", "advice": "Continue with normal activities"
    }
    assert backfilled == []


def test_scene_backfills_days_without_psi(temp_db, service, client, monkeypatch):
    calls = []

    async def fake_backfill(dates):
        calls.append(dates)
        return 0

    monkeypatch.setattr(hs, "backfill_air", fake_backfill)
    body = client.get("/api/haze/scene?hours=24").json()

    assert calls and all(len(d) == 10 for d in calls[0])
    assert body["coverage"]["air_hours"] == 0
    assert body["latest"] == {"air": None, "wind": None}


def test_scene_uses_firms_when_key_is_set(temp_db, service, client, monkeypatch):
    monkeypatch.setenv("FIRMS_MAP_KEY", "test-key")
    monkeypatch.setattr(hs, "backfill_air", lambda dates: _noop())
    seen = {}

    async def fake_fetch(key, days, since=None):
        seen["key"] = key
        seen["days"] = days
        return {"status": "ok", "days": days, "bbox": hs.FIRMS_BBOX, "points": hs.merge_hotspots(hs.parse_firms_csv(FIRMS_CSV))}

    monkeypatch.setattr(hs, "fetch_hotspots", fake_fetch)
    body = client.get("/api/haze/scene?hours=24").json()

    assert seen["key"] == "test-key"
    assert seen["days"] in (2, 3)  # 24-hour window plus the day before, in UTC days
    assert body["hotspots"]["status"] == "ok"
    assert len(body["hotspots"]["points"]) == 2


async def _noop():
    return 0


def test_scene_says_when_the_air_path_has_no_wind(temp_db, service, client, monkeypatch, wind):
    monkeypatch.setattr(hs, "backfill_air", lambda dates: _noop())
    wind._grid = None
    body = client.get("/api/haze/scene?hours=24").json()

    assert body["air_path"]["status"] == "unavailable"
    assert "paths" not in body["air_path"]


def test_wind_field_endpoint_covers_the_window_and_a_day_either_side(client):
    body = client.get("/api/haze/wind-field?hours=24").json()

    assert body["status"] == "ok"
    assert body["level"] == "850hPa"
    assert body["hours"] == 24 + 48
    assert len(body["u"]) == body["hours"] * len(body["lats"]) * len(body["lons"])
    assert body["u"][0] == 40 and body["v"][0] == 40
    assert body["forecast_from"] is not None


def test_wind_field_endpoint_reports_missing_wind(client, wind):
    wind._grid = None
    assert client.get("/api/haze/wind-field?hours=24").json()["status"] == "unavailable"


def test_scene_rejects_unsupported_window(client):
    assert client.get("/api/haze/scene?hours=500").status_code == 400


def test_scene_is_cached(temp_db, service, client, monkeypatch):
    monkeypatch.setattr(hs, "backfill_air", lambda dates: _noop())
    first = client.get("/api/haze/scene?hours=24").json()
    seed(datetime.now(timezone.utc))
    second = client.get("/api/haze/scene?hours=24").json()

    assert second["fetched_at"] == first["fetched_at"]
    assert second["coverage"]["air_hours"] == 0
