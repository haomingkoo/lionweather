"""Pick the current observation for a point and describe it."""
from datetime import datetime, timedelta, timezone

SGT = timezone(timedelta(hours=8))
MAX_AGE = timedelta(hours=1)

# Open-Meteo sky states we trust when the NEA station reports no rain.
_SKY = {"Clear", "Mainly Clear", "Partly Cloudy", "Overcast", "Foggy"}


def parse_reading_time(ts):
    """NEA rows carry +08:00, Open-Meteo rows are naive UTC."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        dt = ts
    else:
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def pick_current_reading(rows, now, max_age=MAX_AGE):
    """Nearest station first, newest reading as tie-break; stale rows are skipped."""
    fresh = []
    for row in rows:
        t = parse_reading_time(row["timestamp"])
        if t is not None and timedelta(0) <= now - t <= max_age + timedelta(minutes=5):
            fresh.append((round(row["approx_dist"] or 0, 6), -t.timestamp(), row))
    if not fresh:
        return None
    fresh.sort(key=lambda x: (x[0], x[1]))
    return fresh[0][2]


def is_daytime_sgt(now):
    """Singapore sunrise is ~6:45-7:15 and sunset ~18:55-19:20 all year."""
    local = now.astimezone(SGT)
    minutes = local.hour * 60 + local.minute
    return 7 * 60 <= minutes < 19 * 60 + 10


def describe_condition(rainfall, sky=None, is_day=True):
    if rainfall and rainfall > 5:
        return "Rainy"
    if rainfall and rainfall > 0:
        return "Light Rain"
    if sky in ("Clear", "Mainly Clear"):
        return "Sunny" if is_day else "Clear"
    if sky in _SKY:
        return sky
    return "Fair" if is_day else "Fair (Night)"
