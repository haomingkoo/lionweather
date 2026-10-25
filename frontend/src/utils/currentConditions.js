// Hero helpers: every number here comes from one observation, never a default.

// "7:14 AM" -> minutes since midnight
export function parseClock(str) {
  const m = (str || "").match(/^(\d+):(\d+)\s*(AM|PM)$/i);
  if (!m) return null;
  let h = parseInt(m[1], 10);
  const min = parseInt(m[2], 10);
  const ap = m[3].toUpperCase();
  if (ap === "PM" && h !== 12) h += 12;
  if (ap === "AM" && h === 12) h = 0;
  return h * 60 + min;
}

export function isNightAt(now, sunTimes) {
  const mins = now.getHours() * 60 + now.getMinutes();
  const rise = parseClock(sunTimes?.sunrise);
  const set = parseClock(sunTimes?.sunset);
  if (rise === null || set === null) return mins < 7 * 60 || mins >= 19 * 60 + 10;
  return mins < rise || mins >= set;
}

const num = (v) => (v === null || v === undefined || v === "" ? NaN : parseFloat(v));

// Heat index (Steadman/Rothfusz, Celsius). Null when either input is missing.
export function feelsLike(temperature, humidity) {
  const T = num(temperature);
  const RH = num(humidity);
  if (isNaN(T) || isNaN(RH)) return null;
  if (T < 27) return Math.round(T);
  const HI =
    -8.78469 + 1.61139 * T + 2.33855 * RH
    - 0.14612 * T * RH - 0.01231 * T * T
    - 0.01642 * RH * RH + 0.00221 * T * T * RH
    + 0.00073 * T * RH * RH - 0.0000036 * T * T * RH * RH;
  return Math.round(HI);
}

export function generateCommentary({ condition, temperature, humidity, uv_index, sunTimes, now = new Date() }) {
  const c = (condition || "").toLowerCase();
  const night = isNightAt(now, sunTimes);
  const lines = [];

  if (c.includes("thunder") || c.includes("storm")) {
    lines.push("Thunderstorms. Stay indoors and away from open areas.");
  } else if (c.includes("heavy rain") || c.includes("heavy shower")) {
    lines.push("Heavy rain. Carry an umbrella and watch for flash floods.");
  } else if (c.includes("rain") || c.includes("shower") || c.includes("drizzle")) {
    lines.push("Showers likely. Keep an umbrella handy when heading out.");
  } else if (c.includes("partly")) {
    lines.push(night ? "Partly cloudy tonight." : "Partly cloudy with sunny intervals.");
  } else if (c.includes("cloudy") || c.includes("overcast") || c.includes("haze") || c.includes("fog")) {
    lines.push(night ? "Cloudy tonight." : "Overcast, with little sunshine.");
  } else if (c.includes("sunny") || c.includes("clear") || c.includes("fair")) {
    lines.push(night ? "Clear tonight." : "Clear skies and plenty of sunshine.");
  }

  const t = num(temperature);
  if (!isNaN(t)) {
    const r = Math.round(t);
    if (r >= 35) lines.push(`Very hot at ${r}°C. Drink water and limit time outdoors.`);
    else if (r >= 32) lines.push(`Warm at ${r}°C, and the humidity makes it feel hotter.`);
  }

  const uv = num(uv_index);
  if (!isNaN(uv) && !night) {
    const u = Math.round(uv);
    if (u >= 11) lines.push(`Extreme UV (${u}). Sunscreen and shade are essential.`);
    else if (u >= 8) lines.push(`Very high UV (${u}). Use SPF 50+ before heading out.`);
    else if (u >= 6) lines.push(`High UV (${u}). Wear sunscreen if you are out for long.`);
  }

  const h = num(humidity);
  if (!isNaN(h)) {
    const r = Math.round(h);
    if (r >= 85) lines.push(`Humidity ${r}%. Feels close.`);
    else if (r >= 70) lines.push(`Humidity ${r}%. Noticeably sticky.`);
  }

  const set = parseClock(sunTimes?.sunset);
  if (set !== null) {
    const minsToSunset = set - (now.getHours() * 60 + now.getMinutes());
    if (minsToSunset > 0 && minsToSunset <= 90) {
      lines.push(`Sunset in about ${minsToSunset} min at ${sunTimes.sunset}.`);
    }
  }

  return lines;
}
