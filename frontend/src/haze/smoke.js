// Simulated smoke drift: particles released from NASA fire detections, weighted by
// fire power, carried hour by hour through Open-Meteo's 850 hPa wind with a little
// random spread. A picture of where smoke would go, not a forecast of PSI.

export const SINGAPORE = { lat: 1.3521, lon: 103.8198 };
const M_PER_DEG = 111320;
export const RELEASE_HOURS = 12; // each detection keeps smoking this long
export const MAX_PARTICLES = 4000;
export const DIFFUSIVITY = 2000; // m²/s: spreads a plume about 4 km an hour
export const NEAR_KM = 60;
export const AHEAD_HOURS = 24;
export const CLUSTER_DEG = 0.5;
// After two days a plume has spread too thin to trace; it drops out of the drawing and the counts.
export const MAX_AGE_HOURS = 48;

// /api/haze/wind-field payload -> typed arrays in m/s.
export function prepareField(payload) {
  if (!payload || payload.status !== "ok") return null;
  const n = payload.u.length;
  const u = new Float32Array(n);
  const v = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    u[i] = payload.u[i] == null ? NaN : payload.u[i] / 10;
    v[i] = payload.v[i] == null ? NaN : payload.v[i] / 10;
  }
  const { lats, lons } = payload;
  return {
    t0: payload.t0,
    step: payload.step_s,
    nt: payload.hours,
    lat0: lats[0],
    dlat: lats[1] - lats[0],
    nlat: lats.length,
    lon0: lons[0],
    dlon: lons[1] - lons[0],
    nlon: lons.length,
    forecastFrom: payload.forecast_from,
    u,
    v,
  };
}

// Bilinear in space, linear in time; null outside the grid or its hours.
export function velocity(f, t, lat, lon) {
  const ft = (t - f.t0) / f.step;
  const fy = (lat - f.lat0) / f.dlat;
  const fx = (lon - f.lon0) / f.dlon;
  if (ft < 0 || ft > f.nt - 1 || fy < 0 || fy > f.nlat - 1 || fx < 0 || fx > f.nlon - 1) return null;
  const t0 = Math.min(Math.floor(ft), Math.max(f.nt - 2, 0));
  const y0 = Math.min(Math.floor(fy), f.nlat - 2);
  const x0 = Math.min(Math.floor(fx), f.nlon - 2);
  const wt = f.nt > 1 ? ft - t0 : 0;
  const wy = fy - y0;
  const wx = fx - x0;
  const plane = f.nlat * f.nlon;
  const sample = (arr) => {
    let total = 0;
    for (const [dt, a] of [[0, 1 - wt], [1, wt]]) {
      if (!a) continue;
      const base = Math.min(t0 + dt, f.nt - 1) * plane;
      const i00 = base + y0 * f.nlon + x0;
      const top = arr[i00] * (1 - wx) + arr[i00 + 1] * wx;
      const bottom = arr[i00 + f.nlon] * (1 - wx) + arr[i00 + f.nlon + 1] * wx;
      total += a * (top * (1 - wy) + bottom * wy);
    }
    return total;
  };
  const u = sample(f.u);
  const v = sample(f.v);
  return Number.isFinite(u) && Number.isFinite(v) ? [u, v] : null;
}

export function displace(lat, lon, u, v, seconds) {
  const lat2 = lat + (v * seconds) / M_PER_DEG;
  const lon2 = lon + (u * seconds) / (M_PER_DEG * Math.cos((((lat + lat2) / 2) * Math.PI) / 180));
  return [lat2, lon2];
}

// One forward midpoint (RK2) step; null once the parcel leaves the wind grid.
export function advect(f, lat, lon, t, seconds) {
  const k1 = velocity(f, t, lat, lon);
  if (!k1) return null;
  const [mlat, mlon] = displace(lat, lon, k1[0], k1[1], seconds / 2);
  const k2 = velocity(f, t + seconds / 2, mlat, mlon);
  if (!k2) return null;
  return displace(lat, lon, k2[0], k2[1], seconds);
}

