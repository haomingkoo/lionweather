import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.services import wind_grid as wg

T0 = int(datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp())
HOURS = 100


def uniform(u: float, v: float, hours: int = HOURS, levels=wg.LEVELS) -> wg.WindGrid:
    times = np.arange(hours) * 3600 + T0
    grid = wg.WindGrid(times=times, lats=wg.LATS.copy(), lons=wg.LONS.copy())
    shape = (hours, len(wg.LATS), len(wg.LONS))
    for level in levels:
        grid.u[level] = np.full(shape, float(u))
        grid.v[level] = np.full(shape, float(v))
    return grid


def km_east(lon_a, lon_b, lat):
    return (lon_b - lon_a) * wg.M_PER_DEG / 1000 * math.cos(math.radians(lat))


def test_uniform_westerly_traces_back_to_the_west_at_the_wind_speed():
    grid = uniform(5.0, 0.0)  # 5 m/s towards the east: 18 km per hour
    end = T0 + 80 * 3600
    path = wg.back_trajectory(grid, "850hPa", end, hours=24)

    assert path["complete"]
    assert [p[2] for p in path["points"]] == list(range(25))
    lat0, lon0, _ = path["points"][0]
    lat24, lon24, _ = path["points"][-1]
    assert lat24 == pytest.approx(lat0, abs=1e-3)
    assert km_east(lon24, lon0, lat0) == pytest.approx(5 * 24 * 3.6, rel=0.01)


def test_uniform_southerly_traces_back_to_the_south():
    grid = uniform(0.0, 10.0)  # towards the north
    path = wg.back_trajectory(grid, "925hPa", T0 + 50 * 3600, hours=10)
    lat0, lon0, _ = path["points"][0]
    lat10, lon10, _ = path["points"][-1]

    assert lon10 == pytest.approx(lon0, abs=1e-6)
    assert (lat0 - lat10) * wg.M_PER_DEG == pytest.approx(10 * 3600 * 10, rel=1e-3)


def test_each_hour_moves_the_same_distance_in_a_uniform_field():
    grid = uniform(-3.0, 4.0)  # 5 m/s
    pts = wg.back_trajectory(grid, "10m", T0 + 60 * 3600, hours=12)["points"]
    steps = [
        math.hypot((b[0] - a[0]) * wg.M_PER_DEG, (b[1] - a[1]) * wg.M_PER_DEG * math.cos(math.radians(a[0])))
        for a, b in zip(pts, pts[1:])
    ]
    assert all(s == pytest.approx(5 * 3600, rel=0.01) for s in steps)


def test_path_stops_at_the_grid_edge():
    grid = uniform(30.0, 0.0)  # 108 km/h: crosses the 9 degrees to 95E in under 10 hours
    path = wg.back_trajectory(grid, "850hPa", T0 + 90 * 3600, hours=72)

    assert not path["complete"]
    assert len(path["points"]) < 12
    assert all(p[1] >= wg.LONS[0] for p in path["points"])


def test_path_stops_where_the_grid_hours_run_out():
    grid = uniform(1.0, 0.0, hours=6)
    path = wg.back_trajectory(grid, "850hPa", T0 + 5 * 3600, hours=24)

    assert not path["complete"]
    assert path["points"][-1][2] == 5


def test_velocity_interpolates_in_time_and_space():
    grid = uniform(0.0, 0.0, hours=2)
    grid.u["850hPa"][1] = 10.0
    grid.v["850hPa"][:, :, 1] = 4.0  # only the 96E column

    u, v = grid.velocity("850hPa", T0 + 1800, 0.0, 95.5)
    assert u == pytest.approx(5.0)
    assert v == pytest.approx(2.0)
    assert grid.velocity("850hPa", T0, 0.0, 130.0) is None
    assert grid.velocity("850hPa", T0 - 1, 0.0, 100.0) is None


def test_missing_values_stop_the_path_instead_of_inventing_wind():
    grid = uniform(5.0, 0.0)
    grid.u["850hPa"][:, :, :8] = np.nan  # no data west of 103E
    path = wg.back_trajectory(grid, "850hPa", T0 + 80 * 3600, hours=48)

    assert not path["complete"]
    assert path["points"][-1][1] > 102.0


def test_parse_open_meteo_builds_components_from_speed_and_direction():
    lats, lons = [0.0, 1.0], [100.0, 101.0]
    hourly = {"time": [T0, T0 + 3600]}
    for level in wg.LEVELS:
        hourly[f"wind_speed_{level}"] = [10.0, None]
        hourly[f"wind_direction_{level}"] = [270.0, 90.0]  # from the west, then gap
    payload = [{"hourly": hourly} for _ in range(4)]
    grid = wg.parse_open_meteo(payload, lats=lats, lons=lons)

    assert grid.u["850hPa"][0, 0, 0] == pytest.approx(10.0)
    assert grid.v["850hPa"][0, 0, 0] == pytest.approx(0.0, abs=1e-9)
    assert np.isnan(grid.u["10m"][1, 1, 1])
    with pytest.raises(ValueError):
        wg.parse_open_meteo(payload[:3], lats=lats, lons=lons)


def test_field_payload_packs_tenths_and_marks_the_forecast(monkeypatch):
    grid = uniform(1.25, -2.0, hours=48)
    start = datetime.fromtimestamp(T0 + 10 * 3600, timezone.utc)
    body = wg.field_payload(grid, start, start + timedelta(hours=5))

    assert body["hours"] == 6
    assert body["t0"] == T0 + 10 * 3600
    assert len(body["u"]) == 6 * len(wg.LATS) * len(wg.LONS)
    assert body["u"][0] == 12 and body["v"][0] == -20
    assert body["forecast_from"] is None  # all in the past


def test_from_uv_inverts_to_uv():
    for direction in (0, 45, 200, 359):
        speed, back = wg.from_uv(*wg.to_uv(7.0, direction))
        assert speed == pytest.approx(7.0)
        assert back == pytest.approx(direction, abs=1e-6)
