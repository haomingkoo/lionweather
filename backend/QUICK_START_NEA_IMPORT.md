# Quick Start: NEA Multi-Station Data Import

## TL;DR

```bash
# 1. Create directory
cd lionweather/backend
mkdir nea_historical_data

# 2. Download 45 CSV files from data.gov.sg
# Visit: https://data.gov.sg/collections/2281/view
# Download all years (2016-2024) for:
#   - Historical Air Temperature across Singapore
#   - Historical Rainfall across Singapore
#   - Historical Relative Humidity across Singapore
#   - Historical Wind Speed across Singapore
#   - Historical Wind Direction across Singapore

# 3. Import data
python seed_nea_historical_data.py

# 4. Visualize to verify
python ml/visualize_spatial_data.py

# 5. Prepare training data
python prepare_training_data.py nea

# 6. Train models (after updating train_multiclass_classifier.py)
python ml/train_multiclass_classifier.py
```

## What You Get

- **~10-12M observations** from 10+ weather stations
- **8+ years** of historical data (2016-2024)
- **Spatial features**: latitude, longitude for location-aware predictions
- **Neighborhood-level forecasts**: Different predictions for different areas

## Files Created

### Import Script

- `seed_nea_historical_data.py` - Imports NEA CSV files into database

### Documentation

- `NEA_HISTORICAL_DATA_IMPORT_GUIDE.md` - Detailed import guide
- `NEA_MULTI_STATION_IMPLEMENTATION_SUMMARY.md` - Complete implementation summary
- `QUICK_START_NEA_IMPORT.md` - This file

### Updated Files

- `ml/prepare_training_data.py` - Now supports multi-station data with source filtering
- `ml/feature_engineer.py` - Added spatial features (latitude, longitude, distance, coastal)

### New Tools

- `ml/visualize_spatial_data.py` - Visualize station locations and spatial distribution

## Expected Output

### After Import

```
================================================================================
IMPORT COMPLETE
================================================================================
Total records inserted: 850,000
Stations: 12
Date range: 2016-01-01T00:00:00+08:00 to 2024-12-31T23:00:00+08:00

Stations:
  S43: Kim Chuan
  S50: Clementi
  S60: Sentosa
  S107: East Coast Parkway
  S109: Ang Mo Kio
  S111: Scotts Road
  S117: Banyan Road
  ...
================================================================================
```

### After Visualization

- `ml/station_locations.png` - Map showing all station locations
- `ml/rainfall_spatial_distribution.png` - Rainfall/temp/humidity by location
- `ml/rainfall_classes_spatial.png` - NEA rainfall classes by location
- `ml/station_summary.csv` - Statistics for each station

### After Training Data Prep

```
================================================================================
TRAINING DATASET SUMMARY
================================================================================
Total observations: 850,000
Date range: 2016-01-01 to 2024-12-31
Features: 30 columns
Spatial coverage: 12 unique locations
  Latitude range: 1.2500 to 1.4500
  Longitude range: 103.7000 to 104.0000

Rainfall class distribution:
  Class 0 (No Rain): 680,000 (80.0%)
  Class 1 (Light Showers): 102,000 (12.0%)
  Class 2 (Moderate Showers): 51,000 (6.0%)
  Class 3 (Heavy Showers): 12,750 (1.5%)
  Class 4 (Thundery Showers): 3,400 (0.4%)
  Class 5 (Very Heavy Rain): 850 (0.1%)

✓ Training dataset preparation complete
================================================================================
```

## Verification Checklist

After running the import and visualization:

- [ ] Import completed successfully (no errors)
- [ ] 10+ stations imported
- [ ] 500,000+ observations imported
- [ ] Date range covers 2016-2024
- [ ] Station locations map shows stations spread across Singapore
- [ ] Rainfall varies by location (not all identical)
- [ ] Temperature ranges 24-34°C (reasonable for Singapore)
- [ ] Humidity ranges 60-100% (reasonable)

## Next Steps

1. **Update `train_multiclass_classifier.py`**:

   - Include spatial features in training
   - Save models to correct paths
   - Train for 1h, 3h, 6h horizons

2. **Retrain models**:

   ```bash
   python ml/train_multiclass_classifier.py
   ```

3. **Update prediction service**:

   - Match user coordinates to nearest station
   - Generate location-specific forecasts

4. **Compare performance**:
   - Train with NEA data
   - Train with Open-Meteo data
   - Compare accuracy metrics

## Troubleshooting

### No CSV files found

```bash
# Check directory exists
ls nea_historical_data/

# Should see 45 CSV files
# If not, download from data.gov.sg
```

### Import fails with "Invalid coordinates"

- Some rows may have missing lat/lon
- Script will skip these rows automatically
- Check logs for details

### Visualization shows no data

```bash
# Check database has data
sqlite3 data/weather.db "SELECT COUNT(*) FROM weather_records WHERE source_api LIKE '%nea%';"

# Should show >500,000
```

### Models not using spatial features

```python
# In train_multiclass_classifier.py, verify:
from ml.feature_engineer import get_feature_columns

feature_cols = get_feature_columns()
print(feature_cols)  # Should include 'latitude', 'longitude'
```

## Support

- **Import issues**: Check `NEA_HISTORICAL_DATA_IMPORT_GUIDE.md`
- **Implementation details**: Check `NEA_MULTI_STATION_IMPLEMENTATION_SUMMARY.md`
- **Data source**: https://data.gov.sg/collections/2281/view
- **NEA contact**: sales_climo@nea.gov.sg

## Key Benefits

✅ **Consistent source**: NEA historical → NEA real-time (no mismatch)  
✅ **Long history**: 8+ years (2016-2024)  
✅ **Multiple stations**: 10+ locations across Singapore  
✅ **Spatial features**: Latitude, longitude for location-aware predictions  
✅ **Neighborhood-level**: Different forecasts for different areas  
✅ **No shortcuts**: Real data, real predictions, real locations

**Ready to get started? Download the CSV files and run the import!** 🚀
