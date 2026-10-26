// Pure mapping from the /api/haze/scene payload to what the page draws.

export const REGIONS = ["north", "south", "east", "west", "central"];

export const BAND_COLORS = {
  good: "#4e8a5b",
  normal: "#4e8a5b",
  moderate: "#3f7699",
  unhealthy: "#c99017",
  elevated: "#c99017",
  very_unhealthy: "#c25a22",
  high: "#c25a22",
  hazardous: "#8f2a35",
  very_high: "#8f2a35",
};

// NEA advice for healthy people, in plain words. PSI and PM2.5 bands that ask
// the same thing share a line, so the page can show just the stricter one.
const PLAIN_ADVICE = {
  good: "Fine for normal activities.",
  moderate: "Fine for normal activities.",
  normal: "Fine for normal activities.",
  unhealthy: "Cut back on long or hard exercise outdoors.",
  elevated: "Cut back on long or hard exercise outdoors.",
  very_unhealthy: "Avoid long or hard exercise outdoors.",
  high: "Avoid long or hard exercise outdoors.",
  hazardous: "Stay indoors where you can.",
  very_high: "Stay indoors where you can.",
};
const ADVICE_LEVEL = { good: 0, moderate: 0, normal: 0, unhealthy: 1, elevated: 1, very_unhealthy: 2, high: 2, hazardous: 3, very_high: 3 };

// One line of advice from the 24-hour PSI and 1-hour PM2.5 bands: the stricter wins.
export function adviceFor(psiBand, pm25Band) {
  const bands = [psiBand, pm25Band].filter(Boolean);
  if (!bands.length) return null;
  return bands.reduce((a, b) => (ADVICE_LEVEL[b.key] > ADVICE_LEVEL[a.key] ? b : a)).plain;
}

export function capitalise(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}

export function bandFor(value, bands = []) {
  if (value == null || !Number.isFinite(value)) return null;
  const band = bands.find((b) => b.max == null || value <= b.max);
  if (!band) return null;
  return { ...band, color: BAND_COLORS[band.key], plain: PLAIN_ADVICE[band.key] };
}

// 0 at clean air, 1 at the top of NEA's "High" PM2.5 band (250 µg/m³). Square root
// so the step from clean to elevated is visible, which is where most hours sit.
export function hazeDensity(pm25) {
  if (pm25 == null || !Number.isFinite(pm25) || pm25 <= 0) return 0;
  return Math.min(1, Math.sqrt(pm25 / 250));
}

const SMOKE_TINTS = {
  light: { clean: [206, 211, 218], smoke: [166, 118, 64] },
  dark: { clean: [96, 106, 122], smoke: [158, 124, 86] },
};

// The two numbers the page can show. PSI is the 24-hour index Singaporeans know;
// PM2.5 is the 1-hour concentration.
export const METRICS = {
  psi: { key: "psi", label: "PSI 24-h", unit: "", top: 300, short: "PSI" },
  pm25: { key: "pm25", label: "PM2.5 1-h", unit: "µg/m³", top: 250, short: "PM2.5" },
};

export function parseMetric(value) {
  return METRICS[value] ? value : null;
}

// 0 in clean air, 1 at the top of the scale shown (PSI 300, PM2.5 250).
export function hazeLevel(value, metric = "pm25") {
  if (value == null || !Number.isFinite(value) || value <= 0) return 0;
  return Math.min(1, Math.sqrt(value / METRICS[metric].top));
}

// Smoke tint: pale grey in clean air, yellow-brown as the reading climbs. Lighter at
// night so it still reads against the dark map.
export function hazeColor(value, theme = "light", metric = "pm25") {
  const { clean, smoke } = SMOKE_TINTS[theme] || SMOKE_TINTS.light;
  const t = hazeLevel(value, metric);
  return clean.map((c, i) => Math.round(c + (smoke[i] - c) * t));
}

export function valueAt(series, index) {
  if (!series || index < 0 || index >= series.length) return null;
  return series[index];
}

// Latest non-null value at or before index, with how many hours back it is.
export function lastKnown(series, index) {
  for (let i = Math.min(index, (series?.length ?? 0) - 1); i >= 0; i -= 1) {
    if (series[i] != null) return { value: series[i], age: index - i };
  }
  return null;
}

export function lastIndexWithData(scene) {
  if (!scene) return 0;
  for (let i = scene.hours.length - 1; i >= 0; i -= 1) {
    if (REGIONS.some((r) => scene.psi[r]?.[i] != null)) return i;
  }
  return scene.hours.length - 1;
}

export function regionAt(scene, region, index) {
  const psi = lastKnown(scene.psi[region], index);
  const pm25 = lastKnown(scene.pm25[region], index);
  return {
    region,
    psi: psi && psi.age <= 2 ? psi.value : null,
    pm25: pm25 && pm25.age <= 2 ? pm25.value : null,
    psiBand: psi && psi.age <= 2 ? bandFor(psi.value, scene.bands.psi) : null,
    pm25Band: pm25 && pm25.age <= 2 ? bandFor(pm25.value, scene.bands.pm25) : null,
  };
}

export function worstRegion(scene, index) {
  let best = REGIONS[0];
  let bestValue = -Infinity;
  for (const r of REGIONS) {
    const v = scene.psi[r]?.[index];
    if (v != null && v > bestValue) {
      bestValue = v;
      best = r;
    }
  }
  return best;
}

