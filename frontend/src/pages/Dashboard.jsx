import { useState } from "react";
import { LocationForm } from "../components/LocationForm";
import { EnhancedLocationList } from "../components/EnhancedLocationList";
import { WeatherMap } from "../components/WeatherMap";
import { MLDashboard } from "../components/MLDashboard";
import { ViewToggle } from "../components/ViewToggle";
import { useLocations } from "../hooks/useLocations";
import { Github } from "lucide-react";

export function Dashboard() {
  const [view, setView] = useState("list");
  const { locations } = useLocations();

  return (
    <div className="min-h-screen bg-[#0a0e1a] text-white">
      {/* Header matching Handwriting Lab style */}
      <header className="border-b border-slate-800">
        <div className="mx-auto max-w-7xl px-6 py-4">
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
      <div className="mx-auto max-w-7xl px-6 py-12">
        <h1 className="text-5xl font-bold mb-4">
          LionWeather <span className="text-blue-400">Lab</span>
        </h1>
        <p className="text-slate-400 text-lg mb-8">
          AI-powered weather forecasting for Singapore, Malaysia, and Indonesia
          with real-time data.
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
        <div className="space-y-6">
          {view === "list" && (
            <>
              <LocationForm />
              <EnhancedLocationList />
            </>
          )}
          {view === "map" && <WeatherMap />}
          {view === "ml" && <MLDashboard />}
        </div>
      </div>
    </div>
  );
}
