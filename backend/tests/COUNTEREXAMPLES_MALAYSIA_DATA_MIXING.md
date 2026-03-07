# Counterexamples - Malaysia Data Mixing Bug

**Test File**: `test_malaysia_data_mixing_exploration.py`  
**Bug**: Malaysia API mixes current observations with forecast data in weather_data table  
**Status**: ✓ Bug Confirmed (Tests FAIL as expected on unfixed code)

## Summary

The bug condition exploration tests have successfully surfaced counterexamples demonstrating that Malaysia data collection stores 2,520+ records (mixing current observations with 7 forecast periods per location) instead of ~284 records (current observations only).

## Counterexample 1: Excessive Record Count

**Test**: `test_malaysia_returns_excessive_records_with_forecasts`

**Finding**:

- **Total records returned**: 1,988 records
- **Expected after fix**: ~284 records (current observations only)
- **Unique locations**: 284
- **Records per location**: 7.0
- **Expected records per location after fix**: 1 (current observation only)

**Sample Location Data** (Location_0):

```
Period 0: 2026-03-08 03:35:42 - Temp: 28.0°C (Current observation)
Period 1: 2026-03-08 06:35:42 - Temp: 29.0°C (Forecast +3h)
Period 2: 2026-03-08 09:35:42 - Temp: 30.0°C (Forecast +6h)
Period 3: 2026-03-08 12:35:42 - Temp: 31.0°C (Forecast +9h)
Period 4: 2026-03-08 15:35:42 - Temp: 32.0°C (Forecast +12h)
Period 5: 2026-03-08 18:35:42 - Temp: 33.0°C (Forecast +15h)
Period 6: 2026-03-08 21:35:42 - Temp: 34.0°C (Forecast +18h)
```

**Impact**:

- Data leakage risk: ML training could see future forecast data
- Cannot benchmark ML predictions against official forecasts
- Database bloat: 7x more records than necessary

## Counterexample 2: Property-Based Test Confirms Systematic Bug

**Test**: `test_malaysia_forecast_mixing_property`

**Finding**:

- **Test case**: 50 locations with 5 forecast periods
- **Records returned**: 250 records
- **Expected**: ~50 records (current observations only)
- **Records per location**: 5.0
- **Expected per location**: 1.0

**Conclusion**: The bug occurs systematically across all input variations, not just specific cases.

## Counterexample 3: Forecast Data in weather_data Table

**Test**: `test_malaysia_forecast_data_in_weather_data_table`

**Finding** (Kuala Lumpur):

- **Records stored**: 3 records
- **Expected after fix**: 1 record (current observation only)

**Records breakdown**:

```
Record 1: 2026-03-08 03:35:45 - Temp: 28.0°C (Current)
Record 2: 2026-03-08 06:35:45 - Temp: 29.0°C (Forecast +3h)
Record 3: 2026-03-08 09:35:45 - Temp: 30.0°C (Forecast +6h)
```

**Impact**: The weather_data table contains forecast data mixed with current observations, creating data leakage risk.

## Counterexample 4: Cross-Country Comparison

**Test**: `test_compare_malaysia_vs_singapore_indonesia_record_counts`

**Finding**:

### Singapore:

- Total records: 15
- Unique locations: 15
- Records per location: 1.0 ✓

### Malaysia:

- Total records: 1,988
- Unique locations: 284
- Records per location: 7.0 ✗

**Discrepancy**: Malaysia has 7.0 records per location while Singapore has 1.0 records per location, despite both being current observation systems.

**Conclusion**: Malaysia is mixing current observations with forecast data, while Singapore correctly stores only current observations.

## Root Cause Analysis

The `_parse_malaysia_data()` method in `data_collector.py` does not filter forecast periods. It processes all records from the Malaysia API response, which includes:

- 1 current observation per location (period 0)
- 6 forecast periods per location (periods 1-6)

**Current behavior**: All 7 periods are stored in weather_data table  
**Expected behavior**: Only period 0 (current observation) should be stored in weather_data table  
**Forecast data**: Periods 1-6 should be stored in a separate forecast_data table

## Fix Requirements

1. **Phase 1**: Modify `_parse_malaysia_data()` to filter only current observations (period 0)

   - Reduce Malaysia records from 2,520 to ~284 in weather_data table
   - Update tests to expect ~284 records instead of 2,520

2. **Phase 2**: Create separate forecast_data table
   - Store forecast periods 1-6 in forecast_data table
   - Enable benchmarking ML predictions against official forecasts
   - Prevent data leakage in ML training

## Test Execution Results

All 4 tests **FAILED as expected** on unfixed code, confirming the bug exists:

```
FAILED test_malaysia_returns_excessive_records_with_forecasts
FAILED test_malaysia_forecast_mixing_property
FAILED test_malaysia_forecast_data_in_weather_data_table
FAILED test_compare_malaysia_vs_singapore_indonesia_record_counts
```

**Status**: ✓ Bug condition confirmed  
**Next Step**: Implement fix in Task 10.3 (Phase 1)  
**Expected Outcome After Fix**: All tests PASS
