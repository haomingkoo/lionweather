// NEA band colours as text tokens. The band word always accompanies the colour.
export const BAND_TEXT = {
  good: "text-good",
  normal: "text-good",
  moderate: "text-ink",
  elevated: "text-warn",
  unhealthy: "text-warn",
  high: "text-warn",
  very_unhealthy: "text-bad",
  very_high: "text-bad",
  hazardous: "text-bad",
};

export const BAND_STROKE = {
  good: "rgb(var(--good))",
  moderate: "rgb(var(--accent))",
  unhealthy: "rgb(var(--warn))",
  very_unhealthy: "rgb(var(--bad))",
  hazardous: "rgb(var(--bad))",
};

const SGT_TIME = new Intl.DateTimeFormat("en-SG", {
  timeZone: "Asia/Singapore",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function formatSgtTime(iso) {
  if (!iso) return null;
  return `${SGT_TIME.format(new Date(iso))} SGT`;
}

export function pickLocation(locations = []) {
  return locations.find((l) => l.source === "geolocation") || locations[0] || null;
}

// Nearest NEA region label point; null means national.
export function nearestRegion(location, regions = []) {
  if (!location || location.latitude == null || !regions.length) return null;
  let best = null;
  let bestDist = Infinity;
  for (const r of regions) {
    const d = (r.lat - location.latitude) ** 2 + (r.lng - location.longitude) ** 2;
    if (d < bestDist) {
      bestDist = d;
      best = r;
    }
  }
  return best;
}

// PSI series for one region, or the national max across regions.
export function psiSeries(points = [], region = null) {
  return points
    .map((p) => {
      const values = region
        ? [p.regions?.[region]?.psi_24h]
        : Object.values(p.regions || {}).map((r) => r.psi_24h);
      const valid = values.filter((v) => typeof v === "number");
      return valid.length ? Math.max(...valid) : null;
    })
    .filter((v) => v != null);
}
