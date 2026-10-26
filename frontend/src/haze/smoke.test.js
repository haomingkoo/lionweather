import { describe, expect, it } from "vitest";
import {
  SINGAPORE,
  advect,
  clusterFires,
  distanceKm,
  outlookText,
  prepareField,
  simulateSmoke,
  smokeOutlook,
  velocity,
} from "./smoke";

const T0 = 1_792_000_800;
const LATS = Array.from({ length: 14 }, (_, i) => -6 + i);
const LONS = Array.from({ length: 26 }, (_, i) => 95 + i);

// Uniform wind everywhere, in m/s.
function uniform(u, v, hours = 48, forecastFrom = null) {
  const n = hours * LATS.length * LONS.length;
  return prepareField({
    status: "ok",
    t0: T0,
    step_s: 3600,
    hours,
    lats: LATS,
    lons: LONS,
    u: new Array(n).fill(Math.round(u * 10)),
    v: new Array(n).fill(Math.round(v * 10)),
    forecast_from: forecastFrom,
  });
}

describe("advection in a uniform wind", () => {
  it("moves a parcel east by the wind speed times the time step", () => {
    const f = uniform(10, 0);
    const [lat, lon] = advect(f, 1, 100, T0, 3600);
    expect(lat).toBeCloseTo(1, 6);
    expect(distanceKm(1, 100, lat, lon)).toBeCloseTo(36, 1);
    expect(lon).toBeGreaterThan(100);
  });

  it("moves a parcel north, and steps add up in a straight line", () => {
    const f = uniform(0, 5);
    let p = [-2, 105];
    for (let h = 0; h < 10; h += 1) p = advect(f, p[0], p[1], T0 + h * 3600, 3600);
    expect(p[1]).toBeCloseTo(105, 6);
    expect(distanceKm(-2, 105, p[0], p[1])).toBeCloseTo(180, 0);
  });

  it("returns null once the parcel leaves the grid or its hours", () => {
    const f = uniform(10, 0, 4);
    expect(advect(f, 0, 120.9, T0, 3600)).toBeNull();
    expect(advect(f, 0, 100, T0 + 10 * 3600, 3600)).toBeNull();
    expect(velocity(f, T0, 8, 100)).toBeNull();
  });

  it("reads missing values as no wind rather than zero", () => {
    const f = prepareField({ status: "ok", t0: T0, step_s: 3600, hours: 2, lats: [0, 1], lons: [100, 101], u: [null, 1, 1, 1, 1, 1, 1, 1], v: [0, 0, 0, 0, 0, 0, 0, 0] });
    expect(velocity(f, T0, 0.1, 100.1)).toBeNull();
  });
});

describe("fire clusters", () => {
  it("groups detections by half-degree cell with counts, power and times", () => {
    const c = clusterFires([
      [-1.1, 102.1, 10, T0],
      [-1.2, 102.3, 30, T0 + 3600],
      [0.6, 110.2, 5, T0],
    ]);
    expect(c).toHaveLength(2);
    const sumatra = c.find((x) => x.count === 2);
    expect(sumatra.frp).toBe(40);
    expect(sumatra.first).toBe(T0);
    expect(sumatra.last).toBe(T0 + 3600);
  });
});

describe("smoke drift", () => {
  it("weights particles by fire power and carries them with the wind", () => {
    const f = uniform(8, 0);
    const sim = simulateSmoke(f, [[0, 100, 90, T0], [0, 110, 10, T0]], { maxParticles: 400, diffusivity: 0 });
    let strong = 0;
    for (let i = 0; i < sim.count; i += 1) if (sim.cluster[i] === 0) strong += 1;
    expect(strong / sim.count).toBeGreaterThan(0.8);
    // A particle released at hour h sits about 8 m/s * k hours east k hours later.
    const i = 0;
    const h = sim.release[i];
    const at = (k) => [sim.pos[(i * sim.nt + k) * 2], sim.pos[(i * sim.nt + k) * 2 + 1]];
    const [la0, lo0] = at(h);
    const [la5, lo5] = at(h + 5);
    expect(distanceKm(la0, lo0, la5, lo5)).toBeCloseTo(8 * 3.6 * 5, 0);
    expect(Number.isNaN(at(Math.max(0, h - 1))[0]) || h === 0).toBe(true);
  });

  it("sees smoke from Sumatra heading for Singapore on a south-westerly", () => {
    const f = uniform(6, 6, 72);
    // Riau, south-west of Singapore by about 2 degrees.
    const sim = simulateSmoke(f, [[-0.4, 101.9, 50, T0]], { maxParticles: 300 });
    const out = smokeOutlook(sim, 12);
    expect(out.onCourse).toBe(1);
    expect(outlookText(out, { fires: 1 })).toMatch(/1 fire cluster is on course for Singapore in the next 24 hours\./);
  });

  it("says the smoke misses Singapore on a north-easterly", () => {
    const f = uniform(-6, -6, 72);
    const sim = simulateSmoke(f, [[-0.4, 101.9, 50, T0]], { maxParticles: 300 });
    const out = smokeOutlook(sim, 12);
    expect(out.onCourse).toBe(0);
    expect(out.overNow).toBe(0);
    expect(outlookText(out, { fires: 1 })).toMatch(/none of the smoke in the air reaches Singapore/);
  });

  it("flags when the next day runs on forecast wind", () => {
    const f = uniform(6, 6, 72, T0 + 20 * 3600);
    const sim = simulateSmoke(f, [[-0.4, 101.9, 50, T0]], { maxParticles: 100 });
    expect(smokeOutlook(sim, 12).usesForecast).toBe(true);
  });

  it("is plain when there are no fires or no wind", () => {
    expect(simulateSmoke(uniform(1, 1), [])).toBeNull();
    expect(outlookText(null, { fires: 0 })).toMatch(/no fires/);
    expect(outlookText(null, { fires: 3 })).toMatch(/not available/);
    expect(SINGAPORE.lat).toBeCloseTo(1.35, 2);
  });
});

describe("smoke age", () => {
  it("drops smoke older than two days from the counts", () => {
    const f = uniform(0.2, 0.2, 120); // nearly calm: the plume sits by the fire
    const sim = simulateSmoke(f, [[1.2, 103.6, 50, T0]], { maxParticles: 50, releaseHours: 1, diffusivity: 0 });
    expect(smokeOutlook(sim, 10).overNow).toBe(1);
    expect(smokeOutlook(sim, 60).airborne).toBe(0);
  });
});
