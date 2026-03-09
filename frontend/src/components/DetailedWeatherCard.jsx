import { useState, useEffect } from "react";
import {
  Sun,
  CloudRain,
  CloudLightning,
  Cloud,
  Cloudy,
  CloudSun,
  Wind,
  Droplets,
  Eye,
  Gauge,
  Sunrise,
  Sunset,
  ThermometerSun,
  MapPin,
  Zap,
} from "lucide-react";
import { getWeatherIcon } from "../utils/weatherTheme";
import { request } from "../api/client";
import { get4DayForecast } from "../api/forecasts";
import { PrecipitationMap } from "./PrecipitationMap";
import { MLForecastComparison } from "./MLForecastComparison";
import { getSunTimesSync } from "../utils/sunTimes";
import { getCurrentWeather, get7DayForecast, getHourlyForecast } from "../api/backend";

// Map WMO weather codes to simple condition strings
function wmoToCondition(code) {
  if (code === 0) return "Clear";
  if (code <= 3) return "Partly Cloudy";
  if (code <= 48) return "Cloudy";
  if (code <= 67) return "Rain";
  if (code <= 82) return "Showers";
  if (code <= 99) return "Thunderstorm";
  return "Cloudy";
}

// Generate Apple Weather-style commentary from current conditions
function generateCommentary({ condition, temperature, humidity, uv_index, sunTimes }) {
  const c = (condition || "").toLowerCase();
  const hour = new Date().getHours();
  const isDaytime = hour >= 6 && hour < 20;
  const lines = [];

  if (c.includes("thunder") || c.includes("storm")) {
    lines.push("Thunderstorm conditions — stay indoors and avoid open areas.");
  } else if (c.includes("heavy rain") || c.includes("heavy shower")) {
    lines.push("Heavy rain expected. Carry an umbrella and watch for flash floods.");
  } else if (c.includes("rain") || c.includes("shower") || c.includes("drizzle")) {
    lines.push("Showers likely. Keep an umbrella handy when heading out.");
  } else if (c.includes("cloudy") || c.includes("overcast") || c.includes("haze")) {
    lines.push("Overcast skies with little sunshine today.");
  } else if (c.includes("partly")) {
    lines.push("Partly cloudy with sunny intervals. A brief shower is possible.");
  } else if (c.includes("sunny") || c.includes("clear") || c.includes("fair")) {
    lines.push("Clear skies and plenty of sunshine today.");
  } else {
    lines.push("Conditions are relatively stable throughout the day.");
  }

  if (temperature !== null && temperature !== undefined) {
    const t = Math.round(temperature);
    if (t >= 35) lines.push(`Very hot at ${t}°C — stay hydrated and limit time outdoors.`);
    else if (t >= 32) lines.push(`Warm at ${t}°C with high humidity making it feel hotter.`);
    else if (t <= 25) lines.push(`A comfortable ${t}°C — pleasant for outdoor activities.`);
  }

  if (uv_index !== null && uv_index !== undefined && isDaytime) {
    const uv = Math.round(uv_index);
    if (uv >= 11) lines.push(`Extreme UV index (${uv}) — sunscreen and shade are essential.`);
    else if (uv >= 8) lines.push(`Very high UV (${uv}) — apply SPF 50+ before heading outside.`);
    else if (uv >= 6) lines.push(`High UV index (${uv}) — consider sunscreen for extended outdoor time.`);
  }

  if (humidity !== null && humidity !== undefined) {
    const h = Math.round(humidity);
    if (h >= 85) lines.push(`Humidity at ${h}% will make it feel oppressively muggy.`);
    else if (h >= 70) lines.push(`At ${h}% humidity it will feel noticeably sticky.`);
  }

  if (sunTimes?.sunset && sunTimes.sunset !== "N/A") {
    const now = new Date();
    const parts = sunTimes.sunset.match(/(\d+):(\d+)\s*(AM|PM)/i);
    if (parts) {
      let sh = parseInt(parts[1]);
      const sm = parseInt(parts[2]);
      const meridiem = parts[3].toUpperCase();
      if (meridiem === "PM" && sh !== 12) sh += 12;
      if (meridiem === "AM" && sh === 12) sh = 0;
      const minsToSunset = sh * 60 + sm - (now.getHours() * 60 + now.getMinutes());
      if (minsToSunset > 0 && minsToSunset <= 90) {
        lines.push(`Sunset in about ${minsToSunset} min at ${sunTimes.sunset}.`);
      }
    }
  }

  return lines;
}

