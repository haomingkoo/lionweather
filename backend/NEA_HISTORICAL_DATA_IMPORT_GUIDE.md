# NEA Historical Data Import Guide

This guide explains how to download and import NEA (National Environment Agency) historical weather data from data.gov.sg for training ML models.

## Why NEA Historical Data?

Using NEA historical data provides several advantages:

1. **Consistent Source**: NEA historical → NEA real-time = no data mismatch
2. **Multiple Stations**: 10+ weather stations across Singapore with coordinates
3. **Long History**: 2016-2024 (8+ years of data, ~96M rows)
4. **Neighborhood-Level**: Each station has specific lat/lon for location-aware predictions
5. **Official Data**: Same source as Singapore's official weather service

## Data Source

All data is available from: https://data.gov.sg/collections/2281/view

## Required Datasets

Download the following collections (each has 9 CSV files, one per year 2016-2024):

### 1. Historical Air Temperature across Singapore

- Collection URL: https://data.gov.sg/collections/2281/view
- Files: `air_temperature_2016.csv` through `air_temperature_2024.csv`
- Parameters: Temperature in °C

### 2. Historical Rainfall across Singapore

- Collection URL: https://data.gov.sg/collections/2281/view
- Files: `rainfall_2016.csv` through `rainfall_2024.csv`
- Parameters: Rainfall in mm

### 3. Historical Relative Humidity across Singapore

- Collection URL: https://data.gov.sg/collections/2281/view
- Files: `relative_humidity_2016.csv` through `relative_humidity_2024.csv`
- Parameters: Relative humidity in %

### 4. Historical Wind Speed across Singapore

- Collection URL: https://data.gov.sg/collections/2281/view
- Files: `wind_speed_2016.csv` through `wind_speed_2024.csv`
- Parameters: Wind speed in km/h

### 5. Historical Wind Direction across Singapore

- Collection URL: https://data.gov.sg/collections/2281/view
- Files: `wind_direction_2016.csv` through `wind_direction_2024.csv`
- Parameters: Wind direction in degrees (0-360)

## CSV Format

Each CSV file has the following format:

```csv
Timestamp,Station Id,Station Name,Station Device Id,Location Longitude,Location Latitude,value
2024-01-01T00:00:00+08:00,S50,Clementi,S50,103.7768,1.3337,28.5
2024-01-01T00:00:00+08:00,S43,Kim Chuan,S43,103.8853,1.3399,27.8
...
```

## Download Instructions

### Option 1: Manual Download (Recommended for First Time)

1. Visit https://data.gov.sg/collections/2281/view
2. Search for "Historical Air Temperature across Singapore"
3. Click on the collection
4. Download all 9 CSV files (2016-2024)
5. Repeat for the other 4 parameters (Rainfall, Humidity, Wind Speed, Wind Direction)
6. Total: 45 CSV files (5 parameters × 9 years)

### Option 2: API Download (Advanced)

You can use the data.gov.sg API to download files programmatically:

```python
import requests

collection_id = 2281  # Historical weather data collection
url = f"https://api-production.data.gov.sg/v2/public/api/collections/{collection_id}/metadata"
response = requests.get(url)
metadata = response.json()

# Extract download URLs from metadata
# (Implementation left as exercise)
```

## File Organization

Create a directory structure like this:

```
lionweather/backend/nea_historical_data/
├── air_temperature_2016.csv
├── air_temperature_2017.csv
├── air_temperature_2018.csv
├── air_temperature_2019.csv
├── air_temperature_2020.csv
├── air_temperature_2021.csv
├── air_temperature_2022.csv
├── air_temperature_2023.csv
├── air_temperature_2024.csv
├── rainfall_2016.csv
├── rainfall_2017.csv
├── rainfall_2018.csv
├── rainfall_2019.csv
├── rainfall_2020.csv
├── rainfall_2021.csv
├── rainfall_2022.csv
├── rainfall_2023.csv
├── rainfall_2024.csv
├── relative_humidity_2016.csv
├── relative_humidity_2017.csv
├── relative_humidity_2018.csv
├── relative_humidity_2019.csv
├── relative_humidity_2020.csv
├── relative_humidity_2021.csv
├── relative_humidity_2022.csv
├── relative_humidity_2023.csv
├── relative_humidity_2024.csv
├── wind_speed_2016.csv
├── wind_speed_2017.csv
├── wind_speed_2018.csv
├── wind_speed_2019.csv
├── wind_speed_2020.csv
├── wind_speed_2021.csv
├── wind_speed_2022.csv
├── wind_speed_2023.csv
├── wind_speed_2024.csv
├── wind_direction_2016.csv
├── wind_direction_2017.csv
├── wind_direction_2018.csv
├── wind_direction_2019.csv
├── wind_direction_2020.csv
├── wind_direction_2021.csv
├── wind_direction_2022.csv
├── wind_direction_2023.csv
└── wind_direction_2024.csv
```

