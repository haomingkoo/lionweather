import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Dashboard } from "./Dashboard";
import * as useLocationsHook from "../hooks/useLocations";
import * as weatherTheme from "../utils/weatherTheme";

// Mock the hooks and utilities
vi.mock("../hooks/useLocations");
vi.mock("../utils/weatherTheme", async () => {
  const actual = await vi.importActual("../utils/weatherTheme");
  return {
    ...actual,
    getWeatherGradient: vi.fn(actual.getWeatherGradient),
    isDarkGradient: vi.fn(actual.isDarkGradient),
  };
});

// Mock child components to simplify testing
vi.mock("../components/LocationForm", () => ({
  LocationForm: () => <div data-testid="location-form">LocationForm</div>,
}));
vi.mock("../components/EnhancedLocationList", () => ({
  EnhancedLocationList: () => (
    <div data-testid="location-list">EnhancedLocationList</div>
  ),
}));
vi.mock("../components/WeatherMap", () => ({
  WeatherMap: () => <div data-testid="weather-map">WeatherMap</div>,
}));
vi.mock("../components/ViewToggle", () => ({
  ViewToggle: () => <div data-testid="view-toggle">ViewToggle</div>,
}));

describe("Dashboard Component - Gradient Background", () => {
  describe("Requirement 1.5: Background gradient reflects most recent location", () => {
    it("should use the first location's weather condition for gradient", () => {
      // Arrange: Mock locations with different weather conditions
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
        {
          id: 2,
          latitude: 1.4,
          longitude: 103.9,
          weather: {
            area: "Jurong",
            condition: "Rainy",
            valid_period_text: "Today",
            observed_at: "2024-01-01T11:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: Verify getWeatherGradient was called with the first location's condition
      expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith("Sunny");

      // Verify the gradient classes are applied to the container
      const mainContainer = container.firstChild;
      expect(mainContainer.className).toContain("bg-gradient-to-br");
      expect(mainContainer.className).toContain("from-yellow-400");
      expect(mainContainer.className).toContain("via-orange-400");
      expect(mainContainer.className).toContain("to-pink-500");
    });

    it("should update gradient when first location changes", () => {
      // Arrange: Initial locations with sunny weather
      const initialLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      const useLocationsSpy = vi
        .spyOn(useLocationsHook, "useLocations")
        .mockReturnValue({
          locations: initialLocations,
          isLoading: false,
          error: null,
        });

      // Act: Initial render
      const { container, rerender } = render(<Dashboard />);

      // Assert: Initial gradient is sunny
      expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith("Sunny");
      let mainContainer = container.firstChild;
      expect(mainContainer.className).toContain("from-yellow-400");

      // Arrange: Update to rainy weather
      const updatedLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Rainy",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:30:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      useLocationsSpy.mockReturnValue({
        locations: updatedLocations,
        isLoading: false,
        error: null,
      });

      // Act: Re-render with updated locations
      rerender(<Dashboard />);

      // Assert: Gradient updates to rainy
      expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith("Rainy");
      mainContainer = container.firstChild;
      expect(mainContainer.className).toContain("from-blue-500");
    });

    it("should ignore subsequent locations and only use the first one", () => {
      // Arrange: Multiple locations with different conditions
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Thunderstorm",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
        {
          id: 2,
          latitude: 1.4,
          longitude: 103.9,
          weather: {
            area: "Jurong",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T11:00:00Z",
            source: "weather.gov.sg",
          },
        },
        {
          id: 3,
          latitude: 1.2,
          longitude: 103.7,
          weather: {
            area: "Tampines",
            condition: "Rainy",
            valid_period_text: "Today",
            observed_at: "2024-01-01T10:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Clear previous calls
      vi.mocked(weatherTheme.getWeatherGradient).mockClear();

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: Only the first location's condition (Thunderstorm) is used
      expect(weatherTheme.getWeatherGradient).toHaveBeenCalledTimes(1);
      expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith(
        "Thunderstorm",
      );

      // Verify thunderstorm gradient is applied
      const mainContainer = container.firstChild;
      expect(mainContainer.className).toContain("from-indigo-900");
      expect(mainContainer.className).toContain("via-purple-900");
      expect(mainContainer.className).toContain("to-pink-900");
    });

    it("should handle empty locations array gracefully", () => {
      // Arrange: No locations
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [],
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: getWeatherGradient is called with undefined
      expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith(undefined);

      // Verify default gradient is applied
      const mainContainer = container.firstChild;
      expect(mainContainer.className).toContain("bg-gradient-to-br");
      expect(mainContainer.className).toContain("from-sky-400");
    });

    it("should handle location without weather data", () => {
      // Arrange: Location without weather property
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: null,
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: getWeatherGradient is called with undefined
      expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith(undefined);

      // Verify default gradient is applied
      const mainContainer = container.firstChild;
      expect(mainContainer.className).toContain("from-sky-400");
    });
  });

  describe("Requirement 1.6: Smooth gradient transitions (500ms)", () => {
    it("should apply transition classes for smooth gradient changes", () => {
      // Arrange: Mock locations
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: Verify transition classes are present with 500ms duration
      const mainContainer = container.firstChild;
      expect(mainContainer.className).toContain("transition-all");
      expect(mainContainer.className).toContain("duration-500");
      expect(mainContainer.className).toContain("ease-in-out");
    });

    it("should maintain transition classes across gradient changes", () => {
      // Arrange: Initial locations
      const initialLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      const useLocationsSpy = vi
        .spyOn(useLocationsHook, "useLocations")
        .mockReturnValue({
          locations: initialLocations,
          isLoading: false,
          error: null,
        });

      // Act: Initial render
      const { container, rerender } = render(<Dashboard />);

      // Assert: Transition classes present initially with 500ms duration
      let mainContainer = container.firstChild;
      expect(mainContainer.className).toContain("transition-all");
      expect(mainContainer.className).toContain("duration-500");

      // Arrange: Update weather condition
      const updatedLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Cloudy",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:30:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      useLocationsSpy.mockReturnValue({
        locations: updatedLocations,
        isLoading: false,
        error: null,
      });

      // Act: Re-render
      rerender(<Dashboard />);

      // Assert: Transition classes still present after update with 500ms duration
      mainContainer = container.firstChild;
      expect(mainContainer.className).toContain("transition-all");
      expect(mainContainer.className).toContain("duration-500");
      expect(mainContainer.className).toContain("ease-in-out");
    });
  });

  describe("Text color adaptation based on gradient", () => {
    it("should use light text on dark gradients", () => {
      // Arrange: Thunderstorm condition (dark gradient)
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Thunderstorm",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      render(<Dashboard />);

      // Assert: Verify isDarkGradient was called
      expect(weatherTheme.isDarkGradient).toHaveBeenCalledWith("Thunderstorm");

      // Verify light text is used
      const title = screen.getByText("Weather");
      expect(title.className).toContain("text-white");
    });

    it("should use dark text on light gradients", () => {
      // Arrange: Sunny condition (light gradient)
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      render(<Dashboard />);

      // Assert: Verify isDarkGradient was called
      expect(weatherTheme.isDarkGradient).toHaveBeenCalledWith("Sunny");

      // Verify dark text is used
      const title = screen.getByText("Weather");
      expect(title.className).toContain("text-slate-900");
    });
  });
});

