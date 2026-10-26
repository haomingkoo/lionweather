// Rain between NEA's rain gauges: a smooth field interpolated from the gauges'
// 5-minute totals. Gauges are the only measurements; everything between them is
// interpolation, and the field fades out beyond the gauge network.

// Wide enough that the fade beyond the gauges reaches zero before the edge.
export const RAIN_BOUNDS = [103.45, 1.1, 104.25, 1.56]; // west, south, east, north
export const COVER_KM = 6;
export const DRY_MMH = 0.5;
export const SIGMA_KM = 3.5; // beyond this from the nearest gauge the field fades out
const KM_PER_DEG = 111.32;

export const RAIN_BANDS = [
  { max: 2.5, label: "Light", color: [125, 196, 240] },
  { max: 10, label: "Moderate", color: [58, 134, 214] },
  { max: 50, label: "Heavy", color: [57, 68, 184] },
  { max: Infinity, label: "Very heavy", color: [128, 52, 170] },
];

export function bandFor(mmh) {
  if (!(mmh > 0)) return null;
  return RAIN_BANDS.find((b) => mmh < b.max) || RAIN_BANDS[RAIN_BANDS.length - 1];
}

// mm in 5 minutes -> mm per hour
export const toRate = (mm5) => (mm5 == null ? null : mm5 * 12);

/**
 * Field of rain rates (mm/h) on a cols x rows grid over bounds, row 0 at the north.
 * gauges: [{lat, lng, rate}] with rate in mm/h (null readings are skipped).
 *
 * Gaussian-weighted average of the gauges (about 3.5 km wide): dry gauges pull the
 * field to zero around them, so one wet gauge does not tint the whole island.
 */
export function rainField(gauges, { bounds = RAIN_BOUNDS, cols = 160, rows = 100, sigmaKm = SIGMA_KM } = {}) {
  const pts = gauges.filter((g) => g.rate != null && Number.isFinite(g.rate));
  const out = new Float32Array(cols * rows);
  if (!pts.length) return { cols, rows, bounds, data: out, max: 0 };
  const [w, s, e, n] = bounds;
  const k = Math.cos((((s + n) / 2) * Math.PI) / 180);
  const inv2s2 = 1 / (2 * sigmaKm * sigmaKm);
  let max = 0;
  for (let r = 0; r < rows; r += 1) {
    const lat = n - ((n - s) * (r + 0.5)) / rows;
    for (let c = 0; c < cols; c += 1) {
      const lng = w + ((e - w) * (c + 0.5)) / cols;
      let num = 0;
      let den = 0;
      let nearest = Infinity;
      for (const g of pts) {
        const d = Math.hypot((g.lng - lng) * k, g.lat - lat) * KM_PER_DEG;
        nearest = Math.min(nearest, d);
        const wgt = Math.exp(-d * d * inv2s2);
        num += wgt * g.rate;
        den += wgt;
      }
      let v = den > 1e-12 ? num / den : 0;
      if (nearest > COVER_KM) v *= Math.exp(-(((nearest - COVER_KM) / 3) ** 2));
      out[r * cols + c] = v;
      max = Math.max(max, v);
    }
  }
  return { cols, rows, bounds, data: out, max };
}

// RGBA pixels for a field: transparent where dry, band colours where wet, opacity
// rising with the rate. For the 2D overlay and the 3D rain layer's texture.
export function fieldPixels(field, { alpha = 0.75 } = {}) {
  const px = new Uint8ClampedArray(field.cols * field.rows * 4);
  for (let i = 0; i < field.data.length; i += 1) {
    const v = field.data[i];
    const b = bandFor(v);
    // Below half a millimetre an hour the blend is just the tail of a distant gauge.
    if (!b || v < DRY_MMH) continue;
    const a = Math.min(1, 0.25 + Math.log10(1 + v) / 2) * alpha;
    px[i * 4] = b.color[0];
    px[i * 4 + 1] = b.color[1];
    px[i * 4 + 2] = b.color[2];
    px[i * 4 + 3] = Math.round(a * 255);
  }
  return px;
}

// Gauges at one frame, and the hour of rain up to it.
export function gaugesAt(data, frame) {
  return data.stations.map((s) => {
    const series = data.values[s.id] || [];
    const mm5 = series[frame] ?? null;
    const lastHour = series.slice(Math.max(0, frame - 11), frame + 1).filter((v) => v != null);
    return { ...s, mm5, rate: toRate(mm5), hourMm: lastHour.length ? lastHour.reduce((a, b) => a + b, 0) : null };
  });
}
