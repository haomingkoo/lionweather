import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import fc from "fast-check";
import { LocationList } from "./LocationList";
import { LocationsProvider } from "../hooks/useLocations";
import * as useLocationsHook from "../hooks/useLocations";

/**
 * Property-Based Tests for LocationList Component
 * Feature: apple-weather-ui-redesign, Property 10: Responsive grid layout
 *
 * **Validates: Requirements 10.1**
 *
 * Property 10: Responsive grid layout
 * For any viewport width, the LocationList grid should use appropriate column counts:
 * - 1 column when width < 768px
 * - 2 columns when 768px ≤ width < 1024px
 * - 3 columns when width ≥ 1024px
 */

describe("Property 10: Responsive grid layout", () => {
  const createMockLocation = (id, latitude, longitude, condition) => ({
    id,
    latitude,
    longitude,
    weather: {
      area: "Singapore",
      condition,
      temperature: "29",
      valid_period_text: "Today",
      observed_at: new Date().toISOString(),
      source: "weather.gov.sg",
    },
  });

  beforeEach(() => {
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
  });

  describe("Grid column classes verification", () => {
    it("should have base grid class without column specification (mobile-first)", () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.record({
              id: fc.integer({ min: 1, max: 1000 }),
              latitude: fc.float({
                min: Math.fround(1.1),
                max: Math.fround(1.5),
              }),
              longitude: fc.float({
                min: Math.fround(103.6),
                max: Math.fround(104.1),
              }),
              condition: fc.constantFrom(
                "Sunny",
                "Rainy",
                "Cloudy",
                "Thunderstorm",
                "Partly Cloudy",
              ),
            }),
            { minLength: 1, maxLength: 10 },
          ),
          (locationData) => {
            const locations = locationData.map((data) =>
              createMockLocation(
                data.id,
                data.latitude,
                data.longitude,
                data.condition,
              ),
            );

            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations,
              isLoading: false,
              error: null,
            });

            const { container } = render(
              <LocationsProvider>
                <LocationList isDark={false} />
              </LocationsProvider>,
            );

            const gridContainer = container.querySelector(".grid");
            expect(gridContainer).not.toBeNull();

            // Verify base grid class is present
            expect(gridContainer.className).toContain("grid");
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should have md:grid-cols-2 class for tablet breakpoint (768px+)", () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.record({
              id: fc.integer({ min: 1, max: 1000 }),
              latitude: fc.float({
                min: Math.fround(1.1),
                max: Math.fround(1.5),
              }),
              longitude: fc.float({
                min: Math.fround(103.6),
                max: Math.fround(104.1),
              }),
              condition: fc.constantFrom(
                "Sunny",
                "Rainy",
                "Cloudy",
                "Thunderstorm",
                "Partly Cloudy",
              ),
            }),
            { minLength: 1, maxLength: 10 },
          ),
          (locationData) => {
            const locations = locationData.map((data) =>
              createMockLocation(
                data.id,
                data.latitude,
                data.longitude,
                data.condition,
              ),
            );

            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations,
              isLoading: false,
              error: null,
            });

            const { container } = render(
              <LocationsProvider>
                <LocationList isDark={false} />
              </LocationsProvider>,
            );

            const gridContainer = container.querySelector(".grid");
            expect(gridContainer).not.toBeNull();

            // Verify md:grid-cols-2 class for tablet (768px ≤ width < 1024px)
            expect(gridContainer.className).toContain("md:grid-cols-2");
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should have lg:grid-cols-3 class for desktop breakpoint (1024px+)", () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.record({
              id: fc.integer({ min: 1, max: 1000 }),
              latitude: fc.float({
                min: Math.fround(1.1),
                max: Math.fround(1.5),
              }),
              longitude: fc.float({
                min: Math.fround(103.6),
                max: Math.fround(104.1),
              }),
              condition: fc.constantFrom(
                "Sunny",
                "Rainy",
                "Cloudy",
                "Thunderstorm",
                "Partly Cloudy",
              ),
            }),
            { minLength: 1, maxLength: 10 },
          ),
          (locationData) => {
            const locations = locationData.map((data) =>
              createMockLocation(
                data.id,
                data.latitude,
                data.longitude,
                data.condition,
              ),
            );

            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations,
              isLoading: false,
              error: null,
            });

            const { container } = render(
              <LocationsProvider>
                <LocationList isDark={false} />
              </LocationsProvider>,
            );

            const gridContainer = container.querySelector(".grid");
            expect(gridContainer).not.toBeNull();

            // Verify lg:grid-cols-3 class for desktop (width ≥ 1024px)
            expect(gridContainer.className).toContain("lg:grid-cols-3");
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should have all responsive grid classes together", () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.record({
              id: fc.integer({ min: 1, max: 1000 }),
              latitude: fc.float({
                min: Math.fround(1.1),
                max: Math.fround(1.5),
              }),
              longitude: fc.float({
                min: Math.fround(103.6),
                max: Math.fround(104.1),
              }),
              condition: fc.constantFrom(
                "Sunny",
                "Rainy",
                "Cloudy",
                "Thunderstorm",
                "Partly Cloudy",
              ),
            }),
            { minLength: 1, maxLength: 10 },
          ),
          (locationData) => {
            const locations = locationData.map((data) =>
              createMockLocation(
                data.id,
                data.latitude,
                data.longitude,
                data.condition,
              ),
            );

            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations,
              isLoading: false,
              error: null,
            });

            const { container } = render(
              <LocationsProvider>
                <LocationList isDark={false} />
              </LocationsProvider>,
            );

            const gridContainer = container.querySelector(".grid");
            expect(gridContainer).not.toBeNull();

            const className = gridContainer.className;

            // Verify complete responsive grid pattern:
            // - Base: grid (mobile-first, 1 column by default)
            // - Tablet: md:grid-cols-2 (768px ≤ width < 1024px)
            // - Desktop: lg:grid-cols-3 (width ≥ 1024px)
            expect(className).toContain("grid");
            expect(className).toContain("md:grid-cols-2");
            expect(className).toContain("lg:grid-cols-3");
          },
        ),
        { numRuns: 100 },
      );
    });
  });

  describe("Grid behavior with different location counts", () => {
    it("should maintain responsive grid classes regardless of location count", () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1, max: 20 }), // Number of locations
          (locationCount) => {
            const locations = Array.from({ length: locationCount }, (_, i) => ({
              id: i + 1,
              latitude: 1.3 + i * 0.01,
              longitude: 103.8 + i * 0.01,
              weather: {
                area: `Location ${i + 1}`,
                condition: "Sunny",
                temperature: "29",
                valid_period_text: "Today",
                observed_at: new Date().toISOString(),
                source: "weather.gov.sg",
              },
            }));

            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations,
              isLoading: false,
              error: null,
            });

            const { container } = render(
              <LocationsProvider>
                <LocationList isDark={false} />
              </LocationsProvider>,
            );

            const gridContainer = container.querySelector(".grid");
            expect(gridContainer).not.toBeNull();

            // Grid classes should be present regardless of item count
            const className = gridContainer.className;
            expect(className).toContain("grid");
            expect(className).toContain("md:grid-cols-2");
            expect(className).toContain("lg:grid-cols-3");

            // Verify correct number of cards are rendered
            const cards = container.querySelectorAll("article");
            expect(cards.length).toBe(locationCount);
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should work with single location", () => {
      fc.assert(
        fc.property(
          fc.record({
            id: fc.integer({ min: 1, max: 1000 }),
            latitude: fc.float({
              min: Math.fround(1.1),
              max: Math.fround(1.5),
            }),
            longitude: fc.float({
              min: Math.fround(103.6),
              max: Math.fround(104.1),
            }),
            condition: fc.constantFrom(
              "Sunny",
              "Rainy",
              "Cloudy",
              "Thunderstorm",
              "Partly Cloudy",
            ),
          }),
          (locationData) => {
            const location = createMockLocation(
              locationData.id,
              locationData.latitude,
              locationData.longitude,
              locationData.condition,
            );

            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations: [location],
              isLoading: false,
              error: null,
            });

            const { container } = render(
              <LocationsProvider>
                <LocationList isDark={false} />
              </LocationsProvider>,
            );

            const gridContainer = container.querySelector(".grid");
            expect(gridContainer).not.toBeNull();

            // Grid classes should be present even with single item
            const className = gridContainer.className;
            expect(className).toContain("grid");
            expect(className).toContain("md:grid-cols-2");
            expect(className).toContain("lg:grid-cols-3");
          },
        ),
        { numRuns: 100 },
      );
    });
  });

  describe("Grid behavior with different themes", () => {
    it("should maintain responsive grid classes in both light and dark themes", () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.record({
              id: fc.integer({ min: 1, max: 1000 }),
              latitude: fc.float({
                min: Math.fround(1.1),
                max: Math.fround(1.5),
              }),
              longitude: fc.float({
                min: Math.fround(103.6),
                max: Math.fround(104.1),
              }),
              condition: fc.constantFrom(
                "Sunny",
                "Rainy",
                "Cloudy",
                "Thunderstorm",
                "Partly Cloudy",
              ),
            }),
            { minLength: 1, maxLength: 10 },
          ),
          fc.boolean(), // isDark theme
          (locationData, isDark) => {
            const locations = locationData.map((data) =>
              createMockLocation(
                data.id,
                data.latitude,
                data.longitude,
                data.condition,
              ),
            );

            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations,
              isLoading: false,
              error: null,
            });

            const { container } = render(
              <LocationsProvider>
                <LocationList isDark={isDark} />
              </LocationsProvider>,
            );

            const gridContainer = container.querySelector(".grid");
            expect(gridContainer).not.toBeNull();

            // Grid classes should be present regardless of theme
            const className = gridContainer.className;
            expect(className).toContain("grid");
            expect(className).toContain("md:grid-cols-2");
            expect(className).toContain("lg:grid-cols-3");
          },
        ),
        { numRuns: 100 },
      );
    });
  });

  describe("Grid gap spacing", () => {
    it("should have consistent gap spacing across all viewport sizes", () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.record({
              id: fc.integer({ min: 1, max: 1000 }),
              latitude: fc.float({
                min: Math.fround(1.1),
                max: Math.fround(1.5),
              }),
              longitude: fc.float({
                min: Math.fround(103.6),
                max: Math.fround(104.1),
              }),
              condition: fc.constantFrom(
                "Sunny",
                "Rainy",
                "Cloudy",
                "Thunderstorm",
                "Partly Cloudy",
              ),
            }),
            { minLength: 1, maxLength: 10 },
          ),
          (locationData) => {
            const locations = locationData.map((data) =>
              createMockLocation(
                data.id,
                data.latitude,
                data.longitude,
                data.condition,
              ),
            );

            vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
              locations,
              isLoading: false,
              error: null,
            });

            const { container } = render(
              <LocationsProvider>
                <LocationList isDark={false} />
              </LocationsProvider>,
            );

            const gridContainer = container.querySelector(".grid");
            expect(gridContainer).not.toBeNull();

            // Verify gap-6 class is present (24px gap)
            expect(gridContainer.className).toContain("gap-6");
          },
        ),
        { numRuns: 100 },
      );
    });
  });

  describe("Edge cases", () => {
    it("should not render grid when loading", () => {
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [],
        isLoading: true,
        error: null,
      });

      const { container } = render(
        <LocationsProvider>
          <LocationList isDark={false} />
        </LocationsProvider>,
      );

      const gridContainer = container.querySelector(".grid");
      // Grid should not be present during loading state
      expect(gridContainer).toBeNull();
    });

    it("should not render grid when error occurs", () => {
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [],
        isLoading: false,
        error: new Error("Test error"),
      });

      const { container } = render(
        <LocationsProvider>
          <LocationList isDark={false} />
        </LocationsProvider>,
      );

      const gridContainer = container.querySelector(".grid");
      // Grid should not be present during error state
      expect(gridContainer).toBeNull();
    });

    it("should not render grid when no locations exist", () => {
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [],
        isLoading: false,
        error: null,
      });

      const { container } = render(
        <LocationsProvider>
          <LocationList isDark={false} />
        </LocationsProvider>,
      );

      const gridContainer = container.querySelector(".grid");
      // Grid should not be present when there are no locations
      expect(gridContainer).toBeNull();
    });
  });
});
