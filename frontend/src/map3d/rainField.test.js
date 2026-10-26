import { describe, expect, it } from "vitest";
import { bandFor, fieldPixels, gaugesAt, rainField, toRate } from "./rainField";

const AMK = { lat: 1.37, lng: 103.85 };
const CHANGI = { lat: 1.36, lng: 103.99 };

describe("rain field from gauges", () => {
  it("is dry everywhere when every gauge is dry", () => {
    const f = rainField([{ ...AMK, rate: 0 }, { ...CHANGI, rate: 0 }]);
    expect(f.max).toBe(0);
    expect(fieldPixels(f).some((v) => v > 0)).toBe(false);
  });

  it("peaks at a wet gauge and falls off smoothly towards dry ones", () => {
    const f = rainField([{ ...AMK, rate: 24 }, { ...CHANGI, rate: 0 }], { cols: 92, rows: 56 });
    const at = (lat, lng) => {
      const [w, s, e, n] = f.bounds;
      const c = Math.floor(((lng - w) / (e - w)) * f.cols);
      const r = Math.floor(((n - lat) / (n - s)) * f.rows);
      return f.data[r * f.cols + c];
    };
    const near = at(1.37, 103.851);
    const mid = at(1.365, 103.92);
    const far = at(1.36, 103.985);
    expect(near).toBeGreaterThan(18);
    expect(mid).toBeLessThan(near);
    expect(far).toBeLessThan(mid);
    expect(f.max).toBeLessThanOrEqual(24.0001);
  });

  it("does not invent rain far beyond the gauge network", () => {
    const f = rainField([{ ...AMK, rate: 30 }], { bounds: [103.0, 0.8, 104.6, 1.9], cols: 80, rows: 55 });
    expect(f.data[0]).toBeLessThan(0.01); // far north-west corner, about 70 km away
  });

  it("skips missing readings and reads 5-minute totals as hourly rates", () => {
    expect(toRate(0.5)).toBe(6);
    expect(toRate(null)).toBeNull();
    const data = { stations: [{ id: "S1", ...AMK }], values: { S1: [0.2, null, 1.0] } };
    const [g] = gaugesAt(data, 2);
    expect(g.rate).toBe(12);
    expect(g.hourMm).toBeCloseTo(1.2, 6);
    expect(gaugesAt(data, 1)[0].rate).toBeNull();
  });

  it("names bands for drizzle to downpour", () => {
    expect(bandFor(0)).toBeNull();
    expect(bandFor(1).label).toBe("Light");
    expect(bandFor(20).label).toBe("Heavy");
    expect(bandFor(80).label).toBe("Very heavy");
  });
});

describe("locality", () => {
  it("keeps one wet gauge from tinting the far side of the island", () => {
    const west = { lat: 1.35, lng: 103.7, rate: 0 };
    const centre = { lat: 1.35, lng: 103.82, rate: 0 };
    const f = rainField([{ ...CHANGI, rate: 72 }, west, centre, { ...AMK, rate: 0 }], { cols: 92, rows: 56 });
    const [w, s, e, n] = f.bounds;
    const at = (lat, lng) => f.data[Math.floor(((n - lat) / (n - s)) * f.rows) * f.cols + Math.floor(((lng - w) / (e - w)) * f.cols)];
    expect(at(1.36, 103.985)).toBeGreaterThan(40);
    expect(at(1.35, 103.71)).toBeLessThan(0.5);
  });
});
