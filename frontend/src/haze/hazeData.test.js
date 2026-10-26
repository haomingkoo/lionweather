import { describe, expect, it } from "vitest";
import {
  bandFor,
  compass,
  findEvents,
  hazeColor,
  hazeDensity,
  lastIndexWithData,
  peak,
  regionAt,
  sampleField,
  windField,
  worstRegion,
} from "./hazeData";

const BANDS = {
  psi: [
    { max: 50, key: "good", label: "Good", advice: "Normal activities" },
    { max: 100, key: "moderate", label: "Moderate", advice: "Normal activities" },
    { max: 200, key: "unhealthy", label: "Unhealthy", advice: "Reduce" },
    { max: 300, key: "very_unhealthy", label: "Very unhealthy", advice: "Avoid" },
    { max: null, key: "hazardous", label: "Hazardous", advice: "Minimise" },
  ],
  pm25: [
    { max: 55, key: "normal", label: "Normal", advice: "Continue" },
    { max: 150, key: "elevated", label: "Elevated", advice: "Reduce" },
    { max: 250, key: "high", label: "High", advice: "Avoid" },
    { max: null, key: "very_high", label: "Very high", advice: "Minimise" },
  ],
};

function scene(psiWest, pmWest, extra = {}) {
  const n = psiWest.length;
  const flat = (v) => Array(n).fill(v);
  return {
    hours: Array.from({ length: n }, (_, i) => `2026-10-25T${String(i).padStart(2, "0")}:00:00+08:00`),
    psi: { north: flat(60), south: flat(60), east: flat(60), central: flat(60), west: psiWest },
    pm25: { north: flat(20), south: flat(20), east: flat(20), central: flat(20), west: pmWest },
    bands: BANDS,
    ...extra,
  };
}

