import { useState } from "react";
import { LocationForm } from "../components/LocationForm";
import { EnhancedLocationList } from "../components/EnhancedLocationList";
import { WeatherMap } from "../components/WeatherMap";
import { MLAnalysisDashboard } from "../components/MLAnalysisDashboard";
import { MLLiveForecast } from "../components/MLLiveForecast";
import { AnimatedBackground } from "../components/AnimatedBackground";
import { useLocations } from "../hooks/useLocations";
import { Github, Bell, BellOff } from "lucide-react";

export function Dashboard() {
  const [view, setView] = useState("list");
  const [geoLoading, setGeoLoading] = useState(false);
  const [geoError, setGeoError] = useState(null);
  const {
    locations,
    addLocationFromGeolocation,
    rainNotifyEnabled,
    setRainNotifyEnabled,
  } = useLocations();

  // Check if user has a current location (from geolocation)
  const hasCurrentLocation = locations.some(
    (loc) => loc.source === "geolocation",
  );

  // Directly request geolocation — one browser prompt, no custom toast
  const handleAddCurrentLocation = () => {
    if (!navigator.geolocation) {
      setGeoError("Not supported by your browser.");
      return;
    }
    setGeoLoading(true);
    setGeoError(null);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          await addLocationFromGeolocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        } catch (err) {
          setGeoError("Could not load weather for your location.");
        } finally {
          setGeoLoading(false);
        }
      },
      () => {
        setGeoError("Location access denied.");
        setGeoLoading(false);
      },
      { timeout: 10000, maximumAge: 300000, enableHighAccuracy: false },
    );
  };

  return (
    <div className="min-h-screen bg-[#0a0e1a] text-white relative">
      {/* Animated Background */}
      {locations.length > 0 && locations[0]?.weather?.forecast && (
        <AnimatedBackground
          condition={locations[0].weather.forecast}
          isDark={true}
        />
      )}


      {/* Header matching Handwriting Lab style */}
      <header className="border-b border-slate-800">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <div className="flex items-center justify-between">
            {/* HK Logo - links to kooexperience.com */}
            <a
              href="https://kooexperience.com/"
              className="text-2xl font-bold hover:text-blue-400 transition-colors"
            >
              HK
            </a>

            {/* Navigation */}
            <nav className="flex items-center gap-6">
              <a
                href="https://kooexperience.com/"
                className="text-slate-400 hover:text-white transition-colors"
              >
                Home
              </a>
              <a
                href="https://github.com/haomingkoo/lionweather"
                target="_blank"
                rel="noopener noreferrer"
                className="text-slate-400 hover:text-white transition-colors flex items-center gap-2"
              >
                <Github className="w-5 h-5" />
                GitHub
              </a>
            </nav>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <div className="mx-auto max-w-6xl px-6 py-12">
        <h1 className="text-5xl font-bold mb-4 bg-gradient-to-r from-white via-blue-100 to-indigo-300 bg-clip-text text-transparent">
          LionWeather Lab
        </h1>
        <p className="text-slate-400 text-lg mb-8">
          Singapore weather intelligence — NEA real-time data, ML-powered
          rainfall forecasting, and radar.
        </p>

        {/* View Toggle Tabs */}
        <div className="flex gap-4 mb-8">
          <button
            onClick={() => setView("list")}
            className={`px-6 py-2 rounded-full border transition-all ${
              view === "list"
                ? "bg-blue-600 border-blue-600 text-white"
                : "border-slate-700 text-slate-400 hover:border-slate-600"
            }`}
          >
            LOCATIONS
          </button>
          <button
            onClick={() => setView("map")}
            className={`px-6 py-2 rounded-full border transition-all ${
              view === "map"
                ? "bg-blue-600 border-blue-600 text-white"
                : "border-slate-700 text-slate-400 hover:border-slate-600"
            }`}
          >
            MAP VIEW
          </button>
          <button
            onClick={() => setView("ml")}
            className={`px-6 py-2 rounded-full border transition-all ${
              view === "ml"
                ? "bg-blue-600 border-blue-600 text-white"
                : "border-slate-700 text-slate-400 hover:border-slate-600"
            }`}
          >
            ML DASHBOARD
          </button>
        </div>

        {/* Content */}
        {view === "list" && (
          <EnhancedLocationList
            isDark={true}
            sidebarHeader={
              <div className="space-y-3">
                <LocationForm compact />
                {!hasCurrentLocation && (
                  <div>
                    <button
                      onClick={handleAddCurrentLocation}
                      disabled={geoLoading}
                      className="w-full px-4 py-2 rounded-xl bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-blue-300 text-sm font-medium transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      {geoLoading ? (
                        <span className="w-3.5 h-3.5 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" />
                      ) : (
                        "📍"
                      )}
                      {geoLoading ? "Detecting…" : "Use my location"}
                    </button>
                    {geoError ? (
                      <p className="text-red-400 text-[11px] mt-1 text-center">{geoError}</p>
                    ) : (
                      <p className="text-slate-500 text-[11px] mt-1 text-center">Your location stays in your browser — never sent to our servers.</p>
                    )}
                  </div>
                )}
                {/* Rain notification toggle */}
                <button
                  onClick={() => setRainNotifyEnabled(!rainNotifyEnabled)}
                  className={`w-full px-4 py-2 rounded-xl border text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                    rainNotifyEnabled
                      ? "bg-indigo-600/20 border-indigo-500/30 text-indigo-300 hover:bg-indigo-600/30"
                      : "bg-white/5 border-white/10 text-slate-400 hover:bg-white/10"
                  }`}
                >
                  {rainNotifyEnabled ? <Bell className="w-3.5 h-3.5" /> : <BellOff className="w-3.5 h-3.5" />}
                  {rainNotifyEnabled ? "Rain alerts on" : "Enable rain alerts"}
                </button>
                {rainNotifyEnabled && (
                  <p className="text-slate-500 text-[11px] text-center">
                    You'll be notified when rain is likely in the next 1–2 hours.
                  </p>
                )}
              </div>
            }
          />
        )}
        <div className="max-w-6xl mx-auto">
          {view === "map" && <WeatherMap />}
          {view === "ml" && (
            <div className="space-y-8">
              <MLLiveForecast />
              <MLAnalysisDashboard isDark={true} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
