// Lattice-Boltzmann (D2Q9, BGK) wind among buildings: the obstacle grid built from
// OSM footprints, and a CPU reference solver that the WebGL2 shaders mirror.
//
// The grid is turned so the wind always enters on the left (x = 0) and leaves on
// the right; y wraps around. Buildings are solid cells with bounce-back walls.

export const E = [[0, 0], [1, 0], [0, 1], [-1, 0], [0, -1], [1, 1], [-1, 1], [-1, -1], [1, -1]];
export const W = [4 / 9, 1 / 9, 1 / 9, 1 / 9, 1 / 9, 1 / 36, 1 / 36, 1 / 36, 1 / 36];
export const OPP = [0, 3, 4, 1, 2, 7, 8, 5, 6];
export const TAU = 0.56; // relaxation time: viscosity (TAU - 0.5) / 3 in lattice units
export const MAX_U = 0.1; // inflow speed cap in lattice units, for stability

const M_PER_DEG = 111320;

/**
 * A square simulation frame centred on a place, turned to the wind.
 * fromDeg is the meteorological direction the wind comes from.
 */
export function makeFrame({ lat, lng, sizeM, n, fromDeg }) {
  const to = ((fromDeg + 180) * Math.PI) / 180;
  const d = [Math.sin(to), Math.cos(to)]; // downwind, as [east, north]
  const p = [-d[1], d[0]]; // across the wind, to the left of downwind
  return { lat, lng, sizeM, n, d, p, kx: Math.cos((lat * Math.PI) / 180) * M_PER_DEG };
}

// [lng, lat] -> grid [x, y] (cells, may fall outside 0..n).
export function toGrid(f, lng, lat) {
  const e = (lng - f.lng) * f.kx;
  const nn = (lat - f.lat) * M_PER_DEG;
  const x = e * f.d[0] + nn * f.d[1];
  const y = e * f.p[0] + nn * f.p[1];
  return [(x / f.sizeM + 0.5) * f.n, (y / f.sizeM + 0.5) * f.n];
}

// grid [x, y] -> [lng, lat]
export function fromGrid(f, gx, gy) {
  const x = (gx / f.n - 0.5) * f.sizeM;
  const y = (gy / f.n - 0.5) * f.sizeM;
  const e = x * f.d[0] + y * f.p[0];
  const nn = x * f.d[1] + y * f.p[1];
  return [f.lng + e / f.kx, f.lat + nn / M_PER_DEG];
}

/**
 * Rasterise footprint polygons into a solid mask (1 = building), even-odd per
 * polygon, sampling each cell at its centre. polygons: [[ring of [lng, lat]], ...]
 * where the first ring is the outline and later rings are courtyards.
 */
export function buildObstacleMask(polygons, f) {
  const { n } = f;
  const mask = new Uint8Array(n * n);
  for (const rings of polygons) {
    const edges = [];
    let minY = Infinity;
    let maxY = -Infinity;
    for (const ring of rings) {
      const pts = ring.map(([lng, lat]) => toGrid(f, lng, lat));
      for (let i = 0; i < pts.length; i += 1) {
        const a = pts[i];
        const b = pts[(i + 1) % pts.length];
        if (a[1] === b[1]) continue;
        edges.push([a[0], a[1], b[0], b[1]]);
        minY = Math.min(minY, a[1], b[1]);
        maxY = Math.max(maxY, a[1], b[1]);
      }
    }
    const y0 = Math.max(0, Math.ceil(minY - 0.5));
    const y1 = Math.min(n - 1, Math.floor(maxY - 0.5));
    for (let row = y0; row <= y1; row += 1) {
      const yc = row + 0.5;
      const xs = [];
      for (const [ax, ay, bx, by] of edges) {
        if ((ay <= yc) !== (by <= yc)) xs.push(ax + ((yc - ay) * (bx - ax)) / (by - ay));
      }
      xs.sort((a, b) => a - b);
      for (let k = 0; k + 1 < xs.length; k += 2) {
        const c0 = Math.max(0, Math.ceil(xs[k] - 0.5));
        const c1 = Math.min(n - 1, Math.floor(xs[k + 1] - 0.5));
        for (let c = c0; c <= c1; c += 1) mask[row * n + c] = 1;
      }
    }
  }
  return mask;
}

