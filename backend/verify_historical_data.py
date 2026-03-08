"""
Historical Data Quality Verification Script

This script verifies the quality and completeness of historical weather data
stored in the database.

Checks:
1. Data completeness (no large gaps)
2. Data ranges are reasonable for Singapore
3. Timestamps are correct
4. No mock/synthetic data present
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.db.database import get_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalDataVerifier:
    """Verifies quality of historical weather data"""
    
    def __init__(self):
        """Initialize the verifier"""
        pass
    
    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of historical data.
        
        Returns:
            Dictionary with summary statistics
        """
        con = get_connection()
        cursor = con.cursor()
        
        # Get total record count
        cursor.execute("""
            SELECT COUNT(*) FROM weather_records
            WHERE country = 'singapore'
        """)
        total_records = cursor.fetchone()[0]
        
        # Get date range
        cursor.execute("""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM weather_records
            WHERE country = 'singapore'
        """)
        min_date, max_date = cursor.fetchone()
        
        # Get source API breakdown
        cursor.execute("""
            SELECT source_api, COUNT(*) as count
            FROM weather_records
            WHERE country = 'singapore'
            GROUP BY source_api
        """)
        sources = {row[0]: row[1] for row in cursor.fetchall()}
        
        con.close()
        
        return {
            "total_records": total_records,
            "date_range": {
                "start": min_date,
                "end": max_date
            },
            "sources": sources
        }
    
    def check_completeness(self) -> Dict[str, Any]:
        """
        Check for gaps in the historical data.
        
        Returns:
            Dictionary with completeness analysis
        """
        con = get_connection()
        cursor = con.cursor()
        
        # Get all timestamps
        cursor.execute("""
            SELECT timestamp
            FROM weather_records
            WHERE country = 'singapore'
            ORDER BY timestamp ASC
        """)
        
        timestamps = [row[0] for row in cursor.fetchall()]
        con.close()
        
        if len(timestamps) < 2:
            return {
                "complete": False,
                "error": "Insufficient data"
            }
        
        # Check for gaps
        gaps = []
        for i in range(1, len(timestamps)):
            prev_time = datetime.fromisoformat(timestamps[i-1])
            curr_time = datetime.fromisoformat(timestamps[i])
            gap_hours = (curr_time - prev_time).total_seconds() / 3600
            
            if gap_hours > 2:  # More than 2 hours gap
                gaps.append({
                    "start": timestamps[i-1],
                    "end": timestamps[i],
                    "hours": round(gap_hours, 2)
                })
        
        # Calculate expected hours
        first_time = datetime.fromisoformat(timestamps[0])
        last_time = datetime.fromisoformat(timestamps[-1])
        expected_hours = (last_time - first_time).total_seconds() / 3600
        actual_hours = len(timestamps)
        completeness = (actual_hours / expected_hours) * 100 if expected_hours > 0 else 0
        
        return {
            "complete": completeness >= 95,
            "completeness_percent": round(completeness, 2),
            "expected_hours": int(expected_hours),
            "actual_hours": actual_hours,
            "gaps": gaps[:10],  # Show first 10 gaps
            "total_gaps": len(gaps)
        }
    
    def check_data_ranges(self) -> Dict[str, Any]:
        """
        Check if data values are in reasonable ranges for Singapore.
        
        Returns:
            Dictionary with range analysis
        """
        con = get_connection()
        cursor = con.cursor()
        
        # Get temperature statistics
        cursor.execute("""
            SELECT 
                MIN(temperature) as min_temp,
                MAX(temperature) as max_temp,
                AVG(temperature) as avg_temp,
                MIN(humidity) as min_humidity,
                MAX(humidity) as max_humidity,
                AVG(humidity) as avg_humidity,
                MIN(rainfall) as min_rainfall,
                MAX(rainfall) as max_rainfall,
                AVG(rainfall) as avg_rainfall,
                MIN(wind_speed) as min_wind,
                MAX(wind_speed) as max_wind,
                AVG(wind_speed) as avg_wind
            FROM weather_records
            WHERE country = 'singapore'
        """)
        
        row = cursor.fetchone()
        
        # Count outliers
        cursor.execute("""
            SELECT COUNT(*) FROM weather_records
            WHERE country = 'singapore'
            AND (
                temperature < 18 OR temperature > 40
                OR humidity < 40 OR humidity > 100
                OR rainfall < 0 OR rainfall > 200
                OR wind_speed < 0 OR wind_speed > 100
            )
        """)
        outlier_count = cursor.fetchone()[0]
        
        con.close()
        
        # Singapore typical ranges:
        # Temperature: 24-34°C (can go 20-36°C in extremes)
        # Humidity: 60-95%
        # Rainfall: 0-100mm/hour (extreme storms can be higher)
        # Wind speed: 0-40 km/h (typhoons can be higher but rare)
        
        temp_valid = 18 <= row[0] <= 40 and 18 <= row[1] <= 40
        humidity_valid = 40 <= row[3] <= 100 and 40 <= row[4] <= 100
        rainfall_valid = 0 <= row[6] and row[7] <= 200
        wind_valid = 0 <= row[9] and row[10] <= 100
        
        return {
            "valid": temp_valid and humidity_valid and rainfall_valid and wind_valid,
            "temperature": {
                "min": round(row[0], 1) if row[0] else None,
                "max": round(row[1], 1) if row[1] else None,
                "avg": round(row[2], 1) if row[2] else None,
                "valid": temp_valid,
                "expected_range": "20-35°C for Singapore"
            },
            "humidity": {
                "min": round(row[3], 1) if row[3] else None,
                "max": round(row[4], 1) if row[4] else None,
                "avg": round(row[5], 1) if row[5] else None,
                "valid": humidity_valid,
                "expected_range": "60-95% for Singapore"
            },
            "rainfall": {
                "min": round(row[6], 1) if row[6] else None,
                "max": round(row[7], 1) if row[7] else None,
                "avg": round(row[8], 1) if row[8] else None,
                "valid": rainfall_valid,
                "expected_range": "0-100mm/hour typical"
            },
            "wind_speed": {
                "min": round(row[9], 1) if row[9] else None,
                "max": round(row[10], 1) if row[10] else None,
                "avg": round(row[11], 1) if row[11] else None,
                "valid": wind_valid,
                "expected_range": "0-40 km/h typical"
            },
            "outlier_count": outlier_count
        }
    
    def check_for_mock_data(self) -> Dict[str, Any]:
        """
        Check for any signs of mock/synthetic data.
        
        Returns:
            Dictionary with mock data detection results
        """
        con = get_connection()
        cursor = con.cursor()
        
        # Check for suspicious patterns that might indicate mock data:
        # 1. Repeated identical values
        # 2. Perfect round numbers
        # 3. Unrealistic patterns
        
        # Check for repeated temperature values
        cursor.execute("""
            SELECT temperature, COUNT(*) as count
            FROM weather_records
            WHERE country = 'singapore'
            GROUP BY temperature
            HAVING count > 100
            ORDER BY count DESC
            LIMIT 5
        """)
        repeated_temps = cursor.fetchall()
        
        # Check for source APIs that might be mock
        cursor.execute("""
            SELECT DISTINCT source_api
            FROM weather_records
            WHERE country = 'singapore'
        """)
        sources = [row[0] for row in cursor.fetchall()]
        
        # Flag suspicious sources
        suspicious_sources = [
            s for s in sources 
            if 'mock' in s.lower() or 'fake' in s.lower() or 'test' in s.lower()
        ]
        
        con.close()
        
        has_mock_data = len(suspicious_sources) > 0 or len(repeated_temps) > 0
        
        return {
            "has_mock_data": has_mock_data,
            "suspicious_sources": suspicious_sources,
            "repeated_values": [
                {"temperature": row[0], "count": row[1]} 
                for row in repeated_temps
            ],
            "all_sources": sources
        }
    
    def verify_all(self) -> Dict[str, Any]:
        """
        Run all verification checks.
        
        Returns:
            Dictionary with all verification results
        """
        logger.info("🔍 Starting historical data verification...")
        
        # Get summary
        logger.info("Checking data summary...")
        summary = self.get_data_summary()
        logger.info(f"✓ Found {summary['total_records']} records")
        
        # Check completeness
        logger.info("Checking data completeness...")
        completeness = self.check_completeness()
        if completeness.get("complete"):
            logger.info(f"✓ Data is {completeness['completeness_percent']}% complete")
        else:
            logger.warning(f"⚠️  Data completeness: {completeness['completeness_percent']}%")
        
        # Check ranges
        logger.info("Checking data ranges...")
        ranges = self.check_data_ranges()
        if ranges["valid"]:
            logger.info("✓ All data ranges are valid for Singapore")
        else:
            logger.warning("⚠️  Some data ranges are outside expected values")
        
        # Check for mock data
        logger.info("Checking for mock/synthetic data...")
        mock_check = self.check_for_mock_data()
        if not mock_check["has_mock_data"]:
            logger.info("✓ No mock/synthetic data detected")
        else:
            logger.error("❌ MOCK DATA DETECTED!")
        
        # Overall assessment
        all_valid = (
            completeness.get("complete", False) and
            ranges["valid"] and
            not mock_check["has_mock_data"]
        )
        
        result = {
            "valid": all_valid,
            "summary": summary,
            "completeness": completeness,
            "ranges": ranges,
            "mock_data_check": mock_check
        }
        
        logger.info(f"🎉 Verification complete! Overall valid: {all_valid}")
        
        return result