export function peak(scene, key) {
  let best = null;
  for (const r of REGIONS) {
    (scene[key][r] || []).forEach((v, i) => {
      if (v != null && (!best || v > best.value)) best = { value: v, region: r, index: i };
    });
  }
  return best;
}

function nationalMax(scene, key, i) {
  const values = REGIONS.map((r) => scene[key][r]?.[i]).filter((v) => v != null);
  return values.length ? Math.max(...values) : null;
}

// Key changes worth a marker for the metric shown: band changes in the worst
// region, and the peak. A change undone within an hour (normal, elevated, normal) is
// noise and is dropped; a change followed by another within an hour keeps the later.
export function findEvents(scene, metric = "pm25") {
  const order = (kind, key) => scene.bands[kind].findIndex((b) => b.key === key);
  const kinds = { psi: [], pm25: [] };
  const prev = { psi: null, pm25: null };
  scene.hours.forEach((_, i) => {
    for (const kind of [metric]) {
      const band = bandFor(nationalMax(scene, kind, i), scene.bands[kind]);
      if (!band) continue;
      const before = prev[kind];
      prev[kind] = band;
      if (!before || band.key === before.key) continue;
      const list = kinds[kind];
      const last = list[list.length - 1];
      if (last && i - last.index < 2) {
        list.pop();
        if (band.key === last.from.key) continue;
        list.push({ index: i, kind, band, from: last.from });
      } else {
        list.push({ index: i, kind, band, from: before });
      }
    }
  });
  const label = ({ kind, band, from }) => {
    const up = order(kind, band.key) > order(kind, from.key);
    const name = band.label.toLowerCase();
    if (band.key === "normal" || band.key === "good") return kind === "psi" ? "PSI back to good" : "Back to normal";
    if (kind === "psi") return `PSI ${up ? "up" : "down"} to ${name}`;
    return `${up ? "Rose" : "Down"} to ${name}`;
  };
  const events = [...kinds.psi, ...kinds.pm25].map((e) => ({ index: e.index, kind: e.kind, color: e.band.color, label: label(e) }));
  const top = peak(scene, metric);
  if (top) {
    events.push({
      index: top.index,
      kind: "peak",
      color: bandFor(top.value, scene.bands[metric])?.color,
      label: metric === "psi" ? `Peak: PSI ${top.value} in the ${top.region}` : `Peak: ${top.value} µg/m³ in the ${top.region}`,
    });
  }
  return events.sort((a, b) => a.index - b.index);
}

// Inverse-distance blend of station winds into a u/v grid (knots, towards).
export function windField(stations, hourly, index, bounds, cols = 28, rows = 18) {
  const samples = [];
  stations.forEach((s) => {
    const reading = hourly[s.name]?.[index];
    if (!reading) return;
    const [speed, dir] = reading;
    const rad = (dir * Math.PI) / 180;
    samples.push({ lng: s.lng, lat: s.lat, u: -speed * Math.sin(rad), v: -speed * Math.cos(rad) });
  });
  if (!samples.length) return null;
  const [west, south, east, north] = bounds;
  const u = new Float32Array(cols * rows);
  const v = new Float32Array(cols * rows);
  for (let y = 0; y < rows; y += 1) {
    for (let x = 0; x < cols; x += 1) {
      const lng = west + ((east - west) * x) / (cols - 1);
      const lat = north - ((north - south) * y) / (rows - 1);
      let wu = 0;
      let wv = 0;
      let wsum = 0;
      for (const s of samples) {
        const d2 = (s.lng - lng) ** 2 + (s.lat - lat) ** 2 + 1e-5;
        const w = 1 / (d2 * d2);
        wu += s.u * w;
        wv += s.v * w;
        wsum += w;
      }
      u[y * cols + x] = wu / wsum;
      v[y * cols + x] = wv / wsum;
    }
  }
  return { u, v, cols, rows, bounds };
}

export function sampleField(field, lng, lat) {
  const [west, south, east, north] = field.bounds;
  const fx = ((lng - west) / (east - west)) * (field.cols - 1);
  const fy = ((north - lat) / (north - south)) * (field.rows - 1);
  const x = Math.max(0, Math.min(field.cols - 1, Math.round(fx)));
  const y = Math.max(0, Math.min(field.rows - 1, Math.round(fy)));
  const i = y * field.cols + x;
  return [field.u[i], field.v[i]];
}

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

export function compass(deg) {
  if (deg == null) return "";
  return COMPASS[Math.round(((deg % 360) + 360) % 360 / 45) % 8];
}

const TIME = new Intl.DateTimeFormat("en-SG", {
  timeZone: "Asia/Singapore",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const DAY = new Intl.DateTimeFormat("en-SG", {
  timeZone: "Asia/Singapore",
  day: "numeric",
  month: "short",
});

export function fmtTime(iso) {
  return iso ? TIME.format(new Date(iso)) : "";
}

export function fmtDay(iso) {
  return iso ? DAY.format(new Date(iso)) : "";
}

export function fmtDayTime(iso) {
  return iso ? `${fmtDay(iso)}, ${fmtTime(iso)}` : "";
}
