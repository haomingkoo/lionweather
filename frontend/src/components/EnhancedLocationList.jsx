import { useState, useEffect } from "react";
import {
  useLocations,
  useRefreshLocation,
  useDeleteLocation,
} from "../hooks/useLocations.jsx";
import { DetailedWeatherCard } from "./DetailedWeatherCard";
import { AnimatedBackground } from "./AnimatedBackground";
import { RefreshCw, Trash2, Navigation, GripVertical } from "lucide-react";

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

// Sky-like gradient that varies by condition AND time of day (like Apple Weather)
function conditionStyle(condition = "") {
  const c = condition.toLowerCase();
  const h = new Date().getHours();
  const isNight  = h >= 20 || h < 6;   // 8 PM – 6 AM
  const isDusk   = h >= 18 && h < 20;  // 6 – 8 PM golden hour
  const isDawn   = h >= 6  && h < 9;   // 6 – 9 AM sunrise
  // isDay = everything else

  if (c.includes("thunder") || c.includes("storm"))
    return { grad: "from-[#1a0a2e] via-[#2d1b4e] to-[#0f0f1a]", cloud: "rgba(120,80,200,0.15)" };

  if (c.includes("heavy rain") || c.includes("moderate rain")) {
    if (isNight) return { grad: "from-[#0c1a2e] via-[#0a1628] to-[#050d1a]", cloud: "rgba(30,80,140,0.2)" };
    return { grad: "from-[#1c3a5e] via-[#1a3050] to-[#0f1e36]", cloud: "rgba(40,100,180,0.2)" };
  }

  if (c.includes("rain") || c.includes("shower") || c.includes("drizzle")) {
    if (isNight) return { grad: "from-[#0f1e32] via-[#0d1a2e] to-[#080f1e]", cloud: "rgba(30,70,130,0.18)" };
    if (isDusk)  return { grad: "from-[#2a3a5c] via-[#1e2e50] to-[#12203c]", cloud: "rgba(80,100,160,0.2)" };
    return { grad: "from-[#2a4a72] via-[#1e3860] to-[#142848]", cloud: "rgba(60,120,200,0.2)" };
  }

  if (c.includes("haze") || c.includes("fog") || c.includes("mist")) {
    if (isNight) return { grad: "from-[#1a1e28] via-[#1c2030] to-[#10121c]", cloud: "rgba(80,100,120,0.15)" };
    return { grad: "from-[#7a7e8c] via-[#5a6070] to-[#3c4050]", cloud: "rgba(200,210,220,0.2)" };
  }

  if (c.includes("overcast")) {
    if (isNight) return { grad: "from-[#12161e] via-[#1a1e2a] to-[#0c1018]", cloud: "rgba(60,80,120,0.15)" };
    return { grad: "from-[#606878] via-[#505868] to-[#3c4452]", cloud: "rgba(180,190,210,0.25)" };
  }

  if (c.includes("partly")) {
    if (isNight) return { grad: "from-[#0e1a30] via-[#0c1828] to-[#080f1e]", cloud: "rgba(60,100,160,0.15)" };
    if (isDusk)  return { grad: "from-[#c4603a] via-[#7a5898] to-[#2a3a6c]", cloud: "rgba(255,160,80,0.15)" };
    if (isDawn)  return { grad: "from-[#e87040] via-[#a06090] to-[#3a6090]", cloud: "rgba(255,180,100,0.15)" };
    return { grad: "from-[#4a88c8] via-[#2e6aaa] to-[#1a4a80]", cloud: "rgba(180,220,255,0.2)" };
  }

  if (c.includes("cloud") || c.includes("mostly cloud")) {
    if (isNight) return { grad: "from-[#101828] via-[#141c2e] to-[#0a1020]", cloud: "rgba(50,80,130,0.15)" };
    if (isDusk)  return { grad: "from-[#8878a0] via-[#5a6088] to-[#2a3060]", cloud: "rgba(180,160,220,0.2)" };
    return { grad: "from-[#7890b0] via-[#5070a0] to-[#2c4878]", cloud: "rgba(200,220,255,0.2)" };
  }

  if (c.includes("clear") || c.includes("sunny")) {
    if (isNight) return { grad: "from-[#0a0e1a] via-[#0c1428] to-[#050810]", cloud: "rgba(100,140,200,0.1)" };
    if (isDusk)  return { grad: "from-[#e8824a] via-[#c05a3c] to-[#6a3090]", cloud: "rgba(255,160,80,0.2)" };
    if (isDawn)  return { grad: "from-[#f09050] via-[#e07060] to-[#6090c0]", cloud: "rgba(255,200,120,0.2)" };
    return { grad: "from-[#5ab0e8] via-[#2e8ad8] to-[#1460b0]", cloud: "rgba(220,240,255,0.25)" };
  }

  if (c.includes("fair")) {
    if (isNight) return { grad: "from-[#0c1428] via-[#101c38] to-[#080f20]", cloud: "rgba(80,120,180,0.12)" };
    if (isDusk)  return { grad: "from-[#d07840] via-[#a05880] to-[#4860a0]", cloud: "rgba(255,180,80,0.18)" };
    return { grad: "from-[#48a0e0] via-[#2878c8] to-[#1050a0]", cloud: "rgba(200,235,255,0.22)" };
  }

  // Default
  if (isNight) return { grad: "from-[#0e1828] via-[#0c1420] to-[#080f18]", cloud: "rgba(50,90,150,0.12)" };
  return { grad: "from-[#3a78c0] via-[#2860a8] to-[#164080]", cloud: "rgba(160,210,255,0.2)" };
}

