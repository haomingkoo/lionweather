# Location Granularity Analysis & Recommendations

## Current Problem

**User's concern**: "If the whole singapore is one weather, that kind of suck right? like whats the point of asking people to set their location"

**Current state**:

- ✅ Real-time data collection: Uses **multiple Singapore weather stations** (~14 stations across neighborhoods)
- ❌ Historical data: Only **1 central location** (1.3521°N, 103.8198°E)
- ❌ ML training: Trained on single-location data
- ❌ Predictions: Cannot provide neighborhood-specific forecasts

## Available Data Sources

### 1. Singapore Weather Stations (Real-time)

From `data_collector.py`, we collect from multiple stations:

- S24 Upper Changi Road North
- S43 Kim Chuan Road
- S44 Nanyang Avenue
- S50 Clementi Road
- S60 Sentosa
- S102 Semakau Island Landfill
- S104 Woodlands Avenue 9
- S106 Pulau Ubin
- S107 East Coast Parkway
- S109 Ang Mo Kio Avenue 5
- S111 Scotts Road
- S115 Tuas South Avenue 3
- S116 West Coast Highway
- S117 Banyan Road

**Coverage**: ~14 stations across Singapore neighborhoods

### 2. Open-Meteo Historical API

Currently using: Single central location (1.3521°N, 103.8198°E)

**Capability**: Can fetch historical data for ANY lat/lon coordinates

- Supports multiple locations
- 3+ years of hourly data available (2022-01-01 to present)
- Same parameters: temperature, rainfall, humidity, wind, pressure, weather_code

## Recommendations

### Option 1: Neighborhood-Level Predictions (RECOMMENDED)

**Approach**: Train separate models for each major Singapore region

**Regions** (5-7 major areas):

1. **Central** (1.3521, 103.8198) - CBD, Orchard
2. **North** (1.4382, 103.7891) - Woodlands, Yishun
3. **East** (1.3236, 103.9273) - Changi, Bedok, Tampines
4. **West** (1.3399, 103.7090) - Jurong, Clementi, Tuas
5. **Northeast** (1.3644, 103.8917) - Ang Mo Kio, Serangoon

**Benefits**:

- ✅ Meaningful location selection for users
- ✅ Captures local weather variations (especially rainfall)
- ✅ Singapore has microclimates - rain in East doesn't mean rain in West
- ✅ Better user experience - "Your neighborhood" vs "All of Singapore"

**Implementation**:

1. Seed historical data for 5-7 locations (3+ years each)
2. Train separate models per location OR train one model with location features
3. User selects neighborhood → get location-specific forecast
4. Match user coordinates to nearest region

**Data volume**: ~140k records (5 locations × 3 years × 8760 hours/year)

### Option 2: Single Island-Wide Model (CURRENT - NOT RECOMMENDED)

**Current approach**: One model for all of Singapore

**Problems**:

- ❌ No point in asking user location
- ❌ Misses local rainfall variations
- ❌ Poor user experience
- ❌ Less accurate (averages out local patterns)

### Option 3: Grid-Based High-Resolution (FUTURE)

**Approach**: 1km × 1km grid across Singapore

**Benefits**:

- ✅ Highest accuracy
- ✅ Precise location matching
- ✅ Can show rainfall maps

**Challenges**:

- ⚠️ Requires 700+ grid points (Singapore is ~730 km²)
- ⚠️ Massive data volume (~2.1M records for 3 years)
- ⚠️ Complex model training
- ⚠️ May hit API rate limits

**Verdict**: Overkill for MVP, consider for v2

## Recommended Action Plan

### Phase 1: Expand to 5 Regions (IMMEDIATE)

1. **Update `seed_historical_data.py`**:

   - Add 5 Singapore regions with coordinates
   - Fetch 3+ years of data per region
   - Store with location labels

2. **Update ML training**:

   - Add `location` as categorical feature OR
   - Train separate models per region

3. **Update prediction service**:

   - Match user coordinates to nearest region
   - Return region-specific forecast

4. **Update UI**:
   - Show region name in forecast
   - "Rainfall forecast for East Singapore"

### Phase 2: Validate Improvement (TESTING)

1. **Backtest by region**:

   - Compare single-model vs multi-region accuracy
   - Measure improvement in rainfall prediction

2. **User testing**:
   - Does neighborhood-level feel more useful?
   - Are predictions more accurate for users?

## Data Availability Confirmation

**Historical data**: ✅ 3+ years available (2022-01-01 to 2025-03-08)

- Current database: 27,912 records (single location)
- Potential: 139,560 records (5 locations × 27,912)

**Open-Meteo supports**:

- Multiple locations: ✅ Yes
- Historical data: ✅ Yes (back to 1940 for some locations)
- Hourly resolution: ✅ Yes
- All required parameters: ✅ Yes

## Conclusion

**Answer to user's question**: You're absolutely right! Predicting for "all of Singapore" makes location selection pointless.

**Solution**: Implement neighborhood-level predictions (5 regions) to provide meaningful, location-specific forecasts.

**Next steps**:

1. Seed historical data for 5 Singapore regions
2. Retrain models with location awareness
3. Update prediction service to use user's region
4. Test and validate improvement
