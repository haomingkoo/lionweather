import SunCalc from "suncalc";

// Singapore coordinates (default)
const SINGAPORE_LAT = 1.3521;
const SINGAPORE_LNG = 103.8198;

/**
 * Calculate sunrise and sunset times based on coordinates and current date
 * Primary approach: Sunrise-Sunset.org API
 * Fallback: suncalc library calculation
 * Last resort: "N/A"
 *
 * @param {number} latitude - Latitude coordinate (defaults to Singapore)
 * @param {number} longitude - Longitude coordinate (defaults to Singapore)
 * @returns {Promise<Object>} Object containing sunrise and sunset times formatted as strings
 */
export async function getSunTimes(
  latitude = SINGAPORE_LAT,
  longitude = SINGAPORE_LNG,
) {
  // Format times to 12-hour format with AM/PM
  const formatTime = (date) => {
    return date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  };

  // Primary approach: Try Sunrise-Sunset.org API
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

    const response = await fetch(
      `https://api.sunrise-sunset.org/json?lat=${latitude}&lng=${longitude}&formatted=0`,
      { signal: controller.signal },
    );
    clearTimeout(timeoutId);

    if (response.ok) {
      const data = await response.json();
      if (data.status === "OK") {
        const sunrise = new Date(data.results.sunrise);
        const sunset = new Date(data.results.sunset);

        return {
          sunrise: formatTime(sunrise),
          sunset: formatTime(sunset),
        };
      }
    }
  } catch (err) {
    console.warn(
      "Sunrise-Sunset.org API failed, falling back to suncalc:",
      err.message,
    );
  }

  // Fallback: Use suncalc library for client-side calculation
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

  // Last resort: Return N/A
  return {
    sunrise: "N/A",
    sunset: "N/A",
  };
}