/**
 * Property-Based Tests for Dashboard Component
 * Feature: apple-weather-ui-redesign
 */

describe("Property-Based Tests: Dashboard Background Gradient", () => {
  /**
   * Property 3: Background gradient reflects most recent location
   * **Validates: Requirements 1.5**
   *
   * For any array of locations with different weather conditions, the Dashboard
   * component should display a gradient background that matches the weather condition
   * of the first location in the array (most recently updated).
   */
  describe("Feature: apple-weather-ui-redesign, Property 3: Background gradient reflects most recent location", () => {
    it("should always use the first location's weather condition for gradient selection", () => {
      const fc = require("fast-check");

      // Define weather condition generator
      const weatherConditionArbitrary = fc.constantFrom(
        "Sunny",
        "Clear",
        "Fair",
        "Rainy",
        "Showers",
        "Drizzle",
        "Thunderstorm",
        "Stormy",
        "Cloudy",
        "Overcast",
        "Partly Cloudy",
      );

      // Define location generator
      const locationArbitrary = fc.record({
        id: fc.integer({ min: 1, max: 10000 }),
        latitude: fc.float({ min: Math.fround(1.1), max: Math.fround(1.5) }),
        longitude: fc.float({
          min: Math.fround(103.6),
          max: Math.fround(104.1),
        }),
        weather: fc.record({
          area: fc.constantFrom("Singapore", "Jurong", "Tampines", "Woodlands"),
          condition: weatherConditionArbitrary,
          valid_period_text: fc.constantFrom("Today", "Tonight", "Tomorrow"),
          observed_at: fc.constant("2024-06-15T12:00:00.000Z"),
          source: fc.constant("weather.gov.sg"),
        }),
      });

      // Generate arrays of locations with at least 1 location
      const locationsArrayArbitrary = fc.array(locationArbitrary, {
        minLength: 1,
        maxLength: 10,
      });

      fc.assert(
        fc.property(locationsArrayArbitrary, (locations) => {
          // Arrange: Mock useLocations to return the generated locations
          vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
            locations,
            isLoading: false,
            error: null,
          });

          // Clear previous mock calls
          vi.mocked(weatherTheme.getWeatherGradient).mockClear();

          // Act: Render the Dashboard
          const { container } = render(<Dashboard />);

          // Assert: Verify getWeatherGradient was called with the first location's condition
          const firstLocationCondition = locations[0].weather.condition;
          expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith(
            firstLocationCondition,
          );

          // Verify the gradient from the first location is applied
          const expectedGradient = weatherTheme.getWeatherGradient(
            firstLocationCondition,
          );
          const mainContainer = container.firstChild;

          // The gradient classes should be present in the container
          expect(mainContainer.className).toContain("bg-gradient-to-br");

          // Verify that the gradient matches the first location's condition
          const gradientParts = expectedGradient.split(" ");
          gradientParts.forEach((part) => {
            expect(mainContainer.className).toContain(part);
          });

          // If there are multiple locations, verify that subsequent locations are ignored
          if (locations.length > 1) {
            for (let i = 1; i < locations.length; i++) {
              const subsequentCondition = locations[i].weather.condition;
              // Check if any call was made with a subsequent condition that differs from the first
              if (subsequentCondition !== firstLocationCondition) {
                const calls = vi.mocked(weatherTheme.getWeatherGradient).mock
                  .calls;
                const calledWithSubsequent = calls.some(
                  (call) => call[0] === subsequentCondition,
                );
                expect(calledWithSubsequent).toBe(false);
              }
            }
          }
        }),
        { numRuns: 100 },
      );
    });

    it("should update gradient when the first location's weather condition changes", () => {
      const fc = require("fast-check");

      // Define weather condition generator
      const weatherConditionArbitrary = fc.constantFrom(
        "Sunny",
        "Clear",
        "Fair",
        "Rainy",
        "Showers",
        "Drizzle",
        "Thunderstorm",
        "Stormy",
        "Cloudy",
        "Overcast",
        "Partly Cloudy",
      );

      // Generate two different weather conditions
      const twoConditionsArbitrary = fc
        .tuple(weatherConditionArbitrary, weatherConditionArbitrary)
        .filter(([cond1, cond2]) => cond1 !== cond2);

      fc.assert(
        fc.property(twoConditionsArbitrary, ([condition1, condition2]) => {
          // Arrange: Initial location with first condition
          const initialLocation = {
            id: 1,
            latitude: 1.3,
            longitude: 103.8,
            weather: {
              area: "Singapore",
              condition: condition1,
              valid_period_text: "Today",
              observed_at: "2024-01-01T12:00:00Z",
              source: "weather.gov.sg",
            },
          };

          const useLocationsSpy = vi
            .spyOn(useLocationsHook, "useLocations")
            .mockReturnValue({
              locations: [initialLocation],
              isLoading: false,
              error: null,
            });

          // Clear previous mock calls
          vi.mocked(weatherTheme.getWeatherGradient).mockClear();

          // Act: Initial render
          const { container, rerender } = render(<Dashboard />);

          // Assert: Initial gradient matches first condition
          expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith(
            condition1,
          );
          const initialGradient = weatherTheme.getWeatherGradient(condition1);
          let mainContainer = container.firstChild;
          const initialGradientParts = initialGradient.split(" ");
          initialGradientParts.forEach((part) => {
            expect(mainContainer.className).toContain(part);
          });

          // Arrange: Update location with second condition
          const updatedLocation = {
            ...initialLocation,
            weather: {
              ...initialLocation.weather,
              condition: condition2,
              observed_at: "2024-01-01T12:30:00Z",
            },
          };

          useLocationsSpy.mockReturnValue({
            locations: [updatedLocation],
            isLoading: false,
            error: null,
          });

          // Clear mock calls before re-render
          vi.mocked(weatherTheme.getWeatherGradient).mockClear();

          // Act: Re-render with updated condition
          rerender(<Dashboard />);

          // Assert: Gradient updates to match second condition
          expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith(
            condition2,
          );
          const updatedGradient = weatherTheme.getWeatherGradient(condition2);
          mainContainer = container.firstChild;
          const updatedGradientParts = updatedGradient.split(" ");
          updatedGradientParts.forEach((part) => {
            expect(mainContainer.className).toContain(part);
          });

          // Verify the gradient changed (if the gradients are different)
          if (initialGradient !== updatedGradient) {
            expect(mainContainer.className).not.toContain(
              initialGradientParts[0],
            );
          }
        }),
        { numRuns: 100 },
      );
    });

    it("should ignore subsequent locations and only use the first location's condition", () => {
      const fc = require("fast-check");

      // Define weather condition generator
      const weatherConditionArbitrary = fc.constantFrom(
        "Sunny",
        "Clear",
        "Fair",
        "Rainy",
        "Showers",
        "Drizzle",
        "Thunderstorm",
        "Stormy",
        "Cloudy",
        "Overcast",
        "Partly Cloudy",
      );

      // Define location generator
      const locationArbitrary = fc.record({
        id: fc.integer({ min: 1, max: 10000 }),
        latitude: fc.float({ min: Math.fround(1.1), max: Math.fround(1.5) }),
        longitude: fc.float({
          min: Math.fround(103.6),
          max: Math.fround(104.1),
        }),
        weather: fc.record({
          area: fc.constantFrom("Singapore", "Jurong", "Tampines", "Woodlands"),
          condition: weatherConditionArbitrary,
          valid_period_text: fc.constantFrom("Today", "Tonight", "Tomorrow"),
          observed_at: fc.constant("2024-06-15T12:00:00.000Z"),
          source: fc.constant("weather.gov.sg"),
        }),
      });

      // Generate arrays with at least 2 locations to test that subsequent ones are ignored
      const locationsArrayArbitrary = fc.array(locationArbitrary, {
        minLength: 2,
        maxLength: 10,
      });

      fc.assert(
        fc.property(locationsArrayArbitrary, (locations) => {
          // Arrange: Mock useLocations to return the generated locations
          vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
            locations,
            isLoading: false,
            error: null,
          });

          // Clear previous mock calls
          vi.mocked(weatherTheme.getWeatherGradient).mockClear();

          // Act: Render the Dashboard
          const { container } = render(<Dashboard />);

          // Assert: Only the first location's condition is used
          const firstLocationCondition = locations[0].weather.condition;
          expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith(
            firstLocationCondition,
          );

          // Verify that subsequent locations' conditions are NOT used
          for (let i = 1; i < locations.length; i++) {
            const subsequentCondition = locations[i].weather.condition;
            // The function should not have been called with any subsequent condition
            // (unless it happens to be the same as the first one)
            if (subsequentCondition !== firstLocationCondition) {
              const calls = vi.mocked(weatherTheme.getWeatherGradient).mock
                .calls;
              const calledWithSubsequent = calls.some(
                (call) => call[0] === subsequentCondition,
              );
              expect(calledWithSubsequent).toBe(false);
            }
          }

          // Verify the gradient matches the first location
          const expectedGradient = weatherTheme.getWeatherGradient(
            firstLocationCondition,
          );
          const mainContainer = container.firstChild;
          const gradientParts = expectedGradient.split(" ");
          gradientParts.forEach((part) => {
            expect(mainContainer.className).toContain(part);
          });
        }),
        { numRuns: 100 },
      );
    });

    it("should handle empty locations array gracefully", () => {
      const fc = require("fast-check");

      fc.assert(
        fc.property(fc.constant([]), (emptyLocations) => {
          // Arrange: Mock useLocations to return empty array
          vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
            locations: emptyLocations,
            isLoading: false,
            error: null,
          });

          // Clear previous mock calls
          vi.mocked(weatherTheme.getWeatherGradient).mockClear();

          // Act: Render the Dashboard
          const { container } = render(<Dashboard />);

          // Assert: getWeatherGradient is called with undefined
          expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith(
            undefined,
          );

          // Verify default gradient is applied
          const mainContainer = container.firstChild;
          expect(mainContainer.className).toContain("bg-gradient-to-br");
          expect(mainContainer.className).toContain("from-sky-400");
        }),
        { numRuns: 100 },
      );
    });

    it("should handle locations with missing or null weather data", () => {
      const fc = require("fast-check");

      // Generate locations with potentially missing weather data
      const locationWithMissingWeatherArbitrary = fc.record({
        id: fc.integer({ min: 1, max: 10000 }),
        latitude: fc.float({ min: Math.fround(1.1), max: Math.fround(1.5) }),
        longitude: fc.float({
          min: Math.fround(103.6),
          max: Math.fround(104.1),
        }),
        weather: fc.oneof(
          fc.constant(null),
          fc.constant(undefined),
          fc.record({
            area: fc.constantFrom(
              "Singapore",
              "Jurong",
              "Tampines",
              "Woodlands",
            ),
            condition: fc.oneof(
              fc.constant(null),
              fc.constant(undefined),
              fc.constant(""),
            ),
            valid_period_text: fc.constantFrom("Today", "Tonight", "Tomorrow"),
            observed_at: fc.constant("2024-06-15T12:00:00.000Z"),
            source: fc.constant("weather.gov.sg"),
          }),
        ),
      });

      fc.assert(
        fc.property(
          fc.array(locationWithMissingWeatherArbitrary, {
            minLength: 1,
            maxLength: 5,
          }),
          (locations) => {
            // Arrange: Mock useLocations to return locations with missing weather
            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations,
              isLoading: false,
              error: null,
            });

            // Clear previous mock calls
            vi.mocked(weatherTheme.getWeatherGradient).mockClear();

            // Act: Render the Dashboard
            const { container } = render(<Dashboard />);

            // Assert: getWeatherGradient is called with undefined or null
            const firstLocation = locations[0];
            const expectedCondition = firstLocation?.weather?.condition;
            expect(weatherTheme.getWeatherGradient).toHaveBeenCalledWith(
              expectedCondition,
            );

            // Verify default gradient is applied when condition is missing
            const mainContainer = container.firstChild;
            expect(mainContainer.className).toContain("bg-gradient-to-br");
            expect(mainContainer.className).toContain("from-sky-400");
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should maintain gradient consistency across re-renders with same first location", () => {
      const fc = require("fast-check");

      // Define weather condition generator
      const weatherConditionArbitrary = fc.constantFrom(
        "Sunny",
        "Clear",
        "Fair",
        "Rainy",
        "Showers",
        "Drizzle",
        "Thunderstorm",
        "Stormy",
        "Cloudy",
        "Overcast",
        "Partly Cloudy",
      );

      fc.assert(
        fc.property(weatherConditionArbitrary, (condition) => {
          // Arrange: Location with specific condition
          const location = {
            id: 1,
            latitude: 1.3,
            longitude: 103.8,
            weather: {
              area: "Singapore",
              condition,
              valid_period_text: "Today",
              observed_at: "2024-01-01T12:00:00Z",
              source: "weather.gov.sg",
            },
          };

          vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
            locations: [location],
            isLoading: false,
            error: null,
          });

          // Clear previous mock calls
          vi.mocked(weatherTheme.getWeatherGradient).mockClear();

          // Act: Initial render
          const { container, rerender } = render(<Dashboard />);

          // Get initial gradient
          const initialGradient = weatherTheme.getWeatherGradient(condition);
          let mainContainer = container.firstChild;
          const initialGradientParts = initialGradient.split(" ");

          // Assert: Initial gradient is correct
          initialGradientParts.forEach((part) => {
            expect(mainContainer.className).toContain(part);
          });

          // Act: Re-render without changing location
          rerender(<Dashboard />);

          // Assert: Gradient remains the same
          mainContainer = container.firstChild;
          initialGradientParts.forEach((part) => {
            expect(mainContainer.className).toContain(part);
          });
        }),
        { numRuns: 100 },
      );
    });
  });
});

