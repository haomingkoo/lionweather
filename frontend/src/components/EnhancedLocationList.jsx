import { useState, useEffect } from "react";
import {
  useLocations,
  useRefreshLocation,
  useDeleteLocation,
} from "../hooks/useLocations.jsx";
import { DetailedWeatherCard } from "./DetailedWeatherCard";
import { AnimatedBackground } from "./AnimatedBackground";
import { RefreshCw, Trash2, Navigation } from "lucide-react";

function getRelativeTime(isoTimestamp) {
  if (!isoTimestamp) return "Unknown";
  const now = Date.now();
  const fetchedTime = new Date(isoTimestamp).getTime();
  const diffMs = now - fetchedTime;
  if (diffMs < 0 || diffMs < 60000) return "Just now";
  const diffMinutes = Math.floor(diffMs / 60000);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}

// Map weather condition string to a gradient for the card background
function conditionGradient(condition = "") {
  const c = condition.toLowerCase();
  if (c.includes("thunder") || c.includes("storm"))
    return "from-slate-700 to-slate-900";
  if (c.includes("heavy rain") || c.includes("moderate rain"))
    return "from-blue-700 to-slate-800";
  if (c.includes("rain") || c.includes("shower") || c.includes("drizzle"))
    return "from-blue-500 to-blue-800";
  if (c.includes("cloud") || c.includes("overcast") || c.includes("haze"))
    return "from-slate-500 to-slate-700";
  if (c.includes("clear") || c.includes("sunny") || c.includes("fair"))
    return "from-sky-400 to-blue-600";
  if (c.includes("partly"))
    return "from-sky-500 to-slate-600";
  return "from-indigo-500 to-slate-700";
}