def main():
    """Main entry point for the verification script"""
    verifier = HistoricalDataVerifier()
    
    try:
        result = verifier.verify_all()
        
        print("\n" + "="*60)
        print("HISTORICAL DATA QUALITY VERIFICATION")
        print("="*60)
        
        # Summary
        print("\n📊 DATA SUMMARY:")
        print(f"  Total records: {result['summary']['total_records']}")
        print(f"  Date range: {result['summary']['date_range']['start']} to {result['summary']['date_range']['end']}")
        print(f"  Sources: {', '.join(result['summary']['sources'].keys())}")
        for source, count in result['summary']['sources'].items():
            print(f"    - {source}: {count} records")
        
        # Completeness
        print("\n✅ COMPLETENESS CHECK:")
        comp = result['completeness']
        print(f"  Complete: {comp.get('complete', False)}")
        print(f"  Completeness: {comp.get('completeness_percent', 0)}%")
        print(f"  Expected hours: {comp.get('expected_hours', 0)}")
        print(f"  Actual hours: {comp.get('actual_hours', 0)}")
        if comp.get('total_gaps', 0) > 0:
            print(f"  ⚠️  Found {comp['total_gaps']} time gaps")
            if comp.get('gaps'):
                print(f"  Largest gaps:")
                for gap in comp['gaps'][:3]:
                    print(f"    - {gap['hours']} hours: {gap['start']} to {gap['end']}")
        
        # Ranges
        print("\n📏 DATA RANGE CHECK:")
        ranges = result['ranges']
        print(f"  Valid: {ranges['valid']}")
        print(f"  Temperature: {ranges['temperature']['min']}°C to {ranges['temperature']['max']}°C (avg: {ranges['temperature']['avg']}°C)")
        print(f"    Expected: {ranges['temperature']['expected_range']}")
        print(f"  Humidity: {ranges['humidity']['min']}% to {ranges['humidity']['max']}% (avg: {ranges['humidity']['avg']}%)")
        print(f"    Expected: {ranges['humidity']['expected_range']}")
        print(f"  Rainfall: {ranges['rainfall']['min']}mm to {ranges['rainfall']['max']}mm (avg: {ranges['rainfall']['avg']}mm)")
        print(f"    Expected: {ranges['rainfall']['expected_range']}")
        print(f"  Wind speed: {ranges['wind_speed']['min']} to {ranges['wind_speed']['max']} km/h (avg: {ranges['wind_speed']['avg']} km/h)")
        print(f"    Expected: {ranges['wind_speed']['expected_range']}")
        if ranges['outlier_count'] > 0:
            print(f"  ⚠️  Found {ranges['outlier_count']} outlier records")
        
        # Mock data check
        print("\n🚫 MOCK DATA CHECK:")
        mock = result['mock_data_check']
        if mock['has_mock_data']:
            print("  ❌ MOCK DATA DETECTED!")
            if mock['suspicious_sources']:
                print(f"  Suspicious sources: {', '.join(mock['suspicious_sources'])}")
            if mock['repeated_values']:
                print(f"  Repeated values detected:")
                for rv in mock['repeated_values']:
                    print(f"    - Temperature {rv['temperature']}°C appears {rv['count']} times")
        else:
            print("  ✓ No mock/synthetic data detected")
        
        # Overall
        print("\n" + "="*60)
        if result['valid']:
            print("✅ OVERALL: DATA QUALITY IS GOOD")
        else:
            print("⚠️  OVERALL: DATA QUALITY ISSUES DETECTED")
        print("="*60 + "\n")
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
