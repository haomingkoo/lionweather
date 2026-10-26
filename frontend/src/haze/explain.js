// "Why is one region worse this hour?", built only from what the page has: the
// regional ranking, wind at 850 hPa and at the surface, the wind path, and NASA fire
// detections near that path. It names a cause only when those line up.

import { capitalise, compass } from "./hazeData";
import { distanceKm, SINGAPORE } from "./smoke";

export const CORRIDOR_KM = 75;
const CALM_850_MS = 2;
const CALM_SURFACE_KN = 2;

// Rough outlines, enough to say which land the air crossed. [lon, lat].
export const LANDS = {
  Sumatra: [[95.2, 5.6], [97.5, 5.3], [98.7, 3.8], [100.3, 2.3], [101.3, 2.0], [103.0, 0.7], [103.8, -0.9], [104.6, -1.9], [106.0, -3.0], [105.9, -5.9], [104.6, -5.9], [102.3, -4.0], [100.9, -2.2], [99.2, 0.2], [97.6, 2.2], [96.0, 3.8]],
  "Peninsular Malaysia": [[100.1, 6.5], [101.1, 6.9], [102.1, 6.2], [103.4, 4.6], [103.5, 2.7], [104.3, 1.6], [103.6, 1.42], [102.6, 1.9], [101.3, 2.8], [100.6, 3.9], [100.3, 5.4]],
  Borneo: [[109.0, 1.8], [109.6, 2.1], [111.0, 1.6], [113.0, 3.2], [114.5, 4.6], [115.5, 5.3], [116.8, 7.0], [117.7, 6.0], [119.3, 5.3], [118.0, 4.3], [117.7, 2.0], [118.9, 1.0], [117.5, 0.0], [116.7, -2.0], [116.5, -3.5], [114.6, -4.1], [113.0, -3.2], [111.5, -3.5], [110.2, -2.9], [109.9, -1.3], [109.0, 0.0], [108.9, 1.0]],
  Java: [[105.2, -6.8], [106.0, -5.9], [108.3, -6.2], [110.4, -6.9], [112.6, -6.9], [114.4, -7.7], [114.4, -8.7], [111.0, -8.2], [108.0, -7.8], [106.4, -7.4]],
};

// The side of the island that air from each direction reaches first.
const FIRST_SIDE = {
  N: ["north"], NE: ["north", "east"], E: ["east"], SE: ["east", "south"],
  S: ["south"], SW: ["west", "south"], W: ["west"], NW: ["west", "north"],
};
export const DIRECTION_WORDS = {
  N: "north", NE: "northeast", E: "east", SE: "southeast", S: "south", SW: "southwest", W: "west", NW: "northwest",
};

function inRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function landAt(lat, lon) {
  return Object.keys(LANDS).find((name) => inRing(lon, lat, LANDS[name])) || null;
}

export function bearing(fromLat, fromLon, toLat, toLon) {
  const x = (toLon - fromLon) * Math.cos((((fromLat + toLat) / 2) * Math.PI) / 180);
  return ((Math.atan2(x, toLat - fromLat) * 180) / Math.PI + 360) % 360;
}

function segmentKm(lat, lon, a, b) {
  // Distance from a point to the segment a-b on a local flat projection.
  const k = Math.cos((lat * Math.PI) / 180);
  const ax = (a[1] - lon) * k;
  const ay = a[0] - lat;
  const bx = (b[1] - lon) * k;
  const by = b[0] - lat;
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  const t = len2 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2)) : 0;
  return Math.hypot(ax + t * dx, ay + t * dy) * 111.32;
}

// Path points are [lat, lon, hours_before]. Uses the first `hours` of the path.
export function pathSummary(points, { hours = 48 } = {}) {
  if (!points || points.length < 2) return null;
  const used = points.filter((p) => p[2] <= hours);
  const ref = used.find((p) => p[2] >= 12) || used[used.length - 1];
  const from = compass(bearing(SINGAPORE.lat, SINGAPORE.lon, ref[0], ref[1]));
  const lands = [];
  used.forEach((p) => {
    if (p[2] < 3) return; // the first hours are over Singapore and the Strait
    const land = landAt(p[0], p[1]);
    if (land && !lands.includes(land)) lands.push(land);
  });
  const end = used[used.length - 1];
  return { from, lands, reachKm: Math.round(distanceKm(SINGAPORE.lat, SINGAPORE.lon, end[0], end[1])), points: used };
}

