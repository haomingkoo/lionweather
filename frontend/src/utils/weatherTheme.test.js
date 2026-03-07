import { describe, it, expect } from "vitest";
import {
  getWeatherGradient,
  getWeatherIcon,
  isDarkGradient,
  getMockTemperature,
} from "./weatherTheme";

describe("weatherTheme.js utility functions", () => {
  describe("getWeatherGradient", () => {
    describe("Sunny/Clear conditions (Requirements 1.1)", () => {
      it('returns warm gradient for "sunny"', () => {
        const gradient = getWeatherGradient("sunny");
        expect(gradient).toBe("from-yellow-400 via-orange-400 to-pink-500");
        expect(gradient).toContain("yellow");
        expect(gradient).toContain("orange");
      });

      it('returns warm gradient for "clear"', () => {
        const gradient = getWeatherGradient("clear");
        expect(gradient).toBe("from-yellow-400 via-orange-400 to-pink-500");
      });

      it('returns warm gradient for "fair"', () => {
        const gradient = getWeatherGradient("fair");
        expect(gradient).toBe("from-yellow-400 via-orange-400 to-pink-500");
      });

      it("handles case insensitivity for sunny conditions", () => {
        expect(getWeatherGradient("SUNNY")).toBe(
          "from-yellow-400 via-orange-400 to-pink-500",
        );
        expect(getWeatherGradient("Sunny")).toBe(
          "from-yellow-400 via-orange-400 to-pink-500",
        );
        expect(getWeatherGradient("SuNnY")).toBe(
          "from-yellow-400 via-orange-400 to-pink-500",
        );
      });
    });

    describe("Rainy conditions (Requirements 1.2)", () => {
      it('returns cool blue gradient for "rainy"', () => {
        const gradient = getWeatherGradient("rainy");
        expect(gradient).toBe("from-blue-500 via-cyan-500 to-teal-400");
        expect(gradient).toContain("blue");
        expect(gradient).toContain("cyan");
      });

      it('returns cool blue gradient for "rain"', () => {
        const gradient = getWeatherGradient("rain");
        expect(gradient).toBe("from-blue-500 via-cyan-500 to-teal-400");
      });

      it('returns cool blue gradient for "shower"', () => {
        const gradient = getWeatherGradient("shower");
        expect(gradient).toBe("from-blue-500 via-cyan-500 to-teal-400");
      });

      it('returns cool blue gradient for "drizzle"', () => {
        const gradient = getWeatherGradient("drizzle");
        expect(gradient).toBe("from-blue-500 via-cyan-500 to-teal-400");
      });

      it("handles case insensitivity for rainy conditions", () => {
        expect(getWeatherGradient("RAINY")).toBe(
          "from-blue-500 via-cyan-500 to-teal-400",
        );
        expect(getWeatherGradient("SHOWER")).toBe(
          "from-blue-500 via-cyan-500 to-teal-400",
        );
      });
    });

    describe("Cloudy conditions (Requirements 1.3)", () => {
      it('returns neutral gray gradient for "cloudy"', () => {
        const gradient = getWeatherGradient("cloudy");
        expect(gradient).toBe("from-slate-300 via-gray-300 to-zinc-400");
        expect(gradient).toContain("slate");
        expect(gradient).toContain("gray");
      });

      it('returns neutral gray gradient for "cloud"', () => {
        const gradient = getWeatherGradient("cloud");
        expect(gradient).toBe("from-slate-300 via-gray-300 to-zinc-400");
      });

      it('returns neutral gray gradient for "overcast"', () => {
        const gradient = getWeatherGradient("overcast");
        expect(gradient).toBe("from-slate-300 via-gray-300 to-zinc-400");
      });

      it("handles case insensitivity for cloudy conditions", () => {
        expect(getWeatherGradient("CLOUDY")).toBe(
          "from-slate-300 via-gray-300 to-zinc-400",
        );
        expect(getWeatherGradient("OVERCAST")).toBe(
          "from-slate-300 via-gray-300 to-zinc-400",
        );
      });
    });

    describe("Thunderstorm conditions (Requirements 1.4)", () => {
      it('returns dark gradient for "thunderstorm"', () => {
        const gradient = getWeatherGradient("thunderstorm");
        expect(gradient).toBe("from-indigo-900 via-purple-900 to-pink-900");
        expect(gradient).toContain("indigo-900");
        expect(gradient).toContain("purple-900");
      });

      it('returns dark gradient for "thunder"', () => {
        const gradient = getWeatherGradient("thunder");
        expect(gradient).toBe("from-indigo-900 via-purple-900 to-pink-900");
      });

      it('returns dark gradient for "storm"', () => {
        const gradient = getWeatherGradient("storm");
        expect(gradient).toBe("from-indigo-900 via-purple-900 to-pink-900");
      });

      it("handles case insensitivity for thunderstorm conditions", () => {
        expect(getWeatherGradient("THUNDERSTORM")).toBe(
          "from-indigo-900 via-purple-900 to-pink-900",
        );
        expect(getWeatherGradient("STORM")).toBe(
          "from-indigo-900 via-purple-900 to-pink-900",
        );
      });
    });

    describe("Partly cloudy conditions", () => {
      it('returns mixed gradient for "partly cloudy"', () => {
        const gradient = getWeatherGradient("partly cloudy");
        expect(gradient).toBe("from-blue-400 via-sky-300 to-amber-300");
      });

      it('returns mixed gradient for "partly"', () => {
        const gradient = getWeatherGradient("partly");
        expect(gradient).toBe("from-blue-400 via-sky-300 to-amber-300");
      });
    });

    describe("Edge cases", () => {
      it("returns default gradient for unknown condition", () => {
        const gradient = getWeatherGradient("unknown");
        expect(gradient).toBe("from-sky-400 via-blue-500 to-indigo-500");
      });

      it("handles null condition", () => {
        const gradient = getWeatherGradient(null);
        expect(gradient).toBe("from-sky-400 via-blue-500 to-indigo-500");
      });

      it("handles undefined condition", () => {
        const gradient = getWeatherGradient(undefined);
        expect(gradient).toBe("from-sky-400 via-blue-500 to-indigo-500");
      });

      it("handles empty string", () => {
        const gradient = getWeatherGradient("");
        expect(gradient).toBe("from-sky-400 via-blue-500 to-indigo-500");
      });
    });
  });

  describe("getWeatherIcon", () => {
    describe("Sunny/Clear conditions (Requirements 3.1)", () => {
      it('returns Sun icon for "sunny"', () => {
        expect(getWeatherIcon("sunny")).toBe("Sun");
      });

      it('returns Sun icon for "clear"', () => {
        expect(getWeatherIcon("clear")).toBe("Sun");
      });

      it('returns Sun icon for "fair"', () => {
        expect(getWeatherIcon("fair")).toBe("Sun");
      });

      it("handles case insensitivity", () => {
        expect(getWeatherIcon("SUNNY")).toBe("Sun");
        expect(getWeatherIcon("CLEAR")).toBe("Sun");
      });
    });

    describe("Rainy conditions (Requirements 3.3)", () => {
      it('returns CloudRain icon for "rainy"', () => {
        expect(getWeatherIcon("rainy")).toBe("CloudRain");
      });

      it('returns CloudRain icon for "rain"', () => {
        expect(getWeatherIcon("rain")).toBe("CloudRain");
      });

      it('returns CloudRain icon for "shower"', () => {
        expect(getWeatherIcon("shower")).toBe("CloudRain");
      });

      it('returns CloudRain icon for "drizzle"', () => {
        expect(getWeatherIcon("drizzle")).toBe("CloudRain");
      });

      it("handles case insensitivity", () => {
        expect(getWeatherIcon("RAINY")).toBe("CloudRain");
        expect(getWeatherIcon("SHOWER")).toBe("CloudRain");
      });
    });

    describe("Thunderstorm conditions (Requirements 3.4)", () => {
      it('returns CloudLightning icon for "thunderstorm"', () => {
        expect(getWeatherIcon("thunderstorm")).toBe("CloudLightning");
      });

      it('returns CloudLightning icon for "thunder"', () => {
        expect(getWeatherIcon("thunder")).toBe("CloudLightning");
      });

      it('returns CloudLightning icon for "storm"', () => {
        expect(getWeatherIcon("storm")).toBe("CloudLightning");
      });

      it("handles case insensitivity", () => {
        expect(getWeatherIcon("THUNDERSTORM")).toBe("CloudLightning");
        expect(getWeatherIcon("STORM")).toBe("CloudLightning");
      });
    });

    describe("Cloudy conditions (Requirements 3.2)", () => {
      it('returns Cloud icon for "cloudy"', () => {
        expect(getWeatherIcon("cloudy")).toBe("Cloud");
      });

      it('returns Cloud icon for "cloud"', () => {
        expect(getWeatherIcon("cloud")).toBe("Cloud");
      });

      it('returns Cloudy icon for "overcast"', () => {
        expect(getWeatherIcon("overcast")).toBe("Cloudy");
      });

      it("handles case insensitivity", () => {
        expect(getWeatherIcon("CLOUDY")).toBe("Cloud");
        expect(getWeatherIcon("OVERCAST")).toBe("Cloudy");
      });
    });

    describe("Partly cloudy conditions", () => {
      it('returns CloudSun icon for "partly cloudy"', () => {
        expect(getWeatherIcon("partly cloudy")).toBe("CloudSun");
      });

      it('returns CloudSun icon for "partly"', () => {
        expect(getWeatherIcon("partly")).toBe("CloudSun");
      });
    });

    describe("Edge cases", () => {
      it("returns default CloudSun icon for unknown condition", () => {
        expect(getWeatherIcon("unknown")).toBe("CloudSun");
      });

      it("handles null condition", () => {
        expect(getWeatherIcon(null)).toBe("CloudSun");
      });

      it("handles undefined condition", () => {
        expect(getWeatherIcon(undefined)).toBe("CloudSun");
      });

      it("handles empty string", () => {
        expect(getWeatherIcon("")).toBe("CloudSun");
      });
    });
  });

  describe("isDarkGradient", () => {
    describe("Text color adaptation (Requirements 7.1, 7.2)", () => {
      it("returns true for thunderstorm conditions", () => {
        expect(isDarkGradient("thunderstorm")).toBe(true);
        expect(isDarkGradient("thunder")).toBe(true);
        expect(isDarkGradient("storm")).toBe(true);
      });

      it("returns false for sunny conditions", () => {
        expect(isDarkGradient("sunny")).toBe(false);
        expect(isDarkGradient("clear")).toBe(false);
        expect(isDarkGradient("fair")).toBe(false);
      });

      it("returns false for rainy conditions", () => {
        expect(isDarkGradient("rainy")).toBe(false);
        expect(isDarkGradient("rain")).toBe(false);
        expect(isDarkGradient("shower")).toBe(false);
      });

      it("returns false for cloudy conditions", () => {
        expect(isDarkGradient("cloudy")).toBe(false);
        expect(isDarkGradient("cloud")).toBe(false);
        expect(isDarkGradient("overcast")).toBe(false);
      });

      it("returns false for partly cloudy conditions", () => {
        expect(isDarkGradient("partly cloudy")).toBe(false);
      });

      it("handles case insensitivity", () => {
        expect(isDarkGradient("THUNDERSTORM")).toBe(true);
        expect(isDarkGradient("STORM")).toBe(true);
        expect(isDarkGradient("SUNNY")).toBe(false);
      });

      it("returns false for unknown conditions", () => {
        expect(isDarkGradient("unknown")).toBe(false);
      });

      it("handles null condition", () => {
        expect(isDarkGradient(null)).toBe(false);
      });

      it("handles undefined condition", () => {
        expect(isDarkGradient(undefined)).toBe(false);
      });

      it("handles empty string", () => {
        expect(isDarkGradient("")).toBe(false);
      });
    });
  });

  describe("getMockTemperature", () => {
    it("returns appropriate temperature for sunny conditions", () => {
      expect(getMockTemperature("sunny")).toBe("32");
      expect(getMockTemperature("clear")).toBe("32");
    });

    it("returns appropriate temperature for rainy conditions", () => {
      expect(getMockTemperature("rainy")).toBe("26");
      expect(getMockTemperature("rain")).toBe("26");
      expect(getMockTemperature("shower")).toBe("26");
    });

    it("returns appropriate temperature for thunderstorm conditions", () => {
      expect(getMockTemperature("thunderstorm")).toBe("24");
      expect(getMockTemperature("thunder")).toBe("24");
      expect(getMockTemperature("storm")).toBe("24");
    });

    it("returns appropriate temperature for cloudy conditions", () => {
      expect(getMockTemperature("cloudy")).toBe("28");
      expect(getMockTemperature("cloud")).toBe("28");
    });

    it("returns default temperature for unknown conditions", () => {
      expect(getMockTemperature("unknown")).toBe("29");
    });

    it("handles case insensitivity", () => {
      expect(getMockTemperature("SUNNY")).toBe("32");
      expect(getMockTemperature("RAINY")).toBe("26");
    });

    it("handles null condition", () => {
      expect(getMockTemperature(null)).toBe("29");
    });

    it("handles undefined condition", () => {
      expect(getMockTemperature(undefined)).toBe("29");
    });
  });

  describe("Integration tests - Consistency across functions", () => {
    it("sunny conditions have consistent mappings", () => {
      const condition = "sunny";
      expect(getWeatherGradient(condition)).toContain("yellow");
      expect(getWeatherIcon(condition)).toBe("Sun");
      expect(isDarkGradient(condition)).toBe(false);
      expect(getMockTemperature(condition)).toBe("32");
    });

    it("rainy conditions have consistent mappings", () => {
      const condition = "rainy";
      expect(getWeatherGradient(condition)).toContain("blue");
      expect(getWeatherIcon(condition)).toBe("CloudRain");
      expect(isDarkGradient(condition)).toBe(false);
      expect(getMockTemperature(condition)).toBe("26");
    });

    it("thunderstorm conditions have consistent mappings", () => {
      const condition = "thunderstorm";
      expect(getWeatherGradient(condition)).toContain("indigo-900");
      expect(getWeatherIcon(condition)).toBe("CloudLightning");
      expect(isDarkGradient(condition)).toBe(true);
      expect(getMockTemperature(condition)).toBe("24");
    });

    it("cloudy conditions have consistent mappings", () => {
      const condition = "cloudy";
      expect(getWeatherGradient(condition)).toContain("gray");
      expect(getWeatherIcon(condition)).toBe("Cloud");
      expect(isDarkGradient(condition)).toBe(false);
      expect(getMockTemperature(condition)).toBe("28");
    });
  });

  describe("Dark mode gradient support (Requirements 2.6)", () => {
    describe("Sunny/Clear dark mode gradients", () => {
      it('returns darker warm gradient for "sunny" in dark mode', () => {
        const gradient = getWeatherGradient("sunny", true);
        expect(gradient).toBe("from-yellow-600 via-orange-600 to-pink-700");
        expect(gradient).toContain("yellow-600");
        expect(gradient).toContain("orange-600");
      });

      it('returns darker warm gradient for "clear" in dark mode', () => {
        const gradient = getWeatherGradient("clear", true);
        expect(gradient).toBe("from-yellow-600 via-orange-600 to-pink-700");
      });

      it("maintains visual hierarchy between light and dark sunny gradients", () => {
        const lightGradient = getWeatherGradient("sunny", false);
        const darkGradient = getWeatherGradient("sunny", true);
        expect(lightGradient).toContain("400");
        expect(darkGradient).toContain("600");
      });
    });

    describe("Rainy dark mode gradients", () => {
      it('returns darker blue gradient for "rainy" in dark mode', () => {
        const gradient = getWeatherGradient("rainy", true);
        expect(gradient).toBe("from-blue-700 via-cyan-700 to-teal-600");
        expect(gradient).toContain("blue-700");
        expect(gradient).toContain("cyan-700");
      });

      it('returns darker blue gradient for "rain" in dark mode', () => {
        const gradient = getWeatherGradient("rain", true);
        expect(gradient).toBe("from-blue-700 via-cyan-700 to-teal-600");
      });

      it("maintains visual hierarchy between light and dark rainy gradients", () => {
        const lightGradient = getWeatherGradient("rainy", false);
        const darkGradient = getWeatherGradient("rainy", true);
        expect(lightGradient).toContain("500");
        expect(darkGradient).toContain("700");
      });
    });

    describe("Cloudy dark mode gradients", () => {
      it('returns darker gray gradient for "cloudy" in dark mode', () => {
        const gradient = getWeatherGradient("cloudy", true);
        expect(gradient).toBe("from-slate-600 via-gray-600 to-zinc-700");
        expect(gradient).toContain("slate-600");
        expect(gradient).toContain("gray-600");
      });

      it('returns darker gray gradient for "overcast" in dark mode', () => {
        const gradient = getWeatherGradient("overcast", true);
        expect(gradient).toBe("from-slate-600 via-gray-600 to-zinc-700");
      });

      it("maintains visual hierarchy between light and dark cloudy gradients", () => {
        const lightGradient = getWeatherGradient("cloudy", false);
        const darkGradient = getWeatherGradient("cloudy", true);
        expect(lightGradient).toContain("300");
        expect(darkGradient).toContain("600");
      });
    });

    describe("Thunderstorm dark mode gradients", () => {
      it('returns even darker gradient for "thunderstorm" in dark mode', () => {
        const gradient = getWeatherGradient("thunderstorm", true);
        expect(gradient).toBe("from-indigo-950 via-purple-950 to-pink-950");
        expect(gradient).toContain("indigo-950");
        expect(gradient).toContain("purple-950");
      });

      it('returns even darker gradient for "storm" in dark mode', () => {
        const gradient = getWeatherGradient("storm", true);
        expect(gradient).toBe("from-indigo-950 via-purple-950 to-pink-950");
      });

      it("maintains visual hierarchy between light and dark stormy gradients", () => {
        const lightGradient = getWeatherGradient("thunderstorm", false);
        const darkGradient = getWeatherGradient("thunderstorm", true);
        expect(lightGradient).toContain("900");
        expect(darkGradient).toContain("950");
      });
    });

    describe("Partly cloudy dark mode gradients", () => {
      it('returns darker mixed gradient for "partly cloudy" in dark mode', () => {
        const gradient = getWeatherGradient("partly cloudy", true);
        expect(gradient).toBe("from-blue-600 via-sky-600 to-amber-600");
      });

      it("maintains visual hierarchy between light and dark partly cloudy gradients", () => {
        const lightGradient = getWeatherGradient("partly", false);
        const darkGradient = getWeatherGradient("partly", true);
        expect(lightGradient).toContain("300");
        expect(darkGradient).toContain("600");
      });
    });

    describe("Default dark mode gradient", () => {
      it("returns darker default gradient for unknown condition in dark mode", () => {
        const gradient = getWeatherGradient("unknown", true);
        expect(gradient).toBe("from-sky-600 via-blue-700 to-indigo-700");
      });

      it("maintains visual hierarchy between light and dark default gradients", () => {
        const lightGradient = getWeatherGradient("unknown", false);
        const darkGradient = getWeatherGradient("unknown", true);
        expect(lightGradient).toContain("400");
        expect(darkGradient).toContain("600");
      });
    });

    describe("Dark mode parameter defaults", () => {
      it("defaults to light mode when isDark parameter is omitted", () => {
        const gradientWithoutParam = getWeatherGradient("sunny");
        const gradientWithFalse = getWeatherGradient("sunny", false);
        expect(gradientWithoutParam).toBe(gradientWithFalse);
      });

      it("handles null isDark parameter as false", () => {
        const gradient = getWeatherGradient("sunny", null);
        expect(gradient).toBe("from-yellow-400 via-orange-400 to-pink-500");
      });

      it("handles undefined isDark parameter as false", () => {
        const gradient = getWeatherGradient("sunny", undefined);
        expect(gradient).toBe("from-yellow-400 via-orange-400 to-pink-500");
      });
    });

    describe("All weather conditions have dark mode variants", () => {
      const conditions = [
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
        "partly cloudy",
        "partly",
        "cloudy",
        "cloud",
        "overcast",
        "unknown",
      ];

      conditions.forEach((condition) => {
        it(`returns valid gradient for "${condition}" in both light and dark modes`, () => {
          const lightGradient = getWeatherGradient(condition, false);
          const darkGradient = getWeatherGradient(condition, true);

          // Both should be valid Tailwind gradient classes
          expect(lightGradient).toMatch(
            /^from-\w+-\d+\s+via-\w+-\d+\s+to-\w+-\d+$/,
          );
          expect(darkGradient).toMatch(
            /^from-\w+-\d+\s+via-\w+-\d+\s+to-\w+-\d+$/,
          );

          // Light and dark should be different
          expect(lightGradient).not.toBe(darkGradient);
        });
      });
    });
  });
});
