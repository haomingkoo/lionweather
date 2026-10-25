"""
Data health endpoints for the weather_records table used by the app and ML routes.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException

from app.db.database import fetch_all, fetch_one, is_postgres

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-health", tags=["data-health"])


def _row_dict(row) -> dict[str, Any]:
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _hour_bucket_expr() -> str:
    if is_postgres():
        return "date_trunc('hour', timestamp::timestamp)"
    return "strftime('%Y-%m-%d %H:00:00', timestamp)"


@router.get("/status")
async def get_data_health_status():
    try:
        now = datetime.utcnow()
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        one_day_ago = (now - timedelta(days=1)).isoformat()
        two_days_ago = (now - timedelta(days=2)).isoformat()
        seven_days_ago = (now - timedelta(days=7)).isoformat()

        total = fetch_one("SELECT COUNT(*) AS count FROM weather_records")
        latest = fetch_one("SELECT MAX(timestamp) AS latest FROM weather_records")
        by_country_rows = fetch_all("""
            SELECT country, COUNT(*) AS count
            FROM weather_records
            GROUP BY country
            ORDER BY count DESC
        """)
        recent = fetch_one("""
            SELECT
                SUM(CASE WHEN timestamp > :one_hour THEN 1 ELSE 0 END) AS last_hour,
                SUM(CASE WHEN timestamp > :one_day THEN 1 ELSE 0 END) AS last_24h,
                SUM(CASE WHEN timestamp > :seven_days THEN 1 ELSE 0 END) AS last_7d
            FROM weather_records
        """, {
            "one_hour": one_hour_ago,
            "one_day": one_day_ago,
            "seven_days": seven_days_ago,
        })
        missing = fetch_one("""
            SELECT
                COUNT(CASE WHEN humidity IS NULL THEN 1 END) AS missing_humidity,
                COUNT(CASE WHEN wind_speed IS NULL THEN 1 END) AS missing_wind_speed,
                COUNT(CASE WHEN pressure IS NULL THEN 1 END) AS missing_pressure,
                COUNT(CASE WHEN temperature IS NULL THEN 1 END) AS missing_temperature,
                COUNT(CASE WHEN rainfall < 0 THEN 1 END) AS invalid_rainfall
            FROM weather_records
        """)
        bucket = _hour_bucket_expr()
        ml_hours = fetch_one(f"""
            SELECT COUNT(DISTINCT {bucket}) AS count
            FROM weather_records
            WHERE country = 'singapore'
              AND timestamp > :two_days
              AND temperature IS NOT NULL
              AND rainfall IS NOT NULL
              AND humidity IS NOT NULL
              AND wind_speed IS NOT NULL
        """, {"two_days": two_days_ago})

        total_count = (total._mapping["count"] if total else 0) or 0
        latest_timestamp = latest._mapping["latest"] if latest else None
        recent_map = _row_dict(recent) if recent else {}
        last_hour = recent_map.get("last_hour") or 0
        by_country = {
            row._mapping["country"]: row._mapping["count"]
            for row in by_country_rows
        }

        latest_age_hours = None
        if latest_timestamp:
            try:
                latest_dt = datetime.fromisoformat(str(latest_timestamp).replace("Z", "+00:00"))
                latest_dt = latest_dt.replace(tzinfo=None)
                latest_age_hours = max(0, (now - latest_dt).total_seconds() / 3600)
            except ValueError:
                latest_age_hours = None

        last_24h = recent_map.get("last_24h") or 0
        growth_rate = last_hour if last_hour else last_24h / 24
        expected_per_hour = 90
        recent_singapore_hours = (ml_hours._mapping["count"] if ml_hours else 0) or 0
        freshness_ok = latest_age_hours is not None and latest_age_hours <= 2
        health_score = min(100, (growth_rate / expected_per_hour) * 100) if growth_rate else 0
        if not freshness_ok:
            health_score = min(health_score, 10)

        return {
            "status": "healthy" if health_score > 50 else "degraded" if health_score > 10 else "critical",
            "health_score": round(health_score, 1),
            "total_records": total_count,
            "by_country": by_country,
            "recent_activity": {
                "last_hour": last_hour,
                "last_24_hours": last_24h,
                "last_7_days": recent_map.get("last_7d") or 0,
            },
            "ml_readiness": {
                "recent_singapore_hours": recent_singapore_hours,
                "required_hours": 25,
                "ready": recent_singapore_hours >= 25,
            },
            "latest_timestamp": latest_timestamp,
            "latest_age_hours": round(latest_age_hours, 1) if latest_age_hours is not None else None,
            "missing_data": _row_dict(missing) if missing else {},
            "data_gaps": detect_data_gaps(),
            "growth_rate": {
                "records_per_hour": round(growth_rate, 1),
                "expected_per_hour": expected_per_hour,
                "percentage": round((growth_rate / expected_per_hour) * 100, 1)
                if expected_per_hour else 0,
            },
            "recommendations": generate_recommendations(
                total_count,
                latest_age_hours,
                recent_map,
                recent_singapore_hours,
            ),
        }
    except Exception as e:
        logger.error(f"Failed to get data health status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/gaps")
async def get_data_gaps():
    try:
        gaps = detect_data_gaps()
        return {"total_gaps": len(gaps), "gaps": gaps}
    except Exception as e:
        logger.error(f"Failed to detect data gaps: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/quality")
async def get_data_quality():
    try:
        total_row = fetch_one("SELECT COUNT(*) AS count FROM weather_records")
        total = (total_row._mapping["count"] if total_row else 0) or 0

        if total == 0:
            return {"status": "no_data", "message": "No weather_records rows available"}

        complete_row = fetch_one("""
            SELECT COUNT(*) AS count
            FROM weather_records
            WHERE temperature IS NOT NULL
              AND humidity IS NOT NULL
              AND wind_speed IS NOT NULL
              AND rainfall IS NOT NULL
        """)
        valid_row = fetch_one("""
            SELECT COUNT(*) AS count
            FROM weather_records
            WHERE temperature BETWEEN -50 AND 60
              AND humidity BETWEEN 0 AND 100
              AND wind_speed >= 0
              AND rainfall >= 0
        """)
        duplicate_row = fetch_one("""
            SELECT COUNT(*) AS count FROM (
                SELECT timestamp, country, location, COUNT(*) AS dup_count
                FROM weather_records
                GROUP BY timestamp, country, location
                HAVING COUNT(*) > 1
            ) duplicates
        """)

        complete = complete_row._mapping["count"] if complete_row else 0
        valid = valid_row._mapping["count"] if valid_row else 0
        duplicates = duplicate_row._mapping["count"] if duplicate_row else 0
        completeness = (complete / total) * 100
        validity = (valid / total) * 100
        duplicate_pct = (duplicates / total) * 100
        quality_score = completeness * 0.45 + validity * 0.45 + (100 - duplicate_pct) * 0.10

        return {
            "quality_score": round(quality_score, 1),
            "total_records": total,
            "completeness": {
                "percentage": round(completeness, 1),
                "complete_records": complete,
                "incomplete_records": total - complete,
            },
            "validity": {
                "percentage": round(validity, 1),
                "valid_records": valid,
                "invalid_records": total - valid,
            },
            "duplicates": {
                "count": duplicates,
                "percentage": round(duplicate_pct, 1),
            },
            "status": "excellent" if quality_score > 90 else "good" if quality_score > 70 else "fair" if quality_score > 50 else "poor",
        }
    except Exception as e:
        logger.error(f"Failed to analyze data quality: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/timeline")
async def get_data_timeline():
    try:
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        bucket = _hour_bucket_expr()
        rows = fetch_all(f"""
            SELECT
                {bucket} AS hour,
                COUNT(*) AS count,
                COUNT(DISTINCT country) AS countries
            FROM weather_records
            WHERE timestamp > :seven_days
            GROUP BY hour
            ORDER BY hour DESC
        """, {"seven_days": seven_days_ago})

        return {
            "timeline": [
                {
                    "hour": str(row._mapping["hour"]),
                    "record_count": row._mapping["count"],
                    "countries": row._mapping["countries"],
                }
                for row in rows
            ],
            "period": "last_7_days",
        }
    except Exception as e:
        logger.error(f"Failed to get data timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


def detect_data_gaps() -> list[dict[str, Any]]:
    rows = fetch_all("""
        SELECT timestamp, country, location
        FROM weather_records
        WHERE timestamp > :cutoff
        ORDER BY country, location, timestamp
    """, {"cutoff": (datetime.utcnow() - timedelta(days=7)).isoformat()})

    gaps = []
    last_seen: dict[tuple[str, str], datetime] = {}
    for row in rows:
        item = row._mapping
        key = (item["country"], item["location"])
        try:
            ts = datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            continue

        previous = last_seen.get(key)
        if previous:
            gap_minutes = (ts - previous).total_seconds() / 60
            if gap_minutes > 90:
                gaps.append({
                    "country": key[0],
                    "location": key[1],
                    "gap_start": previous.isoformat(),
                    "gap_end": ts.isoformat(),
                    "duration_minutes": round(gap_minutes, 1),
                })
        last_seen[key] = ts

    return gaps[:100]


def generate_recommendations(
    total_records: int,
    latest_age_hours: float | None,
    recent_activity: dict[str, Any],
    recent_singapore_hours: int = 0,
) -> list[str]:
    recommendations = []
    if total_records == 0:
        recommendations.append("No weather records found. Run the collector or restore a populated database.")
    if latest_age_hours is None:
        recommendations.append("No latest timestamp is available.")
    elif latest_age_hours > 2:
        recommendations.append(
            f"Latest weather record is {latest_age_hours:.1f} hours old. Start the backend collector or run /admin/collect-now."
        )
    if (recent_activity.get("last_24h") or 0) == 0:
        recommendations.append("No records were collected in the last 24 hours; live ML forecasts will be unavailable.")
    if recent_singapore_hours < 25:
        noun = "hour is" if recent_singapore_hours == 1 else "hours are"
        recommendations.append(
            f"Live ML needs 25 recent Singapore hourly observations; only {recent_singapore_hours} {noun} available."
        )
    if not recommendations:
        recommendations.append("Data collection is current.")
    return recommendations
