"""Climate figures on the Forecast model tab must be per-gauge or island averages."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("statsmodels")

from ml.train_full_analysis import compute_climate_trends, island_hourly_rainfall

N_GAUGES = 60


def _raw_readings(start: str, end: str, storm_at: str) -> pd.DataFrame:
    """5-min readings for N_GAUGES gauges: dry except one storm hour: 20 mm per 5 min on S00, 2 mm on the rest."""
    ts = pd.date_range(start, end, freq="5min", tz="Asia/Singapore", inclusive="left")
    storm = (ts >= pd.Timestamp(storm_at, tz="Asia/Singapore")) & (ts < pd.Timestamp(storm_at, tz="Asia/Singapore") + pd.Timedelta("1h"))
    frames = []
    for g in range(N_GAUGES):
        value = np.where(storm, 20.0 if g == 0 else 2.0, 0.0)
        frames.append(pd.DataFrame({"timestamp": ts, "station_id": f"S{g:02d}", "reading_value": value}))
    return pd.concat(frames, ignore_index=True)


def _hourly(index: pd.DatetimeIndex, value: float) -> pd.Series:
    return pd.Series(value, index=index)


@pytest.fixture(scope="module")
def trends():
    # 2016 is a stub (two days), 2017-2019 are full years.
    raw = _raw_readings("2016-12-30", "2020-01-01", storm_at="2018-06-01 10:00")
    rain = island_hourly_rainfall(raw)
    idx = rain.index
    return compute_climate_trends(rain, _hourly(idx, 28.0), _hourly(idx, 80.0), _hourly(idx, 8.0))


def test_wettest_hour_is_one_gauge_not_a_sum_across_gauges(trends):
    rec = trends["all_time_records"]
    # Gauge S00 got 12 x 20 mm = 240 mm in the storm hour; the others 24 mm.
    assert rec["wettest_station_hour"]["value_mm"] == pytest.approx(240.0)
    assert rec["wettest_island_hour"]["value_mm"] == pytest.approx((240 + 59 * 24) / 60)
    assert "wettest_hour" not in rec
    # The old island-wide sum would have been 240 + 59 * 24 = 1656 mm.
    assert rec["wettest_station_hour"]["value_mm"] < 300


def test_annual_totals_are_island_averages(trends):
    total_2018 = trends["annual"]["2018"]["rainfall"]["total_mm"]
    assert total_2018 == pytest.approx((240 + 59 * 24) / 60, abs=0.1)


def test_partial_years_are_left_out(trends):
    assert trends["years_covered"] == [2017, 2018, 2019]
    assert trends["partial_years_excluded"] == [2016]
    assert "2016" not in trends["annual"]


def test_category_shares_count_gauge_hours(trends):
    pct = trends["annual"]["2018"]["rainfall"]["rain_category_pct"]
    assert sum(pct.values()) == pytest.approx(100, abs=0.2)
    rain = trends["annual"]["2018"]["rainfall"]
    assert rain["thundery_station_hours"] == 1  # only S00 crossed 30 mm in an hour