## Import Process

### Step 1: Create Data Directory

```bash
cd lionweather/backend
mkdir nea_historical_data
```

### Step 2: Download CSV Files

Download all 45 CSV files from data.gov.sg and place them in the `nea_historical_data` directory.

### Step 3: Run Import Script

```bash
cd lionweather/backend
python seed_nea_historical_data.py
```

Or specify a custom data directory:

```bash
python seed_nea_historical_data.py /path/to/csv/files
```

### Step 4: Verify Import

The script will output:

- Number of records parsed from each CSV
- Number of complete observations created
- Number of records inserted into database
- List of stations imported
- Date range of imported data

Example output:

```
================================================================================
NEA HISTORICAL DATA IMPORT
================================================================================
Data directory: /path/to/nea_historical_data
Years: 2016-2024

Found 45 CSV files total

Parsing air_temperature_2024.csv...
✓ Parsed 96,000 records from air_temperature_2024.csv
...

Parsing summary:
  Temperature records: 864,000
  Rainfall records: 864,000
  Humidity records: 864,000
  Wind speed records: 864,000
  Wind direction records: 864,000

Grouping records by timestamp and station...
Found 864,000 unique (timestamp, station) combinations
✓ Created 850,000 complete observations

Storing 850,000 observations in database...
✓ Inserted 850,000 records, skipped 0 duplicates

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

## Expected Data Volume

- **Total rows per parameter**: ~96M rows (as mentioned by user)
- **File size per parameter**: ~1.1 GB
- **Total data**: ~5.5 GB (5 parameters)
- **After grouping**: ~10-12M complete observations (one per timestamp per station)
- **Database size**: ~2-3 GB (SQLite with indexes)

## Station Coverage

NEA operates multiple weather stations across Singapore:

- **S50**: Clementi (West)
- **S43**: Kim Chuan (East)
- **S109**: Ang Mo Kio (North)
- **S111**: Scotts Road (Central)
- **S117**: Banyan Road (Central)
- **S107**: East Coast Parkway (East)
- **S60**: Sentosa (South)
- And more...

Each station has specific coordinates, enabling neighborhood-level predictions.

## Next Steps After Import

Once the data is imported:

1. **Update `prepare_training_data.py`** to query multi-station data
2. **Add spatial features** (latitude, longitude) to `feature_engineer.py`
3. **Retrain models** with NEA multi-station data for 1h, 3h, 6h horizons
4. **Update prediction service** to match user coordinates to nearest station
5. **Compare performance** against Open-Meteo baseline (optional)

## Troubleshooting

### "No CSV files found"

- Check that CSV files are in the correct directory
- Verify file names match the expected patterns (e.g., `air_temperature_2024.csv`)
- Check file permissions

### "Invalid coordinates for station"

- Some rows may have missing or invalid lat/lon values
- The script will skip these rows and continue

### "Error parsing row"

- CSV format may have changed
- Check that CSV files are not corrupted
- Verify encoding is UTF-8

### Database errors

- Ensure `weather_records` table exists (run migrations first)
- Check database file permissions
- Verify sufficient disk space

## Data Quality Notes

From the NEA data.gov.sg disclaimer:

> This dataset may contain missing records and has not undergone quality control procedures applied to climate data and records. For official climate records or climate data reports, please contact sales_climo@nea.gov.sg.

The import script handles missing data by:

- Skipping rows with missing critical features (temperature, humidity)
- Using 0.0 for missing rainfall (no rain)
- Using None for missing wind speed/direction
- Filtering out observations without complete critical features

## License

NEA data is provided under the Singapore Open Data License:
https://data.gov.sg/open-data-licence

Please review the license terms before using the data.

## Support

For issues with:

- **Data download**: Contact data.gov.sg support
- **Import script**: Check logs and error messages
- **Data quality**: Contact NEA at sales_climo@nea.gov.sg
