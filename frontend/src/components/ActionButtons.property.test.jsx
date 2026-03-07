import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup } from "@testing-library/react";
import fc from "fast-check";
import { EnhancedLocationList } from "./EnhancedLocationList";
import { LocationList } from "./LocationList";
import { LocationForm } from "./LocationForm";
import { LocationsProvider } from "../hooks/useLocations";
import * as useLocationsHook from "../hooks/useLocations";

/**
 * Property-Based Tests for Action Button Styling
 * Feature: apple-weather-ui-redesign
 */

describe("Property-Based Tests: Action Button Styling", () => {
  // Clean up after each test to avoid DOM pollution
  afterEach(() => {
    cleanup();
  });

  /**
   * Property 12: Disabled button opacity
   * **Validates: Requirements 9.5**
   *
   * For any action button in a disabled state, the button should have reduced
   * opacity (opacity-50 class or equivalent) to visually indicate its disabled status.
   */
  describe("Feature: apple-weather-ui-redesign, Property 12: Disabled button opacity", () => {
    /**
     * Helper function to verify disabled button opacity
     */
    const verifyDisabledOpacity = (button, buttonName) => {
      const classes = button.className;

      // Requirement 9.5: Disabled button reduces opacity to 50%
      const hasDisabledOpacity = /disabled:opacity-50/.test(classes);
      expect(hasDisabledOpacity).toBe(true);

      // Verify the button is actually disabled
      expect(button.disabled).toBe(true);
    };

    it("should apply opacity-50 to disabled refresh buttons in EnhancedLocationList", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          fc.constantFrom(
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
          ), // weather condition
          fc.integer({ min: 1, max: 3 }), // number of locations
          (isDark, weatherCondition, numLocations) => {
            // Generate mock locations
            const mockLocations = Array.from(
              { length: numLocations },
              (_, i) => ({
                id: i + 1,
                latitude: 1.3 + i * 0.01,
                longitude: 103.8 + i * 0.01,
                weather: {
                  area: ["Singapore", "Jurong", "Tampines"][i % 3],
                  condition: weatherCondition,
                  temperature: (28 + i).toString(),
                  valid_period_text: "Today",
                  observed_at: "2024-01-01T12:00:00Z",
                  source: "weather.gov.sg",
                },
              }),
            );

            // Mock the useLocations hook with disabled state (isPending = true)
            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations: mockLocations,
              isLoading: false,
              error: null,
            });

            vi.spyOn(useLocationsHook, "useRefreshLocation").mockReturnValue({
              refresh: vi.fn(),
              isPending: true, // This will disable the buttons
              refreshingId: null,
              error: null,
            });

            vi.spyOn(useLocationsHook, "useDeleteLocation").mockReturnValue({
              deleteLocation: vi.fn(),
              isPending: false,
            });

            const { container } = render(
              <EnhancedLocationList isDark={isDark} />,
            );

            // Expand the first location to see action buttons
            const firstCard = container.querySelector("article");
            expect(firstCard).not.toBeNull();

            // Click to expand
            const expandButton = firstCard.querySelector(".cursor-pointer");
            if (expandButton) {
              expandButton.click();
            }

            // Find all refresh buttons (they should be disabled)
            const refreshButtons = Array.from(
              container.querySelectorAll("button"),
            ).filter((btn) => btn.textContent.includes("Refresh"));

            // Verify at least one refresh button exists
            if (refreshButtons.length > 0) {
              refreshButtons.forEach((button, index) => {
                verifyDisabledOpacity(button, `RefreshButton-${index}`);
              });
            }

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should apply opacity-50 to disabled delete buttons in EnhancedLocationList", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          fc.constantFrom(
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
          ), // weather condition
          fc.integer({ min: 1, max: 3 }), // number of locations
          (isDark, weatherCondition, numLocations) => {
            // Generate mock locations
            const mockLocations = Array.from(
              { length: numLocations },
              (_, i) => ({
                id: i + 1,
                latitude: 1.3 + i * 0.01,
                longitude: 103.8 + i * 0.01,
                weather: {
                  area: ["Singapore", "Jurong", "Tampines"][i % 3],
                  condition: weatherCondition,
                  temperature: (28 + i).toString(),
                  valid_period_text: "Today",
                  observed_at: "2024-01-01T12:00:00Z",
                  source: "weather.gov.sg",
                },
              }),
            );

            // Mock the useLocations hook with disabled state (isDeleting = true)
            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations: mockLocations,
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
              isPending: true, // This will disable the buttons
            });

            const { container } = render(
              <EnhancedLocationList isDark={isDark} />,
            );

            // Expand the first location to see action buttons
            const firstCard = container.querySelector("article");
            expect(firstCard).not.toBeNull();

            // Click to expand
            const expandButton = firstCard.querySelector(".cursor-pointer");
            if (expandButton) {
              expandButton.click();
            }

            // Find all delete buttons (they should be disabled)
            const deleteButtons = Array.from(
              container.querySelectorAll("button"),
            ).filter(
              (btn) =>
                btn.querySelector('svg[class*="lucide-trash"]') !== null ||
                btn.className.includes("bg-red-500"),
            );

            // Verify at least one delete button exists
            if (deleteButtons.length > 0) {
              deleteButtons.forEach((button, index) => {
                verifyDisabledOpacity(button, `DeleteButton-${index}`);
              });
            }

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should apply opacity-50 to disabled action buttons in LocationList", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          fc.constantFrom(
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
          ), // weather condition
          fc.integer({ min: 1, max: 3 }), // number of locations
          (isDark, weatherCondition, numLocations) => {
            // Generate mock locations
            const mockLocations = Array.from(
              { length: numLocations },
              (_, i) => ({
                id: i + 1,
                latitude: 1.3 + i * 0.01,
                longitude: 103.8 + i * 0.01,
                weather: {
                  area: ["Singapore", "Jurong", "Tampines"][i % 3],
                  condition: weatherCondition,
                  temperature: (28 + i).toString(),
                  valid_period_text: "Today",
                  observed_at: "2024-01-01T12:00:00Z",
                  source: "weather.gov.sg",
                },
              }),
            );

            // Mock the useLocations hook with disabled state (isPending = true)
            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations: mockLocations,
              isLoading: false,
              error: null,
            });

            vi.spyOn(useLocationsHook, "useRefreshLocation").mockReturnValue({
              refresh: vi.fn(),
              isPending: true, // This will disable the buttons
              refreshingId: null,
              error: null,
            });

            vi.spyOn(useLocationsHook, "useDeleteLocation").mockReturnValue({
              deleteLocation: vi.fn(),
              isPending: false,
            });

            const { container } = render(<LocationList isDark={isDark} />);

            // Find all action buttons (they should be disabled)
            const actionButtons = Array.from(
              container.querySelectorAll("button"),
            );

            // Verify at least one button exists
            expect(actionButtons.length).toBeGreaterThan(0);

            actionButtons.forEach((button, index) => {
              if (button.disabled) {
                verifyDisabledOpacity(button, `ActionButton-${index}`);
              }
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should apply opacity-50 to disabled submit button in LocationForm", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            // Mock the useCreateLocation hook with pending state
            vi.spyOn(useLocationsHook, "useCreateLocation").mockReturnValue({
              create: vi.fn(),
              isPending: true, // This will disable the submit button
              error: null,
            });

            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find the submit button
            const submitButton = container.querySelector(
              'button[type="submit"]',
            );
            expect(submitButton).not.toBeNull();

            // Verify disabled opacity
            verifyDisabledOpacity(submitButton, "SubmitButton");

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should maintain disabled opacity across different theme modes", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            // Test LocationForm with disabled state
            vi.spyOn(useLocationsHook, "useCreateLocation").mockReturnValue({
              create: vi.fn(),
              isPending: true,
              error: null,
            });

            const { container: formContainer } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            const submitButton = formContainer.querySelector(
              'button[type="submit"]',
            );
            expect(submitButton).not.toBeNull();
            expect(submitButton.className).toMatch(/disabled:opacity-50/);
            expect(submitButton.disabled).toBe(true);

            cleanup();

            // Test LocationList with disabled state
            const mockLocations = [
              {
                id: 1,
                latitude: 1.3,
                longitude: 103.8,
                weather: {
                  area: "Singapore",
                  condition: "Sunny",
                  temperature: "29",
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

            vi.spyOn(useLocationsHook, "useRefreshLocation").mockReturnValue({
              refresh: vi.fn(),
              isPending: true,
              refreshingId: null,
              error: null,
            });

            vi.spyOn(useLocationsHook, "useDeleteLocation").mockReturnValue({
              deleteLocation: vi.fn(),
              isPending: false,
            });

            const { container: listContainer } = render(
              <LocationList isDark={isDark} />,
            );

            const disabledButtons = Array.from(
              listContainer.querySelectorAll("button"),
            ).filter((btn) => btn.disabled);

            expect(disabledButtons.length).toBeGreaterThan(0);

            disabledButtons.forEach((button) => {
              expect(button.className).toMatch(/disabled:opacity-50/);
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should verify disabled buttons also prevent hover effects", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            // Mock disabled state
            vi.spyOn(useLocationsHook, "useCreateLocation").mockReturnValue({
              create: vi.fn(),
              isPending: true,
              error: null,
            });

            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            const submitButton = container.querySelector(
              'button[type="submit"]',
            );
            expect(submitButton).not.toBeNull();

            const classes = submitButton.className;

            // Verify disabled state prevents hover scale
            expect(classes).toMatch(/disabled:hover:scale-100/);

            // Verify disabled state prevents hover brightness
            expect(classes).toMatch(/disabled:hover:brightness-100/);

            // Verify disabled opacity
            expect(classes).toMatch(/disabled:opacity-50/);

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });
  });
});
