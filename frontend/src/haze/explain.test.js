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
    expect(out.headline).toBe("The west is highest this hour, 92 against 61 µg/m³ in the east.");
    expect(out.body).toBe(
      "Air is arriving from the southwest, over Sumatra, where NASA satellites saw 3 fire detections near its path in the last 24 hours, so the west side gets it first.",
    );
    expect(out.context).toMatch(/Jurong and Tuas/);
    expect(out.context).toMatch(/can't separate/);
  });

  it("NE wind: fires in Sumatra are off the path and no cause is claimed", () => {
    const out = explainHour({ pm25: WEST_HIGH, wind850: [7, 45], surface: [6, 40], path: NE_PATH, fires: RIAU_FIRES });
    expect(out.facts.firesOnPath).toBe(0);
    expect(out.body).toBe(
      "Air is arriving from the northeast, and NASA satellites saw no fires along its path in the last 24 hours, so there is no clear outside source.",
    );
    expect(out.body).not.toMatch(/gets it first/);
  });

  it("calm winds: says the difference looks local and claims no source", () => {
    const out = explainHour({ pm25: WEST_HIGH, wind850: [1.2, 200], surface: [1, 180], path: SW_PATH, fires: RIAU_FIRES });
    expect(out.facts.calm).toBe(true);
    expect(out.body).toMatch(/Winds are light/);
    expect(out.body).toMatch(/no clear outside source/);
    expect(out.body).not.toMatch(/fire/);
  });

  it("no fires anywhere: says so plainly", () => {
    const out = explainHour({ pm25: WEST_HIGH, wind850: [6, 225], surface: [5, 220], path: SW_PATH, fires: [] });
    expect(out.body).toMatch(/saw no fires along its path/);
  });

  it("similar readings: no region is singled out", () => {
    const out = explainHour({ pm25: { west: 30, east: 28, north: 29, south: 31, central: 30 }, wind850: [1, 90], surface: [1, 90], path: null });
    expect(out.headline).toBe("Readings are similar across the island this hour.");
    expect(out.body).toBe("Winds are light, so there is no clear source this hour.");
    expect(out.context).toBeNull();
  });

  it("does not credit fires when the high region is not on the windward side", () => {
    const out = explainHour({ pm25: { east: 90, west: 60, north: 62, south: 61, central: 63 }, wind850: [6, 225], surface: [5, 220], path: SW_PATH, fires: RIAU_FIRES });
    expect(out.body).toMatch(/doesn't show why the east is highest/);
  });

  it("is honest when fire data or the air path is missing", () => {
    expect(explainHour({ pm25: WEST_HIGH, wind850: [6, 225], path: SW_PATH, firesKnown: false }).body).toMatch(/Fire detections are not available/);
    expect(explainHour({ pm25: WEST_HIGH, wind850: null, surface: [5, 220], path: null, fires: RIAU_FIRES }).body).toMatch(/air path is not available/);
    expect(explainHour({ pm25: { west: 50 } }).headline).toMatch(/Not enough regional readings/);
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
