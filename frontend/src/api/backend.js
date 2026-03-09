/**
 * Backend API integration for LionWeather
 *
 * This module provides functions to fetch weather data from the LionWeather backend API.
 * The backend caches data from multiple sources (Singapore, Malaysia, Indonesia) and
 * provides a unified interface for the frontend.
 *
 * API Base URL is determined by:
 * - Production: Uses VITE_API_BASE_URL environment variable (set in Railway)
 * - Development: Uses Vite proxy to forward /api requests to localhost backend
 */

// Always use relative /api — Vite proxy handles routing to backend
// in both development (vite dev) and production (vite preview on Railway).
// Never call the backend URL directly from the browser to avoid CORS.
const API_BASE = "/api";

/**
 * Fetch current weather conditions from backend
 *
 * @param {number} latitude - Location latitude
 * @param {number} longitude - Location longitude
 * @returns {Promise<Object>} Current weather data including all variables
 * @throws {Error} If the API request fails
 *
 * Response format:
 * {
 *   condition: string,      // Weather condition description
 *   temperature: number,    // Temperature in Celsius
 *   humidity: number,       // Humidity percentage
 *   wind_speed: number,     // Wind speed in km/h
 *   area: string,          // Location name
 *   source: string         // Data source identifier
 * }
 */
export async function getCurrentWeather(latitude, longitude) {
  try {
    const params = new URLSearchParams({
      lat: latitude.toString(),
      lng: longitude.toString(),
    });

    const response = await fetch(`${API_BASE}/weather?${params}`);

    if (!response.ok) {
      throw new Error(
        `Backend API error: ${response.status} ${response.statusText}`,
      );
    }

    const data = await response.json();

    return {
      condition: data.condition || "Unknown",
      temperature: data.temperature ?? null,
      humidity: data.humidity ?? null,
      wind_speed: data.wind_speed ?? null,
      pressure: data.pressure ?? null,
      visibility: data.visibility ?? null,
      uv_index: data.uv_index ?? null,
      area: data.area || "Unknown Area",
      source: data.source || "Backend",
    };
  } catch (error) {
    console.error("Error fetching current weather from backend:", error);

    // Re-throw with more context
    throw new Error(`Failed to fetch weather data: ${error.message}`);
  }
}

/**
 * Fetch 7-day forecast from backend
 *
 * @param {number} latitude - Location latitude
 * @param {number} longitude - Location longitude
 * @returns {Promise<Array>} Array of daily forecast objects
 * @throws {Error} If the API request fails
 *
 * Response format:
 * [
 *   {
 *     date: string,           // ISO date string
 *     temperature: {
 *       high: number,         // Max temperature in Celsius
 *       low: number           // Min temperature in Celsius
 *     },
 *     forecast: string,       // Weather condition
 *     source: string          // Data source identifier
 *   },
 *   ...
 * ]
 */
export async function get7DayForecast(latitude, longitude) {
  try {
    const params = new URLSearchParams({
      lat: latitude.toString(),
      lng: longitude.toString(),
      days: "7",
    });

    const response = await fetch(`${API_BASE}/forecasts?${params}`);

    if (!response.ok) {
      throw new Error(
        `Backend API error: ${response.status} ${response.statusText}`,
      );
    }

    const data = await response.json();

    // Ensure we return an array
    if (!Array.isArray(data)) {
      console.warn("Backend returned non-array forecast data:", data);
      return [];
    }

    // Normalize forecast data
    return data.map((forecast) => ({
      date: forecast.date,
      temperature: {
        high: forecast.temperature?.high ?? forecast.temp_high ?? null,
        low: forecast.temperature?.low ?? forecast.temp_low ?? null,
      },
      forecast: forecast.forecast || forecast.condition || "Unknown",
      source: forecast.source || "Backend",
    }));
  } catch (error) {
    console.error("Error fetching 7-day forecast from backend:", error);

    // Re-throw with more context
    throw new Error(`Failed to fetch forecast data: ${error.message}`);
  }
}

/**
 * Fetch hourly forecast from Open-Meteo (next 24 hours)
 *
 * @param {number} latitude - Location latitude
 * @param {number} longitude - Location longitude
 * @returns {Promise<Array>} Array of hourly forecast objects with real temperatures
 */
export async function getHourlyForecast(latitude, longitude) {
  try {
    const params = new URLSearchParams({
      latitude: latitude.toString(),
      longitude: longitude.toString(),
      hourly: "temperature_2m,weather_code,precipitation_probability",
      forecast_days: "2",
      timezone: "auto",
    });

    const response = await fetch(
      `https://api.open-meteo.com/v1/forecast?${params}`,
    );

    if (!response.ok) {
      throw new Error(`Open-Meteo error: ${response.status}`);
    }

    const data = await response.json();
    const hourly = data.hourly;
    if (!hourly?.time) return [];

    const now = new Date();
    const results = [];

    for (let i = 0; i < hourly.time.length; i++) {
      const slotTime = new Date(hourly.time[i]);
      // Only include hours from now onwards, max 24 slots
      if (slotTime >= now && results.length < 24) {
        results.push({
          time: slotTime,
          temperature: hourly.temperature_2m[i],
          weather_code: hourly.weather_code[i],
          precip_prob: hourly.precipitation_probability?.[i] ?? null,
        });
      }
    }

    return results;
  } catch (error) {
    console.error("Error fetching hourly forecast:", error);
    return [];
  }
}

/**
 * Fetch weather data for a specific location by name
 *
 * @param {string} locationName - Location name (e.g., "Singapore", "Kuala Lumpur")
 * @returns {Promise<Object>} Weather data for the location
 * @throws {Error} If the API request fails
 */
export async function getWeatherByLocation(locationName) {
  try {
    const params = new URLSearchParams({
      location: locationName,
    });

    const response = await fetch(`${API_BASE}/weather/location?${params}`);

    if (!response.ok) {
      throw new Error(
        `Backend API error: ${response.status} ${response.statusText}`,
      );
    }

    return await response.json();
  } catch (error) {
    console.error("Error fetching weather by location from backend:", error);
    throw new Error(
      `Failed to fetch weather for ${locationName}: ${error.message}`,
    );
  }
}

/**
 * Check backend health status
 *
 * @returns {Promise<Object>} Health status information
 */
export async function checkBackendHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`);

    if (!response.ok) {
      throw new Error(`Backend health check failed: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Backend health check failed:", error);
    throw error;
  }
}

/**
 * Get backend status including data collection statistics
 *
 * @returns {Promise<Object>} Status information including database stats
 */
export async function getBackendStatus() {
  try {
    const response = await fetch(`${API_BASE}/status`);

    if (!response.ok) {
      throw new Error(`Backend status check failed: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Backend status check failed:", error);
    throw error;
  }
}
