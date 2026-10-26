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

// NEA advice for healthy people, reworded in plain language.
const PLAIN_ADVICE = {
  good: "Normal activities are fine.",
  moderate: "Normal activities are fine.",
  unhealthy: "Cut down on long or hard exercise outdoors.",
  very_unhealthy: "Avoid long or hard exercise outdoors.",
  hazardous: "Stay indoors as much as you can.",
  normal: "Fine for normal activities this hour.",
  elevated: "Go easier on hard exercise outdoors for the next hour.",
  high: "Avoid hard exercise outdoors for the next hour.",
  very_high: "Stay indoors where you can for the next hour.",
};

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

// Smoke tint: pale grey in clean air, yellow-brown as PM2.5 climbs. Lighter at night
// so it still reads against the dark map.
export function hazeColor(pm25, theme = "light") {
  const { clean, smoke } = SMOKE_TINTS[theme] || SMOKE_TINTS.light;
  const t = hazeDensity(pm25);
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

// Moments worth a marker: band changes in the worst region, and the PM2.5 peak.
export function findEvents(scene) {
  const events = [];
  let prevPsi = null;
  let prevPm = null;
  scene.hours.forEach((_, i) => {
    const psi = bandFor(nationalMax(scene, "psi", i), scene.bands.psi);
    const pm = bandFor(nationalMax(scene, "pm25", i), scene.bands.pm25);
    if (psi && prevPsi && psi.key !== prevPsi.key) {
      const worse = scene.bands.psi.findIndex((b) => b.key === psi.key) >
        scene.bands.psi.findIndex((b) => b.key === prevPsi.key);
      events.push({
        index: i,
        kind: "psi",
        color: psi.color,
        label: worse ? `PSI rose to ${psi.label.toLowerCase()}` : `PSI eased to ${psi.label.toLowerCase()}`,
      });
    }
    if (pm && prevPm && pm.key !== prevPm.key) {
      events.push({
        index: i,
        kind: "pm25",
        color: pm.color,
        label: `PM2.5 ${pm.label.toLowerCase()}`,
      });
    }
    if (psi) prevPsi = psi;
    if (pm) prevPm = pm;
  });
  const top = peak(scene, "pm25");
  if (top) {
    events.push({
      index: top.index,
      kind: "peak",
      color: bandFor(top.value, scene.bands.pm25)?.color,
      label: `Highest PM2.5: ${top.value} in the ${top.region}`,
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