// Compact Apple Weather-style sidebar card
function LocationCard({ location, isSelected, onClick, onDelete, isRefreshing }) {
  const { grad, cloud } = conditionStyle(location.weather?.condition);
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
      <div className={`relative bg-gradient-to-br ${grad} p-4 overflow-hidden`}>
        {/* Subtle cloud highlight — simulates sky depth like Apple Weather */}
        <div className="absolute inset-0 pointer-events-none" style={{
          background: `radial-gradient(ellipse at 75% 25%, ${cloud} 0%, transparent 65%), radial-gradient(ellipse at 20% 70%, ${cloud} 0%, transparent 55%)`
        }} />
        <div className="relative z-10 flex items-start justify-between">
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
  const { locations, isLoading, error, reorderLocations } = useLocations();
  const { refresh, isPending, refreshingId } = useRefreshLocation();
  const { deleteLocation, isPending: isDeleting } = useDeleteLocation();
  const [selectedId, setSelectedId] = useState(null);
  const [, setUpdateTrigger] = useState(0);
  const [draggedId, setDraggedId] = useState(null);
  const [dragOverId, setDragOverId] = useState(null);

  const handleDragStart = (e, id) => {
    setDraggedId(id);
    e.dataTransfer.effectAllowed = "move";
  };
  const handleDragOver = (e, id) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (id !== draggedId) setDragOverId(id);
  };
  const handleDrop = (e, targetId) => {
    e.preventDefault();
    if (!draggedId || draggedId === targetId) return;
    const newOrder = [...locations];
    const fromIdx = newOrder.findIndex((l) => l.id === draggedId);
    const toIdx = newOrder.findIndex((l) => l.id === targetId);
    newOrder.splice(toIdx, 0, newOrder.splice(fromIdx, 1)[0]);
    reorderLocations(newOrder);
    setDraggedId(null);
    setDragOverId(null);
  };
  const handleDragEnd = () => {
    setDraggedId(null);
    setDragOverId(null);
  };

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
            <div
              key={location.id}
              draggable={locations.length > 1}
              onDragStart={(e) => handleDragStart(e, location.id)}
              onDragOver={(e) => handleDragOver(e, location.id)}
              onDrop={(e) => handleDrop(e, location.id)}
              onDragEnd={handleDragEnd}
              className={`group/drag relative transition-all duration-150 ${
                draggedId === location.id ? "opacity-40 scale-[0.98]" : ""
              } ${
                dragOverId === location.id && draggedId !== location.id
                  ? "ring-2 ring-white/40 rounded-2xl scale-[1.01]"
                  : ""
              }`}
            >
              {locations.length > 1 && (
                <div className="absolute left-1 top-1/2 -translate-y-1/2 z-20 opacity-0 group-hover/drag:opacity-60 transition-opacity cursor-grab active:cursor-grabbing">
                  <GripVertical className="w-3 h-3 text-white" />
                </div>
              )}
              <LocationCard
                location={location}
                isSelected={location.id === selectedLocation?.id}
                onClick={() => setSelectedId(location.id)}
                onDelete={() => deleteLocation(location.id)}
                isRefreshing={isPending && refreshingId === location.id}
              />
            </div>
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
