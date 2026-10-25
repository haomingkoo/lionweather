// NEA band colours. Text labels always accompany the colour.
export const BAND_STYLES = {
  good: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
  normal: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
  moderate: "bg-sky-500/20 text-sky-200 border-sky-400/40",
  elevated: "bg-yellow-500/20 text-yellow-100 border-yellow-400/40",
  unhealthy: "bg-orange-500/25 text-orange-100 border-orange-400/50",
  high: "bg-orange-500/25 text-orange-100 border-orange-400/50",
  very_unhealthy: "bg-red-500/25 text-red-100 border-red-400/50",
  very_high: "bg-red-500/25 text-red-100 border-red-400/50",
  hazardous: "bg-purple-600/30 text-purple-100 border-purple-400/50",
};

export const BAND_STROKE = {
  good: "#34d399",
  moderate: "#38bdf8",
  unhealthy: "#fb923c",
  very_unhealthy: "#f87171",
  hazardous: "#c084fc",
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