const iconMap = {
  Sun,
  CloudRain,
  CloudLightning,
  Cloud,
  Cloudy,
  CloudSun,
};

export function DetailedWeatherCard({ location, isDark = false }) {
  const [comprehensiveData, setComprehensiveData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hourlyForecast, setHourlyForecast] = useState([]);
  const [dailyForecast, setDailyForecast] = useState([]);
  const [showPrecipMap, setShowPrecipMap] = useState(false);
  const [error, setError] = useState(null);
  // Compute synchronously — SunCalc is pure JS, no API call needed, so no layout shift
  const [sunTimes] = useState(() =>
    getSunTimesSync(location.latitude, location.longitude),
  );
  const [openMeteoData, setOpenMeteoData] = useState({
    visibility: null,
    pressure: null,
    uv_index: null,
  });

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const tertiaryTextColor = isDark ? "text-white/60" : "text-slate-600";

  // Fetch Open-Meteo data for visibility, pressure, and UV index
  useEffect(() => {
    const fetchOpenMeteoData = async () => {
      try {
        const data = await getCurrentWeather(
          location.latitude,
          location.longitude,
        );
        setOpenMeteoData({
          visibility: data.visibility ?? null,
          pressure: data.pressure ?? null,
          uv_index: data.uv_index ?? null,
        });
      } catch (err) {
        console.error("Error fetching Open-Meteo data:", err);
      }
    };

    fetchOpenMeteoData();
  }, [location.latitude, location.longitude]);

  useEffect(() => {
    const fetchComprehensiveData = async () => {
      try {
        setIsLoading(true);
        const data = await request(
          `/weather/comprehensive/${location.id}?lat=${location.latitude}&lng=${location.longitude}`,
        );
        setComprehensiveData(data);
      } catch (err) {
        // Silently handle error - non-critical
      } finally {
        setIsLoading(false);
      }
    };

    const fetchForecasts = async () => {
      try {
        // Fetch hourly forecast from Open-Meteo (real per-hour temperatures)
        const hourlyData = await getHourlyForecast(location.latitude, location.longitude);
        if (hourlyData.length > 0) {
          const now = new Date();
          const hourly = hourlyData.slice(0, 24).map((slot, i) => ({
            time: i === 0
              ? "Now"
              : slot.time.toLocaleTimeString("en-US", { hour: "numeric", hour12: true }),
            temperature: slot.temperature !== null ? Math.round(slot.temperature) : null,
            condition: wmoToCondition(slot.weather_code),
            precip_prob: slot.precip_prob,
            isActualTime: slot.time,
          }));
          setHourlyForecast(hourly);
        }

        // Fetch 4-day forecast from NEA
        const forecast4day = await get4DayForecast();

        // Fetch 7-day forecast from Open-Meteo
        const openMeteoForecast = await get7DayForecast(
          location.latitude,
          location.longitude,
        );

        // Hybrid: NEA 4-day (primary) + Open-Meteo extension for days 5-7
        const daily = [];

        if (forecast4day?.forecasts) {
          const neaForecasts = forecast4day.forecasts
            .slice(0, 4)
            .map((day, i) => ({
              date: day.date,
              dayName:
                i === 0
                  ? "Today"
                  : new Date(day.date).toLocaleDateString("en-US", {
                      weekday: "short",
                    }),
              high: day.temperature?.high || null,
              low: day.temperature?.low || null,
              condition: day.forecast || location.weather.condition,
              source: "NEA",
            }));
          daily.push(...neaForecasts);
        }

        // Extend with Open-Meteo days 5-7 (skip dates already covered by NEA)
        if (openMeteoForecast.length > 0) {
          const neaDates = new Set(daily.map((d) => d.date));
          const extended = openMeteoForecast
            .filter((d) => !neaDates.has(d.date))
            .slice(0, 3)
            .map((day) => ({
              date: day.date,
              dayName: new Date(day.date).toLocaleDateString("en-US", { weekday: "short" }),
              high: day.temperature?.high || null,
              low: day.temperature?.low || null,
              condition: day.forecast,
              source: "Open-Meteo",
            }));
          daily.push(...extended);
        }

        // Fallback: all Open-Meteo if NEA failed
        if (daily.length === 0 && openMeteoForecast.length > 0) {
          openMeteoForecast.slice(0, 7).forEach((day) => {
            daily.push({
              date: day.date,
              dayName: new Date(day.date).toLocaleDateString("en-US", { weekday: "short" }),
              high: day.temperature?.high || null,
              low: day.temperature?.low || null,
              condition: day.forecast,
              source: "Open-Meteo",
            });
          });
        }

        setDailyForecast(daily);
      } catch (err) {
        setError("Unable to refresh weather data");
      }
    };

    fetchComprehensiveData();
    fetchForecasts();
  }, [
    location.id,
    location.weather.condition,
    location.latitude,
    location.longitude,
  ]);

  // Map NEA condition text → rain category badge
  const getRainBadge = (condition) => {
    const c = (condition || "").toLowerCase();
    if (c.includes("thunder")) return { label: "Thundery", color: "text-purple-300 bg-purple-500/20" };
    if (c.includes("heavy")) return { label: "Heavy Rain", color: "text-blue-300 bg-blue-500/20" };
    if (c.includes("shower") || c.includes("rain") || c.includes("drizzle"))
      return { label: "Rain", color: "text-sky-300 bg-sky-500/20" };
    if (c.includes("fair") || c.includes("sunny") || c.includes("clear"))
      return { label: "Dry", color: "text-amber-300 bg-amber-500/20" };
    return null;
  };

  const temperature = location.weather.temperature || "N/A";
  const feelsLike =
    comprehensiveData?.temperature ||
    (temperature !== "N/A" ? parseInt(temperature) - 2 : "N/A");

  // Apple Weather-style contextual descriptions
  const humidity = comprehensiveData?.humidity || location.weather?.humidity || null;
  const dewPoint = (temperature !== "N/A" && humidity)
    ? Math.round(parseFloat(temperature) - ((100 - humidity) / 5))
    : null;
  const humidityDesc = humidity
    ? humidity >= 85 ? "Very muggy — feels sticky"
    : humidity >= 70 ? `Dew point is ${dewPoint}°C`
    : humidity >= 50 ? "Comfortable humidity"
    : "Dry air today"
    : null;

  const vis = openMeteoData.visibility;
  const visibilityDesc = vis !== null
    ? vis >= 20 ? "Perfectly clear view."
    : vis >= 10 ? "Good visibility."
    : vis >= 5 ? "Slightly hazy."
    : "Poor visibility — haze or fog."
    : null;

  const pressure = openMeteoData.pressure;
  const pressureDesc = pressure !== null
    ? pressure >= 1013 ? "Normal — stable conditions."
    : pressure >= 1005 ? "Slightly low — change possible."
    : "Low pressure — rain likely."
    : null;

  const uv = openMeteoData.uv_index;
  const uvDesc = uv !== null
    ? uv >= 11 ? "Extreme — stay indoors."
    : uv >= 8 ? `Very high — use SPF 50+ outside.`
    : uv >= 6 ? `High — apply sunscreen if out long.`
    : uv >= 3 ? `Moderate — consider sunscreen.`
    : "Low — no protection needed."
    : null;
  const uvColor = uv !== null
    ? uv >= 11 ? "text-purple-300"
    : uv >= 8 ? "text-red-400"
    : uv >= 6 ? "text-orange-400"
    : uv >= 3 ? "text-yellow-400"
    : "text-green-400"
    : "text-white/60";

  const windSpeed = comprehensiveData?.wind_speed;
  const windDesc = windSpeed !== null && windSpeed !== undefined
    ? windSpeed >= 40 ? "Strong winds — take care outside."
    : windSpeed >= 20 ? "Breezy conditions."
    : windSpeed >= 10 ? "Light breeze."
    : "Calm winds."
    : null;

  const rainfall = comprehensiveData?.rainfall;
  const rainfallDesc = rainfall !== null && rainfall !== undefined
    ? rainfall >= 10 ? "Heavy downpour — seek shelter."
    : rainfall >= 2.5 ? "Moderate rain ongoing."
    : rainfall > 0 ? "Light drizzle."
    : "No active rainfall."
    : null;

  // Parse a time string like "7:18 PM" → minutes since midnight
  const parseTimeStr = (s) => {
    const m = (s || "").match(/^(\d+):(\d+)\s*(AM|PM)$/i);
    if (!m) return null;
    let h = parseInt(m[1], 10);
    const min = parseInt(m[2], 10);
    if (m[3].toUpperCase() === "PM" && h !== 12) h += 12;
    if (m[3].toUpperCase() === "AM" && h === 12) h = 0;
    return h * 60 + min;
  };

  // Sunset arc progress (0–1) based on current time between sunrise and sunset
  const sunriseMin = parseTimeStr(sunTimes.sunrise);
  const sunsetMin  = parseTimeStr(sunTimes.sunset);
  const nowMin     = new Date().getHours() * 60 + new Date().getMinutes();
  const sunProgress = (sunriseMin !== null && sunsetMin !== null && sunsetMin > sunriseMin)
    ? Math.max(0, Math.min(1, (nowMin - sunriseMin) / (sunsetMin - sunriseMin)))
    : 0.5;

  // UV — "Use sun protection until X" (2h before sunset for UV≥3, 1h for UV≥6)
  const uvProtectionUntil = (() => {
    if (uv === null || uv < 3 || sunsetMin === null) return null;
    const offsetMins = uv >= 6 ? 60 : 120;
    const safeMin = sunsetMin - offsetMins;
    const sh = Math.floor(safeMin / 60);
    const sm = safeMin % 60;
    const period = sh >= 12 ? "PM" : "AM";
    const displayH = sh > 12 ? sh - 12 : sh === 0 ? 12 : sh;
    return `${displayH}:${sm.toString().padStart(2, "0")} ${period}`;
  })();

  // Next rainy day from forecast
  const nextRainDay = (() => {
    if (!dailyForecast.length) return null;
    const rainy = dailyForecast.find((d, i) => {
      if (i === 0) return false; // skip today
      const c = (d.condition || "").toLowerCase();
      return c.includes("rain") || c.includes("shower") || c.includes("thunder");
    });
    return rainy ? rainy.dayName : null;
  })();

  // Wind direction degrees
  const windDir = comprehensiveData?.wind_direction ?? null;
  const windDirLabel = (() => {
    if (windDir === null) return null;
    const dirs = ["N","NE","E","SE","S","SW","W","NW"];
    return dirs[Math.round(windDir / 45) % 8];
  })();

  // Generate commentary once we have data
  const commentary = generateCommentary({
    condition: location.weather.condition,
    temperature: location.weather.temperature,
    humidity: comprehensiveData?.humidity,
    uv_index: openMeteoData.uv_index,
    sunTimes,
  });

  return (
    <div className="space-y-3">
      {/* Error — subtle inline note, not a big banner */}
      {error && (
        <p className="text-white/40 text-xs px-1">{error} — showing cached data</p>
      )}

      {/* Weather Commentary — Apple Weather style */}
      {commentary.length > 0 && (
        <div className={`rounded-2xl backdrop-blur-2xl px-4 py-3 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}>
          {commentary.map((line, i) => (
            <p key={i} className={`text-sm leading-relaxed ${i === 0 ? textColor : secondaryTextColor} ${i > 0 ? "mt-1" : ""}`}>
              {line}
            </p>
          ))}
        </div>
      )}

      {/* Hourly Forecast - Horizontal Slider */}
      <div
        className={`rounded-2xl backdrop-blur-2xl p-3 ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
      >
        <div className="flex items-center justify-between mb-2">
          <h3
            className={`text-xs font-semibold ${tertiaryTextColor} uppercase tracking-wide`}
          >
            Hourly Forecast
          </h3>
          <button
            onClick={() => setShowPrecipMap(true)}
            className={`flex items-center gap-1 px-2 py-1 rounded-full transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-white/60 focus:ring-offset-2 focus:ring-offset-transparent ${isDark ? "bg-white/15 hover:bg-white/25" : "bg-white/30 hover:bg-white/40"}`}
            aria-label="Open precipitation map"
          >
            <MapPin className={`h-3 w-3 ${textColor}`} />
            <span className={`text-xs ${textColor}`}>Map</span>
          </button>
        </div>
        {/* Horizontal scrolling container */}
        <div
          className="flex gap-2 overflow-x-auto pb-1"
          style={{
            scrollbarWidth: "thin",
            scrollbarColor: "rgba(255, 255, 255, 0.2) transparent",
          }}
        >
          {(() => {
            // Build a merged list: hourly slots + sunrise/sunset inserted chronologically
            const slots = hourlyForecast.map((hour, i) => ({
              type: "hour",
              sortKey: hour.isActualTime ? hour.isActualTime.getTime() : i * 3_600_000,
              data: hour,
              origIndex: i,
            }));

            // Parse "7:14 AM" / "7:19 PM" → today's Date for sorting
            function parseSunTime(str) {
              if (!str || str === "N/A") return null;
              const m = str.match(/^(\d+):(\d+)\s*(AM|PM)$/i);
              if (!m) return null;
              let h = parseInt(m[1], 10);
              const min = parseInt(m[2], 10);
              const ap = m[3].toUpperCase();
              if (ap === "PM" && h !== 12) h += 12;
              if (ap === "AM" && h === 12) h = 0;
              const d = new Date();
              d.setHours(h, min, 0, 0);
              return d;
            }

            const riseDate = parseSunTime(sunTimes.sunrise);
            const setDate  = parseSunTime(sunTimes.sunset);
            const nowSlot  = new Date();
            if (riseDate && riseDate > nowSlot) slots.push({ type: "sunrise", sortKey: riseDate.getTime(), data: riseDate });
            if (setDate  && setDate  > nowSlot) slots.push({ type: "sunset",  sortKey: setDate.getTime(),  data: setDate });

            slots.sort((a, b) => a.sortKey - b.sortKey);

            return slots.map((slot, i) => {
              if (slot.type === "sunrise") {
                return (
                  <div key="sunrise" className={`flex flex-col items-center gap-1 min-w-[52px] p-2 rounded-xl ${isDark ? "bg-amber-500/10" : "bg-amber-100/30"}`}>
                    <span className="text-xs font-medium text-amber-300">Rise</span>
                    <Sunrise className="h-5 w-5 text-amber-400" strokeWidth={1.5} />
                    <span className="text-xs font-semibold text-amber-300">{sunTimes.sunrise}</span>
                    <span className="text-[9px] text-transparent select-none">0%</span>
                  </div>
                );
              }
              if (slot.type === "sunset") {
                return (
                  <div key="sunset" className={`flex flex-col items-center gap-1 min-w-[52px] p-2 rounded-xl ${isDark ? "bg-orange-500/10" : "bg-orange-100/30"}`}>
                    <span className="text-xs font-medium text-orange-300">Set</span>
                    <Sunset className="h-5 w-5 text-orange-400" strokeWidth={1.5} />
                    <span className="text-xs font-semibold text-orange-300">{sunTimes.sunset}</span>
                    <span className="text-[9px] text-transparent select-none">0%</span>
                  </div>
                );
              }
              const hour = slot.data;
              const idx  = slot.origIndex;
              const hourIconKey = getWeatherIcon(hour.condition);
              const HourIcon = iconMap[hourIconKey];
              return (
                <div
                  key={idx}
                  className={`flex flex-col items-center gap-1 min-w-[52px] p-2 rounded-xl transition-all duration-200 ${isDark ? "hover:bg-white/10" : "hover:bg-white/30"}`}
                >
                  <span className={`text-xs font-medium ${idx === 0 ? textColor : secondaryTextColor}`}>
                    {hour.time}
                  </span>
                  {HourIcon ? (
                    <HourIcon className={`h-5 w-5 ${textColor}`} strokeWidth={1.5} />
                  ) : (
                    <Sun className={`h-5 w-5 ${textColor}`} strokeWidth={1.5} />
                  )}
                  <span className={`text-sm font-semibold ${textColor}`}>
                    {hour.temperature !== null ? `${hour.temperature}°` : "—"}
                  </span>
                  {/* Always show precip prob for consistent row height */}
                  <span className={`text-[9px] font-medium ${hour.precip_prob ? "text-sky-300" : "text-transparent"}`}>
                    {hour.precip_prob != null ? `${hour.precip_prob}%` : "0%"}
                  </span>
                </div>
              );
            });
          })()}
        </div>
      </div>

      {/* N-Day Forecast — Apple Weather style */}
      {dailyForecast.length > 0 && (() => {
        const validLows  = dailyForecast.map(d => d.low).filter(v => v !== null);
        const validHighs = dailyForecast.map(d => d.high).filter(v => v !== null);
        const weekMin = validLows.length  ? Math.min(...validLows)  : 24;
        const weekMax = validHighs.length ? Math.max(...validHighs) : 34;
        const weekRange = Math.max(weekMax - weekMin, 1);
        return (
          <div className={`rounded-2xl backdrop-blur-2xl p-3 ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}>
            <h3 className={`text-xs font-semibold ${tertiaryTextColor} uppercase tracking-wide mb-2`}>
              {dailyForecast.length}-Day Forecast
            </h3>
            <div className="space-y-0.5">
              {dailyForecast.map((day, i) => {
                const iconKey = getWeatherIcon(day.condition);
                const DayIcon = iconMap[iconKey] || Cloud;
                const isRainy = ["CloudRain", "CloudLightning"].includes(iconKey);
                const iconColor = iconKey === "Sun" ? "text-amber-400"
                  : iconKey === "CloudSun" ? "text-amber-300"
                  : iconKey === "CloudLightning" ? "text-purple-400"
                  : "text-sky-300";
                const low  = day.low  !== null ? Math.round(day.low)  : null;
                const high = day.high !== null ? Math.round(day.high) : null;
                const barLeft  = low  !== null ? ((low  - weekMin) / weekRange) * 100 : 0;
                const barWidth = (low !== null && high !== null) ? ((high - low) / weekRange) * 100 : 0;
                return (
                  <div key={i} className="flex items-center gap-2 py-0.5">
                    {/* Day name */}
                    <span className={`text-sm font-medium ${textColor} w-9 shrink-0`}>
                      {day.dayName}
                    </span>
                    {/* Weather icon */}
                    <div className="w-8 flex flex-col items-center shrink-0">
                      <DayIcon className={`h-4 w-4 ${iconColor}`} strokeWidth={1.5} />
                      {isRainy && (
                        <span className="text-[9px] text-sky-300 leading-none mt-0.5">
                          {day.rainCategory ? day.rainCategory.replace("Thundery","") || "—" : "—"}
                        </span>
                      )}
                    </div>
                    {/* Low temp */}
                    <span className={`text-xs ${tertiaryTextColor} w-6 text-right shrink-0`}>
                      {low !== null ? `${low}°` : "—"}
                    </span>
                    {/* Proportional range bar */}
                    <div className="flex-1 relative h-1.5 rounded-full overflow-hidden" style={{ background: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)" }}>
                      <div
                        className="absolute h-full rounded-full"
                        style={{
                          left: `${barLeft}%`,
                          width: `${Math.max(barWidth, 4)}%`,
                          background: "linear-gradient(to right, #fb923c, #f59e0b)",
                        }}
                      />
                    </div>
                    {/* High temp */}
                    <span className={`text-xs font-semibold ${textColor} w-6 shrink-0`}>
                      {high !== null ? `${high}°` : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* ML Forecast Comparison */}
      <MLForecastComparison location={location} isDark={isDark} />

      {/* Weather Details Grid */}
      <div className="grid grid-cols-2 gap-2">
        {/* Sunrise — only show if sunrise hasn't passed yet */}
        {(() => {
          if (sunTimes.sunrise === "N/A") return null;
          const m = sunTimes.sunrise.match(/^(\d+):(\d+)\s*(AM|PM)$/i);
          if (m) {
            let h = parseInt(m[1], 10);
            const min = parseInt(m[2], 10);
            if (m[3].toUpperCase() === "PM" && h !== 12) h += 12;
            if (m[3].toUpperCase() === "AM" && h === 12) h = 0;
            const sunriseDate = new Date();
            sunriseDate.setHours(h, min, 0, 0);
            if (new Date() > sunriseDate) return null;
          }
          return (
            <div
              className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
            >
              <div className="flex items-center gap-2 mb-2">
                <Sunrise className={`h-4 w-4 text-amber-400`} />
                <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>Sunrise</span>
              </div>
              <div className={`text-2xl font-light ${textColor}`}>{sunTimes.sunrise}</div>
            </div>
          );
        })()}

        {/* Sunset — arc */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 transition-all duration-200 ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-1">
            <Sunset className="h-4 w-4 text-orange-400" />
            <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>Sunset</span>
          </div>
          <div className={`text-2xl font-light ${textColor} mb-2`}>{sunTimes.sunset}</div>
          {/* Arc SVG */}
          <svg viewBox="0 0 100 55" width="100%" className="overflow-visible">
            {/* Horizon line */}
            <line x1="5" y1="50" x2="95" y2="50" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
            {/* Arc path */}
            <path d="M 5,50 A 45,45 0 0 1 95,50" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" />
            {/* Progress arc (orange) */}
            {(() => {
              const prog = Math.min(sunProgress, 0.999);
              const ex = 50 - 45 * Math.cos(prog * Math.PI);
              const ey = 50 - 45 * Math.sin(prog * Math.PI);
              return (
                <>
                  <path d={`M 5,50 A 45,45 0 0 1 ${ex},${ey}`}
                    fill="none" stroke="rgba(251,146,60,0.6)" strokeWidth="1.5" />
                  {/* Sun dot */}
                  <circle cx={ex} cy={ey} r="4" fill="#fb923c" opacity="0.9" />
                  <circle cx={ex} cy={ey} r="7" fill="rgba(251,146,60,0.2)" />
                </>
              );
            })()}
            {/* Sunrise label */}
            <text x="5" y="58" fontSize="6" fill="rgba(255,255,255,0.35)" textAnchor="middle" fontFamily="sans-serif">
              {sunTimes.sunrise !== "N/A" ? sunTimes.sunrise : ""}
            </text>
            {/* Sunset label */}
            <text x="95" y="58" fontSize="6" fill="rgba(255,255,255,0.35)" textAnchor="middle" fontFamily="sans-serif">
              {sunTimes.sunset !== "N/A" ? sunTimes.sunset : ""}
            </text>
          </svg>
        </div>

        {/* Feels Like */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <ThermometerSun className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>
              Feels Like
            </span>
          </div>
          <div className={`text-2xl font-light ${textColor}`}>{feelsLike}°</div>
        </div>

        {/* Humidity */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Droplets className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>Humidity</span>
          </div>
          <div className={`text-2xl font-light ${textColor}`}>
            {comprehensiveData?.humidity || 75}%
          </div>
          {humidityDesc && <p className={`text-xs ${tertiaryTextColor} mt-1 leading-snug`}>{humidityDesc}</p>}
        </div>

        {/* Wind — compass dial */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 transition-all duration-200 ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Wind className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>Wind</span>
          </div>
          <div className="flex items-center gap-3">
            {/* Compass SVG */}
            <svg viewBox="0 0 100 100" width="72" height="72" className="shrink-0">
              <circle cx="50" cy="50" r="44" stroke="rgba(255,255,255,0.12)" strokeWidth="1" fill="none" />
              <circle cx="50" cy="50" r="38" stroke="rgba(255,255,255,0.08)" strokeWidth="1" fill="none" />
              {/* Cardinal ticks */}
              {[0,45,90,135,180,225,270,315].map(deg => {
                const r = (deg - 90) * Math.PI / 180;
                const inner = deg % 90 === 0 ? 33 : 37;
                return <line key={deg}
                  x1={50 + inner * Math.cos(r)} y1={50 + inner * Math.sin(r)}
                  x2={50 + 43 * Math.cos(r)} y2={50 + 43 * Math.sin(r)}
                  stroke={deg % 90 === 0 ? "rgba(255,255,255,0.4)" : "rgba(255,255,255,0.15)"}
                  strokeWidth={deg % 90 === 0 ? 1.5 : 0.8} />;
              })}
              {/* N/S/E/W labels */}
              <text x="50" y="11" textAnchor="middle" fontSize="8" fontWeight="600" fill="rgba(255,255,255,0.85)" fontFamily="sans-serif">N</text>
              <text x="50" y="96" textAnchor="middle" fontSize="7" fill="rgba(255,255,255,0.35)" fontFamily="sans-serif">S</text>
              <text x="92" y="53" textAnchor="middle" fontSize="7" fill="rgba(255,255,255,0.35)" fontFamily="sans-serif">E</text>
              <text x="8"  y="53" textAnchor="middle" fontSize="7" fill="rgba(255,255,255,0.35)" fontFamily="sans-serif">W</text>
              {/* Arrow needle */}
              {windDir !== null && (() => {
                const rad = (windDir - 90) * Math.PI / 180;
                const tipX = 50 + 28 * Math.cos(rad);
                const tipY = 50 + 28 * Math.sin(rad);
                const tailX = 50 - 14 * Math.cos(rad);
                const tailY = 50 - 14 * Math.sin(rad);
                // Arrowhead perpendicular points
                const perpRad = rad + Math.PI / 2;
                const hw = 4;
                const ahX1 = tipX - 8 * Math.cos(rad) + hw * Math.cos(perpRad);
                const ahY1 = tipY - 8 * Math.sin(rad) + hw * Math.sin(perpRad);
                const ahX2 = tipX - 8 * Math.cos(rad) - hw * Math.cos(perpRad);
                const ahY2 = tipY - 8 * Math.sin(rad) - hw * Math.sin(perpRad);
                return (
                  <g>
                    <line x1={tailX} y1={tailY} x2={tipX} y2={tipY} stroke="white" strokeWidth="2" strokeLinecap="round" opacity="0.9" />
                    <polygon points={`${tipX},${tipY} ${ahX1},${ahY1} ${ahX2},${ahY2}`} fill="white" opacity="0.9" />
                    <line x1="50" y1="50" x2={tailX} y2={tailY} stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" strokeLinecap="round" />
                  </g>
                );
              })()}
              {/* Center dot */}
              <circle cx="50" cy="50" r="3" fill="white" opacity="0.6" />
            </svg>
            {/* Speed + direction label */}
            <div>
              <div className="flex items-baseline gap-1">
                <span className={`text-2xl font-light ${textColor}`}>{comprehensiveData?.wind_speed ?? 12}</span>
                <span className={`text-sm ${secondaryTextColor}`}>km/h</span>
              </div>
              {windDirLabel && <p className={`text-xs ${tertiaryTextColor}`}>{windDirLabel} · {windDir}°</p>}
              {windDesc && <p className={`text-xs ${tertiaryTextColor} mt-1 leading-snug`}>{windDesc}</p>}
            </div>
          </div>
        </div>

        {/* Rainfall */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <CloudRain className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>Rainfall</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`text-2xl font-light ${textColor}`}>{comprehensiveData?.rainfall || 0}</div>
            <span className={`text-base ${secondaryTextColor}`}>mm</span>
          </div>
          {rainfallDesc && <p className={`text-xs ${tertiaryTextColor} mt-1 leading-snug`}>{rainfallDesc}</p>}
          {rainfall === 0 && nextRainDay && (
            <p className={`text-xs ${tertiaryTextColor} mt-0.5 leading-snug`}>
              Next expected on {nextRainDay}.
            </p>
          )}
        </div>

        {/* Visibility */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Eye className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>Visibility</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`text-2xl font-light ${textColor}`}>
              {vis !== null ? vis : "N/A"}
            </div>
            {vis !== null && <span className={`text-base ${secondaryTextColor}`}>km</span>}
          </div>
          {visibilityDesc && <p className={`text-xs ${tertiaryTextColor} mt-1 leading-snug`}>{visibilityDesc}</p>}
        </div>

        {/* Pressure */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Gauge className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>Pressure</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`text-2xl font-light ${textColor}`}>
              {pressure !== null ? pressure : "N/A"}
            </div>
            {pressure !== null && <span className={`text-base ${secondaryTextColor}`}>hPa</span>}
          </div>
          {pressureDesc && <p className={`text-xs ${tertiaryTextColor} mt-1 leading-snug`}>{pressureDesc}</p>}
        </div>

        {/* UV Index */}
        {uv !== null && (
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Zap className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>UV Index</span>
          </div>
          <div className="flex items-baseline gap-2">
            <div className={`text-2xl font-light ${uvColor}`}>{Math.round(uv)}</div>
            {uvDesc && <span className={`text-xs ${uvColor} opacity-80`}>{uvDesc.split("—")[0].trim()}</span>}
          </div>
          {uvProtectionUntil && (
            <p className={`text-xs ${tertiaryTextColor} mt-0.5 leading-snug`}>
              Use sun protection until {uvProtectionUntil}.
            </p>
          )}
          {/* UV bar */}
          <div className="mt-2 h-1.5 rounded-full overflow-hidden" style={{ background: "linear-gradient(to right, #22c55e, #eab308, #f97316, #ef4444, #a855f7)" }}>
            <div className="h-full w-1 bg-white rounded-full opacity-90" style={{ marginLeft: `${Math.min(Math.round(uv) / 12 * 100, 96)}%` }} />
          </div>
        </div>
        )}
      </div>

      {/* Precipitation Map Modal */}
      {showPrecipMap && (
        <PrecipitationMap
          location={location}
          onClose={() => setShowPrecipMap(false)}
          isDark={isDark}
        />
      )}
    </div>
  );
}
