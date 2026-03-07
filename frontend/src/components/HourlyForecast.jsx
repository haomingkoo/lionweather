import { useRef } from "react";
import { Cloud, CloudRain, Sun, Wind } from "lucide-react";

export function HourlyForecast({ forecast = [], isDark = false }) {
  const scrollRef = useRef(null);

  // Generate mock hourly data if no forecast provided
  const hourlyData = forecast.length > 0 ? forecast : generateMockHourlyData();

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/70" : "text-slate-600";

  return (
    <div
      className={`rounded-[2rem] backdrop-blur-xl p-6 shadow-2xl ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
    >
      <h3 className={`text-xl font-semibold ${textColor} mb-4`}>
        Hourly Forecast
      </h3>

      <div
        ref={scrollRef}
        className="flex gap-4 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-white/20 scrollbar-track-transparent"
        style={{
          scrollbarWidth: "thin",
          scrollbarColor: isDark
            ? "rgba(255,255,255,0.2) transparent"
            : "rgba(0,0,0,0.2) transparent",
        }}
      >
        {hourlyData.map((hour, index) => (
          <div
            key={index}
            className={`flex-shrink-0 w-20 text-center rounded-2xl p-4 transition-all hover:scale-105 ${isDark ? "bg-white/10 hover:bg-white/15" : "bg-white/30 hover:bg-white/40"}`}
          >
            <div className={`text-sm font-medium ${secondaryTextColor} mb-2`}>
              {hour.time}
            </div>
            <div className="flex justify-center mb-2">
              {getWeatherIcon(hour.condition, isDark)}
            </div>
            <div className={`text-2xl font-light ${textColor} mb-1`}>
              {hour.temp}°
            </div>
            <div className={`text-xs ${secondaryTextColor}`}>
              {hour.condition}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function getWeatherIcon(condition, isDark) {
  const iconColor = isDark ? "text-white/80" : "text-slate-700";
  const lowerCondition = condition.toLowerCase();

  if (lowerCondition.includes("rain") || lowerCondition.includes("shower")) {
    return <CloudRain className={`h-8 w-8 ${iconColor}`} />;
  } else if (lowerCondition.includes("cloud")) {
    return <Cloud className={`h-8 w-8 ${iconColor}`} />;
  } else if (lowerCondition.includes("wind")) {
    return <Wind className={`h-8 w-8 ${iconColor}`} />;
  } else {
    return <Sun className={`h-8 w-8 ${iconColor}`} />;
  }
}

function generateMockHourlyData() {
  const hours = [];
  const now = new Date();
  const conditions = ["Sunny", "Cloudy", "Partly Cloudy", "Light Rain"];

  for (let i = 0; i < 24; i++) {
    const hour = new Date(now.getTime() + i * 60 * 60 * 1000);
    const temp = 25 + Math.floor(Math.random() * 8);
    const condition = conditions[Math.floor(Math.random() * conditions.length)];

    hours.push({
      time: hour.toLocaleTimeString("en-US", {
        hour: "numeric",
        hour12: true,
      }),
      temp,
      condition,
    });
  }

  return hours;
}