// Compact Apple Weather-style sidebar card
function LocationCard({ location, isSelected, onClick, onDelete, isRefreshing }) {
  const gradient = conditionGradient(location.weather?.condition);
  const isCurrentLocation = location.source === "geolocation";
  const areaName = location.weather?.area || location.name || "Unknown Area";

  return (
    <button
      onClick={onClick}
      className={`relative w-full text-left rounded-2xl overflow-hidden transition-all duration-200 group ${
        isSelected
          ? "ring-2 ring-white/60 shadow-xl scale-[1.01]"
          : "hover:scale-[1.01] hover:ring-1 hover:ring-white/30"
      }`}
    >
      <div className={`bg-gradient-to-br ${gradient} p-4`}>
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5">
              {isCurrentLocation && (
                <Navigation className="h-3 w-3 text-white/80 shrink-0" />
              )}
              <span className="text-white/70 text-xs font-medium truncate">
                {isCurrentLocation ? "My Location" : "Saved Location"}
              </span>
            </div>
            <h3 className="text-white font-semibold text-base leading-tight truncate">
              {areaName}
            </h3>
            <p className="text-white/80 text-xs mt-0.5 truncate">
              {location.weather?.condition || "—"}
            </p>
          </div>
          <div className="text-right ml-2 shrink-0">
            <div className="text-white text-3xl font-thin leading-none">
              {location.weather?.temperature != null
                ? `${Math.round(location.weather.temperature)}°`
                : "—"}
            </div>
            {(location.weather?.tempHigh != null || location.weather?.tempLow != null) && (
              <div className="text-white/70 text-xs mt-1">
                H:{location.weather.tempHigh ?? "—"}° L:{location.weather.tempLow ?? "—"}°
              </div>
            )}
          </div>
        </div>

        {/* Refresh spinner overlay */}
        {isRefreshing && (
          <div className="absolute top-2 right-2">
            <RefreshCw className="h-3 w-3 text-white/60 animate-spin" />
          </div>
        )}
      </div>

      {/* Delete button - appears on hover */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-black/40 hover:bg-red-500/70 rounded-full p-1"
        aria-label="Delete location"
      >
        <Trash2 className="h-3 w-3 text-white" />
      </button>
    </button>
  );
}

export function EnhancedLocationList({ isDark = false, sidebarHeader = null }) {
  const { locations, isLoading, error } = useLocations();
  const { refresh, isPending, refreshingId } = useRefreshLocation();
  const { deleteLocation, isPending: isDeleting } = useDeleteLocation();
  const [selectedId, setSelectedId] = useState(null);
  const [, setUpdateTrigger] = useState(0);

  // Auto-select first location
  useEffect(() => {
    if (locations.length > 0 && !selectedId) {
      setSelectedId(locations[0].id);
    }
  }, [locations, selectedId]);

  // Auto-update timestamps every minute
  useEffect(() => {
    const interval = setInterval(() => setUpdateTrigger((p) => p + 1), 60000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="rounded-3xl backdrop-blur-xl px-12 py-8 shadow-2xl bg-white/15 border border-white/25">
          <p className="text-white text-lg animate-pulse">Loading locations...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="rounded-3xl backdrop-blur-xl px-12 py-8 shadow-2xl bg-red-500/40 border border-red-400/50">
          <p className="text-lg text-red-50">{error.message}</p>
        </div>
      </div>
    );
  }

  if (locations.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="rounded-3xl backdrop-blur-xl px-12 py-8 shadow-2xl text-center bg-white/15 border border-white/25">
          <p className="text-white text-lg mb-2">No locations yet</p>
          <p className="text-white/80">Add your first location above to get started</p>
        </div>
      </div>
    );
  }

  const selectedLocation = locations.find((l) => l.id === selectedId) || locations[0];

  return (
    <div className="max-w-7xl mx-auto px-6">
      {locations.length > 0 && (
        <AnimatedBackground
          condition={selectedLocation?.weather?.condition}
          isDark={isDark}
        />
      )}

      {/* Desktop: sidebar + detail. Mobile: stacked cards */}
      <div className="flex flex-col lg:flex-row gap-4 lg:gap-6">

        {/* Sidebar: compact location cards */}
        <div className="w-full lg:w-72 xl:w-80 shrink-0 flex flex-col gap-3">
          {sidebarHeader && <div>{sidebarHeader}</div>}
          {locations.map((location) => (
            <LocationCard
              key={location.id}
              location={location}
              isSelected={location.id === selectedLocation?.id}
              onClick={() => setSelectedId(location.id)}
              onDelete={() => deleteLocation(location.id)}
              isRefreshing={isPending && refreshingId === location.id}
            />
          ))}
        </div>

        {/* Detail panel: shown to the right on desktop, below on mobile */}
        {selectedLocation && (
          <div className="flex-1 min-w-0">
            <div className="rounded-3xl backdrop-blur-xl shadow-2xl overflow-hidden bg-white/10 border border-white/20">
              {/* Detail header */}
              <div className="px-5 pt-5 pb-2 flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-1.5 mb-1">
                    {selectedLocation.source === "geolocation" && (
                      <Navigation className="h-4 w-4 text-white/70" />
                    )}
                    <span className="text-white/60 text-sm">
                      {selectedLocation.source === "geolocation" ? "My Location" : "Saved Location"}
                    </span>
                  </div>
                  <h2 className="text-white text-2xl font-semibold">
                    {selectedLocation.weather?.area || selectedLocation.name || "Unknown Area"}
                  </h2>
                </div>
                <div className="text-right">
                  <div className="text-white text-5xl font-thin">
                    {selectedLocation.weather?.temperature != null
                      ? `${Math.round(selectedLocation.weather.temperature)}°`
                      : "—"}
                  </div>
                  <div className="text-white/70 text-sm mt-1">
                    {selectedLocation.weather?.condition || "—"}
                  </div>
                  {(selectedLocation.weather?.tempHigh != null || selectedLocation.weather?.tempLow != null) && (
                    <div className="text-white/60 text-xs">
                      H:{selectedLocation.weather.tempHigh ?? "—"}° L:{selectedLocation.weather.tempLow ?? "—"}°
                    </div>
                  )}
                </div>
              </div>

              {/* Detailed card content */}
              <div className="px-5 pb-5">
                <DetailedWeatherCard location={selectedLocation} isDark={true} />
              </div>

              {/* Footer: last updated + delete */}
              <div className="px-5 pb-4 pt-2 border-t border-white/10 flex items-center justify-between">
                <div className="flex flex-col gap-0.5">
                  <span className="text-white/50 text-xs">
                    Updated {getRelativeTime(selectedLocation.lastFetched)}
                  </span>
                  {selectedLocation.weather?.source && (
                    <span className="text-white/30 text-[10px]">
                      Source: {selectedLocation.weather.source}
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => refresh(selectedLocation.id)}
                    disabled={isPending || isDeleting}
                    className="rounded-xl bg-white/10 hover:bg-white/20 border border-white/20 px-3 py-1.5 text-xs text-white/80 flex items-center gap-1.5 transition-all disabled:opacity-50"
                    aria-label="Refresh weather"
                  >
                    <RefreshCw className={`h-3 w-3 ${isPending && refreshingId === selectedLocation.id ? "animate-spin" : ""}`} />
                    Refresh
                  </button>
                  <button
                    onClick={() => {
                      deleteLocation(selectedLocation.id);
                      setSelectedId(null);
                    }}
                    disabled={isPending || isDeleting}
                    className="rounded-xl bg-red-500/30 hover:bg-red-500/50 border border-red-400/40 px-3 py-1.5 text-xs text-red-200 flex items-center gap-1.5 transition-all disabled:opacity-50"
                    aria-label="Delete location"
                  >
                    <Trash2 className="h-3 w-3" />
                    Remove
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
