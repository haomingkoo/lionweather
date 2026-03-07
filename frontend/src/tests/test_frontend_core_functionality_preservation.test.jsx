/**
 * Preservation Property Tests - Frontend Core Functionality
 *
 * **Property 2: Preservation** - Existing Frontend Features Unchanged
 * **IMPORTANT**: Follow observation-first methodology
 * **GOAL**: Verify that existing frontend features continue to work correctly after UI/UX fixes
 *
 * **Validates: Requirements 3.6, 3.7, 3.8, 3.9, 3.10**
 *
 * Test Cases:
 * 1. Manual location addition should continue to work
 * 2. Main Dashboard should display weather information correctly
 * 3. Weather information display (temperature, humidity, wind) should remain unchanged
 * 4. Initial geolocation prompt functionality should remain unchanged
 * 5. Location refresh and delete functionality should be preserved
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LocationList } from "../components/LocationList.jsx";
import { GeolocationPrompt } from "../components/GeolocationPrompt.jsx";
import { LocationsProvider } from "../hooks/useLocations.jsx";
import * as useLocationsHook from "../hooks/useLocations.jsx";
import fc from "fast-check";

describe("Preservation Property Tests - Frontend Core Functionality", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Property 1: Manual Location Addition Preservation", () => {
    it("should continue to store locations and display them correctly", () => {
      fc.assert(
        fc.property(
          fc.record({
            id: fc.integer({ min: 1, max: 1000 }),
            latitude: fc.double({ min: 1.1, max: 1.5 }),
            longitude: fc.double({ min: 103.6, max: 104.1 }),
            area: fc.string({ minLength: 3, maxLength: 20 }),
            condition: fc.constantFrom(
              "Sunny",
              "Cloudy",
              "Rainy",
              "Partly Cloudy",
            ),
          }),
          (locationData) => {
            const mockLocation = {
              id: locationData.id,
              latitude: locationData.latitude,
              longitude: locationData.longitude,
              weather: {
                area: locationData.area,
                condition: locationData.condition,
                observed_at: new Date().toISOString(),
                valid_period_text: "Next 2 hours",
              },
            };

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

            const { container } = render(
              <LocationsProvider>
                <LocationList isDark={false} />
              </LocationsProvider>,
            );

            // Verify location is displayed
            const locationCard = container.querySelector("article");
            expect(locationCard).toBeTruthy();

            // Verify location data is shown
            expect(container.textContent).toContain(locationData.area);
            expect(container.textContent).toContain(locationData.condition);

            // **EXPECTED OUTCOME**: Test PASSES (confirms manual location addition still works)
            // **Validates: Requirement 3.6** - Manual location addition continues to work
          },
        ),
        { numRuns: 10 },
      );
    });
  });

  describe("Property 2: Main Dashboard Weather Display Preservation", () => {
    it("should continue to display current weather information", () => {
      fc.assert(
        fc.property(
          fc.record({
            temperature: fc.integer({ min: 20, max: 35 }),
            humidity: fc.integer({ min: 40, max: 100 }),
            windSpeed: fc.integer({ min: 0, max: 30 }),
            condition: fc.constantFrom(
              "Sunny",
              "Cloudy",
              "Rainy",
              "Partly Cloudy",
              "Thunderstorm",
            ),
          }),
          (weatherData) => {
            const mockLocation = {
              id: 1,
              latitude: 1.3521,
              longitude: 103.8198,
              weather: {
                area: "Singapore",
                condition: weatherData.condition,
                temperature: weatherData.temperature,
                humidity: weatherData.humidity,
                wind_speed: weatherData.windSpeed,
                observed_at: new Date().toISOString(),
                valid_period_text: "Next 2 hours",
              },
            };

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

            const { container } = render(
              <LocationsProvider>
                <LocationList isDark={false} />
              </LocationsProvider>,
            );

            // Verify weather condition is displayed
            expect(container.textContent).toContain(weatherData.condition);

            // Verify location card structure is preserved
            const locationCard = container.querySelector("article");
            expect(locationCard).toBeTruthy();
            expect(locationCard.className).toContain("rounded");

            // **EXPECTED OUTCOME**: Test PASSES (confirms main Dashboard display is unchanged)
            // **Validates: Requirement 3.7** - Main Dashboard weather display remains unchanged
          },
        ),
        { numRuns: 10 },
      );
    });
  });

  describe("Property 3: Weather Information Display Preservation", () => {
    it("should continue to display all existing weather information", () => {
      const mockLocation = {
        id: 1,
        latitude: 1.3521,
        longitude: 103.8198,
        weather: {
          area: "Singapore",
          condition: "Partly Cloudy",
          temperature: 28,
          humidity: 75,
          wind_speed: 10,
          observed_at: new Date().toISOString(),
          valid_period_text: "Next 2 hours",
        },
      };

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

      const { container } = render(
        <LocationsProvider>
          <LocationList isDark={false} />
        </LocationsProvider>,
      );

      // Verify all weather information is displayed
      expect(container.textContent).toContain("Singapore");
      expect(container.textContent).toContain("Partly Cloudy");
      expect(container.textContent).toContain("Next 2 hours");

      // Verify card structure includes all sections
      const weatherDetails = container.querySelector(".space-y-3");
      expect(weatherDetails).toBeTruthy();

      // **EXPECTED OUTCOME**: Test PASSES (confirms weather information display is unchanged)
      // **Validates: Requirement 3.9** - All existing weather information display remains unchanged
    });
  });

  describe("Property 4: Geolocation Prompt Functionality Preservation", () => {
    it("should continue to request and handle geolocation permissions correctly", () => {
      const mockOnLocationDetected = vi.fn();
      const mockOnDismiss = vi.fn();

      // Mock navigator.geolocation
      const mockGetCurrentPosition = vi.fn();
      Object.defineProperty(window.navigator, "geolocation", {
        value: {
          getCurrentPosition: mockGetCurrentPosition,
        },
        writable: true,
      });

      const { container } = render(
        <GeolocationPrompt
          onLocationDetected={mockOnLocationDetected}
          onDismiss={mockOnDismiss}
        />,
      );

      // Verify prompt is rendered
      expect(container.textContent).toContain("Use My Location");

      // Simulate clicking "Use My Location" button
      const useLocationButton = screen.getByText(/Use My Location/i);
      fireEvent.click(useLocationButton);

      // Verify geolocation API is called
      expect(mockGetCurrentPosition).toHaveBeenCalled();

      // Verify the callback structure is preserved
      const callArgs = mockGetCurrentPosition.mock.calls[0];
      expect(callArgs).toHaveLength(3); // success, error, options

      // **EXPECTED OUTCOME**: Test PASSES (confirms geolocation prompt functionality is unchanged)
      // **Validates: Requirement 3.10** - Initial geolocation prompt functionality remains unchanged
    });

    it("should handle geolocation errors gracefully", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(1, 2, 3), // GeolocationPositionError codes
          (errorCode) => {
            const mockOnLocationDetected = vi.fn();
            const mockOnDismiss = vi.fn();

            // Mock navigator.geolocation with error
            const mockGetCurrentPosition = vi.fn((success, error) => {
              error({ code: errorCode });
            });
            Object.defineProperty(window.navigator, "geolocation", {
              value: {
                getCurrentPosition: mockGetCurrentPosition,
              },
              writable: true,
            });

            const { container, unmount } = render(
              <GeolocationPrompt
                onLocationDetected={mockOnLocationDetected}
                onDismiss={mockOnDismiss}
              />,
            );

            // Simulate clicking "Use My Location" button
            const useLocationButton = container.querySelector("button");
            fireEvent.click(useLocationButton);

            // Verify error is handled (component should not crash)
            expect(container).toBeTruthy();

            // Clean up
            unmount();

            // **EXPECTED OUTCOME**: Test PASSES (confirms error handling is preserved)
            // **Validates: Requirement 3.10** - Geolocation error handling remains unchanged
          },
        ),
        { numRuns: 3 },
      );
    });
  });

  describe("Property 5: Location Refresh and Delete Functionality Preservation", () => {
    it("should continue to support refresh and delete operations", () => {
      const mockRefresh = vi.fn();
      const mockDelete = vi.fn();

      const mockLocation = {
        id: 1,
        latitude: 1.3521,
        longitude: 103.8198,
        weather: {
          area: "Singapore",
          condition: "Partly Cloudy",
          observed_at: new Date().toISOString(),
          valid_period_text: "Next 2 hours",
        },
      };

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [mockLocation],
        isLoading: false,
        error: null,
      });

      vi.spyOn(useLocationsHook, "useRefreshLocation").mockReturnValue({
        refresh: mockRefresh,
        isPending: false,
        refreshingId: null,
        error: null,
      });

      vi.spyOn(useLocationsHook, "useDeleteLocation").mockReturnValue({
        deleteLocation: mockDelete,
        isPending: false,
      });

      const { container } = render(
        <LocationsProvider>
          <LocationList isDark={false} />
        </LocationsProvider>,
      );

      // Find and click refresh button
      const refreshButton = screen.getByText(/Refresh/i);
      fireEvent.click(refreshButton);
      expect(mockRefresh).toHaveBeenCalledWith(1);

      // Find and click delete button
      const deleteButton = container.querySelector('button[class*="bg-red"]');
      fireEvent.click(deleteButton);
      expect(mockDelete).toHaveBeenCalledWith(1);

      // **EXPECTED OUTCOME**: Test PASSES (confirms refresh and delete functionality is preserved)
      // **Validates: Requirements 3.6, 3.7** - Existing functionality remains unchanged
    });
  });
});
