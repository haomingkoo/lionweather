import { describe, expect, it } from "vitest";
import { buildObstacleMask, createLattice, fromGrid, makeFrame, stepCPU, toGrid, velocityAt, latticeSpeed } from "./lbm";

const CENTRE = { lat: 1.2835, lng: 103.853 };
const M = 111320;

// A square footprint of side `s` metres centred `dx`, `dy` metres east and north.
function square(s, dx = 0, dy = 0) {
  const kx = Math.cos((CENTRE.lat * Math.PI) / 180) * M;
  const c = [CENTRE.lng + dx / kx, CENTRE.lat + dy / M];
  const h = s / 2;
  return [[
    [c[0] - h / kx, c[1] - h / M],
    [c[0] + h / kx, c[1] - h / M],
    [c[0] + h / kx, c[1] + h / M],
    [c[0] - h / kx, c[1] + h / M],
  ]];
}

const count = (mask) => mask.reduce((a, b) => a + b, 0);

describe("obstacle mask from footprints", () => {
  it("fills the cells a footprint covers, at the right size", () => {
    // 1000 m frame on a 100-cell grid: 10 m cells. A 200 m square covers 20 x 20 cells.
    const f = makeFrame({ ...CENTRE, sizeM: 1000, n: 100, fromDeg: 270 });
    const mask = buildObstacleMask([square(200)], f);
    expect(count(mask)).toBe(400);
    expect(mask[50 * 100 + 50]).toBe(1);
    expect(mask[10 * 100 + 10]).toBe(0);
  });

  it("turns with the wind so it always blows from the left of the grid", () => {
    // Building 300 m east of centre. Wind from the west: it sits downwind, to the right.
    const west = makeFrame({ ...CENTRE, sizeM: 1000, n: 100, fromDeg: 270 });
    const [gx, gy] = toGrid(west, ...fromGrid(west, 50, 50));
    expect(gx).toBeCloseTo(50, 6);
    expect(gy).toBeCloseTo(50, 6);
    const mw = buildObstacleMask([square(100, 300, 0)], west);
    expect(mw[50 * 100 + 80]).toBe(1);
    // Wind from the east: the same building is now upwind, on the left.
    const east = makeFrame({ ...CENTRE, sizeM: 1000, n: 100, fromDeg: 90 });
    const me = buildObstacleMask([square(100, 300, 0)], east);
    expect(me[50 * 100 + 20]).toBe(1);
    expect(count(me)).toBe(count(mw));
  });

  it("leaves courtyards open and clips footprints at the frame edge", () => {
    const f = makeFrame({ ...CENTRE, sizeM: 1000, n: 100, fromDeg: 0 });
    const ring = square(300)[0];
    const hole = square(100)[0];
    const mask = buildObstacleMask([[ring, hole]], f);
    expect(count(mask)).toBe(900 - 100);
    expect(mask[50 * 100 + 50]).toBe(0);
    const edge = buildObstacleMask([square(400, 500, 0)], f);
    // A 400 m square (40 x 40 cells) half outside the frame keeps its inside half.
    expect(count(edge)).toBe(800);
  });
});

describe("solver", () => {
  it("leaves a wake behind a single block and keeps free flow beside it", () => {
    const nx = 96;
    const ny = 48;
    const mask = new Uint8Array(nx * ny);
    for (let y = 20; y < 28; y += 1) for (let x = 24; x < 32; x += 1) mask[y * nx + x] = 1;
    const u0 = 0.08;
    const L = createLattice(nx, ny, mask, u0);
    for (let s = 0; s < 1500; s += 1) stepCPU(L);
    const behind = [];
    for (let x = 33; x < 41; x += 1) behind.push(velocityAt(L, x, 24)[0]);
    const wake = behind.reduce((a, b) => a + b, 0) / behind.length;
    const beside = velocityAt(L, 36, 6)[0];
    expect(wake).toBeLessThan(0.5 * u0);
    expect(beside).toBeGreaterThan(0.85 * u0);
    // Air speeds up through the gap at the block's side.
    expect(velocityAt(L, 28, 16)[0]).toBeGreaterThan(u0);
    // Nothing blew up.
    expect(Number.isFinite(L.f.reduce((a, b) => a + b, 0))).toBe(true);
  });

  it("is uniform flow when there are no buildings", () => {
    const L = createLattice(32, 16, new Uint8Array(32 * 16), 0.05);
    for (let s = 0; s < 200; s += 1) stepCPU(L);
    const [ux, uy] = velocityAt(L, 20, 8);
    expect(ux).toBeCloseTo(0.05, 4);
    expect(uy).toBeCloseTo(0, 5);
  });

  it("maps wind speed to a capped lattice speed", () => {
    expect(latticeSpeed(0)).toBeGreaterThan(0);
    expect(latticeSpeed(4)).toBeLessThan(latticeSpeed(8));
    expect(latticeSpeed(40)).toBe(0.1);
  });
});