/**
 * Tests for Header Component
 * Requirement 4.6: Header glassmorphism and sticky positioning
 */
describe("Dashboard Header - Glassmorphism and Sticky Positioning", () => {
  describe("Requirement 4.6: Header has translucent background with backdrop blur", () => {
    it("should render header with glassmorphism styling", () => {
      // Arrange: Mock locations
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: Find the header element
      const header = container.querySelector("header");
      expect(header).toBeTruthy();

      // Verify glassmorphism classes
      expect(header.className).toContain("bg-white/10"); // Translucent background with 10% opacity
      expect(header.className).toContain("backdrop-blur-xl"); // Backdrop blur effect
      expect(header.className).toContain("border-white/20"); // Border with white opacity
    });

    it("should have translucent background with correct opacity", () => {
      // Arrange: Mock locations
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Rainy",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: Verify translucent background
      const header = container.querySelector("header");
      expect(header.className).toMatch(/bg-white\/\d+/); // Has translucent background pattern
    });

    it("should apply backdrop blur effect", () => {
      // Arrange: Mock locations
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Cloudy",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: Verify backdrop blur
      const header = container.querySelector("header");
      expect(header.className).toMatch(/backdrop-blur/); // Has backdrop blur effect
    });

    it("should have border with white opacity", () => {
      // Arrange: Mock locations
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Thunderstorm",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: Verify border with white opacity
      const header = container.querySelector("header");
      expect(header.className).toMatch(/border-white\/\d+/); // Has white border with opacity
    });
  });

  describe("Requirement 4.6: Header sticky positioning at top of viewport", () => {
    it("should have sticky positioning", () => {
      // Arrange: Mock locations
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: Verify sticky positioning
      const header = container.querySelector("header");
      expect(header.className).toContain("sticky");
      expect(header.className).toContain("top-0");
    });

    it("should have appropriate z-index for stacking", () => {
      // Arrange: Mock locations
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Rainy",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      const { container } = render(<Dashboard />);

      // Assert: Verify z-index for proper stacking
      const header = container.querySelector("header");
      expect(header.className).toContain("z-50"); // High z-index to stay on top
    });

    it("should maintain sticky positioning across different weather conditions", () => {
      // Arrange: Initial sunny condition
      const initialLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      const useLocationsSpy = vi
        .spyOn(useLocationsHook, "useLocations")
        .mockReturnValue({
          locations: initialLocations,
          isLoading: false,
          error: null,
        });

      // Act: Initial render
      const { container, rerender } = render(<Dashboard />);

      // Assert: Initial sticky positioning
      let header = container.querySelector("header");
      expect(header.className).toContain("sticky");
      expect(header.className).toContain("top-0");

      // Arrange: Update to rainy condition
      const updatedLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Rainy",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:30:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      useLocationsSpy.mockReturnValue({
        locations: updatedLocations,
        isLoading: false,
        error: null,
      });

      // Act: Re-render
      rerender(<Dashboard />);

      // Assert: Sticky positioning maintained
      header = container.querySelector("header");
      expect(header.className).toContain("sticky");
      expect(header.className).toContain("top-0");
    });
  });

  describe("Header content and structure", () => {
    it("should render header with title and subtitle", () => {
      // Arrange: Mock locations
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      render(<Dashboard />);

      // Assert: Verify header content
      expect(screen.getByText("Weather")).toBeInTheDocument();
      expect(
        screen.getByText("Your locations at a glance"),
      ).toBeInTheDocument();
    });

    it("should include ViewToggle component in header", () => {
      // Arrange: Mock locations
      const mockLocations = [
        {
          id: 1,
          latitude: 1.3,
          longitude: 103.8,
          weather: {
            area: "Singapore",
            condition: "Sunny",
            valid_period_text: "Today",
            observed_at: "2024-01-01T12:00:00Z",
            source: "weather.gov.sg",
          },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      // Act: Render the Dashboard
      render(<Dashboard />);

      // Assert: Verify ViewToggle is present
      expect(screen.getByTestId("view-toggle")).toBeInTheDocument();
    });
  });

  describe("Header glassmorphism consistency", () => {
    it("should maintain glassmorphism styling across all weather conditions", () => {
      const weatherConditions = [
        "Sunny",
        "Rainy",
        "Cloudy",
        "Thunderstorm",
        "Partly Cloudy",
      ];

      weatherConditions.forEach((condition) => {
        // Arrange: Mock location with specific condition
        const mockLocations = [
          {
            id: 1,
            latitude: 1.3,
            longitude: 103.8,
            weather: {
              area: "Singapore",
              condition,
              valid_period_text: "Today",
              observed_at: "2024-01-01T12:00:00Z",
              source: "weather.gov.sg",
            },
          },
        ];

        vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
          locations: mockLocations,
          isLoading: false,
          error: null,
        });

        // Act: Render the Dashboard
        const { container } = render(<Dashboard />);

        // Assert: Verify glassmorphism is consistent
        const header = container.querySelector("header");
        expect(header.className).toContain("bg-white/10");
        expect(header.className).toContain("backdrop-blur-xl");
        expect(header.className).toContain("border-white/20");
        expect(header.className).toContain("sticky");
        expect(header.className).toContain("top-0");
      });
    });
  });
});
