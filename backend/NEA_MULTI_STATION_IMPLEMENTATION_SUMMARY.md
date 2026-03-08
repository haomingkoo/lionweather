# NEA Multi-Station Implementation Summary

## Overview

This document summarizes the implementation of NEA multi-station historical data import and spatial feature engineering for neighborhood-level rainfall predictions.

## What Was Implemented

### 1. NEA Historical Data Importer (`seed_nea_historical_data.py`)

A complete CSV import system for NEA historical weather data from data.gov.sg:

**Features:**

- Parses NEA CSV format (Timestamp, Station Id, Station Name, Location Longitude, Location Latitude, value)
- Imports 5 parameters: Temperature, Rainfall, Humidity, Wind Speed, Wind Direction
- Groups data by timestamp and station to create complete observations
- Stores in `weather_records` table with station coordinates
- Handles 2016-2024 data (8+ years, ~10-12M observations expected)

**Usage:**

```bash
cd lionweather/backend
mkdir nea_historical_data
# Download CSV files from data.gov.sg
python seed_nea_historical_data.py
```

### 2. Import Guide (`NEA_HISTORICAL_DATA_IMPORT_GUIDE.md`)

Complete documentation for downloading and importing NEA data:

- Data source URLs
- CSV format specification
- Download instructions
- File organization
- Troubleshooting guide

### 3. Updated Training Data Preparation (`prepare_training_data.py`)

Enhanced to support multi-station data:

**New Features:**

- `source_filter` parameter to select data source (NEA, Open-Meteo, or all)
- Multi-station data extraction with station breakdown
- Spatial coordinate preservation (latitude, longitude)
- Class distribution reporting

**Usage:**

```bash
# Use NEA multi-station data
python prepare_training_data.py nea

# Use Open-Meteo data (baseline comparison)
python prepare_training_data.py open-meteo

# Use all available data
python prepare_training_data.py all
```

### 4. Spatial Feature Engineering (`feature_engineer.py`)

Added spatial features for location-aware predictions:

**New Features:**

- `latitude`: Raw station latitude coordinate
- `longitude`: Raw station longitude coordinate
- `distance_from_center`: Distance from Singapore center (km)
- `is_coastal`: Binary flag for coastal stations

**Total Features:** 26 features (was 22)

- 5 base weather features
- 4 spatial features (NEW)
- 7 temporal features
- 4 lagged features
- 6 thunderstorm indicator features

### 5. Spatial Data Visualization (`visualize_spatial_data.py`)

Tool to verify multi-station data makes sense geographically:

**Visualizations:**

1. **Station Locations Map**: Shows all weather stations on Singapore map
2. **Spatial Distribution**: Rainfall, temperature, humidity across stations
3. **Rainfall Classes Spatial**: NEA class distribution by location
4. **Station Summary CSV**: Statistics for each station

**Usage:**

```bash
python ml/visualize_spatial_data.py
```

**Output Files:**

- `ml/station_locations.png`
- `ml/rainfall_spatial_distribution.png`
- `ml/rainfall_classes_spatial.png`
- `ml/station_summary.csv`

## Data Flow

### Training Pipeline (NEA Multi-Station)

```
1. Download NEA CSV files from data.gov.sg
   ↓
2. Run seed_nea_historical_data.py
   → Imports ~10-12M observations from 10+ stations
   ↓
3. Run visualize_spatial_data.py
   → Verify spatial distribution makes sense
   ↓
4. Run prepare_training_data.py nea
   → Extract multi-station data with spatial features
   ↓
5. Run train_multiclass_classifier.py
   → Train models with latitude/longitude features
   → Models learn location-specific patterns
   ↓
6. Prediction Service
   → Match user coordinates to nearest station
   → Generate location-specific forecast
```

### Prediction Flow (Location-Aware)

```
User Request (lat, lon)
   ↓
Find Nearest Station
   ↓
Fetch Recent History for Station
   ↓
Compute Features (including lat/lon)
   ↓
Run ML Models
   → Models use spatial features
   → Predict for specific location
   ↓
Return Location-Specific Forecast
```

## Key Advantages

### 1. Consistent Data Source

- NEA historical → NEA real-time = no data mismatch
- Same stations, same measurement methods
- No need to reconcile different APIs

### 2. Neighborhood-Level Predictions

- Each station has specific coordinates
- Models learn location-specific patterns
- Users get forecasts for their actual location
- No more "whole Singapore is one weather"

### 3. Long Training History

- 2016-2024 = 8+ years of data
- Captures seasonal patterns, monsoons, rare events
- Much better than 2 years initially assumed

### 4. Multiple Stations

- 10+ stations across Singapore
- Covers North, South, East, West, Central
- Captures local weather variations
- Especially important for rainfall (highly variable)

## NEA Stations (Examples)

Based on user's data:

- **S50**: Clementi (West)
- **S43**: Kim Chuan (East)
- **S109**: Ang Mo Kio (North)
- **S111**: Scotts Road (Central)
- **S117**: Banyan Road (Central)
- **S107**: East Coast Parkway (East)
- **S60**: Sentosa (South)

Each station has:

- Unique coordinates (lat/lon)
- 8+ years of hourly data
- All 5 weather parameters

## Next Steps

### Immediate (Required for Location-Aware Predictions)

1. **Download NEA Data**

   - Visit https://data.gov.sg/collections/2281/view
   - Download 45 CSV files (5 parameters × 9 years)
   - Place in `lionweather/backend/nea_historical_data/`

2. **Import NEA Data**

   ```bash
   python seed_nea_historical_data.py
   ```

3. **Verify Spatial Distribution**

   ```bash
   python ml/visualize_spatial_data.py
   ```

   - Check that stations are distributed across Singapore
   - Verify rainfall varies by location
   - Ensure data quality is good