export function equilibrium(rho, ux, uy, out = new Float32Array(9)) {
  const uu = ux * ux + uy * uy;
  for (let i = 0; i < 9; i += 1) {
    const eu = E[i][0] * ux + E[i][1] * uy;
    out[i] = W[i] * rho * (1 + 3 * eu + 4.5 * eu * eu - 1.5 * uu);
  }
  return out;
}

// A lattice of nx by ny cells, at rest with the inflow speed everywhere.
export function createLattice(nx, ny, mask, u0) {
  const f = new Float32Array(nx * ny * 9);
  const eq = equilibrium(1, u0, 0);
  for (let c = 0; c < nx * ny; c += 1) f.set(eq, c * 9);
  return { nx, ny, mask, u0, f, g: new Float32Array(f.length), tau: TAU };
}

// One step: pull streaming with bounce-back off solid cells, BGK collision,
// equilibrium inflow on the left, zero-gradient outflow on the right.
export function stepCPU(L) {
  const { nx, ny, mask, f, g, tau, u0 } = L;
  const inflow = equilibrium(1, u0, 0);
  const local = new Float32Array(9);
  const eq = new Float32Array(9);
  for (let y = 0; y < ny; y += 1) {
    for (let x = 0; x < nx; x += 1) {
      const c = y * nx + x;
      if (mask[c]) {
        for (let i = 0; i < 9; i += 1) g[c * 9 + i] = W[i];
        continue;
      }
      if (x === 0) {
        g.set(inflow, c * 9);
        continue;
      }
      for (let i = 0; i < 9; i += 1) {
        const sx = Math.min(nx - 1, x - E[i][0]);
        const sy = (y - E[i][1] + ny) % ny;
        const s = sy * nx + sx;
        local[i] = mask[s] ? f[c * 9 + OPP[i]] : f[s * 9 + i];
      }
      let rho = 0;
      let ux = 0;
      let uy = 0;
      for (let i = 0; i < 9; i += 1) {
        rho += local[i];
        ux += local[i] * E[i][0];
        uy += local[i] * E[i][1];
      }
      ux /= rho;
      uy /= rho;
      equilibrium(rho, ux, uy, eq);
      for (let i = 0; i < 9; i += 1) g[c * 9 + i] = local[i] - (local[i] - eq[i]) / tau;
    }
  }
  // Outflow: copy the last column from its neighbour.
  for (let y = 0; y < ny; y += 1) {
    const c = y * nx + nx - 1;
    if (!mask[c]) for (let i = 0; i < 9; i += 1) g[c * 9 + i] = g[(c - 1) * 9 + i];
  }
  L.f = g;
  L.g = f;
  return L;
}

export function velocityAt(L, x, y) {
  const c = y * L.nx + x;
  if (L.mask[c]) return [0, 0];
  let rho = 0;
  let ux = 0;
  let uy = 0;
  for (let i = 0; i < 9; i += 1) {
    const v = L.f[c * 9 + i];
    rho += v;
    ux += v * E[i][0];
    uy += v * E[i][1];
  }
  return [ux / rho, uy / rho];
}

// Inflow speed in lattice units for a wind speed in knots: proportional, capped.
export function latticeSpeed(knots) {
  return Math.min(MAX_U, 0.015 + 0.012 * Math.max(0, knots));
}

// Grid resolution for the device: finer on a desktop GPU, coarser on a phone.
export function gridSizeFor({ phone = false, maxTexture = 4096 } = {}) {
  return Math.min(phone ? 192 : 320, maxTexture);
}
