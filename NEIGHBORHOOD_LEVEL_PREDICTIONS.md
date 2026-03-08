# Neighborhood-Level Weather Predictions for Singapore

## Problem Solved

**Your concern**: "If the whole singapore is one weather, that kind of suck right? like whats the point of asking people to set their location"

**You're absolutely right!** Predicting weather for "all of Singapore" makes location selection pointless.

## Solution Implemented

### Multi-Region Historical Data Collection

Updated `seed_historical_data.py` to collect data for **5 Singapore regions**:

1. **Central** (1.3521°N, 103.8198°E)
   - CBD, Orchard, Marina Bay
2. **North** (1.4382°N, 103.7891°E)
   - Woodlands, Yishun, Sembawang
3. **East** (1.3236°N, 103.9273°E)
   - Changi, Bedok, Tampines
4. **West** (1.3399°N, 103.7090°E)
   - Jurong, Clementi, Tuas
5. **Northeast** (1.3644°N, 103.8917°E)
   - Ang Mo Kio, Serangoon, Hougang

### Why This Matters

**Singapore has microclimates**:

- Rain in the East doesn't mean rain in the West
- Coastal areas vs inland areas have different patterns
- Afternoon thunderstorms are highly localized
- Rainfall is the most variable weather parameter in Singapore

**Better user experience**:

- "Rainfall forecast for East Singapore" vs "Rainfall forecast for Singapore"
- Users see predictions relevant to their actual location
- Location selection becomes meaningful

## Data Availability

### Historical Data

- ✅ **3+ years available** (2022-01-01 to 2025-03-08)
- ✅ **27,912 records** currently in database (single location)
- ✅ **~140,000 records** after multi-region seeding (5 locations × 27,912)

### Current Status

- ❌ Only 1 central location in database
- ✅ Script updated to support 5 regions
- ⏳ Need to run seeding to populate data

## Next Steps

### 1. Seed Multi-Region Historical Data (IMMEDIATE)

Run the updated seeding script:

```bash
cd lionweather/backend
python seed_historical_data.py
```

This will:

- Fetch 3 years of hourly data for all 5 regions
- Insert ~140,000 records into the database
- Take ~15-20 minutes (API rate limiting)

### 2. Update ML Training (NEXT)

Two approaches:

**Option A: Single Model with Location Feature**

- Add `location` as categorical feature
- Train one model that learns location-specific patterns
- Simpler to maintain

**Option B: Separate Models per Region**

- Train 5 independent models
- Each model specialized for its region
- More complex but potentially more accurate

### 3. Update Prediction Service

Match user coordinates to nearest region:

```python
def get_user_region(lat: float, lon: float) -> str:
    """Match user coordinates to nearest Singapore region"""
    regions = {
        "Central": (1.3521, 103.8198),
        "North": (1.4382, 103.7891),
        "East": (1.3236, 103.9273),
        "West": (1.3399, 103.7090),
        "Northeast": (1.3644, 103.8917),
    }

    # Find nearest region using Haversine distance
    min_dist = float('inf')
    nearest_region = "Central"

    for region_name, (region_lat, region_lon) in regions.items():
        dist = haversine_distance(lat, lon, region_lat, region_lon)
        if dist < min_dist:
            min_dist = dist
            nearest_region = region_name

    return nearest_region
```

### 4. Update UI

Show region in forecast:

- "Rainfall forecast for **East Singapore**"
- "Your location: **Bedok (East)**"
- Optional: Show map with regions

## Expected Improvements

### Accuracy

- **Rainfall prediction**: Significant improvement (most variable parameter)
- **Temperature**: Minimal improvement (stable across Singapore)
- **Humidity**: Moderate improvement (coastal vs inland)

### User Experience

- ✅ Location selection becomes meaningful
- ✅ Predictions feel more relevant
- ✅ Users trust the app more

### Validation

After implementation, backtest by region:

- Compare single-model vs multi-region accuracy
- Measure improvement in rainfall F1 score
- Test with real users

## Technical Details

### Database Schema

No changes needed! The `weather_records` table already has:

- `location` column (stores region name)
- `latitude` and `longitude` columns

### API Changes

Minimal changes needed:

- Prediction endpoint accepts user coordinates
- Returns region-specific forecast
- Includes region name in response

### Backward Compatibility

The script supports both modes:

```python
# Multi-region mode (new)
seeder = HistoricalDataSeeder(months_back=36, use_regions=True)

# Single location mode (legacy)
seeder = HistoricalDataSeeder(months_back=36, use_regions=False)
```

## Conclusion

**Answer**: You're absolutely right - predicting for "all of Singapore" makes location selection pointless.

**Solution**: Neighborhood-level predictions (5 regions) provide meaningful, location-specific forecasts.

**Status**: Script updated ✅, ready to seed data ⏳

**Next**: Run `python seed_historical_data.py` to populate multi-region data, then retrain models.
