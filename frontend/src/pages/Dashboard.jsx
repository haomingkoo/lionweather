import { useState } from "react";
import { LocationForm } from "../components/LocationForm";
import { EnhancedLocationList } from "../components/EnhancedLocationList";
import { WeatherMap } from "../components/WeatherMap";
import { MLDashboard } from "../components/MLDashboard";
import { ViewToggle } from "../components/ViewToggle";
import { useLocations } from "../hooks/useLocations";
import { getWeatherGradient, isDarkGradient } from "../utils/weatherTheme";
import { useTheme } from "../contexts/ThemeContext";

export function Dashboard() {
  const [view, setView] = useState("list");
  const { locations } = useLocations();
  const { theme } = useTheme();

  // Get gradient based on most recent location and current theme
  const mostRecentLocation = locations[0];
  const isThemeDark = theme === "dark";
  const gradient = getWeatherGradient(
    mostRecentLocation?.weather?.condition,
    isThemeDark,
  );
  const isDark = isDarkGradient(mostRecentLocation?.weather?.condition);
  const textColor = isDark ? "text-white" : "text-slate-900";

  return (
    <div
      className={`min-h-screen bg-gradient-to-br ${gradient} transition-all duration-500 ease-in-out`}
    >
      {/* Glassmorphism Header */}
      <header className="sticky top-0 z-50 border-b border-white/20 backdrop-blur-xl bg-white/10 shadow-lg">
        <div className="mx-auto max-w-2xl px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1
                className={`text-3xl font-extralight ${textColor} tracking-tight`}
              >
                Weather
              </h1>
              <p
                className={`text-sm mt-1 ${isDark ? "text-white/70" : "text-slate-700/80"}`}
              >
                Your locations at a glance
              </p>
            </div>
            <ViewToggle view={view} onViewChange={setView} isDark={isDark} />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 md:px-6 py-10">
        <div className="space-y-6">
          {view === "list" && <LocationForm isDark={isDark} />}
          {view === "list" && <EnhancedLocationList isDark={isDark} />}
          {view === "map" && <WeatherMap isDark={isDark} />}
          {view === "ml" && <MLDashboard isDark={isDark} />}
        </div>
      </main>
    </div>
  );
}
