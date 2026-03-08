# Historical Weather Data Seeding

This document describes the process for seeding historical weather data from Open-Meteo Historical API for ML model training.

## Quick Start

To seed historical data in one command:

```bash
cd lionweather/backend
python seed_all_historical_data.py --months 12
```

This will:

1. Fetch 12 months of historical weather data from Open-Meteo
2. Create forecast-actual pairs for ML training
3. Verify data quality

For individual steps, see the detailed sections below.

## Overview

The historical data seeding process consists of three main steps:

1. **Seed Historical Weather Data** - Fetch hourly weather observations from Open-Meteo
2. **Seed Historical Forecast Data** - Create forecast-actual pairs for ML training
3. **Verify Data Quality** - Validate completeness and accuracy of seeded data

## Critical Requirements

⚠️ **ZERO TOLERANCE FOR MOCK DATA**

- All data MUST come from real API sources (Open-Meteo Historical API)
- NO mock/synthetic data generation is allowed
- NO hardcoded values or fake data
- Data validation MUST reject any suspicious patterns

## Data Sources

### Open-Meteo Historical Weather API

- **API**: https://archive-api.open-meteo.com/v1/archive
- **Documentation**: https://open-meteo.com/en/docs/historical-weather-api
- **Coverage**: Historical weather data from 1940 to present
- **Resolution**: Hourly data
- **Location**: Singapore (1.3521°N, 103.8198°E)

### Parameters Fetched

- `temperature_2m` - Temperature at 2 meters (°C)
- `relative_humidity_2m` - Relative humidity at 2 meters (%)
- `precipitation` - Precipitation (mm)
- `wind_speed_10m` - Wind speed at 10 meters (km/h)
- `wind_direction_10m` - Wind direction at 10 meters (degrees)
- `surface_pressure` - Surface pressure (hPa)
- `visibility` - Visibility (meters)
- `weather_code` - Weather condition code

## Usage

### Step 1: Seed Historical Weather Data

Fetch 12 months of historical hourly weather data:

```bash
cd lionweather/backend
python seed_historical_data.py
```

This will:

- Fetch hourly weather data for the past 12 months
- Validate data quality (completeness, ranges)
- Store data in `weather_records` table
- Report statistics and any issues

**Expected Output:**

- ~8,760 records (365 days × 24 hours)
- Completeness: >95%
- Temperature range: 20-35°C for Singapore
- No mock data detected

### Step 2: Seed Historical Forecast Data

Create forecast-actual pairs from historical data:

```bash
cd lionweather/backend
python seed_historical_forecasts.py
```

This will:

- Read historical weather records from database
- Create forecast-actual pairs for 1h, 3h, 6h, 12h, 24h ahead
- Store pairs in `forecast_data` table
- Report statistics

**Expected Output:**

- ~43,800 forecast pairs (8,760 records × 5 horizons)
- Pairs for each forecast horizon (1h, 3h, 6h, 12h, 24h)

### Step 3: Verify Data Quality

Validate the seeded data:

```bash
cd lionweather/backend
python verify_historical_data.py
```

This will:

- Check data completeness (no large gaps)
- Validate data ranges for Singapore climate
- Detect any mock/synthetic data
- Report overall data quality

**Expected Output:**

- ✅ Data completeness: >95%
- ✅ Temperature: 20-35°C
- ✅ Humidity: 60-95%
- ✅ No mock data detected

## Database Schema

### weather_records Table

Stores historical weather observations:

```sql
CREATE TABLE weather_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    country TEXT NOT NULL,
    location TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    temperature REAL NOT NULL,
    rainfall REAL NOT NULL,
    humidity REAL NOT NULL,
    wind_speed REAL NOT NULL,
    wind_direction REAL,
    pressure REAL,
    source_api TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(timestamp, country, location)
);
```

### forecast_data Table

Stores historical forecast-actual pairs:

