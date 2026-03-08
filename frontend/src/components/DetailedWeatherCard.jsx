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
} from "lucide-react";
import { getWeatherIcon } from "../utils/weatherTheme";
import { request } from "../api/client";
import { get24HourForecast, get4DayForecast } from "../api/forecasts";
import { PrecipitationMap } from "./PrecipitationMap";
import { MLForecastComparison } from "./MLForecastComparison";
import { getSunTimes } from "../utils/sunTimes";
import { getCurrentWeather, get7DayForecast } from "../api/backend";

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
  const [sunTimes, setSunTimes] = useState({ sunrise: "N/A", sunset: "N/A" });
  const [openMeteoData, setOpenMeteoData] = useState({
    visibility: null,
    pressure: null,
  });

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const tertiaryTextColor = isDark ? "text-white/60" : "text-slate-600";

  // Calculate sunrise/sunset times based on location coordinates
  useEffect(() => {
    const fetchSunTimes = async () => {
      try {
        const times = await getSunTimes(location.latitude, location.longitude);
        setSunTimes(times);
      } catch (err) {
        console.error("Error calculating sun times:", err);
        // Keep default N/A values if calculation fails
      }
    };

    fetchSunTimes();
  }, [location.latitude, location.longitude]);

  // Fetch Open-Meteo data for visibility and pressure
  useEffect(() => {
    const fetchOpenMeteoData = async () => {
      try {
        const data = await getCurrentWeather(
          location.latitude,
          location.longitude,
        );
        setOpenMeteoData(data);
      } catch (err) {
        console.error("Error fetching Open-Meteo data:", err);
        // Keep default null values if fetch fails
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
        // Fetch 24-hour forecast
        const forecast24h = await get24HourForecast();
        if (forecast24h?.periods) {
          // Convert periods to hourly format
          const hourly = [];
          const now = new Date();
          for (let i = 0; i < 24; i++) {
            const hour = new Date(now.getTime() + i * 60 * 60 * 1000);
            // Find the period that covers this hour
            const period = forecast24h.periods.find((p) => {
              const periodStart = new Date(p.time.start);
              const periodEnd = new Date(p.time.end);
              return hour >= periodStart && hour < periodEnd;
            });

            // Parse temperature from period forecast text or use location's current temperature
            let temp = location.weather.temperature || "N/A";
            if (period?.temperature) {
              temp = period.temperature;
            }

            hourly.push({
              time:
                i === 0
                  ? "Now"
                  : hour.toLocaleTimeString("en-US", {
                      hour: "numeric",
                      hour12: true,
                    }),
              temperature: temp,
              condition: period?.forecast || location.weather.condition,
            });
          }
          setHourlyForecast(hourly);
        }

        // Fetch 4-day forecast from NEA
        const forecast4day = await get4DayForecast();

        // Fetch 7-day forecast from Open-Meteo
        const openMeteoForecast = await get7DayForecast(
          location.latitude,
          location.longitude,
        );

        // Hybrid approach: Use NEA for days 1-4, Open-Meteo for days 5-7
        const daily = [];

        if (forecast4day?.forecasts) {
          // Add NEA forecasts (days 1-4) with source indicator
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

        // Try ML predictions for days 5-7, fall back to Open-Meteo
        // ML endpoint returns null when model hasn't been trained yet
        let mlExtended = [];
        try {
          const mlRes = await fetch(`/api/ml/predictions/7d?country=singapore&parameter=rainfall`);
          if (mlRes.ok) {
            const mlData = await mlRes.json();
            if (Array.isArray(mlData?.predictions) && mlData.predictions.length > 4) {
              mlExtended = mlData.predictions.slice(4, 7).map((p) => ({
                date: p.date,
                dayName: new Date(p.date).toLocaleDateString("en-US", { weekday: "short" }),
                high: p.temperature_high || null,
                low: p.temperature_low || null,
                condition: p.condition || "Partly Cloudy",
                rainCategory: p.rain_category || null,
                source: "ML",
              }));
            }
          }
        } catch (_) {}

        if (mlExtended.length > 0) {
          daily.push(...mlExtended);
        } else if (openMeteoForecast.length > 4) {
          const openMeteoExtended = openMeteoForecast
            .slice(4, 7)
            .map((day) => ({
              date: day.date,
              dayName: new Date(day.date).toLocaleDateString("en-US", { weekday: "short" }),
              high: day.temperature?.high || null,
              low: day.temperature?.low || null,
              condition: day.forecast,
              source: "Open-Meteo",
            }));
          daily.push(...openMeteoExtended);
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

  const IconComponent = iconMap[getWeatherIcon(location.weather.condition)];
  const temperature = location.weather.temperature || "N/A";
  const feelsLike =
    comprehensiveData?.temperature ||
    (temperature !== "N/A" ? parseInt(temperature) - 2 : "N/A");

  return (
    <div className="space-y-3">
      {/* Error — subtle inline note, not a big banner */}
      {error && (
        <p className="text-white/40 text-xs px-1">{error} — showing cached data</p>
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
          className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin scrollbar-thumb-white/20 scrollbar-track-transparent hover:scrollbar-thumb-white/30"
          style={{
            scrollbarWidth: "thin",
            scrollbarColor: "rgba(255, 255, 255, 0.2) transparent",
          }}
        >
          {hourlyForecast.map((hour, i) => (
            <div
              key={i}
              className={`flex flex-col items-center gap-1 min-w-[50px] p-2 rounded-xl transition-all duration-200 hover:scale-105 ${isDark ? "hover:bg-white/10" : "hover:bg-white/30"}`}
            >
              <span
                className={`text-xs font-medium ${i === 0 ? textColor : secondaryTextColor}`}
              >
                {hour.time}
              </span>
              {IconComponent && (
                <IconComponent
                  className={`h-5 w-5 ${textColor}`}
                  strokeWidth={1.5}
                  aria-label={`${hour.condition} weather icon`}
                />
              )}
              <span className={`text-sm font-semibold ${textColor}`}>
                {hour.temperature}°
              </span>
            </div>
          ))}
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
        {/* Feels Like */}
        <div
          className={`rounded-2xl backdrop-blur-2xl p-2 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-1 mb-1">
            <ThermometerSun className={`h-3 w-3 ${tertiaryTextColor}`} />
            <span
              className={`text-[10px] ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Feels Like
            </span>
          </div>
          <div className={`text-xl font-light ${textColor}`}>{feelsLike}°</div>
        </div>

        {/* Humidity */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Droplets className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Humidity
            </span>
          </div>
          <div
            className={`text-2xl xl:text-2xl 2xl:text-2xl font-light ${textColor}`}
          >
            {comprehensiveData?.humidity || 75}%
          </div>
        </div>

        {/* Wind */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Wind className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Wind
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={`text-2xl xl:text-2xl 2xl:text-2xl font-light ${textColor}`}
            >
              {comprehensiveData?.wind_speed || 12}
            </div>
            <span className={`text-base ${secondaryTextColor}`}>km/h</span>
          </div>
          {comprehensiveData?.wind_direction && (
            <div className="flex items-center gap-2 mt-1">
              <Navigation
                className={`h-3 w-3 ${tertiaryTextColor}`}
                style={{
                  transform: `rotate(${comprehensiveData.wind_direction}deg)`,
                }}
              />
              <span className={`text-xs ${tertiaryTextColor}`}>
                {comprehensiveData.wind_direction}°
              </span>
            </div>
          )}
        </div>

        {/* Rainfall */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <CloudRain className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Rainfall
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={`text-2xl xl:text-2xl 2xl:text-2xl font-light ${textColor}`}
            >
              {comprehensiveData?.rainfall || 0}
            </div>
            <span className={`text-base ${secondaryTextColor}`}>mm</span>
          </div>
        </div>

        {/* Visibility */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Eye className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Visibility
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={`text-2xl xl:text-2xl 2xl:text-2xl font-light ${textColor}`}
            >
              {openMeteoData.visibility !== null
                ? openMeteoData.visibility
                : "N/A"}
            </div>
            {openMeteoData.visibility !== null && (
              <span className={`text-base ${secondaryTextColor}`}>km</span>
            )}
          </div>
          <div className={`text-[9px] ${tertiaryTextColor} mt-1`}>
            Open-Meteo
          </div>
        </div>

        {/* Pressure */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Gauge className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Pressure
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={`text-2xl xl:text-2xl 2xl:text-2xl font-light ${textColor}`}
            >
              {openMeteoData.pressure !== null ? openMeteoData.pressure : "N/A"}
            </div>
            {openMeteoData.pressure !== null && (
              <span className={`text-base ${secondaryTextColor}`}>hPa</span>
            )}
          </div>
          <div className={`text-[9px] ${tertiaryTextColor} mt-1`}>
            Open-Meteo
          </div>
        </div>

        {/* Sunrise */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Sunrise className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Sunrise
            </span>
          </div>
          <div
            className={`text-2xl xl:text-2xl 2xl:text-2xl font-light ${textColor}`}
          >
            {sunTimes.sunrise}
          </div>
        </div>

        {/* Sunset */}
        <div
          className={`rounded-3xl backdrop-blur-2xl p-3 xl:p-3 2xl:p-3 transition-all duration-200  ${isDark ? "bg-white/10 border border-white/30" : "bg-white/25 border border-white/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Sunset className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Sunset
            </span>
          </div>
          <div
            className={`text-2xl xl:text-2xl 2xl:text-2xl font-light ${textColor}`}
          >
            {sunTimes.sunset}
          </div>
        </div>
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
