import { useState, useEffect } from "react";
import {
  useLocations,
  useRefreshLocation,
  useDeleteLocation,
} from "../hooks/useLocations.jsx";
import { DetailedWeatherCard } from "./DetailedWeatherCard";
import { AnimatedBackground } from "./AnimatedBackground";
import { RefreshCw, Trash2, ChevronDown, ChevronUp } from "lucide-react";

// Helper function to format timestamps as relative time
function getRelativeTime(isoTimestamp) {
  if (!isoTimestamp) return "Unknown";

  const now = Date.now();
  const fetchedTime = new Date(isoTimestamp).getTime();
  const diffMs = now - fetchedTime;

  if (diffMs < 0) return "Just now"; // Future timestamp edge case
  if (diffMs < 60000) return "Just now"; // Less than 1 minute

  const diffMinutes = Math.floor(diffMs / 60000);
  if (diffMinutes < 60) {
    return `${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
}

export function EnhancedLocationList({ isDark = false }) {
  const { locations, isLoading, error } = useLocations();
  const {
    refresh,
    isPending,
    refreshingId,
    error: refreshError,
  } = useRefreshLocation();
  const { deleteLocation, isPending: isDeleting } = useDeleteLocation();
  const [expandedId, setExpandedId] = useState(null);
  const [, setUpdateTrigger] = useState(0);

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const tertiaryTextColor = isDark ? "text-white/60" : "text-slate-600";

  // Auto-update timestamps every minute
  useEffect(() => {
    const interval = setInterval(() => {
      setUpdateTrigger((prev) => prev + 1);
    }, 60000); // Update every minute

    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div
          className={`rounded-3xl backdrop-blur-xl px-12 py-8 shadow-2xl ${isDark ? "bg-white/15 border border-white/25" : "bg-white/30 border border-white/40"}`}
        >
          <p className={`${textColor} text-lg animate-pulse`}>
            Loading locations...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-20">
        <div
          className={`rounded-3xl backdrop-blur-xl px-12 py-8 shadow-2xl ${isDark ? "bg-red-500/40 border border-red-400/50" : "bg-red-500/30 border border-red-400/40"}`}
        >
          <p className={`text-lg ${isDark ? "text-red-50" : "text-red-900"}`}>
            {error.message}
          </p>
        </div>
      </div>
    );
  }

  if (locations.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <div
          className={`rounded-3xl backdrop-blur-xl px-12 py-8 shadow-2xl text-center ${isDark ? "bg-white/15 border border-white/25" : "bg-white/30 border border-white/40"}`}
        >
          <p className={`${textColor} text-lg mb-2`}>No locations yet</p>
          <p className={secondaryTextColor}>
            Add your first location above to get started
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Animated Background */}
      {locations.length > 0 && (
        <AnimatedBackground
          condition={locations[0].weather.condition}
          isDark={isDark}
        />
      )}

      {/* Grid layout: 1 column mobile, 2 columns desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
        {locations.map((location, index) => {
          const isExpanded = expandedId === location.id;

          return (
            <article
              key={location.id}
              style={{ animationDelay: `${index * 50}ms` }}
              className={`rounded-[2rem] backdrop-blur-xl shadow-2xl overflow-hidden transition-all duration-300 animate-fade-in ${isDark ? "bg-white/10 border border-white/20 hover:bg-white/15" : "bg-white/25 border border-white/40 hover:bg-white/30"}`}
            >
              {/* Collapsed Header */}
              <button
                className="w-full p-3 xl:p-3 cursor-pointer transition-all text-left focus:outline-none focus:ring-2 focus:ring-white/60 focus:ring-inset"
                onClick={() => setExpandedId(isExpanded ? null : location.id)}
                aria-expanded={isExpanded}
                aria-label={`${isExpanded ? "Collapse" : "Expand"} weather details for ${location.weather.area || "Singapore"}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h3
                      className={`text-lg xl:text-xl font-semibold ${textColor} mb-1`}
                    >
                      {location.weather.area || "Singapore"}
                    </h3>
                    <p className={`text-xs xl:text-sm ${tertiaryTextColor}`}>
                      {location.latitude.toFixed(4)},{" "}
                      {location.longitude.toFixed(4)}
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div
                        className={`text-2xl xl:text-3xl font-extralight ${textColor}`}
                      >
                        {location.weather.temperature || "29"}°
                      </div>
                      <div
                        className={`text-xs xl:text-sm ${secondaryTextColor} mt-1`}
                      >
                        {location.weather.condition}
                      </div>
                    </div>

                    {isExpanded ? (
                      <ChevronUp className={`h-5 w-5 ${textColor}`} />
                    ) : (
                      <ChevronDown className={`h-5 w-5 ${textColor}`} />
                    )}
                  </div>
                </div>
              </button>

              {/* Expanded Details */}
              {isExpanded && (
                <div
                  className={`px-3 xl:px-3 pb-3 xl:pb-3 ${isDark ? "border-t border-white/10" : "border-t border-white/20"}`}
                >
                  <div className="pt-3">
                    <DetailedWeatherCard location={location} isDark={isDark} />
                  </div>

                  {/* Timestamp and Delete Button */}
                  <div
                    className={`flex items-center justify-between gap-3 mt-4 pt-3 ${isDark ? "border-t border-white/10" : "border-t border-white/20"}`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`text-xs ${tertiaryTextColor}`}>
                        Last updated: {getRelativeTime(location.lastFetched)}
                      </span>
                      {isPending && refreshingId === location.id && (
                        <RefreshCw
                          className={`h-3 w-3 ${tertiaryTextColor} animate-spin`}
                        />
                      )}
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteLocation(location.id);
                      }}
                      disabled={isPending || isDeleting}
                      className={`rounded-xl backdrop-blur-sm px-3 py-2 text-sm font-medium text-white hover:brightness-110 hover:scale-105 active:scale-95 disabled:opacity-50 disabled:hover:scale-100 disabled:hover:brightness-100 transition-all duration-150 shadow-lg focus:outline-none focus:ring-2 focus:ring-red-400/80 focus:ring-offset-2 focus:ring-offset-transparent ${isDark ? "bg-red-500/50 border border-red-400/60 hover:bg-red-500/70" : "bg-red-500/40 border border-red-400/50 hover:bg-red-500/60"}`}
                      aria-label="Delete location"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  {refreshError && refreshingId === null && (
                    <p
                      className={`mt-4 text-sm backdrop-blur-sm rounded-2xl px-4 py-3 ${isDark ? "bg-red-500/40 border border-red-400/50 text-red-100" : "bg-red-500/30 border border-red-400/40 text-red-900"}`}
                    >
                      {refreshError.message}
                    </p>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
