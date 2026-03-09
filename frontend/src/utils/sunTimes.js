import SunCalc from "suncalc";

// Singapore coordinates (default)
const SINGAPORE_LAT = 1.3521;
const SINGAPORE_LNG = 103.8198;

/**
 * Calculate sunrise and sunset times using the SunCalc library (client-side, no external API).
 *
 * @param {number} latitude - Latitude coordinate (defaults to Singapore)
 * @param {number} longitude - Longitude coordinate (defaults to Singapore)
 * @returns {Promise<Object>} Object containing sunrise and sunset times formatted as strings
 */
export async function getSunTimes(
  latitude = SINGAPORE_LAT,
  longitude = SINGAPORE_LNG,
) {
  const formatTime = (date) => {
    return date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  };

  try {
    const now = new Date();
    const times = SunCalc.getTimes(now, latitude, longitude);

    return {
      sunrise: formatTime(times.sunrise),
      sunset: formatTime(times.sunset),
    };
  } catch (err) {
    console.error("Error calculating sun times with suncalc:", err);
  }

  return {
    sunrise: "N/A",
    sunset: "N/A",
  };
}
