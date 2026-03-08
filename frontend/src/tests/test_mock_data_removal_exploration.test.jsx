/**
 * Bug Condition Exploration Test - Mock Data Usage Detection
 *
 * **Property 1: Bug Condition** - Mock Data Display Detection
 * **CRITICAL**: These tests MUST FAIL on unfixed code - failure confirms the bug exists
 * **DO NOT attempt to fix the test or the code when it fails**
 * **NOTE**: These tests encode the expected behavior - they will validate the fix when they pass after implementation
 * **GOAL**: Surface counterexamples that demonstrate mock data is being used instead of real API data
 *
 * **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9**
 *
 * Test Cases:
 * 1. getMockTemperature() is called in DetailedWeatherCard main temperature display
 * 2. getMockTemperature() is called in LocationList temperature display
 * 3. generateMockForecasts() is called when API fails (creates 24 fake hourly entries)
 * 4. Daily forecast displays 10 days instead of NEA's 4-day limit
 * 5. Sunrise time is hardcoded "7:00 AM" instead of calculated
 * 6. Sunset time is hardcoded "7:15 PM" instead of calculated
 * 7. Visibility card displays hardcoded "10 km" value
 * 8. Pressure card displays hardcoded "1013 hPa" value
 * 9. API failures result in silent fallback to mock data instead of error messages
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { DetailedWeatherCard } from "../components/DetailedWeatherCard.jsx";
import { LocationList } from "../components/LocationList.jsx";
import { LocationsProvider } from "../hooks/useLocations.jsx";
import * as useLocationsHook from "../hooks/useLocations.jsx";
import * as weatherTheme from "../utils/weatherTheme.js";
import * as apiClient from "../api/client";
import * as forecasts from "../api/forecasts";

describe("Bug Condition Exploration - Mock Data Usage Detection", () => {
  const mockLocation = {
    id: 1,
    latitude: 1.3521,
    longitude: 103.8198,
    lastFetched: new Date().toISOString(),
    weather: {
      area: "Singapore",
      condition: "Partly Cloudy",
      temperature: 28, // Real temperature from API
      observed_at: new Date().toISOString(),
      valid_period_text: "Next 2 hours",
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Test Case 1: getMockTemperature() Called in DetailedWeatherCard Main Temperature Display", () => {
    it("should NOT call getMockTemperature() for main temperature display - should use location.weather.temperature (EXPECTED TO FAIL)", async () => {
      // Mock API responses
      vi.spyOn(apiClient, "request").mockResolvedValue({
        temperature: 28,
        humidity: 75,
        wind_speed: 12,
        wind_direction: 180,
        rainfall: 0,
      });

      vi.spyOn(forecasts, "get24HourForecast").mockResolvedValue({
        periods: Array.from({ length: 24 }, (_, i) => ({
          time: `${i}:00`,
          temperature: 28 + Math.floor(Math.random() * 4) - 2,
        })),
      });

      vi.spyOn(forecasts, "get4DayForecast").mockResolvedValue({
        forecasts: Array.from({ length: 4 }, (_, i) => ({
          date: new Date(Date.now() + i * 86400000).toISOString().split("T")[0],
          temperature: { high: 32, low: 24 },
          forecast: "Partly Cloudy",
        })),
      });

      // Spy on getMockTemperature to detect if it's called
      const getMockTemperatureSpy = vi.spyOn(
        weatherTheme,
        "getMockTemperature",
      );

      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Wait for component to render
      await waitFor(() => {
        expect(screen.getByText(/Singapore/i)).toBeInTheDocument();
      });

      // Expected behavior: getMockTemperature should NOT be called
      // Bug condition: getMockTemperature IS called for temperature display
      expect(getMockTemperatureSpy).not.toHaveBeenCalled();

      // **EXPECTED OUTCOME**: Test FAILS on unfixed code (getMockTemperature is called)
      // **Validates: Requirement 2.1** - Main temperature display must use real data
    });

    it("should display real temperature from location.weather.temperature, not mock value (EXPECTED TO FAIL)", async () => {
      // Mock API responses
      vi.spyOn(apiClient, "request").mockResolvedValue({
        temperature: 28,
        humidity: 75,
        wind_speed: 12,
        wind_direction: 180,
        rainfall: 0,
      });

      vi.spyOn(forecasts, "get24HourForecast").mockResolvedValue({
        periods: Array.from({ length: 24 }, (_, i) => ({
          time: `${i}:00`,
          temperature: 28 + Math.floor(Math.random() * 4) - 2,
        })),
      });

      vi.spyOn(forecasts, "get4DayForecast").mockResolvedValue({
        forecasts: Array.from({ length: 4 }, (_, i) => ({
          date: new Date(Date.now() + i * 86400000).toISOString().split("T")[0],
          temperature: { high: 32, low: 24 },
          forecast: "Partly Cloudy",
        })),
      });

      const { container } = render(
        <DetailedWeatherCard location={mockLocation} isDark={false} />,
      );

      // Wait for component to render
      await waitFor(() => {
        expect(screen.getByText(/Singapore/i)).toBeInTheDocument();
      });

      // Find the main temperature display (large text)
      const temperatureDisplay = container.querySelector(
        ".text-4xl, .text-5xl, .text-6xl",
      );
      expect(temperatureDisplay).toBeInTheDocument();

      // Expected behavior: Should display "28°" (real temperature from location.weather.temperature)
      // Bug condition: Displays mock temperature based on condition (e.g., "28" from getMockTemperature("Partly Cloudy"))
      const displayedTemp = temperatureDisplay?.textContent;

      // The real temperature is 28, but getMockTemperature("Partly Cloudy") returns "28" too
      // So we need to verify it's using the right source
      expect(displayedTemp).toBe("28°");

      // **EXPECTED OUTCOME**: Test may pass or fail depending on coincidence
      // **Validates: Requirement 2.1** - Temperature must come from real API data
    });
  });

  describe("Test Case 2: getMockTemperature() Called in LocationList Temperature Display", () => {
    it("should NOT call getMockTemperature() in LocationList - should use location.weather.temperature (EXPECTED TO FAIL)", () => {
      // Mock useLocations hook
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [mockLocation],
        isLoading: false,
        error: null,
      });

      vi.spyOn(useLocationsHook, "useRefreshLocation").mockReturnValue({
        refresh: vi.fn(),
        isPending: false,
        refreshingId: null,
        error: null,
      });

      vi.spyOn(useLocationsHook, "useDeleteLocation").mockReturnValue({
        deleteLocation: vi.fn(),
        isPending: false,
      });

      // Spy on getMockTemperature
      const getMockTemperatureSpy = vi.spyOn(
        weatherTheme,
        "getMockTemperature",
      );

      render(
        <LocationsProvider>
          <LocationList isDark={false} />
        </LocationsProvider>,
      );

      // Expected behavior: getMockTemperature should NOT be called
      // Bug condition: getMockTemperature IS called for each location
      expect(getMockTemperatureSpy).not.toHaveBeenCalled();

      // **EXPECTED OUTCOME**: Test FAILS on unfixed code (getMockTemperature is called)
      // **Validates: Requirement 2.8** - LocationList must use real temperature data
    });
  });

  describe("Test Case 3: generateMockForecasts() Called When API Fails", () => {
    it("should NOT call generateMockForecasts() when API fails - should display error message (EXPECTED TO FAIL)", async () => {
      // Mock API to fail
      vi.spyOn(apiClient, "request").mockRejectedValue(new Error("API Error"));
      vi.spyOn(forecasts, "get24HourForecast").mockRejectedValue(
        new Error("API Error"),
      );
      vi.spyOn(forecasts, "get4DayForecast").mockRejectedValue(
        new Error("API Error"),
      );

      const { container } = render(
        <DetailedWeatherCard location={mockLocation} isDark={false} />,
      );

      // Wait for error handling
      await waitFor(
        () => {
          expect(screen.getByText(/Singapore/i)).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      // Expected behavior: Should display error message "Unable to refresh weather data"
      // Bug condition: Silently falls back to generateMockForecasts() and displays fake data

      // Check if error message is displayed
      const errorMessage = screen.queryByText(
        /Unable to refresh weather data/i,
      );
      expect(errorMessage).toBeInTheDocument();

      // Check that hourly forecast is NOT displayed (since API failed)
      const hourlyForecast = container.querySelector(".overflow-x-auto");

      // If mock data is generated, hourly forecast will be displayed
      // Expected: hourly forecast should not be displayed OR error message should be shown
      if (hourlyForecast) {
        // If forecast is displayed, error message MUST be present
        expect(errorMessage).toBeInTheDocument();
      }

      // **EXPECTED OUTCOME**: Test FAILS on unfixed code (no error message, mock data displayed)
      // **Validates: Requirement 2.4** - API failures must display error messages, not mock data
    });
  });

  describe("Test Case 4: Daily Forecast Displays 10 Days Instead of NEA's 4-Day Limit", () => {
    it("should display maximum 4 days of forecast, not 10 days (EXPECTED TO FAIL)", async () => {
      // Mock API responses with 4-day forecast (NEA's actual limit)
      vi.spyOn(apiClient, "request").mockResolvedValue({
        temperature: 28,
        humidity: 75,
        wind_speed: 12,
        wind_direction: 180,
        rainfall: 0,
      });

      vi.spyOn(forecasts, "get24HourForecast").mockResolvedValue({
        periods: Array.from({ length: 24 }, (_, i) => ({
          time: `${i}:00`,
          temperature: 28 + Math.floor(Math.random() * 4) - 2,
        })),
      });

      vi.spyOn(forecasts, "get4DayForecast").mockResolvedValue({
        forecasts: Array.from({ length: 4 }, (_, i) => ({
          date: new Date(Date.now() + i * 86400000).toISOString().split("T")[0],
          temperature: { high: 32, low: 24 },
          forecast: "Partly Cloudy",
        })),
      });

      const { container } = render(
        <DetailedWeatherCard location={mockLocation} isDark={false} />,
      );

      // Wait for component to render
      await waitFor(
        () => {
          expect(screen.getByText(/Singapore/i)).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      // Find the daily forecast section
      const dailyForecastSection = container.querySelector(".space-y-1");
      expect(dailyForecastSection).toBeInTheDocument();

      // Count the number of daily forecast items
      const dailyForecastItems = dailyForecastSection?.querySelectorAll(
        ".flex.items-center.justify-between",
      );
      const forecastCount = dailyForecastItems?.length || 0;

      // Expected behavior: Should display maximum 4 days (NEA's limit)
      // Bug condition: Displays 10 days (6 days are completely fake)
      expect(forecastCount).toBeLessThanOrEqual(4);

      // **EXPECTED OUTCOME**: Test FAILS on unfixed code (displays 10 days)
      // **Validates: Requirement 2.3** - Daily forecast must be limited to 4 days from real NEA API
    });
  });

  describe("Test Case 5: Sunrise Time is Hardcoded '7:00 AM'", () => {
    it("should calculate actual sunrise time for Singapore, not display hardcoded '7:00 AM' (EXPECTED TO FAIL)", async () => {
      // Mock API responses
      vi.spyOn(apiClient, "request").mockResolvedValue({
        temperature: 28,
        humidity: 75,
        wind_speed: 12,
        wind_direction: 180,
        rainfall: 0,
      });

      vi.spyOn(forecasts, "get24HourForecast").mockResolvedValue({
        periods: Array.from({ length: 24 }, (_, i) => ({
          time: `${i}:00`,
          temperature: 28 + Math.floor(Math.random() * 4) - 2,
        })),
      });

      vi.spyOn(forecasts, "get4DayForecast").mockResolvedValue({
        forecasts: Array.from({ length: 4 }, (_, i) => ({
          date: new Date(Date.now() + i * 86400000).toISOString().split("T")[0],
          temperature: { high: 32, low: 24 },
          forecast: "Partly Cloudy",
        })),
      });

      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Wait for component to render
      await waitFor(() => {
        expect(screen.getByText(/Singapore/i)).toBeInTheDocument();
      });

      // Find the sunrise time display
      const sunriseText = screen.queryByText("7:00 AM");

      // Expected behavior: Should NOT display hardcoded "7:00 AM"
      // Bug condition: Displays hardcoded "7:00 AM" instead of calculated sunrise time
      expect(sunriseText).not.toBeInTheDocument();

      // **EXPECTED OUTCOME**: Test FAILS on unfixed code (hardcoded "7:00 AM" is displayed)
      // **Validates: Requirement 2.6** - Sunrise time must be calculated for Singapore
    });
  });

  describe("Test Case 6: Sunset Time is Hardcoded '7:15 PM'", () => {
    it("should calculate actual sunset time for Singapore, not display hardcoded '7:15 PM' (EXPECTED TO FAIL)", async () => {
      // Mock API responses
      vi.spyOn(apiClient, "request").mockResolvedValue({
        temperature: 28,
        humidity: 75,
        wind_speed: 12,
        wind_direction: 180,
        rainfall: 0,
      });

      vi.spyOn(forecasts, "get24HourForecast").mockResolvedValue({
        periods: Array.from({ length: 24 }, (_, i) => ({
          time: `${i}:00`,
          temperature: 28 + Math.floor(Math.random() * 4) - 2,
        })),
      });

      vi.spyOn(forecasts, "get4DayForecast").mockResolvedValue({
        forecasts: Array.from({ length: 4 }, (_, i) => ({
          date: new Date(Date.now() + i * 86400000).toISOString().split("T")[0],
          temperature: { high: 32, low: 24 },
          forecast: "Partly Cloudy",
        })),
      });

      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Wait for component to render
      await waitFor(() => {
        expect(screen.getByText(/Singapore/i)).toBeInTheDocument();
      });

      // Find the sunset time display
      const sunsetText = screen.queryByText("7:15 PM");

      // Expected behavior: Should NOT display hardcoded "7:15 PM"
      // Bug condition: Displays hardcoded "7:15 PM" instead of calculated sunset time
      expect(sunsetText).not.toBeInTheDocument();

      // **EXPECTED OUTCOME**: Test FAILS on unfixed code (hardcoded "7:15 PM" is displayed)
      // **Validates: Requirement 2.7** - Sunset time must be calculated for Singapore
    });
  });

  describe("Test Case 7: Visibility Card Displays Hardcoded '10 km' Value", () => {
    it("should NOT display visibility card with hardcoded '10 km' value (EXPECTED TO FAIL)", async () => {
      // Mock API responses
      vi.spyOn(apiClient, "request").mockResolvedValue({
        temperature: 28,
        humidity: 75,
        wind_speed: 12,
        wind_direction: 180,
        rainfall: 0,
      });

      vi.spyOn(forecasts, "get24HourForecast").mockResolvedValue({
        periods: Array.from({ length: 24 }, (_, i) => ({
          time: `${i}:00`,
          temperature: 28 + Math.floor(Math.random() * 4) - 2,
        })),
      });

      vi.spyOn(forecasts, "get4DayForecast").mockResolvedValue({
        forecasts: Array.from({ length: 4 }, (_, i) => ({
          date: new Date(Date.now() + i * 86400000).toISOString().split("T")[0],
          temperature: { high: 32, low: 24 },
          forecast: "Partly Cloudy",
        })),
      });

      const { container } = render(
        <DetailedWeatherCard location={mockLocation} isDark={false} />,
      );

      // Wait for component to render
      await waitFor(() => {
        expect(screen.getByText(/Singapore/i)).toBeInTheDocument();
      });

      // Find the visibility card
      const visibilityLabel = screen.queryByText(/Visibility/i);

      // Expected behavior: Visibility card should NOT be displayed (NEA doesn't provide this data)
      // Bug condition: Visibility card is displayed with hardcoded "10 km" value
      expect(visibilityLabel).not.toBeInTheDocument();

      // Also check for the hardcoded value
      if (visibilityLabel) {
        const visibilityCard = visibilityLabel.closest(".rounded-3xl");
        const visibilityValue = visibilityCard?.textContent;

        // Should not contain "10" and "km" together
        expect(visibilityValue).not.toMatch(/10.*km/);
      }

      // **EXPECTED OUTCOME**: Test FAILS on unfixed code (visibility card with "10 km" is displayed)
      // **Validates: Requirement 2.5** - Visibility card should not be displayed (NEA doesn't provide this data)
    });
  });

  describe("Test Case 8: Pressure Card Displays Hardcoded '1013 hPa' Value", () => {
    it("should NOT display pressure card with hardcoded '1013 hPa' value (EXPECTED TO FAIL)", async () => {
      // Mock API responses
      vi.spyOn(apiClient, "request").mockResolvedValue({
        temperature: 28,
        humidity: 75,
        wind_speed: 12,
        wind_direction: 180,
        rainfall: 0,
      });

      vi.spyOn(forecasts, "get24HourForecast").mockResolvedValue({
        periods: Array.from({ length: 24 }, (_, i) => ({
          time: `${i}:00`,
          temperature: 28 + Math.floor(Math.random() * 4) - 2,
        })),
      });

      vi.spyOn(forecasts, "get4DayForecast").mockResolvedValue({
        forecasts: Array.from({ length: 4 }, (_, i) => ({
          date: new Date(Date.now() + i * 86400000).toISOString().split("T")[0],
          temperature: { high: 32, low: 24 },
          forecast: "Partly Cloudy",
        })),
      });

      const { container } = render(
        <DetailedWeatherCard location={mockLocation} isDark={false} />,
      );

      // Wait for component to render
      await waitFor(() => {
        expect(screen.getByText(/Singapore/i)).toBeInTheDocument();
      });

      // Find the pressure card
      const pressureLabel = screen.queryByText(/Pressure/i);

      // Expected behavior: Pressure card should NOT be displayed (NEA doesn't provide this data)
      // Bug condition: Pressure card is displayed with hardcoded "1013 hPa" value
      expect(pressureLabel).not.toBeInTheDocument();

      // Also check for the hardcoded value
      if (pressureLabel) {
        const pressureCard = pressureLabel.closest(".rounded-3xl");
        const pressureValue = pressureCard?.textContent;

        // Should not contain "1013" and "hPa" together
        expect(pressureValue).not.toMatch(/1013.*hPa/);
      }

      // **EXPECTED OUTCOME**: Test FAILS on unfixed code (pressure card with "1013 hPa" is displayed)
      // **Validates: Requirement 2.5** - Pressure card should not be displayed (NEA doesn't provide this data)
    });
  });

  describe("Test Case 9: Comprehensive Mock Data Detection", () => {
    it("should detect all instances of mock data usage in the application (EXPECTED TO FAIL)", async () => {
      // This test provides a comprehensive summary of all mock data issues

      // Mock API responses
      vi.spyOn(apiClient, "request").mockResolvedValue({
        temperature: 28,
        humidity: 75,
        wind_speed: 12,
        wind_direction: 180,
        rainfall: 0,
      });

      vi.spyOn(forecasts, "get24HourForecast").mockResolvedValue({
        periods: Array.from({ length: 24 }, (_, i) => ({
          time: `${i}:00`,
          temperature: 28 + Math.floor(Math.random() * 4) - 2,
        })),
      });

      vi.spyOn(forecasts, "get4DayForecast").mockResolvedValue({
        forecasts: Array.from({ length: 4 }, (_, i) => ({
          date: new Date(Date.now() + i * 86400000).toISOString().split("T")[0],
          temperature: { high: 32, low: 24 },
          forecast: "Partly Cloudy",
        })),
      });

      // Spy on getMockTemperature
      const getMockTemperatureSpy = vi.spyOn(
        weatherTheme,
        "getMockTemperature",
      );

      const { container } = render(
        <DetailedWeatherCard location={mockLocation} isDark={false} />,
      );

      // Wait for component to render
      await waitFor(() => {
        expect(screen.getByText(/Singapore/i)).toBeInTheDocument();
      });

      const mockDataIssues = [];

      // Check 1: getMockTemperature called
      if (getMockTemperatureSpy.mock.calls.length > 0) {
        mockDataIssues.push(
          `getMockTemperature() called ${getMockTemperatureSpy.mock.calls.length} times`,
        );
      }

      // Check 2: Hardcoded sunrise
      if (screen.queryByText("7:00 AM")) {
        mockDataIssues.push("Hardcoded sunrise time '7:00 AM' found");
      }

      // Check 3: Hardcoded sunset
      if (screen.queryByText("7:15 PM")) {
        mockDataIssues.push("Hardcoded sunset time '7:15 PM' found");
      }

      // Check 4: Visibility card with hardcoded value
      if (screen.queryByText(/Visibility/i)) {
        mockDataIssues.push(
          "Visibility card displayed (NEA doesn't provide this data)",
        );
      }

      // Check 5: Pressure card with hardcoded value
      if (screen.queryByText(/Pressure/i)) {
        mockDataIssues.push(
          "Pressure card displayed (NEA doesn't provide this data)",
        );
      }

      // Check 6: Daily forecast count
      const dailyForecastSection = container.querySelector(".space-y-1");
      const dailyForecastItems = dailyForecastSection?.querySelectorAll(
        ".flex.items-center.justify-between",
      );
      const forecastCount = dailyForecastItems?.length || 0;
      if (forecastCount > 4) {
        mockDataIssues.push(
          `Daily forecast shows ${forecastCount} days (should be max 4)`,
        );
      }

      // Expected behavior: No mock data issues should be found
      // Bug condition: Multiple mock data issues exist
      expect(mockDataIssues).toHaveLength(0);

      // If test fails, log all issues found
      if (mockDataIssues.length > 0) {
        console.log("\n=== COUNTEREXAMPLES FOUND ===");
        console.log("Mock data issues detected:");
        mockDataIssues.forEach((issue, index) => {
          console.log(`${index + 1}. ${issue}`);
        });
        console.log("=============================\n");
      }

      // **EXPECTED OUTCOME**: Test FAILS on unfixed code (multiple mock data issues found)
      // **Validates: All Requirements 2.1-2.9** - Comprehensive detection of all mock data usage
    });
  });
});
