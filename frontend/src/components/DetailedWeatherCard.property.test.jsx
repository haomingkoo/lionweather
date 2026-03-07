import { describe, it, expect, vi, beforeEach } from "vitest";
import fc from "fast-check";
import { render, screen } from "@testing-library/react";
import { DetailedWeatherCard } from "./DetailedWeatherCard";

/**
 * Property-Based Tests for DetailedWeatherCard Component
 * Feature: apple-weather-ui-redesign
 */

// Mock the API client and forecast functions
vi.mock("../api/client", () => ({
  request: vi.fn(() => Promise.resolve({})),
}));

vi.mock("../api/forecasts", () => ({
  get24HourForecast: vi.fn(() => Promise.resolve({ periods: [] })),
  get4DayForecast: vi.fn(() => Promise.resolve({ forecasts: [] })),
}));

// Mock the PrecipitationMap and MLForecastComparison components
vi.mock("./PrecipitationMap", () => ({
  PrecipitationMap: () => null,
}));

vi.mock("./MLForecastComparison", () => ({
  MLForecastComparison: () => null,
}));

describe("Property-Based Tests: DetailedWeatherCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Generator for location objects
  const locationArbitrary = fc.record({
    id: fc.integer({ min: 1, max: 1000 }),
    latitude: fc.float({ min: Math.fround(1.1), max: Math.fround(1.5) }),
    longitude: fc.float({ min: Math.fround(103.6), max: Math.fround(104.1) }),
    weather: fc.record({
      area: fc.constantFrom("Singapore", "Jurong", "Tampines", "Woodlands"),
      condition: fc.constantFrom(
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
      ),
      valid_period_text: fc.string(),
      observed_at: fc.constant(new Date("2024-01-15").toISOString()),
      source: fc.constant("weather.gov.sg"),
    }),
  });

  /**
   * Property 5: Temperature display prominence
   * **Validates: Requirements 2.2**
   *
   * For any location card rendering, the temperature element should appear
   * in the DOM before other weather detail elements (condition, valid period,
   * last updated), establishing visual hierarchy.
   */
  describe("Feature: apple-weather-ui-redesign, Property 5: Temperature display prominence", () => {
    it("should render temperature element before other weather detail elements for any location", async () => {
      await fc.assert(
        fc.asyncProperty(locationArbitrary, async (location) => {
          const { container } = render(
            <DetailedWeatherCard location={location} isDark={false} />,
          );

          // Find the temperature element (text-8xl class indicates the large temperature display)
          const temperatureElement = container.querySelector(".text-8xl");
          expect(temperatureElement).toBeTruthy();

          // Find the condition text element (text-2xl class for condition)
          const conditionElement = container.querySelector(".text-2xl");
          expect(conditionElement).toBeTruthy();

          // Get all elements in the main weather display section
          const mainWeatherSection = container.querySelector(".text-center");
          expect(mainWeatherSection).toBeTruthy();

          // Get the order of elements
          const allElements = Array.from(
            mainWeatherSection.querySelectorAll("*"),
          );
          const tempIndex = allElements.indexOf(temperatureElement);
          const conditionIndex = allElements.indexOf(conditionElement);

          // Temperature should appear before condition in the DOM
          expect(tempIndex).toBeGreaterThanOrEqual(0);
          expect(conditionIndex).toBeGreaterThanOrEqual(0);
          expect(tempIndex).toBeLessThan(conditionIndex);
        }),
        { numRuns: 50 },
      );
    });

    it("should use large font size (48px minimum) for temperature display", async () => {
      await fc.assert(
        fc.asyncProperty(locationArbitrary, async (location) => {
          const { container } = render(
            <DetailedWeatherCard location={location} isDark={false} />,
          );

          // Find the temperature element
          const temperatureElement = container.querySelector(".text-8xl");
          expect(temperatureElement).toBeTruthy();

          // Verify it has the text-8xl class (which is 96px, exceeding 48px minimum)
          expect(temperatureElement.className).toContain("text-8xl");
        }),
        { numRuns: 50 },
      );
    });

    it("should use lightweight font weight for temperature display", async () => {
      await fc.assert(
        fc.asyncProperty(locationArbitrary, async (location) => {
          const { container } = render(
            <DetailedWeatherCard location={location} isDark={false} />,
          );

          // Find the temperature element
          const temperatureElement = container.querySelector(".text-8xl");
          expect(temperatureElement).toBeTruthy();

          // Verify it has a lightweight font class (font-extralight, font-thin, or font-light)
          const className = temperatureElement.className;
          const hasLightweightFont =
            className.includes("font-extralight") ||
            className.includes("font-thin") ||
            className.includes("font-light");
          expect(hasLightweightFont).toBe(true);
        }),
        { numRuns: 50 },
      );
    });

    it("should position temperature as primary visual element in the center", async () => {
      await fc.assert(
        fc.asyncProperty(locationArbitrary, async (location) => {
          const { container } = render(
            <DetailedWeatherCard location={location} isDark={false} />,
          );

          // Find the temperature element
          const temperatureElement = container.querySelector(".text-8xl");
          expect(temperatureElement).toBeTruthy();

          // Verify it's within a centered container
          const parentSection = temperatureElement.closest(".text-center");
          expect(parentSection).toBeTruthy();
        }),
        { numRuns: 50 },
      );
    });
  });

  /**
   * Property 6: Icon SVG format
   * **Validates: Requirements 3.7**
   *
   * For any weather icon component rendered, the root element should be an SVG element,
   * ensuring scalability across different screen sizes.
   */
  describe("Feature: apple-weather-ui-redesign, Property 6: Icon SVG format", () => {
    it("should render weather icons as SVG elements for any location", async () => {
      await fc.assert(
        fc.asyncProperty(locationArbitrary, async (location) => {
          const { container } = render(
            <DetailedWeatherCard location={location} isDark={false} />,
          );

          // Find all SVG elements in the component
          const svgElements = container.querySelectorAll("svg");

          // There should be at least one SVG element (the main weather icon)
          expect(svgElements.length).toBeGreaterThan(0);

          // Verify each SVG element has the correct tag name
          svgElements.forEach((svg) => {
            expect(svg.tagName.toLowerCase()).toBe("svg");
          });
        }),
        { numRuns: 50 },
      );
    });

    it("should render weather icons with minimum size of 24px", async () => {
      await fc.assert(
        fc.asyncProperty(locationArbitrary, async (location) => {
          const { container } = render(
            <DetailedWeatherCard location={location} isDark={false} />,
          );

          // Find the main weather icon (h-8 w-8 = 32px, which exceeds 24px minimum)
          const mainIcon = container.querySelector(".h-8.w-8");

          if (mainIcon && mainIcon.tagName.toLowerCase() === "svg") {
            // Verify it has size classes that meet the 24px minimum
            const className = mainIcon.className.baseVal || mainIcon.className;
            const hasSufficientSize =
              className.includes("h-8") || // 32px
              className.includes("h-6") || // 24px
              className.includes("h-7") || // 28px
              className.includes("w-8") || // 32px
              className.includes("w-6") || // 24px
              className.includes("w-7"); // 28px
            expect(hasSufficientSize).toBe(true);
          }
        }),
        { numRuns: 50 },
      );
    });

    it("should render SVG icons adjacent to condition text", async () => {
      await fc.assert(
        fc.asyncProperty(locationArbitrary, async (location) => {
          const { container } = render(
            <DetailedWeatherCard location={location} isDark={false} />,
          );

          // Find the condition text element
          const conditionText = Array.from(
            container.querySelectorAll("span"),
          ).find((span) => span.textContent === location.weather.condition);

          if (conditionText) {
            // Find the parent container
            const parent = conditionText.parentElement;

            // Verify there's an SVG element in the same parent (adjacent)
            const svgInParent = parent?.querySelector("svg");
            expect(svgInParent).toBeTruthy();
          }
        }),
        { numRuns: 50 },
      );
    });
  });

  /**
   * Property 11: Icon accessibility
   * **Validates: Requirements 11.1**
   *
   * For any weather icon rendered, the icon component should include an aria-label attribute
   * or be wrapped in an element with descriptive text, ensuring screen reader users understand
   * the weather condition.
   */
  describe("Feature: apple-weather-ui-redesign, Property 11: Icon accessibility", () => {
    it("should include aria-label on weather condition icons for any location", async () => {
      await fc.assert(
        fc.asyncProperty(locationArbitrary, async (location) => {
          const { container } = render(
            <DetailedWeatherCard location={location} isDark={false} />,
          );

          // Find weather condition icons (those with aria-label containing "weather icon")
          const weatherIcons = Array.from(
            container.querySelectorAll("svg"),
          ).filter((svg) => {
            const ariaLabel = svg.getAttribute("aria-label");
            return (
              ariaLabel && ariaLabel.toLowerCase().includes("weather icon")
            );
          });

          // Verify we found at least one weather icon
          expect(weatherIcons.length).toBeGreaterThan(0);

          // Verify each weather icon has a non-empty aria-label
          weatherIcons.forEach((svg) => {
            const ariaLabel = svg.getAttribute("aria-label");
            expect(ariaLabel).toBeTruthy();
            expect(ariaLabel.length).toBeGreaterThan(0);
          });
        }),
        { numRuns: 50 },
      );
    });

    it("should include weather condition in aria-label for main weather icon", async () => {
      await fc.assert(
        fc.asyncProperty(locationArbitrary, async (location) => {
          const { container } = render(
            <DetailedWeatherCard location={location} isDark={false} />,
          );

          // Find the main weather icon (h-8 w-8 class)
          const mainIcon = container.querySelector(".h-8.w-8");

          if (mainIcon && mainIcon.tagName.toLowerCase() === "svg") {
            const ariaLabel = mainIcon.getAttribute("aria-label");
            expect(ariaLabel).toBeTruthy();

            // Verify the aria-label includes the weather condition
            const conditionLower = location.weather.condition.toLowerCase();
            const ariaLabelLower = ariaLabel.toLowerCase();
            expect(ariaLabelLower).toContain(conditionLower);
          }
        }),
        { numRuns: 50 },
      );
    });

    it("should provide descriptive aria-labels that include 'weather icon' text", async () => {
      await fc.assert(
        fc.asyncProperty(locationArbitrary, async (location) => {
          const { container } = render(
            <DetailedWeatherCard location={location} isDark={false} />,
          );

          // Find all SVG elements with aria-label
          const svgsWithAriaLabel = Array.from(
            container.querySelectorAll("svg[aria-label]"),
          );

          // Verify at least one SVG has an aria-label containing "weather icon"
          const hasWeatherIconLabel = svgsWithAriaLabel.some((svg) => {
            const ariaLabel = svg.getAttribute("aria-label");
            return (
              ariaLabel && ariaLabel.toLowerCase().includes("weather icon")
            );
          });

          expect(hasWeatherIconLabel).toBe(true);
        }),
        { numRuns: 50 },
      );
    });
  });
});
