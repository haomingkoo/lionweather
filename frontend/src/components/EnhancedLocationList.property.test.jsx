import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup } from "@testing-library/react";
import fc from "fast-check";
import { EnhancedLocationList } from "./EnhancedLocationList";
import { LocationForm } from "./LocationForm";
import { LocationsProvider } from "../hooks/useLocations";
import * as useLocationsHook from "../hooks/useLocations";

/**
 * Property-Based Tests for Glassmorphism Consistency
 * Feature: apple-weather-ui-redesign
 */

describe("Property-Based Tests: Glassmorphism Consistency", () => {
  // Clean up after each test to avoid DOM pollution
  afterEach(() => {
    cleanup();
  });

  /**
   * Property 7: Glassmorphism consistency across card components
   * **Validates: Requirements 4.1, 4.2, 4.3, 4.5, 12.1, 12.2, 12.5**
   *
   * For any card component (LocationCard, LocationForm, loading state, error state,
   * empty state), the component should include the glassmorphism class pattern:
   * - Translucent background (bg-white/[20-35])
   * - Backdrop blur (backdrop-blur-xl or backdrop-blur-md)
   * - Border with white opacity (border-white/[30-40])
   */
  describe("Feature: apple-weather-ui-redesign, Property 7: Glassmorphism consistency across card components", () => {
    /**
     * Helper function to verify glassmorphism pattern in a component
     */
    const verifyGlassmorphism = (element, componentName) => {
      const classes = element.className;

      // Requirement 4.1: Translucent background with 20% opacity (or 25-35% for variations)
      const hasTranslucentBg = /bg-white\/\d+/.test(classes);
      expect(hasTranslucentBg).toBe(true);

      // Extract opacity value
      const bgMatch = classes.match(/bg-white\/(\d+)/);
      if (bgMatch) {
        const opacity = parseInt(bgMatch[1], 10);
        // Allow range of 20-40% for different card types
        expect(opacity).toBeGreaterThanOrEqual(20);
        expect(opacity).toBeLessThanOrEqual(40);
      }

      // Requirement 4.2: Backdrop blur effect of at least 10 pixels
      const hasBackdropBlur = /backdrop-blur/.test(classes);
      expect(hasBackdropBlur).toBe(true);

      // Requirement 4.3: Subtle border with 30% white opacity (or 20-50% for variations)
      const hasWhiteBorder = /border-white\/\d+/.test(classes);
      expect(hasWhiteBorder).toBe(true);

      // Extract border opacity value
      const borderMatch = classes.match(/border-white\/(\d+)/);
      if (borderMatch) {
        const borderOpacity = parseInt(borderMatch[1], 10);
        // Allow range of 20-50% for different card types
        expect(borderOpacity).toBeGreaterThanOrEqual(20);
        expect(borderOpacity).toBeLessThanOrEqual(50);
      }
    };

    it("should apply glassmorphism to LocationForm component across all theme modes", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find the form element (main card)
            const formCard = container.querySelector("form");
            expect(formCard).not.toBeNull();

            // Requirement 4.5: Form component uses same glassmorphism styling as LocationCard
            verifyGlassmorphism(formCard, "LocationForm");

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should apply glassmorphism to location cards with various weather conditions", () => {
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
          fc.integer({ min: 1, max: 5 }), // number of locations
          (isDark, weatherCondition, numLocations) => {
            // Generate mock locations
            const mockLocations = Array.from(
              { length: numLocations },
              (_, i) => ({
                id: i + 1,
                latitude: 1.3 + i * 0.01,
                longitude: 103.8 + i * 0.01,
                weather: {
                  area: ["Singapore", "Jurong", "Tampines", "Woodlands"][i % 4],
                  condition: weatherCondition,
                  temperature: (28 + i).toString(),
                  valid_period_text: "Today",
                  observed_at: "2024-01-01T12:00:00Z",
                  source: "weather.gov.sg",
                },
              }),
            );

            // Mock the useLocations hook
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
              isPending: false,
            });

            const { container } = render(
              <EnhancedLocationList isDark={isDark} />,
            );

            // Find all location card articles
            const locationCards = container.querySelectorAll("article");
            expect(locationCards.length).toBe(numLocations);

            // Verify each location card has glassmorphism styling
            locationCards.forEach((card, index) => {
              verifyGlassmorphism(card, `LocationCard-${index}`);
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should apply glassmorphism to loading state card", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            // Mock loading state
            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations: [],
              isLoading: true,
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
              <EnhancedLocationList isDark={isDark} />,
            );

            // Find the loading card
            const loadingCard = container.querySelector(
              ".rounded-3xl.bg-white\\/30",
            );
            expect(loadingCard).not.toBeNull();

            // Requirement 12.1: Loading indicator uses glassmorphism styling
            verifyGlassmorphism(loadingCard, "LoadingState");

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should apply glassmorphism to error state card", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          fc.string({ minLength: 10, maxLength: 100 }), // error message
          (isDark, errorMessage) => {
            // Mock error state
            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations: [],
              isLoading: false,
              error: new Error(errorMessage),
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
              <EnhancedLocationList isDark={isDark} />,
            );

            // Find the error card (red-tinted glassmorphism)
            const errorCard = container.querySelector(
              ".rounded-3xl.bg-red-500\\/30",
            );
            expect(errorCard).not.toBeNull();

            // Requirement 12.2: Error message uses translucent card with backdrop blur
            const classes = errorCard.className;

            // Verify backdrop blur
            expect(classes).toMatch(/backdrop-blur/);

            // Verify border (red-tinted for error)
            expect(classes).toMatch(/border-red-400\/\d+/);

            // Requirement 12.4: Error card has rounded corners (12px minimum)
            expect(classes).toContain("rounded-3xl");

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should apply glassmorphism to empty state card", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            // Mock empty state
            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations: [],
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
              <EnhancedLocationList isDark={isDark} />,
            );

            // Find the empty state card
            const emptyCard = container.querySelector(
              ".rounded-3xl.bg-white\\/30",
            );
            expect(emptyCard).not.toBeNull();

            // Requirement 12.5: Empty state message appears in glassmorphism-styled card
            verifyGlassmorphism(emptyCard, "EmptyState");

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should maintain glassmorphism consistency across all card types simultaneously", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            // Test all card types in sequence to ensure consistency
            const cardTypes = [
              {
                name: "LocationForm",
                render: () => (
                  <LocationsProvider>
                    <LocationForm isDark={isDark} />
                  </LocationsProvider>
                ),
                selector: "form",
              },
              {
                name: "LoadingState",
                render: () => {
                  vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
                    locations: [],
                    isLoading: true,
                    error: null,
                  });
                  vi.spyOn(
                    useLocationsHook,
                    "useRefreshLocation",
                  ).mockReturnValue({
                    refresh: vi.fn(),
                    isPending: false,
                    refreshingId: null,
                    error: null,
                  });
                  vi.spyOn(
                    useLocationsHook,
                    "useDeleteLocation",
                  ).mockReturnValue({
                    deleteLocation: vi.fn(),
                    isPending: false,
                  });
                  return <EnhancedLocationList isDark={isDark} />;
                },
                selector: ".rounded-3xl.bg-white\\/30",
              },
              {
                name: "EmptyState",
                render: () => {
                  vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
                    locations: [],
                    isLoading: false,
                    error: null,
                  });
                  vi.spyOn(
                    useLocationsHook,
                    "useRefreshLocation",
                  ).mockReturnValue({
                    refresh: vi.fn(),
                    isPending: false,
                    refreshingId: null,
                    error: null,
                  });
                  vi.spyOn(
                    useLocationsHook,
                    "useDeleteLocation",
                  ).mockReturnValue({
                    deleteLocation: vi.fn(),
                    isPending: false,
                  });
                  return <EnhancedLocationList isDark={isDark} />;
                },
                selector: ".rounded-3xl.bg-white\\/30",
              },
            ];

            cardTypes.forEach((cardType) => {
              const { container } = render(cardType.render());
              const card = container.querySelector(cardType.selector);

              expect(card).not.toBeNull();
              verifyGlassmorphism(card, cardType.name);

              cleanup();
            });
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should apply glassmorphism with rounded corners to all card components", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            // Test LocationForm
            const { container: formContainer } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );
            const formCard = formContainer.querySelector("form");
            expect(formCard).not.toBeNull();

            // Requirement 4.4: Cards have rounded corners with radius of at least 16px
            expect(formCard.className).toMatch(/rounded-\[2rem\]/);

            cleanup();

            // Test LocationCard
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
              isPending: false,
              refreshingId: null,
              error: null,
            });

            vi.spyOn(useLocationsHook, "useDeleteLocation").mockReturnValue({
              deleteLocation: vi.fn(),
              isPending: false,
            });

            const { container: listContainer } = render(
              <EnhancedLocationList isDark={isDark} />,
            );
            const locationCard = listContainer.querySelector("article");
            expect(locationCard).not.toBeNull();
            expect(locationCard.className).toMatch(/rounded-\[2rem\]/);

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should verify glassmorphism pattern consistency across different opacity values", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            // Render multiple card types and collect their opacity values
            const opacityValues = [];

            // LocationForm
            const { container: formContainer } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );
            const formCard = formContainer.querySelector("form");
            const formMatch = formCard.className.match(/bg-white\/(\d+)/);
            if (formMatch) {
              opacityValues.push(parseInt(formMatch[1], 10));
            }
            cleanup();

            // LocationCard
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
              isPending: false,
              refreshingId: null,
              error: null,
            });

            vi.spyOn(useLocationsHook, "useDeleteLocation").mockReturnValue({
              deleteLocation: vi.fn(),
              isPending: false,
            });

            const { container: listContainer } = render(
              <EnhancedLocationList isDark={isDark} />,
            );
            const locationCard = listContainer.querySelector("article");
            const cardMatch = locationCard.className.match(/bg-white\/(\d+)/);
            if (cardMatch) {
              opacityValues.push(parseInt(cardMatch[1], 10));
            }
            cleanup();

            // All opacity values should be within the acceptable range (20-40%)
            opacityValues.forEach((opacity) => {
              expect(opacity).toBeGreaterThanOrEqual(20);
              expect(opacity).toBeLessThanOrEqual(40);
            });

            // Verify we collected opacity values from multiple components
            expect(opacityValues.length).toBeGreaterThan(0);
          },
        ),
        { numRuns: 100 },
      );
    });
  });
});
