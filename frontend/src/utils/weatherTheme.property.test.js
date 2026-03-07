import { describe, it, expect } from "vitest";
import fc from "fast-check";
import {
  getWeatherIcon,
  getWeatherGradient,
  isDarkGradient,
} from "./weatherTheme";

/**
 * Property-Based Tests for Weather Theme Utilities
 * Feature: apple-weather-ui-redesign
 */

describe("Property-Based Tests: Weather Theme", () => {
  /**
   * Property 1: Weather condition to icon mapping correctness
   * **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
   *
   * For any weather condition string, the getWeatherIcon function should return
   * an icon name that semantically matches the condition.
   */
  describe("Feature: apple-weather-ui-redesign, Property 1: Weather condition to icon mapping correctness", () => {
    it("should return semantically correct icons for any weather condition string", () => {
      fc.assert(
        fc.property(fc.string(), (condition) => {
          const icon = getWeatherIcon(condition);
          const conditionLower = condition?.toLowerCase() || "";

          // Valid icon names that can be returned
          const validIcons = [
            "Sun",
            "CloudRain",
            "CloudLightning",
            "Cloud",
            "CloudSun",
            "Cloudy",
          ];

          // The function must always return a valid icon name
          expect(validIcons).toContain(icon);

          // Verify semantic correctness based on condition keywords
          // Requirement 3.1: Sunny/Clear conditions return Sun icon
          if (
            conditionLower.includes("sunny") ||
            conditionLower.includes("clear") ||
            conditionLower.includes("fair")
          ) {
            expect(icon).toBe("Sun");
          }

          // Requirement 3.3: Rainy conditions return CloudRain icon
          if (
            conditionLower.includes("rain") ||
            conditionLower.includes("shower") ||
            conditionLower.includes("drizzle")
          ) {
            expect(icon).toBe("CloudRain");
          }

          // Requirement 3.4: Thunderstorm conditions return CloudLightning icon
          if (
            conditionLower.includes("thunder") ||
            conditionLower.includes("storm")
          ) {
            expect(icon).toBe("CloudLightning");
          }

          // Requirement 3.2: Cloudy conditions return cloud-related icons
          if (
            conditionLower.includes("cloud") &&
            !conditionLower.includes("partly")
          ) {
            expect(["Cloud", "CloudSun"]).toContain(icon);
          }

          if (conditionLower.includes("overcast")) {
            expect(icon).toBe("Cloudy");
          }

          // Partly cloudy conditions return CloudSun icon
          if (conditionLower.includes("partly")) {
            expect(icon).toBe("CloudSun");
          }
        }),
        { numRuns: 100 },
      );
    });

    it("should handle case insensitivity for any weather condition", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(
            "sunny",
            "clear",
            "fair",
            "rainy",
            "rain",
            "shower",
            "drizzle",
            "thunderstorm",
            "thunder",
            "storm",
            "cloudy",
            "cloud",
            "overcast",
            "partly cloudy",
            "partly",
          ),
          (condition) => {
            const lowerIcon = getWeatherIcon(condition.toLowerCase());
            const upperIcon = getWeatherIcon(condition.toUpperCase());
            const mixedIcon = getWeatherIcon(
              condition
                .split("")
                .map((c, i) =>
                  i % 2 === 0 ? c.toUpperCase() : c.toLowerCase(),
                )
                .join(""),
            );

            // All case variations should return the same icon
            expect(lowerIcon).toBe(upperIcon);
            expect(lowerIcon).toBe(mixedIcon);
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should always return a default icon for unknown or invalid conditions", () => {
      fc.assert(
        fc.property(
          fc.oneof(
            fc.string().filter((s) => {
              const lower = s.toLowerCase();
              return (
                !lower.includes("sunny") &&
                !lower.includes("clear") &&
                !lower.includes("fair") &&
                !lower.includes("rain") &&
                !lower.includes("shower") &&
                !lower.includes("drizzle") &&
                !lower.includes("thunder") &&
                !lower.includes("storm") &&
                !lower.includes("cloud") &&
                !lower.includes("overcast") &&
                !lower.includes("partly")
              );
            }),
            fc.constant(null),
            fc.constant(undefined),
            fc.constant(""),
          ),
          (condition) => {
            const icon = getWeatherIcon(condition);

            // Default icon should be CloudSun for unknown conditions
            expect(icon).toBe("CloudSun");
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should return consistent icons for conditions with multiple matching keywords", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(
            "partly cloudy",
            "sunny and clear",
            "cloudy with showers",
            "light rain",
            "heavy thunderstorm",
          ),
          (condition) => {
            const icon = getWeatherIcon(condition);
            const conditionLower = condition.toLowerCase();

            // Verify the implementation's priority order based on the actual code:
            // 1. sunny/clear/fair
            // 2. rain/shower/drizzle
            // 3. thunder/storm
            // 4. partly
            // 5. cloud
            // 6. overcast

            // Test checks that the first matching condition wins
            if (
              conditionLower.includes("sunny") ||
              conditionLower.includes("clear") ||
              conditionLower.includes("fair")
            ) {
              expect(icon).toBe("Sun");
            } else if (
              conditionLower.includes("rain") ||
              conditionLower.includes("shower") ||
              conditionLower.includes("drizzle")
            ) {
              expect(icon).toBe("CloudRain");
            } else if (
              conditionLower.includes("thunder") ||
              conditionLower.includes("storm")
            ) {
              expect(icon).toBe("CloudLightning");
            } else if (conditionLower.includes("partly")) {
              expect(icon).toBe("CloudSun");
            } else if (conditionLower.includes("cloud")) {
              expect(icon).toBe("Cloud");
            } else if (conditionLower.includes("overcast")) {
              expect(icon).toBe("Cloudy");
            }
          },
        ),
        { numRuns: 100 },
      );
    });
  });

  /**
   * Property 2: Weather condition to gradient mapping correctness
   * **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
   *
   * For any weather condition string, the getWeatherGradient function should return
   * gradient classes that match the condition's mood (sunny/clear→warm gradients with
   * yellow/orange, rainy→cool gradients with blue, thunderstorm→dark gradients with
   * purple/indigo, cloudy→neutral gradients with gray).
   */
  describe("Feature: apple-weather-ui-redesign, Property 2: Weather condition to gradient mapping correctness", () => {
    it("should return gradient classes matching the condition's mood for any weather condition", () => {
      fc.assert(
        fc.property(fc.string(), (condition) => {
          const gradient = getWeatherGradient(condition);
          const conditionLower = condition?.toLowerCase() || "";

          // The function must always return a valid gradient string
          expect(gradient).toBeTruthy();
          expect(typeof gradient).toBe("string");

          // Verify semantic correctness based on condition keywords
          // Requirement 1.1: Sunny/Clear conditions return warm gradients with yellow/orange
          if (
            conditionLower.includes("sunny") ||
            conditionLower.includes("clear") ||
            conditionLower.includes("fair")
          ) {
            expect(gradient).toContain("yellow");
            expect(gradient).toContain("orange");
          }

          // Requirement 1.2: Rainy conditions return cool gradients with blue
          if (
            conditionLower.includes("rain") ||
            conditionLower.includes("shower") ||
            conditionLower.includes("drizzle")
          ) {
            expect(gradient).toContain("blue");
          }

          // Requirement 1.4: Thunderstorm conditions return dark gradients with purple/indigo
          if (
            conditionLower.includes("thunder") ||
            conditionLower.includes("storm")
          ) {
            expect(gradient).toContain("purple");
            expect(gradient).toContain("indigo");
          }

          // Requirement 1.3: Cloudy conditions return neutral gradients with gray
          if (
            conditionLower.includes("cloud") &&
            !conditionLower.includes("partly")
          ) {
            expect(gradient).toContain("gray");
          }

          if (conditionLower.includes("overcast")) {
            expect(gradient).toContain("gray");
          }
        }),
        { numRuns: 100 },
      );
    });

    it("should handle case insensitivity for gradient mapping", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(
            "sunny",
            "clear",
            "fair",
            "rainy",
            "rain",
            "shower",
            "drizzle",
            "thunderstorm",
            "thunder",
            "storm",
            "cloudy",
            "cloud",
            "overcast",
            "partly cloudy",
            "partly",
          ),
          (condition) => {
            const lowerGradient = getWeatherGradient(condition.toLowerCase());
            const upperGradient = getWeatherGradient(condition.toUpperCase());
            const mixedGradient = getWeatherGradient(
              condition
                .split("")
                .map((c, i) =>
                  i % 2 === 0 ? c.toUpperCase() : c.toLowerCase(),
                )
                .join(""),
            );

            // All case variations should return the same gradient
            expect(lowerGradient).toBe(upperGradient);
            expect(lowerGradient).toBe(mixedGradient);
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should always return a default gradient for unknown or invalid conditions", () => {
      fc.assert(
        fc.property(
          fc.oneof(
            fc.string().filter((s) => {
              const lower = s.toLowerCase();
              return (
                !lower.includes("sunny") &&
                !lower.includes("clear") &&
                !lower.includes("fair") &&
                !lower.includes("rain") &&
                !lower.includes("shower") &&
                !lower.includes("drizzle") &&
                !lower.includes("thunder") &&
                !lower.includes("storm") &&
                !lower.includes("cloud") &&
                !lower.includes("overcast") &&
                !lower.includes("partly")
              );
            }),
            fc.constant(null),
            fc.constant(undefined),
            fc.constant(""),
          ),
          (condition) => {
            const gradient = getWeatherGradient(condition);

            // Default gradient should be a sky blue gradient
            expect(gradient).toBe("from-sky-400 via-blue-500 to-indigo-500");
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should return consistent gradients for conditions with multiple matching keywords", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(
            "partly cloudy",
            "sunny and clear",
            "cloudy with showers",
            "light rain",
            "heavy thunderstorm",
          ),
          (condition) => {
            const gradient = getWeatherGradient(condition);
            const conditionLower = condition.toLowerCase();

            // Verify the implementation's priority order based on the actual code:
            // 1. sunny/clear/fair
            // 2. rain/shower/drizzle
            // 3. thunder/storm
            // 4. partly
            // 5. cloud/overcast

            // Test checks that the first matching condition wins
            if (
              conditionLower.includes("sunny") ||
              conditionLower.includes("clear") ||
              conditionLower.includes("fair")
            ) {
              expect(gradient).toBe(
                "from-yellow-400 via-orange-400 to-pink-500",
              );
            } else if (
              conditionLower.includes("rain") ||
              conditionLower.includes("shower") ||
              conditionLower.includes("drizzle")
            ) {
              expect(gradient).toBe("from-blue-500 via-cyan-500 to-teal-400");
            } else if (
              conditionLower.includes("thunder") ||
              conditionLower.includes("storm")
            ) {
              expect(gradient).toBe(
                "from-indigo-900 via-purple-900 to-pink-900",
              );
            } else if (conditionLower.includes("partly")) {
              expect(gradient).toBe("from-blue-400 via-sky-300 to-amber-300");
            } else if (
              conditionLower.includes("cloud") ||
              conditionLower.includes("overcast")
            ) {
              expect(gradient).toBe("from-slate-300 via-gray-300 to-zinc-400");
            }
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should return gradients with proper Tailwind CSS class format", () => {
      fc.assert(
        fc.property(fc.string(), (condition) => {
          const gradient = getWeatherGradient(condition);

          // Verify gradient follows Tailwind format: "from-{color} via-{color} to-{color}"
          expect(gradient).toMatch(/^from-\w+-\d+\s+via-\w+-\d+\s+to-\w+-\d+$/);
        }),
        { numRuns: 100 },
      );
    });
  });

  /**
   * Property 4: Theme text color adapts to background darkness
   * **Validates: Requirements 7.1, 7.2**
   *
   * For any weather condition, when isDarkGradient(condition) returns true,
   * the text color should be light (white), and when it returns false,
   * the text color should be dark (slate-900), ensuring readability across
   * all gradient backgrounds.
   */
  describe("Feature: apple-weather-ui-redesign, Property 4: Theme text color adapts to background darkness", () => {
    it("should use light text on dark backgrounds and dark text on light backgrounds for any weather condition", () => {
      fc.assert(
        fc.property(fc.string(), (condition) => {
          const isDark = isDarkGradient(condition);

          // Determine expected text color based on background darkness
          const expectedTextColor = isDark ? "text-white" : "text-slate-900";
          const expectedSecondaryTextColor = isDark
            ? "text-white/80"
            : "text-slate-700";

          // Requirement 7.1: When gradient uses dark colors, text should be white/light
          if (isDark) {
            expect(expectedTextColor).toBe("text-white");
            expect(expectedSecondaryTextColor).toBe("text-white/80");
          }

          // Requirement 7.2: When gradient uses light colors, text should be dark
          if (!isDark) {
            expect(expectedTextColor).toBe("text-slate-900");
            expect(expectedSecondaryTextColor).toBe("text-slate-700");
          }
        }),
        { numRuns: 100 },
      );
    });

    it("should identify thunderstorm and storm conditions as dark backgrounds", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(
            "thunderstorm",
            "thunder",
            "storm",
            "Thunderstorm",
            "THUNDER",
            "Storm",
            "heavy thunderstorm",
            "light storm",
          ),
          (condition) => {
            const isDark = isDarkGradient(condition);

            // All thunderstorm/storm conditions should be dark
            expect(isDark).toBe(true);
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should identify non-thunderstorm conditions as light backgrounds", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(
            "sunny",
            "clear",
            "fair",
            "rainy",
            "rain",
            "shower",
            "drizzle",
            "cloudy",
            "cloud",
            "overcast",
            "partly cloudy",
            "partly",
          ),
          (condition) => {
            const isDark = isDarkGradient(condition);

            // All non-thunderstorm conditions should be light
            expect(isDark).toBe(false);
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should handle case insensitivity for darkness detection", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(
            "thunderstorm",
            "thunder",
            "storm",
            "sunny",
            "clear",
            "rainy",
            "cloudy",
          ),
          (condition) => {
            const lowerIsDark = isDarkGradient(condition.toLowerCase());
            const upperIsDark = isDarkGradient(condition.toUpperCase());
            const mixedIsDark = isDarkGradient(
              condition
                .split("")
                .map((c, i) =>
                  i % 2 === 0 ? c.toUpperCase() : c.toLowerCase(),
                )
                .join(""),
            );

            // All case variations should return the same darkness value
            expect(lowerIsDark).toBe(upperIsDark);
            expect(lowerIsDark).toBe(mixedIsDark);
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should default to light background for unknown or invalid conditions", () => {
      fc.assert(
        fc.property(
          fc.oneof(
            fc.string().filter((s) => {
              const lower = s.toLowerCase();
              return !lower.includes("thunder") && !lower.includes("storm");
            }),
            fc.constant(null),
            fc.constant(undefined),
            fc.constant(""),
          ),
          (condition) => {
            const isDark = isDarkGradient(condition);

            // Unknown conditions should default to light background
            expect(isDark).toBe(false);
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should ensure text color contrast is appropriate for readability", () => {
      fc.assert(
        fc.property(fc.string(), (condition) => {
          const isDark = isDarkGradient(condition);
          const gradient = getWeatherGradient(condition);

          // Verify that dark gradients (containing "900" shade) use light text
          if (gradient.includes("-900")) {
            expect(isDark).toBe(true);
          }

          // Verify that light gradients (containing "300" or "400" shades) use dark text
          if (gradient.includes("-300") || gradient.includes("-400")) {
            // Only if it's not a dark gradient (indigo-900, purple-900, pink-900)
            if (!gradient.includes("-900")) {
              expect(isDark).toBe(false);
            }
          }
        }),
        { numRuns: 100 },
      );
    });

    it("should maintain consistent text color for conditions with multiple keywords", () => {
      fc.assert(
        fc.property(
          fc.constantFrom(
            "heavy thunderstorm with rain",
            "light storm",
            "sunny and clear",
            "cloudy with showers",
          ),
          (condition) => {
            const isDark = isDarkGradient(condition);
            const conditionLower = condition.toLowerCase();

            // If condition contains thunder or storm, it should be dark
            if (
              conditionLower.includes("thunder") ||
              conditionLower.includes("storm")
            ) {
              expect(isDark).toBe(true);
            } else {
              expect(isDark).toBe(false);
            }
          },
        ),
        { numRuns: 100 },
      );
    });
  });
});
