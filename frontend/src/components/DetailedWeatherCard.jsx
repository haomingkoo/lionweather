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
  Navigation,
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

      {/* N-Day Forecast — only render when we have data */}
      {dailyForecast.length > 0 && (
      <div
        className={`rounded-2xl backdrop-blur-2xl p-3 ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
      >
        <h3
          className={`text-xs font-semibold ${tertiaryTextColor} uppercase tracking-wide mb-2`}
        >
          {dailyForecast.length}-Day Forecast
        </h3>
        <div className="space-y-1">
          {dailyForecast.map((day, i) => {
            const badge = day.rainCategory
              ? { label: day.rainCategory, color: "text-sky-300 bg-sky-500/20" }
              : getRainBadge(day.condition);
            return (
              <div key={i} className="flex items-center justify-between py-0.5">
                <div className="flex items-center gap-2 w-24">
                  <span className={`text-sm font-medium ${textColor} w-10 shrink-0`}>
                    {day.dayName}
                  </span>
                  {badge && (
                    <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full ${badge.color}`}>
                      {badge.label}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1.5 flex-1 justify-center">
                  <span className={`text-[9px] ${tertiaryTextColor}`}>{day.source}</span>
                  <div className="h-1 w-16 bg-gradient-to-r from-blue-400 to-orange-400 rounded-full opacity-60" />
                </div>
                <div className="flex gap-2 w-14 justify-end">
                  <span className={`text-xs ${tertiaryTextColor}`}>
                    {day.low !== null ? `${Math.round(day.low)}°` : "—"}
                  </span>
                  <span className={`text-xs ${textColor} font-medium`}>
                    {day.high !== null ? `${Math.round(day.high)}°` : "—"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      )}

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

        {/* Sunset */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Sunset className={`h-4 w-4 text-orange-400`} />
            <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>Sunset</span>
          </div>
          <div className={`text-2xl font-light ${textColor}`}>{sunTimes.sunset}</div>
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

        {/* Wind */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Wind className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}>Wind</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`text-2xl font-light ${textColor}`}>{comprehensiveData?.wind_speed || 12}</div>
            <span className={`text-base ${secondaryTextColor}`}>km/h</span>
          </div>
          {comprehensiveData?.wind_direction && (
            <div className="flex items-center gap-2 mt-1">
              <Navigation className={`h-3 w-3 ${tertiaryTextColor}`}
                style={{ transform: `rotate(${comprehensiveData.wind_direction}deg)` }} />
              <span className={`text-xs ${tertiaryTextColor}`}>{comprehensiveData.wind_direction}°</span>
            </div>
          )}
          {windDesc && <p className={`text-xs ${tertiaryTextColor} mt-1 leading-snug`}>{windDesc}</p>}
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
          <div className={`text-2xl font-light ${uvColor}`}>{Math.round(uv)}</div>
          {uvDesc && <p className={`text-xs mt-1 leading-snug ${uvColor} opacity-80`}>{uvDesc}</p>}
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
