# CRITICAL BACKEND DATA COLLECTION ISSUES

**Date**: March 8, 2026
**Status**: 🔴 URGENT - Multiple critical issues blocking ML training

## Summary

The backend data collection has **3 CRITICAL ISSUES** that prevent proper ML training:

1. ❌ **Singapore data: 0 records** (should have thousands)
2. ❌ **Indonesia data: 0 records** (should have thousands)
3. ❌ **Missing variables: humidity, wind_speed, pressure ALL = 0/NULL**

**Current state**: Only 1,988 Malaysia records with ONLY temperature + rainfall

## Issue 1: Singapore Returns 0 Records

**Problem**: Singapore API calls succeed but return 0 records

**Evidence**:

```bash
curl -X POST https://lionweather-backend-production.up.railway.app/admin/collect-now
# Result: {"singapore":0,"malaysia":2520,"indonesia":0}
```

**Root Cause**: Unknown - need to check:

- API endpoint changes
- Response format changes
- Parsing logic errors
- Rate limiting issues

**Impact**: Cannot train Singapore-specific models

## Issue 2: Indonesia Returns 0 Records

**Problem**: Indonesia API calls return 0 records

**Evidence**: Same as Singapore - 0 records collected

**Root Cause**: Unknown - need to investigate BMKG API

**Impact**: Cannot train Indonesia-specific models

## Issue 3: Missing Weather Variables

**Problem**: Database has ONLY temperature and rainfall. Missing:

- Humidity (all 0)
- Wind speed (all 0)
- Wind direction (all NULL)
- Pressure (all NULL)

**Evidence**:

```sql
SELECT
  SUM(CASE WHEN humidity > 0 THEN 1 ELSE 0 END) as has_humidity,
  SUM(CASE WHEN wind_speed > 0 THEN 1 ELSE 0 END) as has_wind,
  SUM(CASE WHEN pressure IS NOT NULL THEN 1 ELSE 0 END) as has_pressure
FROM weather_records;
-- Result: 0, 0, 0
```

**Root Cause**: Malaysia API only provides temperature and rainfall in forecast endpoint

**Impact**:

- Cannot train models for humidity, wind, pressure
- Reduced ML accuracy (missing important features)
- Cannot compete with NEA forecasts (they use all variables)

## Issue 4: Background Polling Not Running

**Problem**: Manual collection works, but automatic 10-minute polling is NOT running

**Evidence**:

- Database stuck at 1,988 records from March 7-13
- Manual `/admin/collect-now` works and adds 2,520 records
- But those records are NOT appearing in database count

**Root Cause**: Either:

1. Background task not starting on Railway
2. Database writes failing silently
3. ON CONFLICT logic replacing instead of appending

**Impact**: No new data being collected automatically

## What We Need for Proper ML

For competitive ML forecasting, we need:

### Essential Variables (MUST HAVE):

- ✅ Temperature (have)
- ✅ Rainfall (have)
- ❌ Humidity (missing)
- ❌ Wind speed (missing)
- ❌ Wind direction (missing)
- ❌ Pressure (missing)

### Additional Variables (NICE TO HAVE):

- Cloud cover
- Visibility
- Dew point
- UV index
- Solar radiation

### Temporal Features (can derive):

- Hour of day
- Day of week
- Month
- Season
- Time since last rain

### Spatial Features (can derive):

- Distance to coast
- Elevation
- Urban/rural classification

## Immediate Actions Needed

### Priority 1: Fix Data Collection

1. Debug Singapore API - why 0 records?
2. Debug Indonesia API - why 0 records?
3. Find Malaysia API endpoints for humidity, wind, pressure
4. Verify background polling is actually running

### Priority 2: Verify Data Storage

1. Check why manual collection records aren't persisting
2. Verify ON CONFLICT logic is working correctly
3. Check Railway volume is mounted at `/app`
4. Verify database isn't being reset on deploy

### Priority 3: Enhance Data Sources

1. Research alternative APIs with more variables
2. Consider using multiple APIs per country
3. Add data validation and quality checks
4. Add logging for every API call and database write

## Testing Commands

### Check current data:

```bash
cd lionweather/backend
python check_data_status.py
```

### Trigger manual collection:

```bash
curl -X POST https://lionweather-backend-production.up.railway.app/admin/collect-now
```

### Check database directly:

```bash
sqlite3 weather.db "SELECT COUNT(*), country FROM weather_records GROUP BY country;"
sqlite3 weather.db "SELECT COUNT(*) as total, SUM(CASE WHEN humidity > 0 THEN 1 ELSE 0 END) as has_humidity FROM weather_records;"
```

### Check if background tasks are running:

```bash
curl https://lionweather-backend-production.up.railway.app/status
```

## Next Steps

1. **Investigate Singapore API failure** - Add detailed logging
2. **Investigate Indonesia API failure** - Add detailed logging
3. **Find humidity/wind/pressure data sources** - Research APIs
4. **Fix background polling** - Ensure it's actually running
5. **Verify data persistence** - Check Railway volume setup

## References

- Singapore API: https://api-open.data.gov.sg/v2/real-time/api/
- Malaysia API: https://api.data.gov.my/weather/
- Indonesia BMKG: https://data.bmkg.go.id/
- Current backend: https://lionweather-backend-production.up.railway.app/
