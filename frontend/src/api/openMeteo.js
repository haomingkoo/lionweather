/**
 * DEPRECATED: This file is deprecated and should not be used.
 * Use backend.js instead to call the LionWeather backend API.
 *
 * The backend caches data from multiple sources and provides a unified interface.
 * Direct API calls bypass the caching layer and defeat the purpose of the backend.
 *
 * Migration:
 * - Replace: import { getCurrentWeather } from './openMeteo'
 * - With: import { getCurrentWeather } from './backend'
 *
 * Open-Meteo API integration for weather data not provided by NEA
 * API Documentation: https://open-meteo.com/en/docs
 */

const OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast";

/**
 * Fetch current weather conditions from Open-Meteo
 * @param {number} latitude - Location latitude
 * @param {number} longitude - Location longitude
 * @returns {Promise<Object>} Current weather data including visibility and pressure
 */
export async function getCurrentWeather(latitude, longitude) {
  try {
    const params = new URLSearchParams({
      latitude: latitude.toString(),
      longitude: longitude.toString(),
      hourly: "temperature_2m,visibility,surface_pressure",
      timezone: "auto",
      forecast_days: "1",
    });

    const response = await fetch(`${OPEN_METEO_BASE_URL}?${params}`);
    if (!response.ok) {
      throw new Error(`Open-Meteo API error: ${response.status}`);
    }

    const data = await response.json();

    // Get current hour's data (first entry in hourly arrays)
    const currentIndex = 0;
    const visibility = data.hourly?.visibility?.[currentIndex];
    const pressure = data.hourly?.surface_pressure?.[currentIndex];

    return {
      visibility: visibility ? Math.round(visibility / 1000) : null, // Convert meters to km
      pressure: pressure ? Math.round(pressure) : null, // Already in hPa
    };
  } catch (error) {
    console.error("Error fetching Open-Meteo current weather:", error);
    return {
      visibility: null,
      pressure: null,
    };
  }
}

/**
 * Fetch 7-day forecast from Open-Meteo (for days 5-7 hybrid forecast)
 * @param {number} latitude - Location latitude
 * @param {number} longitude - Location longitude
 * @returns {Promise<Array>} Array of daily forecast objects
 */
export async function get7DayForecast(latitude, longitude) {
  try {
    const params = new URLSearchParams({
      latitude: latitude.toString(),
      longitude: longitude.toString(),
      daily: "temperature_2m_max,temperature_2m_min,weathercode",
      timezone: "auto",
      forecast_days: "7",
    });

    const response = await fetch(`${OPEN_METEO_BASE_URL}?${params}`);
    if (!response.ok) {
      throw new Error(`Open-Meteo API error: ${response.status}`);
    }

    const data = await response.json();

    if (!data.daily) {
      return [];
    }

    // Map Open-Meteo weather codes to our condition strings
    const weatherCodeToCondition = (code) => {
      if (code === 0) return "Clear";
      if (code <= 3) return "Partly Cloudy";
      if (code <= 48) return "Cloudy";
      if (code <= 67) return "Rainy";
      if (code <= 77) return "Rainy";
      if (code <= 82) return "Rainy";
      if (code <= 86) return "Rainy";
      if (code <= 99) return "Thunderstorm";
      return "Cloudy";
    };

    // Convert to our forecast format
    const forecasts = data.daily.time.map((date, index) => ({
      date,
      temperature: {
        high: data.daily.temperature_2m_max?.[index] || null,
        low: data.daily.temperature_2m_min?.[index] || null,
      },
      forecast: weatherCodeToCondition(data.daily.weathercode?.[index] || 0),
      source: "Open-Meteo",
    }));

    return forecasts;
  } catch (error) {
    console.error("Error fetching Open-Meteo 7-day forecast:", error);
    return [];
  }
}
