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
import { getWeatherIcon, getMockTemperature } from "../utils/weatherTheme";
import { request } from "../api/client";
import { get24HourForecast, get4DayForecast } from "../api/forecasts";
import { PrecipitationMap } from "./PrecipitationMap";
import { MLForecastComparison } from "./MLForecastComparison";

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

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const tertiaryTextColor = isDark ? "text-white/60" : "text-slate-600";

  useEffect(() => {
    const fetchComprehensiveData = async () => {
      try {
        setIsLoading(true);
        const data = await request(`/weather/comprehensive/${location.id}`);
        setComprehensiveData(data);
      } catch (err) {
        console.error("Failed to fetch comprehensive weather:", err);
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
            hourly.push({
              time:
                i === 0
                  ? "Now"
                  : hour.toLocaleTimeString("en-US", {
                      hour: "numeric",
                      hour12: true,
                    }),
              temperature:
                parseInt(getMockTemperature(location.weather.condition)) +
                Math.floor(Math.random() * 6) -
                3,
              condition: location.weather.condition,
            });
          }
          setHourlyForecast(hourly);
        }

        // Fetch 4-day forecast
        const forecast4day = await get4DayForecast();
        if (forecast4day?.forecasts) {
          const daily = forecast4day.forecasts.map((day, i) => ({
            date: day.date,
            dayName:
              i === 0
                ? "Today"
                : new Date(day.date).toLocaleDateString("en-US", {
                    weekday: "short",
                  }),
            high:
              day.temperature?.high ||
              parseInt(getMockTemperature(location.weather.condition)) + 2,
            low:
              day.temperature?.low ||
              parseInt(getMockTemperature(location.weather.condition)) - 6,
            condition: day.forecast || location.weather.condition,
          }));
          setDailyForecast(daily);
        }
      } catch (err) {
        console.error("Failed to fetch forecasts:", err);
        // Fall back to mock data
        generateMockForecasts();
      }
    };

    const generateMockForecasts = () => {
      const temperature = parseInt(
        getMockTemperature(location.weather.condition),
      );

      // Mock hourly
      const hourly = Array.from({ length: 24 }, (_, i) => {
        const hour = (new Date().getHours() + i) % 24;
        return {
          time: i === 0 ? "Now" : `${hour}:00`,
          temperature: temperature + Math.floor(Math.random() * 6) - 3,
          condition: location.weather.condition,
        };
      });
      setHourlyForecast(hourly);

      // Mock daily
      const daily = Array.from({ length: 10 }, (_, i) => {
        const date = new Date();
        date.setDate(date.getDate() + i);
        return {
          date: date.toISOString().split("T")[0],
          dayName:
            i === 0
              ? "Today"
              : date.toLocaleDateString("en-US", { weekday: "short" }),
          high: temperature + Math.floor(Math.random() * 4),
          low: temperature - 8,
          condition: location.weather.condition,
        };
      });
      setDailyForecast(daily);
    };

    fetchComprehensiveData();
    fetchForecasts();
  }, [location.id, location.weather.condition]);

  const IconComponent = iconMap[getWeatherIcon(location.weather.condition)];
  const temperature = getMockTemperature(location.weather.condition);
  const feelsLike = comprehensiveData?.temperature || parseInt(temperature) - 2;

  return (
    <div className="space-y-6">
      {/* Main Weather Display */}
      <div className="text-center py-8">
        <h2 className={`text-3xl font-semibold mb-2 ${textColor}`}>
          {location.weather.area || "Singapore"}
        </h2>
        <div
          className={`text-6xl md:text-8xl xl:text-6xl font-extralight ${textColor} my-6`}
        >
          {temperature}°
        </div>
        <div className="flex items-center justify-center gap-3 mb-2">
          {IconComponent && (
            <IconComponent
              className={`h-8 w-8 ${textColor}`}
              strokeWidth={1.5}
              aria-label={`${location.weather.condition} weather icon`}
            />
          )}
          <span className={`text-2xl ${textColor}`}>
            {location.weather.condition}
          </span>
        </div>
        <p className={`text-lg ${secondaryTextColor}`}>
          H:{parseInt(temperature) + 3}° L:{parseInt(temperature) - 5}°
        </p>
      </div>

      {/* Hourly Forecast - Horizontal Slider */}
      <div
        className={`rounded-3xl backdrop-blur-xl p-6 xl:p-4 2xl:p-5 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
      >
        <div className="flex items-center justify-between mb-4">
          <h3
            className={`text-sm font-semibold ${tertiaryTextColor} uppercase tracking-wide`}
          >
            Hourly Forecast
          </h3>
          <button
            onClick={() => setShowPrecipMap(true)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full transition-all focus:outline-none focus:ring-2 focus:ring-white/60 focus:ring-offset-2 focus:ring-offset-transparent ${isDark ? "bg-white/15 hover:bg-white/25" : "bg-white/30 hover:bg-white/40"}`}
            aria-label="Open precipitation map"
          >
            <MapPin className={`h-4 w-4 ${textColor}`} />
            <span className={`text-sm ${textColor}`}>Precipitation Map</span>
          </button>
        </div>
        {/* Horizontal scrolling container */}
        <div
          className="flex gap-4 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-white/20 scrollbar-track-transparent hover:scrollbar-thumb-white/30"
          style={{
            scrollbarWidth: "thin",
            scrollbarColor: "rgba(255, 255, 255, 0.2) transparent",
          }}
        >
          {hourlyForecast.map((hour, i) => (
            <div
              key={i}
              className={`flex flex-col items-center gap-2 min-w-[70px] p-3 rounded-2xl transition-all hover:scale-105 ${isDark ? "hover:bg-white/10" : "hover:bg-white/30"}`}
            >
              <span
                className={`text-sm font-medium ${i === 0 ? textColor : secondaryTextColor}`}
              >
                {hour.time}
              </span>
              {IconComponent && (
                <IconComponent
                  className={`h-7 w-7 ${textColor}`}
                  strokeWidth={1.5}
                  aria-label={`${hour.condition} weather icon`}
                />
              )}
              <span className={`text-lg font-semibold ${textColor}`}>
                {hour.temperature}°
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 10-Day Forecast */}
      <div
        className={`rounded-3xl backdrop-blur-xl p-6 xl:p-4 2xl:p-5 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
      >
        <h3
          className={`text-sm font-semibold ${tertiaryTextColor} uppercase tracking-wide mb-4`}
        >
          {dailyForecast.length}-Day Forecast
        </h3>
        <div className="space-y-3">
          {dailyForecast.map((day, i) => (
            <div key={i} className="flex items-center justify-between">
              <span className={`text-base font-medium ${textColor} w-16`}>
                {day.dayName}
              </span>
              <div className="flex items-center gap-3 flex-1 justify-center">
                {IconComponent && (
                  <IconComponent
                    className={`h-5 w-5 ${textColor}`}
                    strokeWidth={1.5}
                    aria-label={`${day.condition} weather icon`}
                  />
                )}
                <div className="h-1 w-32 bg-gradient-to-r from-blue-400 to-orange-400 rounded-full"></div>
              </div>
              <div className="flex gap-3 w-20 justify-end">
                <span className={`${tertiaryTextColor}`}>{day.low}°</span>
                <span className={`${textColor} font-medium`}>{day.high}°</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ML Forecast Comparison */}
      <MLForecastComparison location={location} isDark={isDark} />

      {/* Weather Details Grid */}
      <div className="grid grid-cols-2 gap-3 xl:gap-4">
        {/* Feels Like */}
        <div
          className={`rounded-3xl backdrop-blur-xl p-4 xl:p-3 2xl:p-4 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <ThermometerSun className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Feels Like
            </span>
          </div>
          <div className={`text-3xl xl:text-2xl font-light ${textColor}`}>
            {feelsLike}°
          </div>
        </div>

        {/* Humidity */}
        <div
          className={`rounded-3xl backdrop-blur-xl p-4 xl:p-3 2xl:p-4 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Droplets className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Humidity
            </span>
          </div>
          <div className={`text-3xl xl:text-2xl font-light ${textColor}`}>
            {comprehensiveData?.humidity || 75}%
          </div>
        </div>

        {/* Wind */}
        <div
          className={`rounded-3xl backdrop-blur-xl p-4 xl:p-3 2xl:p-4 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
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
            <div className={`text-3xl xl:text-2xl font-light ${textColor}`}>
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
          className={`rounded-3xl backdrop-blur-xl p-4 xl:p-3 2xl:p-4 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
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
            <div className={`text-3xl xl:text-2xl font-light ${textColor}`}>
              {comprehensiveData?.rainfall || 0}
            </div>
            <span className={`text-base ${secondaryTextColor}`}>mm</span>
          </div>
        </div>

        {/* Visibility */}
        <div
          className={`rounded-3xl backdrop-blur-xl p-4 xl:p-3 2xl:p-4 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
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
            <div className={`text-3xl xl:text-2xl font-light ${textColor}`}>
              10
            </div>
            <span className={`text-base ${secondaryTextColor}`}>km</span>
          </div>
        </div>

        {/* Pressure */}
        <div
          className={`rounded-3xl backdrop-blur-xl p-4 xl:p-3 2xl:p-4 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
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
            <div className={`text-3xl xl:text-2xl font-light ${textColor}`}>
              1013
            </div>
            <span className={`text-base ${secondaryTextColor}`}>hPa</span>
          </div>
        </div>

        {/* Sunrise */}
        <div
          className={`rounded-3xl backdrop-blur-xl p-4 xl:p-3 2xl:p-4 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Sunrise className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Sunrise
            </span>
          </div>
          <div className={`text-3xl xl:text-2xl font-light ${textColor}`}>
            7:00 AM
          </div>
        </div>

        {/* Sunset */}
        <div
          className={`rounded-3xl backdrop-blur-xl p-4 xl:p-3 2xl:p-4 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Sunset className={`h-4 w-4 ${tertiaryTextColor}`} />
            <span
              className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
            >
              Sunset
            </span>
          </div>
          <div className={`text-3xl xl:text-2xl font-light ${textColor}`}>
            7:15 PM
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
