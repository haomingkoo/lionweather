import { describe, expect, it } from "vitest";
import { explainHour, firesNearPath, landAt, pathSummary } from "./explain";

// A straight 48-hour path from Singapore towards a bearing, in degrees of lat/lon per hour.
function path(dLat, dLon, hours = 48) {
  return Array.from({ length: hours + 1 }, (_, h) => [1.3521 + dLat * h, 103.8198 + dLon * h, h]);
}

const SW_PATH = path(-0.04, -0.04); // back over Riau and Jambi
const NE_PATH = path(0.025, 0.05); // back over the South China Sea
const WEST_HIGH = { west: 92, central: 70, south: 66, north: 64, east: 61 };
const RIAU_FIRES = [
  [-0.3, 102.1, 40, 0],
  [-0.5, 101.9, 12, 0],
  [-0.4, 102.3, 8, 0],
];

describe("landAt", () => {
  it("knows the big islands and leaves the sea and Singapore out", () => {
    expect(landAt(-0.5, 102)).toBe("Sumatra");
    expect(landAt(0.5, 112)).toBe("Borneo");
    expect(landAt(3, 102)).toBe("Peninsular Malaysia");
    expect(landAt(1.3521, 103.8198)).toBeNull();
    expect(landAt(4, 108)).toBeNull();
  });
});

describe("explainHour", () => {
  it("SW wind with fires on the path: names Sumatra and the west side", () => {
    const out = explainHour({ pm25: WEST_HIGH, wind850: [6, 225], surface: [5, 220], path: SW_PATH, fires: RIAU_FIRES });
    expect(out.headline).toBe("West highest: 92 vs 61 µg/m³ in the east.");
    expect(out.body).toBe("Likely smoke: air came over 3 fires upwind.");
    expect(out.context).toBe("West has industry and shipping (Jurong, Tuas).");
  });

  it("NE wind: fires in Sumatra are off the path and no cause is claimed", () => {
    const out = explainHour({ pm25: WEST_HIGH, wind850: [7, 45], surface: [6, 40], path: NE_PATH, fires: RIAU_FIRES });
    expect(out.facts.firesOnPath).toBe(0);
    expect(out.body).toBe("Cause unclear: air came from the northeast (no fires on its path).");
    expect(out.body).not.toMatch(/Likely/);
  });

  it("calm winds: says the difference looks local and claims no source", () => {
    const out = explainHour({ pm25: WEST_HIGH, wind850: [1.2, 200], surface: [1, 180], path: SW_PATH, fires: RIAU_FIRES });
    expect(out.facts.calm).toBe(true);
    expect(out.body).toBe("Cause unclear: winds are light, so it looks local.");
  });

  it("no fires anywhere: says so plainly", () => {
    const out = explainHour({ pm25: WEST_HIGH, wind850: [6, 225], surface: [5, 220], path: SW_PATH, fires: [] });
    expect(out.body).toBe("Cause unclear: air came from the southwest (no fires on its path).");
  });

  it("similar readings: no region is singled out", () => {
    const out = explainHour({ pm25: { west: 30, east: 28, north: 29, south: 31, central: 30 }, wind850: [1, 90], surface: [1, 90], path: null });
    expect(out.headline).toBe("Similar across the island.");
    expect(out.body).toBe("No clear source: winds are light.");
    expect(out.context).toBeNull();
  });

  it("does not credit fires when the high region is not on the windward side", () => {
    const out = explainHour({ pm25: { east: 90, west: 60, north: 62, south: 61, central: 63 }, wind850: [6, 225], surface: [5, 220], path: SW_PATH, fires: RIAU_FIRES });
    expect(out.body).toBe("Cause unclear: air came from the southwest (3 fires on its path).");
  });

  it("is honest when fire data or the air path is missing", () => {
    expect(explainHour({ pm25: WEST_HIGH, wind850: [6, 225], path: SW_PATH, firesKnown: false }).body).toMatch(/fire data not available/);
    expect(explainHour({ pm25: WEST_HIGH, wind850: null, surface: [5, 220], path: null, fires: RIAU_FIRES }).body).toMatch(/air path not available/);
    expect(explainHour({ pm25: { west: 50 } }).headline).toMatch(/Too few regional readings/);
  });
});

it("never names a country or blames anyone in the sentences", () => {
  const cases = [
    { pm25: WEST_HIGH, wind850: [6, 225], surface: [5, 220], path: SW_PATH, fires: RIAU_FIRES },
    { pm25: WEST_HIGH, wind850: [6, 225], surface: [5, 220], path: SW_PATH, fires: [] },
    { pm25: { west: 50, east: 50, north: 50, south: 50, central: 50 }, wind850: [6, 225], surface: [5, 220], path: SW_PATH, fires: RIAU_FIRES },
  ];
  cases.forEach((c) => {
    const { headline, body } = explainHour(c);
    expect(`${headline} ${body}`).not.toMatch(/Indonesia|Malaysia|Sumatra|Borneo|blame|caused by|country/i);
  });
});

describe("path helpers", () => {
  it("summarises where the air came from and finds fires within the corridor", () => {
    const s = pathSummary(SW_PATH);
    expect(s.from).toBe("SW");
    expect(s.lands).toEqual(["Sumatra"]);
    expect(firesNearPath(s.points, [[-0.3, 102.1, 1, 0], [3, 110, 1, 0]])).toHaveLength(1);
  });
});

describe("fireStretches", () => {
  it("finds the stretch of path that passes over fires", async () => {
    const { fireStretches } = await import("./explain");
    const runs = fireStretches(SW_PATH, RIAU_FIRES);
    expect(runs.length).toBe(1);
    const [a, b] = runs[0];
    expect(SW_PATH[a][2]).toBeGreaterThan(20);
    expect(SW_PATH[b][2]).toBe(48);
    expect(fireStretches(NE_PATH, RIAU_FIRES)).toEqual([]);
  });
});
