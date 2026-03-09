import { useState, useEffect } from "react";
import { LocationForm } from "../components/LocationForm";
import { EnhancedLocationList } from "../components/EnhancedLocationList";
import { WeatherMap } from "../components/WeatherMap";
import { MLAnalysisDashboard } from "../components/MLAnalysisDashboard";
import { GeolocationPrompt } from "../components/GeolocationPrompt";
import { AnimatedBackground } from "../components/AnimatedBackground";
import { useLocations } from "../hooks/useLocations";
import { Github } from "lucide-react";

export function Dashboard() {
  const [view, setView] = useState("list");
  const [showGeolocationPrompt, setShowGeolocationPrompt] = useState(false);
  const {
    locations,
    getGeolocationPermissionState,
    addLocationFromGeolocation,
  } = useLocations();

  // Check if user has a current location (from geolocation)
  const hasCurrentLocation = locations.some(
    (loc) => loc.source === "geolocation",
  );

  // Check if we should show the geolocation prompt on mount
  useEffect(() => {
    const permissionState = getGeolocationPermissionState();
    // Show prompt only if no permission state exists (first visit)
    if (!permissionState) {
      setShowGeolocationPrompt(true);
    }
  }, [getGeolocationPermissionState]);

  const handleLocationDetected = async (coords) => {
    try {
      await addLocationFromGeolocation(coords);
      setShowGeolocationPrompt(false);
    } catch (error) {
      console.error("Failed to add location from geolocation:", error);
      // Keep prompt open so user can try again or dismiss
    }
  };

  const handleDismissPrompt = () => {
    setShowGeolocationPrompt(false);
  };

  const handleAddCurrentLocation = () => {
    setShowGeolocationPrompt(true);
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

      {/* Geolocation Prompt */}
      {showGeolocationPrompt && (
        <GeolocationPrompt
          onLocationDetected={handleLocationDetected}
          onDismiss={handleDismissPrompt}
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
        <h1 className="text-5xl font-bold mb-4">
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
                {!hasCurrentLocation && locations.length > 0 && (
                  <button
                    onClick={handleAddCurrentLocation}
                    className="w-full px-4 py-2 rounded-xl bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-blue-300 text-sm font-medium transition-all"
                  >
                    📍 Use my location
                  </button>
                )}
              </div>
            }
          />
        )}
        <div className="max-w-6xl mx-auto">
          {view === "map" && <WeatherMap />}
          {view === "ml" && <MLAnalysisDashboard isDark={true} />}
        </div>
      </div>
    </div>
  );
}
