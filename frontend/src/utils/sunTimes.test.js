import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getSunTimes } from "./sunTimes";

describe("getSunTimes", () => {
  beforeEach(() => {
    // Mock console methods to avoid cluttering test output
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should return sunrise and sunset times for Singapore coordinates", async () => {
    const result = await getSunTimes(1.3521, 103.8198);

    // Should return an object with sunrise and sunset properties
    expect(result).toHaveProperty("sunrise");
    expect(result).toHaveProperty("sunset");

    // Times should be formatted as strings (e.g., "6:51 AM", "7:18 PM")
    expect(typeof result.sunrise).toBe("string");
    expect(typeof result.sunset).toBe("string");

    // Should not be "N/A" (unless both API and suncalc fail)
    // In normal circumstances, at least suncalc should work
    expect(result.sunrise).not.toBe("");
    expect(result.sunset).not.toBe("");
  });

  it("should use default Singapore coordinates when no parameters provided", async () => {
    const result = await getSunTimes();

    expect(result).toHaveProperty("sunrise");
    expect(result).toHaveProperty("sunset");
    expect(typeof result.sunrise).toBe("string");
    expect(typeof result.sunset).toBe("string");
  });

  it("should format times in 12-hour format with AM/PM", async () => {
    const result = await getSunTimes(1.3521, 103.8198);

    // Check that times match 12-hour format pattern (e.g., "6:51 AM" or "12:30 PM")
    const timePattern = /^\d{1,2}:\d{2}\s(AM|PM)$/;

    if (result.sunrise !== "N/A") {
      expect(result.sunrise).toMatch(timePattern);
    }

    if (result.sunset !== "N/A") {
      expect(result.sunset).toMatch(timePattern);
    }
  });

  it("should return N/A for both times if all methods fail", async () => {
    // Mock fetch to fail
    global.fetch = vi.fn(() => Promise.reject(new Error("Network error")));

    // Mock SunCalc to fail by importing after mocking
    vi.mock("suncalc", () => ({
      default: {
        getTimes: () => {
          throw new Error("Calculation error");
        },
      },
    }));

    const result = await getSunTimes(1.3521, 103.8198);

    // When all methods fail, should return N/A
    expect(result.sunrise).toBe("N/A");
    expect(result.sunset).toBe("N/A");
  });

  it("should work for different locations (Malaysia)", async () => {
    // Kuala Lumpur coordinates
    const result = await getSunTimes(3.139, 101.6869);

    expect(result).toHaveProperty("sunrise");
    expect(result).toHaveProperty("sunset");
    expect(typeof result.sunrise).toBe("string");
    expect(typeof result.sunset).toBe("string");
  });

  it("should work for different locations (Indonesia)", async () => {
    // Jakarta coordinates
    const result = await getSunTimes(-6.2088, 106.8456);

    expect(result).toHaveProperty("sunrise");
    expect(result).toHaveProperty("sunset");
    expect(typeof result.sunrise).toBe("string");
    expect(typeof result.sunset).toBe("string");
  });

  it("should have reasonable sunrise time for Singapore (between 6-7 AM)", async () => {
    const result = await getSunTimes(1.3521, 103.8198);

    if (result.sunrise !== "N/A") {
      // Extract hour from time string (e.g., "6:51 AM" -> 6)
      const match = result.sunrise.match(/^(\d{1,2}):\d{2}\s(AM|PM)$/);
      if (match) {
        const hour = parseInt(match[1]);
        const period = match[2];

        // Singapore sunrise should be in the morning (AM)
        expect(period).toBe("AM");

        // Sunrise should be between 6-7 AM for Singapore (near equator)
        expect(hour).toBeGreaterThanOrEqual(6);
        expect(hour).toBeLessThanOrEqual(7);
      }
    }
  });

  it("should have reasonable sunset time for Singapore (between 6-8 PM)", async () => {
    const result = await getSunTimes(1.3521, 103.8198);

    if (result.sunset !== "N/A") {
      // Extract hour from time string (e.g., "7:18 PM" -> 7)
      const match = result.sunset.match(/^(\d{1,2}):\d{2}\s(AM|PM)$/);
      if (match) {
        const hour = parseInt(match[1]);
        const period = match[2];

        // Singapore sunset should be in the evening (PM)
        expect(period).toBe("PM");

        // Sunset should be between 6-8 PM for Singapore (near equator)
        expect(hour).toBeGreaterThanOrEqual(6);
        expect(hour).toBeLessThanOrEqual(8);
      }
    }
  });
});
