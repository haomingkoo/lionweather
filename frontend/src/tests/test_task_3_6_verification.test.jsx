/**
 * Task 3.6 Verification Test
 * Verifies that visibility and pressure cards display real Open-Meteo data
 * and that the 7-day hybrid forecast works correctly
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { DetailedWeatherCard } from "../components/DetailedWeatherCard";
import * as openMeteoApi from "../api/openMeteo";

// Mock the API modules
vi.mock("../api/client", () => ({
  request: vi.fn(),
}));

vi.mock("../api/forecasts", () => ({
  get24HourForecast: vi.fn(),
  get4DayForecast: vi.fn(),
}));

vi.mock("../utils/sunTimes", () => ({
  getSunTimes: vi.fn().mockResolvedValue({
    sunrise: "6:45 AM",
    sunset: "7:10 PM",
  }),
}));

describe("Task 3.6: Open-Meteo Integration", () => {
  const mockLocation = {
    id: 1,
    name: "Singapore",
    latitude: 1.3521,
    longitude: 103.8198,
    weather: {
      condition: "Partly Cloudy",
      temperature: 28,
      area: "Singapore",
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should display real visibility data from Open-Meteo API", async () => {
    // Mock Open-Meteo API to return visibility data
    const getCurrentWeatherSpy = vi
      .spyOn(openMeteoApi, "getCurrentWeather")
      .mockResolvedValue({
        visibility: 15, // 15 km
        pressure: 1012,
      });

    render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

    // Wait for Open-Meteo data to load
    await waitFor(
      () => {
        const visibilityValue = screen.getByText("15");
        expect(visibilityValue).toBeInTheDocument();
      },
      { timeout: 3000 },
    );

    // Verify Open-Meteo API was called with correct coordinates
    expect(getCurrentWeatherSpy).toHaveBeenCalledWith(1.3521, 103.8198);

    // Verify the source indicator is displayed
    const sourceIndicators = screen.getAllByText("Open-Meteo");
    expect(sourceIndicators.length).toBeGreaterThan(0);
  });

  it("should display real pressure data from Open-Meteo API", async () => {
    // Mock Open-Meteo API to return pressure data
    vi.spyOn(openMeteoApi, "getCurrentWeather").mockResolvedValue({
      visibility: 12,
      pressure: 1015, // 1015 hPa
    });

    render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

    // Wait for Open-Meteo data to load
    await waitFor(
      () => {
        const pressureValue = screen.getByText("1015");
        expect(pressureValue).toBeInTheDocument();
      },
      { timeout: 3000 },
    );

    // Verify the source indicator is displayed
    const sourceIndicators = screen.getAllByText("Open-Meteo");
    expect(sourceIndicators.length).toBeGreaterThan(0);
  });

  it("should display N/A when Open-Meteo data is unavailable", async () => {
    // Mock Open-Meteo API to return null values
    vi.spyOn(openMeteoApi, "getCurrentWeather").mockResolvedValue({
      visibility: null,
      pressure: null,
    });

    render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

    // Wait for component to render
    await waitFor(
      () => {
        const naValues = screen.getAllByText("N/A");
        // Should have at least 2 N/A values (visibility and pressure)
        expect(naValues.length).toBeGreaterThanOrEqual(2);
      },
      { timeout: 3000 },
    );
  });

  it("should implement 7-day hybrid forecast (NEA days 1-4, Open-Meteo days 5-7)", async () => {
    const { get4DayForecast } = await import("../api/forecasts");

    // Mock NEA 4-day forecast
    get4DayForecast.mockResolvedValue({
      forecasts: [
        {
          date: "2024-01-15",
          temperature: { high: 32, low: 25 },
          forecast: "Partly Cloudy",
        },
        {
          date: "2024-01-16",
          temperature: { high: 31, low: 24 },
          forecast: "Cloudy",
        },
        {
          date: "2024-01-17",
          temperature: { high: 30, low: 23 },
          forecast: "Rainy",
        },
        {
          date: "2024-01-18",
          temperature: { high: 29, low: 24 },
          forecast: "Thunderstorm",
        },
      ],
    });

    // Mock Open-Meteo 7-day forecast
    vi.spyOn(openMeteoApi, "get7DayForecast").mockResolvedValue([
      {
        date: "2024-01-15",
        temperature: { high: 32, low: 25 },
        forecast: "Partly Cloudy",
        source: "Open-Meteo",
      },
      {
        date: "2024-01-16",
        temperature: { high: 31, low: 24 },
        forecast: "Cloudy",
        source: "Open-Meteo",
      },
      {
        date: "2024-01-17",
        temperature: { high: 30, low: 23 },
        forecast: "Rainy",
        source: "Open-Meteo",
      },
      {
        date: "2024-01-18",
        temperature: { high: 29, low: 24 },
        forecast: "Thunderstorm",
        source: "Open-Meteo",
      },
      {
        date: "2024-01-19",
        temperature: { high: 31, low: 25 },
        forecast: "Partly Cloudy",
        source: "Open-Meteo",
      },
      {
        date: "2024-01-20",
        temperature: { high: 32, low: 26 },
        forecast: "Clear",
        source: "Open-Meteo",
      },
      {
        date: "2024-01-21",
        temperature: { high: 33, low: 26 },
        forecast: "Partly Cloudy",
        source: "Open-Meteo",
      },
    ]);

    render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

    // Wait for forecast data to load
    await waitFor(
      () => {
        // Should display "7-Day Forecast" title
        const forecastTitle = screen.getByText(/7-Day Forecast/i);
        expect(forecastTitle).toBeInTheDocument();

        // Should have NEA source indicators for days 1-4
        const neaIndicators = screen.getAllByText("NEA");
        expect(neaIndicators.length).toBe(4);

        // Should have Open-Meteo source indicators for days 5-7
        const openMeteoIndicators = screen.getAllByText("Open-Meteo");
        expect(openMeteoIndicators.length).toBeGreaterThanOrEqual(3); // At least 3 for days 5-7, plus visibility/pressure
      },
      { timeout: 3000 },
    );
  });

  it("should not display hardcoded values (10 km visibility, 1013 hPa pressure)", async () => {
    // Mock Open-Meteo API to return different values
    vi.spyOn(openMeteoApi, "getCurrentWeather").mockResolvedValue({
      visibility: 20, // Different from hardcoded 10
      pressure: 1008, // Different from hardcoded 1013
    });

    render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

    // Wait for Open-Meteo data to load
    await waitFor(
      () => {
        // Should NOT find hardcoded values
        expect(screen.queryByText("10")).not.toBeInTheDocument();
        expect(screen.queryByText("1013")).not.toBeInTheDocument();

        // Should find real values
        expect(screen.getByText("20")).toBeInTheDocument();
        expect(screen.getByText("1008")).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });
});