```sql
CREATE TABLE forecast_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_time TEXT NOT NULL,
    target_time_start TEXT NOT NULL,
    target_time_end TEXT NOT NULL,
    country TEXT NOT NULL,
    location TEXT,
    latitude REAL,
    longitude REAL,
    temperature_low REAL,
    temperature_high REAL,
    humidity_low REAL,
    humidity_high REAL,
    wind_speed_low REAL,
    wind_speed_high REAL,
    wind_direction TEXT,
    forecast_description TEXT,
    source_api TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(prediction_time, target_time_start, target_time_end, country, location)
);
```

## Data Quality Checks

### Completeness

- **Target**: >95% completeness
- **Check**: No gaps larger than 2 hours
- **Action**: Log warnings for gaps, continue with available data

### Range Validation

Singapore climate ranges:

- **Temperature**: 20-35°C (typical), 18-40°C (acceptable)
- **Humidity**: 60-95% (typical), 40-100% (acceptable)
- **Rainfall**: 0-100mm/hour (typical), 0-200mm/hour (acceptable)
- **Wind Speed**: 0-40 km/h (typical), 0-100 km/h (acceptable)

### Mock Data Detection

Checks for:

- Suspicious source API names (containing "mock", "fake", "test")
- Repeated identical values (>100 occurrences)
- Unrealistic patterns

**Action**: Reject any data that fails mock detection

## Troubleshooting

### Issue: Low completeness (<95%)

**Cause**: API rate limiting or network issues

**Solution**:

1. Check API response in logs
2. Reduce chunk size in `seed_historical_data.py`
3. Add delays between requests
4. Re-run seeding for missing periods

### Issue: Data ranges outside expected values

**Cause**: Extreme weather events or API errors

**Solution**:

1. Review outlier records in logs
2. Verify against official weather records
3. If valid extreme weather, keep data
4. If API error, re-fetch that period

### Issue: Mock data detected

**Cause**: Incorrect data source or testing data

**Solution**:

1. **STOP IMMEDIATELY**
2. Identify source of mock data
3. Delete mock records from database
4. Re-seed with correct source
5. Verify again

## ML Training Considerations

### Training Dataset

- **Size**: ~8,760 hourly observations (12 months)
- **Features**: temperature, humidity, rainfall, wind_speed, wind_direction, pressure
- **Target**: Future weather conditions (1h, 3h, 6h, 12h, 24h ahead)

### Forecast Pairs

- **Purpose**: Ground truth for ML model evaluation
- **Format**: (prediction_time, target_time, predicted_value, actual_value)
- **Horizons**: 1h, 3h, 6h, 12h, 24h ahead

### Data Splits

Recommended splits for ML training:

- **Training**: 70% (oldest data)
- **Validation**: 15% (middle data)
- **Test**: 15% (most recent data)

**Important**: Use temporal split (not random) to avoid data leakage!

## Continuous Updates

### Daily Updates

To keep training data fresh, run daily:

```bash
# Fetch yesterday's data
python seed_historical_data.py --days 1

# Create forecast pairs
python seed_historical_forecasts.py --days 1

# Verify quality
python verify_historical_data.py
```

### Monthly Retraining

Recommended schedule:

1. Seed new month's data
2. Verify data quality
3. Retrain ML models with updated dataset
4. Evaluate model performance
5. Deploy if performance improves

## API Rate Limits

### Open-Meteo Historical API

- **Free tier**: Unlimited requests
- **Rate limit**: None specified
- **Best practice**: Add 1-second delay between requests
- **Chunk size**: 3 months per request (to avoid timeouts)

## Data Retention

### Storage Requirements

- **12 months**: ~8,760 records × 200 bytes = ~1.7 MB
- **Forecast pairs**: ~43,800 records × 300 bytes = ~13 MB
- **Total**: ~15 MB per year

### Retention Policy

- **Keep**: All historical data for ML training
- **Archive**: Data older than 2 years (optional)
- **Delete**: Never delete training data (unless mock data detected)

## Support

For issues or questions:

1. Check logs in console output
2. Review this documentation
3. Verify API status: https://open-meteo.com/
4. Check database schema and indexes

## References

- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [Singapore Climate](https://www.weather.gov.sg/climate-climate-of-singapore/)
- [ML Training Best Practices](../ML_TRAINING_PLAN.md)
