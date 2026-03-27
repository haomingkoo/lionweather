/**
 * Backend API integration for LionWeather
 *
 * Uses the shared request() wrapper from client.js for unified
 * timeout handling, error messages, and base URL configuration.
 */

import { request } from "./client.js";

export async function getCurrentWeather(latitude, longitude) {
  const params = new URLSearchParams({
    lat: latitude.toString(),
    lng: longitude.toString(),
  });

  const data = await request(`/weather?${params}`);

  return {
    condition: data.condition || "Unknown",
    temperature: data.temperature ?? null,
    humidity: data.humidity ?? null,
    wind_speed: data.wind_speed ?? null,
    wind_direction: data.wind_direction ?? null,
    pressure: data.pressure ?? null,
    visibility: data.visibility ?? null,
    uv_index: data.uv_index ?? null,
    area: data.area || "Unknown Area",
    source: data.source || "Backend",
  };
}

export async function get7DayForecast(latitude, longitude) {
  const params = new URLSearchParams({
    lat: latitude.toString(),
    lng: longitude.toString(),
    days: "7",
  });

  const data = await request(`/forecasts/?${params}`);

  if (!Array.isArray(data)) return [];

  return data.map((forecast) => ({
    date: forecast.date,
    temperature: {
      high: forecast.temperature?.high ?? forecast.temp_high ?? null,
      low: forecast.temperature?.low ?? forecast.temp_low ?? null,
    },
    forecast: forecast.forecast || forecast.condition || "Unknown",
    source: forecast.source || "Backend",
  }));
}

export async function getHourlyForecast(latitude, longitude) {
  try {
    const params = new URLSearchParams({
      lat: latitude.toString(),
      lng: longitude.toString(),
    });

    const slots = await request(`/forecasts/hourly?${params}`);
    return slots.map((slot) => ({
      ...slot,
      time: new Date(slot.time),
    }));
  } catch {
    return [];
  }
}

export async function getWeatherByLocation(locationName) {
  const params = new URLSearchParams({ location: locationName });
  return request(`/weather/location?${params}`);
}

export async function checkBackendHealth() {
  return request("/health");
}

export async function getBackendStatus() {
  return request("/status");
}
