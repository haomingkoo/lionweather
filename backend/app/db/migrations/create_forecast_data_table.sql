-- Migration: Create forecast_data table for official weather forecasts
-- Purpose: Store official forecasts from Singapore, Malaysia, and Indonesia APIs
--          to enable benchmarking ML predictions against official forecasts
-- Separation: This table is separate from weather_data (current observations)
--             to prevent data leakage in ML training

-- Create forecast_data table
CREATE TABLE IF NOT EXISTS forecast_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Timing information
    prediction_time TEXT NOT NULL,        -- When the forecast was made
    target_time_start TEXT NOT NULL,      -- Start of forecast period
    target_time_end TEXT NOT NULL,        -- End of forecast period
    
    -- Location information
    country TEXT NOT NULL,                -- singapore, malaysia, indonesia
    location TEXT,                        -- Location name (optional for country-wide forecasts)
    latitude REAL,                        -- Latitude (optional)
    longitude REAL,                       -- Longitude (optional)
    
    -- Forecast data (ranges for temperature, humidity, wind speed)
    temperature_low REAL,                 -- Minimum temperature forecast (°C)
    temperature_high REAL,                -- Maximum temperature forecast (°C)
    humidity_low REAL,                    -- Minimum humidity forecast (%)
    humidity_high REAL,                   -- Maximum humidity forecast (%)
    wind_speed_low REAL,                  -- Minimum wind speed forecast (km/h)
    wind_speed_high REAL,                 -- Maximum wind speed forecast (km/h)
    wind_direction TEXT,                  -- Wind direction (e.g., "NE", "SW")
    forecast_description TEXT,            -- Weather condition description
    
    -- Metadata
    source_api TEXT NOT NULL,             -- API source (nea, malaysia_met, open_meteo)
    created_at TEXT NOT NULL,             -- When record was stored
    
    -- Prevent duplicate forecasts for same prediction time and target period
    UNIQUE(prediction_time, target_time_start, target_time_end, country, location)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_forecast_country 
ON forecast_data(country);

CREATE INDEX IF NOT EXISTS idx_forecast_location 
ON forecast_data(country, location);

CREATE INDEX IF NOT EXISTS idx_forecast_target_time 
ON forecast_data(target_time_start);

CREATE INDEX IF NOT EXISTS idx_forecast_prediction_time 
ON forecast_data(prediction_time);

CREATE INDEX IF NOT EXISTS idx_forecast_composite 
ON forecast_data(country, location, target_time_start);
