import { describe, it, expect } from "vitest";
import { compassPoint, feelsLike, formatClock, generateCommentary, isNightAt, parseClock, rainOutlook, readingSource, uvBand } from "./currentConditions";

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


describe("reading helpers", () => {
  it("names the source in plain words", () => {
    expect(readingSource("Cached (api-open.data.gov.sg)")).toBe("NEA");
    expect(readingSource("Open-Meteo")).toBe("Open-Meteo");
    expect(readingSource("")).toBeNull();
  });

  it("formats the reading time in Singapore time", () => {
    expect(formatClock("2026-10-26T02:17:00+08:00")).toBe("2:17 am");
    expect(formatClock("not a date")).toBeNull();
  });

  it("gives compass points and UV bands", () => {
    expect(compassPoint(275)).toBe("W");
    expect(compassPoint(null)).toBeNull();
    expect(uvBand(0)).toBe("Low");
    expect(uvBand(9)).toBe("Very high");
  });
});

describe("rainOutlook", () => {
  const at = (h) => new Date(`2026-10-26T${String(h).padStart(2, "0")}:00:00+08:00`);

  it("says when rain becomes likely", () => {
    expect(rainOutlook([
      { time: at(2), rainChance: 20 },
      { time: at(3), rainChance: 40 },
      { time: at(4), rainChance: 65 },
    ])).toBe("Rain likely from about 4 am (65% chance).");
  });

  it("says rain is likely now when the first hour is wet", () => {
    expect(rainOutlook([{ time: at(2), rainChance: 70 }])).toBe("Rain likely now (70% chance).");
  });

  it("says rain is unlikely when no hour crosses the threshold", () => {
    expect(rainOutlook([{ time: at(2), rainChance: 10 }, { time: at(3), rainChance: 5 }])).toBe("Rain unlikely in the next 2 hours.");
  });

  it("says nothing without data", () => {
    expect(rainOutlook([])).toBeNull();
    expect(rainOutlook([{ time: at(2), rainChance: null }])).toBeNull();
  });
});

describe("commentary for fog and haze", () => {
  it("matches the condition instead of calling it cloudy", () => {
    expect(generateCommentary({ condition: "Foggy", sunTimes, now: at(2) })[0]).toBe("Foggy tonight. Visibility is low.");
    expect(generateCommentary({ condition: "Hazy", sunTimes, now: at(12) })[0]).toBe("Hazy. Check the air quality below.");
    expect(generateCommentary({ condition: "Overcast", sunTimes, now: at(12) })[0]).toBe("Overcast, with little sunshine.");
  });
});
