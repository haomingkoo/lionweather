import SunCalc from "suncalc";

// Singapore coordinates (default)
const SINGAPORE_LAT = 1.3521;
const SINGAPORE_LNG = 103.8198;

const _fmt = (date) =>
  date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

/**
 * Calculate sunrise/sunset synchronously (SunCalc is pure JS, no API needed).
 * Use this for useState initialisation to avoid a layout-shift render cycle.
 */
export function getSunTimesSync(
  latitude = SINGAPORE_LAT,
  longitude = SINGAPORE_LNG,
) {
  try {
    const times = SunCalc.getTimes(new Date(), latitude, longitude);
    return { sunrise: _fmt(times.sunrise), sunset: _fmt(times.sunset) };
  } catch {
    return { sunrise: "N/A", sunset: "N/A" };
  }
}

/**
 * Calculate sunrise and sunset times using the SunCalc library (client-side, no external API).
 * Kept for backwards compatibility — prefer getSunTimesSync where possible.
 */
export async function getSunTimes(
  latitude = SINGAPORE_LAT,
  longitude = SINGAPORE_LNG,
) {
  return getSunTimesSync(latitude, longitude);
}
