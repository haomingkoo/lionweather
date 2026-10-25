import { describe, it, expect } from "vitest";
import { feelsLike, generateCommentary, isNightAt, parseClock } from "./currentConditions";

const sunTimes = { sunrise: "6:47 AM", sunset: "6:52 PM" };
const at = (h, m = 0) => new Date(2026, 9, 26, h, m);

describe("parseClock", () => {
  it("parses 12-hour clock strings", () => {
    expect(parseClock("6:47 AM")).toBe(6 * 60 + 47);
    expect(parseClock("12:05 AM")).toBe(5);
    expect(parseClock("6:52 PM")).toBe(18 * 60 + 52);
    expect(parseClock("N/A")).toBeNull();
  });
});

describe("isNightAt", () => {
  it("is night after sunset and before sunrise", () => {
    expect(isNightAt(at(0, 39), sunTimes)).toBe(true);
    expect(isNightAt(at(19, 30), sunTimes)).toBe(true);
    expect(isNightAt(at(12, 0), sunTimes)).toBe(false);
  });

  it("falls back to a Singapore day window without sun times", () => {
    expect(isNightAt(at(0, 39), {})).toBe(true);
    expect(isNightAt(at(12, 0), {})).toBe(false);
  });
});

describe("feelsLike", () => {
  it("returns null instead of inventing humidity", () => {
    expect(feelsLike(31.6, null)).toBeNull();
    expect(feelsLike(31.6, undefined)).toBeNull();
    expect(feelsLike(null, 80)).toBeNull();
  });

  it("equals the air temperature below 27°C", () => {
    expect(feelsLike(25.2, 95.5)).toBe(25);
  });

  it("is deterministic for the same reading", () => {
    expect(feelsLike(31.6, 67.9)).toBe(feelsLike(31.6, 67.9));
    expect(feelsLike(31.6, 67.9)).toBeGreaterThan(32);
  });
});

describe("generateCommentary", () => {
  it("never mentions sunshine at night", () => {
    for (const condition of ["Sunny", "Clear", "Fair (Night)", "Fair"]) {
      const lines = generateCommentary({ condition, temperature: 25, humidity: 96, sunTimes, now: at(0, 39) });
      expect(lines[0]).toBe("Clear tonight.");
      expect(lines.join(" ")).not.toMatch(/sun(shine|ny)/i);
    }
  });

  it("uses daytime wording during the day", () => {
    const lines = generateCommentary({ condition: "Sunny", temperature: 31, sunTimes, now: at(13) });
    expect(lines[0]).toBe("Clear skies and plenty of sunshine.");
  });

  it("describes cloud at night without sunshine", () => {
    const lines = generateCommentary({ condition: "Overcast", sunTimes, now: at(23) });
    expect(lines[0]).toBe("Cloudy tonight.");
  });

  it("skips UV advice at night", () => {
    const lines = generateCommentary({ condition: "Clear", uv_index: 9, sunTimes, now: at(22) });
    expect(lines.join(" ")).not.toMatch(/UV/);
  });

  it("uses no em dashes", () => {
    const lines = generateCommentary({ condition: "Thunderstorm", temperature: 36, humidity: 90, uv_index: 12, sunTimes, now: at(12) });
    expect(lines.join(" ")).not.toMatch(/—/);
  });
});