export function firesNearPath(points, fires, km = CORRIDOR_KM) {
  if (!points || points.length < 2) return [];
  return fires.filter(([lat, lon]) => {
    for (let i = 1; i < points.length; i += 1) if (segmentKm(lat, lon, points[i - 1], points[i]) <= km) return true;
    return false;
  });
}

export function rankRegions(values) {
  return Object.entries(values)
    .filter(([, v]) => v != null && Number.isFinite(v))
    .map(([region, value]) => ({ region, value }))
    .sort((a, b) => b.value - a.value);
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/**
 * inputs:
 *   pm25: {region: µg/m³ | null} this hour
 *   wind850: [m/s, from°] | null   (Open-Meteo, over Singapore)
 *   surface: [knots, from°] | null (NEA stations, averaged)
 *   path: [[lat, lon, hoursBefore], ...] | null  (850 hPa back-trajectory)
 *   fires: [[lat, lon, frp, seen], ...] seen in the 24 hours before this hour
 *   firesKnown: false when the fire layer is off or unavailable
 * returns { headline, body, context, facts }
 */
export function explainHour({ pm25, wind850, surface, path, fires = [], firesKnown = true }) {
  const ranking = rankRegions(pm25 || {});
  if (ranking.length < 2) {
    return { headline: "Too few regional readings to compare.", body: null, context: null, facts: { ranking } };
  }
  const top = ranking[0];
  const low = ranking[ranking.length - 1];
  const spread = top.value - low.value;
  const similar = spread < Math.max(8, 0.2 * top.value);
  const calm = (wind850 ? wind850[0] < CALM_850_MS : true) && (surface ? surface[0] < CALM_SURFACE_KN : true);
  const summary = calm ? null : pathSummary(path);
  const near = summary && firesKnown ? firesNearPath(summary.points, fires) : [];
  const from = summary?.from || (wind850 ? compass(wind850[1]) : surface ? compass(surface[1]) : null);
  const detections = near.reduce((s, p) => s + (p[4] ?? 1), 0);
  const facts = { ranking, spread, similar, calm, from, lands: summary?.lands || [], firesOnPath: detections };

  const headline = similar
    ? "Similar across the island."
    : `${capitalise(top.region)} highest: ${top.value} vs ${low.value} µg/m³ in the ${low.region}.`;

  let body;
  // Regional wording: the sentence describes the air and the fires, not places.
  const route = from ? `the wind came from the ${DIRECTION_WORDS[from]}` : null;
  const fireCount = plural(detections, "fire");
  if (calm) {
    body = similar ? "No clear source: winds are light." : "Cause unclear: winds are light, so it looks local.";
  } else if (!from) {
    body = "Cause unclear: no wind reading this hour.";
  } else if (!summary) {
    body = `Cause unclear: ${route}; wind path not available.`;
  } else if (!firesKnown) {
    body = `Cause unclear: ${route}; fire data not available.`;
  } else if (!detections) {
    body = `Cause unclear: ${route} (no fires on its path).`;
  } else if (similar) {
    body = `Likely smoke island-wide: the wind reaching Singapore at this hour passed over ${fireCount} a day earlier.`;
  } else if (FIRST_SIDE[from].includes(top.region)) {
    body = `Likely smoke: the wind reaching Singapore at this hour passed over ${fireCount} a day earlier.`;
  } else {
    body = `Cause unclear: ${route} (${fireCount} on its path).`;
  }

  const context = !similar && top.region === "west" ? "West has industry and shipping (Jurong, Tuas)." : null;
  return { headline, body, context, facts };
}

// Runs of consecutive path segments that pass within `km` of a fire detection, as
// [first point index, last point index] pairs, for highlighting on the map.
export function fireStretches(points, fires, km = 30) {
  if (!points || points.length < 2 || !fires?.length) return [];
  const runs = [];
  let start = null;
  for (let i = 1; i < points.length; i += 1) {
    const a = points[i - 1];
    const b = points[i];
    const minLat = Math.min(a[0], b[0]) - km / 111;
    const maxLat = Math.max(a[0], b[0]) + km / 111;
    const near = fires.some(([lat, lon]) => lat >= minLat && lat <= maxLat && segmentKm(lat, lon, a, b) <= km);
    if (near && start === null) start = i - 1;
    if (!near && start !== null) {
      runs.push([start, i - 1]);
      start = null;
    }
  }
  if (start !== null) runs.push([start, points.length - 1]);
  return runs;
}