export function distanceKm(lat1, lon1, lat2, lon2) {
  const x = (lon2 - lon1) * Math.cos((((lat1 + lat2) / 2) * Math.PI) / 180);
  return Math.hypot(x, lat2 - lat1) * (M_PER_DEG / 1000);
}

// Detections binned into half-degree cells. Points are [lat, lng, frp, seen_unix].
export function clusterFires(points, cell = CLUSTER_DEG) {
  const cells = new Map();
  points.forEach((p) => {
    const key = `${Math.floor(p[0] / cell)}:${Math.floor(p[1] / cell)}`;
    let c = cells.get(key);
    if (!c) {
      c = { key, count: 0, frp: 0, lat: 0, lon: 0, first: Infinity, last: -Infinity };
      cells.set(key, c);
    }
    c.count += p[4] ?? 1;
    c.frp += p[2];
    c.lat += p[0];
    c.lon += p[1];
    c.first = Math.min(c.first, p[3]);
    c.last = Math.max(c.last, p[3]);
  });
  return [...cells.values()].map((c, id) => ({ ...c, id, lat: c.lat / c.count, lon: c.lon / c.count }));
}

function rng(seed) {
  let t = seed >>> 0;
  return () => {
    t = (t + 0x6d2b79f5) >>> 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function gauss(rand) {
  return Math.sqrt(-2 * Math.log(rand() || 1e-9)) * Math.cos(2 * Math.PI * rand());
}

// Positions of every particle at every field hour: pos[(p * nt + h) * 2] = lat, +1 = lon;
// NaN before release and after the particle leaves the grid.
export function simulateSmoke(f, points, opts = {}) {
  const { maxParticles = MAX_PARTICLES, releaseHours = RELEASE_HOURS, diffusivity = DIFFUSIVITY, seed = 7 } = opts;
  if (!f || !points?.length) return null;
  const rand = rng(seed);
  const clusters = clusterFires(points);
  const cellOf = new Map(clusters.map((c) => [c.key, c.id]));
  const totalFrp = points.reduce((s, p) => s + Math.max(p[2], 0.1), 0);
  const releases = [];
  points.forEach((p) => {
    // Stochastic rounding keeps the share of each fire proportional to its power.
    const share = (Math.max(p[2], 0.1) / totalFrp) * maxParticles;
    const n = Math.floor(share) + (rand() < share % 1 ? 1 : 0);
    const h0 = Math.round((p[3] - f.t0) / f.step);
    const cluster = cellOf.get(`${Math.floor(p[0] / CLUSTER_DEG)}:${Math.floor(p[1] / CLUSTER_DEG)}`);
    for (let k = 0; k < n; k += 1) {
      const h = h0 + Math.floor(rand() * releaseHours);
      if (h < 0 || h >= f.nt) continue;
      releases.push({ lat: p[0] + (rand() - 0.5) * 0.0034, lon: p[1] + (rand() - 0.5) * 0.0034, h, cluster });
    }
  });
  const count = Math.min(releases.length, maxParticles);
  const pos = new Float32Array(count * f.nt * 2).fill(NaN);
  const release = new Int16Array(count);
  const cluster = new Uint16Array(count);
  const sigmaDeg = Math.sqrt(2 * diffusivity * f.step) / M_PER_DEG;
  for (let i = 0; i < count; i += 1) {
    const r = releases[i];
    release[i] = r.h;
    cluster[i] = r.cluster;
    let { lat, lon } = r;
    for (let h = r.h; h < f.nt; h += 1) {
      pos[(i * f.nt + h) * 2] = lat;
      pos[(i * f.nt + h) * 2 + 1] = lon;
      if (h === f.nt - 1) break;
      const next = advect(f, lat, lon, f.t0 + h * f.step, f.step);
      if (!next) break;
      lat = next[0] + gauss(rand) * sigmaDeg;
      lon = next[1] + (gauss(rand) * sigmaDeg) / Math.cos((lat * Math.PI) / 180);
    }
  }
  return { nt: f.nt, t0: f.t0, step: f.step, count, pos, release, cluster, clusters, forecastFrom: f.forecastFrom };
}

// Particle positions at a fractional field hour, for drawing. Calls fn(lat, lon, ageHours).
export function eachParticleAt(sim, hour, fn) {
  if (!sim) return;
  const h0 = Math.floor(hour);
  const w = hour - h0;
  for (let i = 0; i < sim.count; i += 1) {
    if (sim.release[i] > h0 || h0 >= sim.nt || hour - sim.release[i] > MAX_AGE_HOURS) continue;
    const a = (i * sim.nt + h0) * 2;
    const lat0 = sim.pos[a];
    if (Number.isNaN(lat0)) continue;
    let lat = lat0;
    let lon = sim.pos[a + 1];
    if (w > 0 && h0 + 1 < sim.nt) {
      const lat1 = sim.pos[a + 2];
      if (!Number.isNaN(lat1)) {
        lat += (lat1 - lat) * w;
        lon += (sim.pos[a + 3] - lon) * w;
      }
    }
    fn(lat, lon, hour - sim.release[i]);
  }
}

export function fieldHour(sim, iso) {
  return sim ? (new Date(iso).getTime() / 1000 - sim.t0) / sim.step : null;
}

// Which fire clusters' smoke, already in the air at this hour, passes near Singapore
// in the next day.
export function smokeOutlook(sim, hour, { nearKm = NEAR_KM, ahead = AHEAD_HOURS, target = SINGAPORE } = {}) {
  if (!sim || hour == null) return null;
  const h = Math.round(hour);
  if (h < 0 || h >= sim.nt) return null;
  const onCourse = new Set();
  const overNow = new Set();
  let airborne = 0;
  const last = Math.min(sim.nt - 1, h + ahead);
  for (let i = 0; i < sim.count; i += 1) {
    if (sim.release[i] > h || h - sim.release[i] > MAX_AGE_HOURS) continue;
    const base = i * sim.nt;
    if (Number.isNaN(sim.pos[(base + h) * 2])) continue;
    airborne += 1;
    for (let k = h; k <= last; k += 1) {
      const lat = sim.pos[(base + k) * 2];
      if (Number.isNaN(lat) || k - sim.release[i] > MAX_AGE_HOURS) break;
      if (distanceKm(lat, sim.pos[(base + k) * 2 + 1], target.lat, target.lon) <= nearKm) {
        (k === h ? overNow : onCourse).add(sim.cluster[i]);
        break;
      }
    }
  }
  const usesForecast = sim.forecastFrom != null && sim.t0 + last * sim.step >= sim.forecastFrom;
  return { airborne, onCourse: onCourse.size, overNow: overNow.size, usesForecast, aheadHours: last - h };
}

export function outlookText(outlook, { fires = 0 } = {}) {
  if (!fires) return "NASA satellites saw no fires in this window, so there is no smoke to trace.";
  if (!outlook) return "Wind for the smoke drift is not available for this hour.";
  if (!outlook.airborne) return "No smoke from the detected fires is in the air yet at this hour.";
  const parts = [];
  if (outlook.overNow) parts.push(`In the simulation, smoke from ${plural(outlook.overNow, "fire cluster")} is over Singapore now.`);
  if (outlook.onCourse) {
    parts.push(`${outlook.overNow ? "Smoke" : "In the simulation, smoke"} from ${plural(outlook.onCourse, "fire cluster")} is on course for Singapore in the next ${outlook.aheadHours} hours${outlook.usesForecast ? ", on forecast wind" : ""}.`);
  }
  if (!parts.length) parts.push(`On these winds, none of the smoke in the air reaches Singapore in the next ${outlook.aheadHours} hours.`);
  return parts.join(" ");
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}