4. **Prepare Training Data**

   ```bash
   python prepare_training_data.py nea
   ```

5. **Update Model Training**

   - Modify `train_multiclass_classifier.py` to:
     - Include spatial features (latitude, longitude)
     - Save models to correct paths
     - Train for 1h, 3h, 6h horizons

6. **Retrain Models**
   ```bash
   python ml/train_multiclass_classifier.py
   ```
   - Models will learn location-specific patterns
   - Expect better performance than single-location models

### Optional (Comparison & Validation)

7. **Compare NEA vs Open-Meteo**

   - Train models with both data sources
   - Compare performance metrics
   - Determine which source is better

8. **Update Prediction Service**

   - Match user coordinates to nearest NEA station
   - Fetch recent history for that station
   - Generate location-specific forecast

9. **Complete Backtest Framework**
   - Parse NEA official forecasts
   - Compare our predictions vs NEA
   - Test ensemble performance

## File Structure

```
lionweather/backend/
├── seed_nea_historical_data.py          # NEW: NEA CSV importer
├── NEA_HISTORICAL_DATA_IMPORT_GUIDE.md  # NEW: Import documentation
├── NEA_MULTI_STATION_IMPLEMENTATION_SUMMARY.md  # NEW: This file
├── ml/
│   ├── prepare_training_data.py         # UPDATED: Multi-station support
│   ├── feature_engineer.py              # UPDATED: Spatial features
│   ├── visualize_spatial_data.py        # NEW: Spatial visualization
│   ├── train_multiclass_classifier.py   # TODO: Update for spatial features
│   └── ...
└── nea_historical_data/                 # NEW: CSV files directory
    ├── air_temperature_2016.csv
    ├── air_temperature_2017.csv
    ├── ...
    └── wind_direction_2024.csv
```

## Technical Details

### Database Schema

No changes needed - existing `weather_records` table already has:

- `latitude` column
- `longitude` column
- `location` column (station name)
- `source_api` column (to distinguish NEA vs Open-Meteo)

### Feature Engineering

**Spatial Features Added:**

```python
# Raw coordinates (for model to learn location patterns)
latitude: float
longitude: float

# Derived spatial features
distance_from_center: float  # km from Singapore center
is_coastal: int  # 1 if near coast, 0 otherwise
```

**Why Include Raw Coordinates?**

- Models can learn non-linear location patterns
- Captures complex spatial relationships
- Better than just distance from center
- Allows model to learn "East coast gets more rain in afternoon" etc.

### Model Training

Models will now have 26 input features (was 22):

- Temperature, humidity, pressure, wind speed, wind direction
- **Latitude, longitude, distance from center, is coastal** (NEW)
- Hour sin/cos, day sin/cos, month, monsoon flags
- Rainfall lag 1h/3h/6h/24h
- Pressure drop, humidity change, temp drop, wind change, afternoon, wind from west

The model will learn:

- "When latitude=1.33 and longitude=103.77 (Clementi), afternoon rain is common"
- "When latitude=1.32 and longitude=103.93 (Changi), morning rain is common"
- Location-specific rainfall patterns

## Validation

### Spatial Sanity Checks

Run `visualize_spatial_data.py` to verify:

1. **Station Distribution**

   - Stations spread across Singapore
   - Not all clustered in one area
   - Covers North, South, East, West, Central

2. **Rainfall Variation**

   - Different stations have different rainfall patterns
   - Not all stations showing identical values
   - Spatial variation makes sense (e.g., coastal vs inland)

3. **Data Quality**
   - No suspicious patterns (all zeros, all same value)
   - Temperature ranges reasonable (24-34°C for Singapore)
   - Humidity ranges reasonable (60-100%)

### Expected Results

After importing NEA data and visualizing:

- **10-15 stations** across Singapore
- **~10-12M observations** (8 years × 12 stations × 8760 hours/year)
- **Clear spatial variation** in rainfall (most variable parameter)
- **Less variation** in temperature (Singapore is small and tropical)

## Troubleshooting

### "No data found in database"

- Run `seed_nea_historical_data.py` first
- Check that CSV files are in `nea_historical_data/` directory

### "No spatial features computed"

- Check that `latitude` and `longitude` columns exist in data
- Verify NEA import included coordinates

### "All stations showing same values"

- Check data source - might be using single-location Open-Meteo data
- Use `source_filter="data.gov.sg/nea"` to get only NEA multi-station data

### "Models not improving with spatial features"

- Verify spatial features are included in training
- Check that models are using all 26 features
- Ensure sufficient data per station (>1000 observations)

## Performance Expectations

### With Single-Location Data (Before)

- Accuracy: ~67% (1h forecast)
- Rain recall: ~71%
- **Problem**: Same prediction for all of Singapore

### With Multi-Station Data (After)

- Accuracy: Expected 70-75% (location-aware)
- Rain recall: Expected 75-80%
- **Benefit**: Different predictions for different neighborhoods

### Why Better?

- Models learn "Clementi gets afternoon rain, Changi gets morning rain"
- Captures local microclimates
- Matches user's actual location
- More relevant predictions

## Conclusion

The NEA multi-station implementation provides:

1. ✅ Consistent data source (NEA historical → NEA real-time)
2. ✅ Neighborhood-level predictions (10+ stations with coordinates)
3. ✅ Long training history (8+ years, 2016-2024)
4. ✅ Spatial features (latitude, longitude, distance, coastal)
5. ✅ Visualization tools (verify data makes sense)
6. ✅ Flexible training (NEA, Open-Meteo, or both)

**Next Action**: Download NEA CSV files and run the import script!
