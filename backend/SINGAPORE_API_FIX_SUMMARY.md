# Singapore API Data Collection Fix

## Problem

Singapore weather API was returning 0 records despite successful API calls. Expected ~50 records per collection cycle.

## Root Cause

The Singapore API v2 format changed from the old structure:

```json
{
  "data": {
    "records": [
      {
        "item": {
          "readings": [
            {"station": {"id": "...", "name": "..."}, "value": ...}
          ]
        }
      }
    ]
  }
}
```

To the new structure:

```json
{
  "code": 0,
  "data": {
    "stations": [
      {"id": "S50", "name": "Clementi Road", "location": {...}}
    ],
    "readings": [
      {
        "timestamp": "...",
        "data": [
          {"stationId": "S50", "value": 28.5}
        ]
      }
    ]
  }
}
```

The code was still using the old format, causing it to fail to parse any data.

## Solution

Updated `_parse_singapore_data()` method in `lionweather/backend/app/services/data_collector.py` to:

1. Extract stations from `data.stations` instead of `data.records[0].item.readings`
2. Extract readings from `data.readings[0].data` instead of `data.records[0].item.readings`
3. Match readings to stations using `stationId` field
4. Build station map from separate stations list

## Results

- ✅ Successfully collecting 15 Singapore weather records per API call
- ✅ All records have valid temperature, humidity, wind speed, wind direction data
- ✅ All records have proper location names and coordinates
- ✅ Bug condition exploration test now passes
- ✅ Malaysia preservation tests still pass (no regression)

## Files Modified

1. `lionweather/backend/app/services/data_collector.py` - Fixed `_parse_singapore_data()` method
2. `lionweather/backend/tests/test_singapore_data_collection.py` - Updated test mocks to match new API format

## Testing

- Unit tests pass with mocked API responses
- Real API integration test confirms 15 records collected
- All preservation tests pass