describe("bandFor", () => {
  it("uses NEA upper bounds inclusively", () => {
    expect(bandFor(100, BANDS.psi).key).toBe("moderate");
    expect(bandFor(101, BANDS.psi).key).toBe("unhealthy");
    expect(bandFor(55, BANDS.pm25).key).toBe("normal");
    expect(bandFor(56, BANDS.pm25).key).toBe("elevated");
    expect(bandFor(900, BANDS.pm25).key).toBe("very_high");
  });

  it("returns plain advice and a colour, and nothing for missing values", () => {
    const band = bandFor(150, BANDS.psi);
    expect(band.plain).toBe("Cut back on long or hard exercise outdoors.");
    expect(band.color).toMatch(/^#[0-9a-f]{6}$/);
    expect(bandFor(null, BANDS.psi)).toBeNull();
    expect(bandFor(Number.NaN, BANDS.psi)).toBeNull();
  });

  it("has plain advice for every band, with no em dash", () => {
    for (const [kind, values] of [["psi", [10, 80, 150, 250, 400]], ["pm25", [10, 100, 200, 300]]]) {
      for (const v of values) {
        const plain = bandFor(v, BANDS[kind]).plain;
        expect(plain).toMatch(/\.$/);
        expect(plain).not.toContain("\u2014");
      }
    }
  });
});

describe("haze density and colour", () => {
  it("is zero for clean or missing air and saturates at 250 µg/m³", () => {
    expect(hazeDensity(0)).toBe(0);
    expect(hazeDensity(null)).toBe(0);
    expect(hazeDensity(250)).toBe(1);
    expect(hazeDensity(600)).toBe(1);
  });

  it("rises monotonically with PM2.5", () => {
    const values = [5, 20, 55, 100, 150, 250].map(hazeDensity);
    values.slice(1).forEach((v, i) => expect(v).toBeGreaterThan(values[i]));
  });

  it("turns from pale grey to yellow-brown", () => {
    const clean = hazeColor(0);
    const smoky = hazeColor(250);
    expect(clean[0] - clean[2]).toBeLessThan(15);
    expect(smoky[0] - smoky[2]).toBeGreaterThan(80);
  });
});

describe("cursor lookups", () => {
  it("carries a reading forward up to two hours, then reports no data", () => {
    const s = scene([120, null, null, null], [60, null, null, null]);
    expect(regionAt(s, "west", 2).psi).toBe(120);
    expect(regionAt(s, "west", 2).psiBand.key).toBe("unhealthy");
    expect(regionAt(s, "west", 3).psi).toBeNull();
    expect(regionAt(s, "west", 3).pm25Band).toBeNull();
  });

  it("finds the worst region, the overall peak and the last hour with data", () => {
    const s = scene([90, 150, 80, null], [30, 61, 40, null]);
    expect(worstRegion(s, 1)).toBe("west");
    expect(peak(s, "pm25")).toEqual({ value: 61, region: "west", index: 1 });
    expect(lastIndexWithData({ ...s, psi: { ...s.psi, north: [1, 1, 1, null], south: [1, 1, 1, null], east: [1, 1, 1, null], central: [1, 1, 1, null] } })).toBe(2);
  });
});

describe("findEvents", () => {
  it("marks band changes in the worst region and the PM2.5 peak", () => {
    const s = scene([90, 120, 130, 95], [30, 70, 80, 40]);
    const events = findEvents(s);
    expect(events.map((e) => [e.index, e.label])).toEqual([
      [1, "PSI up to unhealthy"],
      [1, "Rose to elevated"],
      [2, "Peak: 80 µg/m³ in the west"],
      [3, "PSI down to moderate"],
      [3, "Back to normal"],
    ]);
  });

  it("drops a change undone within an hour and keeps the later of two quick changes", () => {
    // PM2.5: normal, elevated, normal, ..., then elevated, high in consecutive hours.
    const s = scene([60, 60, 60, 60, 60, 60, 60], [30, 70, 30, 30, 30, 70, 160]);
    const labels = findEvents(s).filter((e) => e.kind === "pm25").map((e) => [e.index, e.label]);
    expect(labels).toEqual([[6, "Rose to high"]]);
  });
});

describe("adviceFor", () => {
  it("gives one line, from the stricter band", async () => {
    const { adviceFor } = await import("./hazeData");
    expect(adviceFor(bandFor(80, BANDS.psi), bandFor(40, BANDS.pm25))).toBe("Fine for normal activities.");
    expect(adviceFor(bandFor(80, BANDS.psi), bandFor(160, BANDS.pm25))).toBe("Avoid long or hard exercise outdoors.");
    expect(adviceFor(null, null)).toBeNull();
  });
});

describe("wind field", () => {
  const stations = [
    { name: "A", lat: 1.3, lng: 103.7 },
    { name: "B", lat: 1.4, lng: 103.9 },
  ];

  it("blends station winds and points downwind", () => {
    const hourly = { A: [[10, 270]], B: [[10, 270]] };
    const field = windField(stations, hourly, 0, [103.6, 1.2, 104.1, 1.5]);
    const [u, v] = sampleField(field, 103.8, 1.35);
    expect(u).toBeCloseTo(10, 5); // westerly blows east
    expect(v).toBeCloseTo(0, 5);
  });

  it("weights the nearest station most", () => {
    const hourly = { A: [[10, 0]], B: [[10, 180]] };
    const field = windField(stations, hourly, 0, [103.6, 1.2, 104.1, 1.5]);
    expect(sampleField(field, 103.7, 1.3)[1]).toBeLessThan(-9);
    expect(sampleField(field, 103.9, 1.4)[1]).toBeGreaterThan(9);
  });

  it("returns null when no station reported that hour", () => {
    expect(windField(stations, { A: [null], B: [null] }, 0, [103.6, 1.2, 104.1, 1.5])).toBeNull();
  });

  it("names compass points", () => {
    expect(compass(0)).toBe("N");
    expect(compass(225)).toBe("SW");
    expect(compass(359)).toBe("N");
  });
});

import { hazeProfile, opticalDepth, LAYER_TOP_M } from "./hazeLayer";

describe("haze column", () => {
  it("stays nearly clear in the normal band and thickens through elevated and high", () => {
    expect(opticalDepth(20)).toBeLessThan(0.03);
    expect(opticalDepth(55)).toBeLessThan(0.03);
    expect(opticalDepth(100)).toBeGreaterThan(0.5);
    expect(opticalDepth(200)).toBeGreaterThan(1.7);
    expect(opticalDepth(null)).toBe(0);
  });

  it("keeps most of the haze below the layer top, so tall towers poke through", () => {
    const { alts, weights } = hazeProfile();
    expect(weights.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 6);
    const below = weights.filter((_, i) => alts[i] < LAYER_TOP_M + 40).reduce((a, b) => a + b, 0);
    expect(below).toBeGreaterThan(0.8);
    expect(Math.max(...alts)).toBeLessThan(700);
  });
});

import { eyeFromMatrix } from "./hazeLayer";

describe("eyeFromMatrix", () => {
  it("recovers a camera position from a translate-then-perspective matrix", () => {
    // Perspective (near 0.1, far 100) times a translation by (-2, -3, -10): eye at (2, 3, 10).
    const n = 0.1, f = 100;
    const P = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -(f + n) / (f - n), -1, 0, 0, (-2 * f * n) / (f - n), 0];
    const T = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -2, -3, -10, 1];
    const M = new Array(16).fill(0);
    for (let c = 0; c < 4; c += 1) for (let r = 0; r < 4; r += 1) for (let k = 0; k < 4; k += 1) M[c * 4 + r] += P[k * 4 + r] * T[c * 4 + k];
    const [x, y, z] = eyeFromMatrix(M);
    expect(x).toBeCloseTo(2, 3);
    expect(y).toBeCloseTo(3, 3);
    expect(z).toBeCloseTo(10 - n, 3);
  });
});
