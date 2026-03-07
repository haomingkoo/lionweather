"""
Data Health Check Router

Provides endpoints to monitor data collection health, detect gaps,
and verify data quality for ML training.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

from app.db.database import execute_sql

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-health", tags=["data-health"])


@router.get("/status")
async def get_data_health_status():
    """
    Get comprehensive data health status including:
    - Total records count
    - Records by country
    - Recent activity (last hour, 24 hours, 7 days)
    - Data gaps detection
    - Missing variables analysis
    - Growth rate
    """
    try:
        # Total records
        total_result = execute_sql("SELECT COUNT(*) as count FROM weather_data")
        total_records = total_result[0]["count"] if total_result else 0

        # Records by country
        country_result = execute_sql("""
            SELECT country, COUNT(*) as count 
            FROM weather_data 
            GROUP BY country
        """)
        by_country = {row["country"]: row["count"] for row in country_result}

        # Recent activity
        now = datetime.now()
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        one_day_ago = (now - timedelta(days=1)).isoformat()
        seven_days_ago = (now - timedelta(days=7)).isoformat()

        last_hour = execute_sql(
            "SELECT COUNT(*) as count FROM weather_data WHERE timestamp > ?",
            (one_hour_ago,)
        )
        last_24h = execute_sql(
            "SELECT COUNT(*) as count FROM weather_data WHERE timestamp > ?",
            (one_day_ago,)
        )
        last_7d = execute_sql(
            "SELECT COUNT(*) as count FROM weather_data WHERE timestamp > ?",
            (seven_days_ago,)
        )

        recent_activity = {
            "last_hour": last_hour[0]["count"] if last_hour else 0,
            "last_24_hours": last_24h[0]["count"] if last_24h else 0,
            "last_7_days": last_7d[0]["count"] if last_7d else 0,
        }

        # Latest timestamp
        latest_result = execute_sql(
            "SELECT MAX(timestamp) as latest FROM weather_data"
        )
        latest_timestamp = latest_result[0]["latest"] if latest_result and latest_result[0]["latest"] else None

        # Missing variables analysis
        missing_vars = execute_sql("""
            SELECT 
                COUNT(CASE WHEN humidity = 0 OR humidity IS NULL THEN 1 END) as missing_humidity,
                COUNT(CASE WHEN wind_speed = 0 OR wind_speed IS NULL THEN 1 END) as missing_wind_speed,
                COUNT(CASE WHEN pressure = 0 OR pressure IS NULL THEN 1 END) as missing_pressure,
                COUNT(CASE WHEN temperature = 0 OR temperature IS NULL THEN 1 END) as missing_temperature,
                COUNT(CASE WHEN rainfall < 0 THEN 1 END) as invalid_rainfall
            FROM weather_data
        """)

        missing_data = missing_vars[0] if missing_vars else {}

        # Data gaps detection (periods with no data)
        gaps = detect_data_gaps()

        # Growth rate (records per hour over last 24h)
        growth_rate = recent_activity["last_24_hours"] / 24 if recent_activity["last_24_hours"] > 0 else 0

        # Expected vs actual (should be ~300-400 records per 10 min = ~1800-2400 per hour)
        expected_per_hour = 2000
        health_score = min(100, (growth_rate / expected_per_hour) * 100) if growth_rate > 0 else 0

        return {
            "status": "healthy" if health_score > 50 else "degraded" if health_score > 10 else "critical",
            "health_score": round(health_score, 1),
            "total_records": total_records,
            "by_country": by_country,
            "recent_activity": recent_activity,
            "latest_timestamp": latest_timestamp,
            "missing_data": missing_data,
            "data_gaps": gaps,
            "growth_rate": {
                "records_per_hour": round(growth_rate, 1),
                "expected_per_hour": expected_per_hour,
                "percentage": round((growth_rate / expected_per_hour) * 100, 1) if expected_per_hour > 0 else 0
            },
            "recommendations": generate_recommendations(
                by_country, 
                missing_data, 
                growth_rate, 
                expected_per_hour,
                gaps
            )
        }

    except Exception as e:
        logger.error(f"Failed to get data health status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gaps")
async def get_data_gaps():
    """
    Detect time periods with missing data collection.
    Returns list of gaps where no data was collected for > 15 minutes.
    """
    try:
        gaps = detect_data_gaps()
        return {
            "total_gaps": len(gaps),
            "gaps": gaps
        }
    except Exception as e:
        logger.error(f"Failed to detect data gaps: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality")
async def get_data_quality():
    """
    Analyze data quality metrics:
    - Completeness (% of records with all fields)
    - Validity (% of records within valid ranges)
    - Consistency (duplicate detection)
    """
    try:
        # Total records
        total_result = execute_sql("SELECT COUNT(*) as count FROM weather_data")
        total = total_result[0]["count"] if total_result else 0

        if total == 0:
            return {
                "status": "no_data",
                "message": "No data available for quality analysis"
            }

        # Completeness - records with all required fields
        complete_result = execute_sql("""
            SELECT COUNT(*) as count FROM weather_data
            WHERE temperature IS NOT NULL AND temperature != 0
            AND humidity IS NOT NULL AND humidity != 0
            AND wind_speed IS NOT NULL AND wind_speed != 0
            AND rainfall IS NOT NULL AND rainfall >= 0
        """)
        complete = complete_result[0]["count"] if complete_result else 0
        completeness = (complete / total) * 100

        # Validity - records within valid ranges
        valid_result = execute_sql("""
            SELECT COUNT(*) as count FROM weather_data
            WHERE temperature BETWEEN -50 AND 60
            AND humidity BETWEEN 0 AND 100
            AND wind_speed >= 0
            AND rainfall >= 0
        """)
        valid = valid_result[0]["count"] if valid_result else 0
        validity = (valid / total) * 100

        # Duplicates detection
        duplicates_result = execute_sql("""
            SELECT COUNT(*) as count FROM (
                SELECT timestamp, country, location, COUNT(*) as dup_count
                FROM weather_data
                GROUP BY timestamp, country, location
                HAVING dup_count > 1
            )
        """)
        duplicates = duplicates_result[0]["count"] if duplicates_result else 0

        # Outliers detection (beyond 3 standard deviations)
        outliers_result = execute_sql("""
            SELECT COUNT(*) as count FROM weather_data
            WHERE ABS(temperature - (SELECT AVG(temperature) FROM weather_data)) > 
                  3 * (SELECT CASE WHEN COUNT(*) > 1 
                       THEN SQRT(SUM((temperature - avg_temp) * (temperature - avg_temp)) / (COUNT(*) - 1))
                       ELSE 0 END
                       FROM weather_data, (SELECT AVG(temperature) as avg_temp FROM weather_data))
        """)
        outliers = outliers_result[0]["count"] if outliers_result else 0

        quality_score = (completeness * 0.4 + validity * 0.4 + (100 - (duplicates / total * 100)) * 0.2)

        return {
            "quality_score": round(quality_score, 1),
            "total_records": total,
            "completeness": {
                "percentage": round(completeness, 1),
                "complete_records": complete,
                "incomplete_records": total - complete
            },
            "validity": {
                "percentage": round(validity, 1),
                "valid_records": valid,
                "invalid_records": total - valid
            },
            "duplicates": {
                "count": duplicates,
                "percentage": round((duplicates / total) * 100, 1)
            },
            "outliers": {
                "count": outliers,
                "percentage": round((outliers / total) * 100, 1)
            },
            "status": "excellent" if quality_score > 90 else "good" if quality_score > 70 else "fair" if quality_score > 50 else "poor"
        }

    except Exception as e:
        logger.error(f"Failed to analyze data quality: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline")
async def get_data_timeline():
    """
    Get data collection timeline showing records collected per hour
    for the last 7 days.
    """
    try:
        # Get hourly counts for last 7 days
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        timeline_result = execute_sql("""
            SELECT 
                strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
                COUNT(*) as count,
                COUNT(DISTINCT country) as countries
            FROM weather_data
            WHERE timestamp > ?
            GROUP BY hour
            ORDER BY hour DESC
        """, (seven_days_ago,))

        timeline = [
            {
                "hour": row["hour"],
                "count": row["count"],
                "countries": row["countries"]
            }
            for row in timeline_result
        ]

        return {
            "timeline": timeline,
            "total_hours": len(timeline),
            "average_per_hour": sum(row["count"] for row in timeline) / len(timeline) if timeline else 0
        }

    except Exception as e:
        logger.error(f"Failed to get data timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def detect_data_gaps() -> List[Dict[str, Any]]:
    """
    Detect time periods with no data collection (gaps > 15 minutes).
    """
    try:
        # Get all timestamps ordered
        timestamps_result = execute_sql("""
            SELECT DISTINCT timestamp 
            FROM weather_data 
            ORDER BY timestamp DESC
            LIMIT 1000
        """)

        if not timestamps_result or len(timestamps_result) < 2:
            return []

        gaps = []
        prev_time = None

        for row in timestamps_result:
            current_time = datetime.fromisoformat(row["timestamp"])
            
            if prev_time:
                gap_duration = (prev_time - current_time).total_seconds() / 60  # minutes
                
                # Gap detected if > 15 minutes (should collect every 10 min)
                if gap_duration > 15:
                    gaps.append({
                        "start": current_time.isoformat(),
                        "end": prev_time.isoformat(),
                        "duration_minutes": round(gap_duration, 1),
                        "severity": "critical" if gap_duration > 60 else "warning"
                    })
            
            prev_time = current_time

        return gaps[:20]  # Return last 20 gaps

    except Exception as e:
        logger.error(f"Failed to detect data gaps: {e}", exc_info=True)
        return []


def generate_recommendations(
    by_country: Dict[str, int],
    missing_data: Dict[str, int],
    growth_rate: float,
    expected_rate: float,
    gaps: List[Dict[str, Any]]
) -> List[str]:
    """
    Generate actionable recommendations based on data health analysis.
    """
    recommendations = []

    # Check country data collection
    if by_country.get("singapore", 0) == 0:
        recommendations.append("🚨 CRITICAL: Singapore data collection is failing (0 records)")
    
    if by_country.get("indonesia", 0) == 0:
        recommendations.append("🚨 CRITICAL: Indonesia data collection is failing (0 records)")
    
    if by_country.get("malaysia", 0) == 0:
        recommendations.append("🚨 CRITICAL: Malaysia data collection is failing (0 records)")

    # Check missing variables
    if missing_data.get("missing_humidity", 0) > 100:
        recommendations.append("⚠️ WARNING: Many records missing humidity data")
    
    if missing_data.get("missing_wind_speed", 0) > 100:
        recommendations.append("⚠️ WARNING: Many records missing wind speed data")
    
    if missing_data.get("missing_pressure", 0) > 100:
        recommendations.append("⚠️ WARNING: Many records missing pressure data")

    # Check growth rate
    if growth_rate < expected_rate * 0.5:
        recommendations.append(f"🚨 CRITICAL: Data collection rate is {round((growth_rate/expected_rate)*100, 1)}% of expected")
    elif growth_rate < expected_rate * 0.8:
        recommendations.append(f"⚠️ WARNING: Data collection rate is {round((growth_rate/expected_rate)*100, 1)}% of expected")

    # Check data gaps
    critical_gaps = [g for g in gaps if g.get("severity") == "critical"]
    if critical_gaps:
        recommendations.append(f"⚠️ WARNING: {len(critical_gaps)} critical data gaps detected (>1 hour)")

    # Positive feedback
    if not recommendations:
        recommendations.append("✅ All systems operational - data collection is healthy")

    return recommendations
