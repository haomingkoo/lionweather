import { describe, expect, it } from "vitest";
import { climateBullets, pctChange } from "./climateSummary";

describe("pctChange", () => {
  it("returns the change for a real baseline", () => {
    expect(pctChange(2890, 1666)).toBe(73);
  });

  it("drops changes computed from a near-zero baseline", () => {
    // The old tab compared 198,028 with a 174.8 stub year: "113189% swing".
    expect(pctChange(198028.4, 174.8)).toBeNull();
    expect(pctChange(10, 0)).toBeNull();
  });
});

const ct = {
  years_covered: [2016, 2017, 2018],
  annual: {
    2016: { rainfall: { total_mm: 3.2, thundery_station_hours: 0 } },
    2017: { rainfall: { total_mm: 2396.2, thundery_station_hours: 300 }, temperature: { mean_c: 27.9 } },
    2018: { rainfall: { total_mm: 2233.6, thundery_station_hours: 280 }, temperature: { mean_c: 28.1 } },
  },
  long_term_trends: {},
  all_time_records: {
    wettest_station_hour: { value_mm: 141.4, date: "2022-08-21" },
    wettest_island_hour: { value_mm: 35.1, date: "2022-10-05" },
  },
};

describe("climateBullets", () => {
  const text = climateBullets(ct).join("\n");

  it("never prints a four-digit-plus percentage", () => {
    expect(text).not.toMatch(/\d{4,}%/);
  });

  it("shows the wettest hour for one gauge, not a sum across gauges", () => {
    expect(text).toContain("single gauge was 141.4 mm");
    expect(text).not.toContain("2103.76");
  });

  it("labels rainfall as an average across gauges", () => {
    expect(text).toContain("2,396 mm averaged across rain gauges");
  });

  it("guards a stub year that slips through", () => {
    expect(text).toMatch(/2016 was the driest, with 3 mm\./);
  });
});
