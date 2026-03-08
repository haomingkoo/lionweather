import {
  useLocations,
  useRefreshLocation,
  useDeleteLocation,
} from "../hooks/useLocations.jsx";
import {
  Sun,
  CloudRain,
  CloudLightning,
  Cloud,
  Cloudy,
  CloudSun,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { getWeatherIcon } from "../utils/weatherTheme";

const iconMap = {
  Sun,
  CloudRain,
  CloudLightning,
  Cloud,
  Cloudy,
  CloudSun,
};

export function LocationList({ isDark = false }) {
  const { locations, isLoading, error } = useLocations();
  const {
    refresh,
    isPending,
    refreshingId,
    error: refreshError,
  } = useRefreshLocation();
  const { deleteLocation, isPending: isDeleting } = useDeleteLocation();

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";

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
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {locations.map((location, index) => {
        const IconComponent =
          iconMap[getWeatherIcon(location.weather.condition)];
        const temperature = location.weather.temperature || "N/A";

        return (
          <article
            key={location.id}
            style={{ animationDelay: `${index * 50}ms` }}
            className={`group rounded-[2rem] backdrop-blur-xl p-8 shadow-2xl hover:scale-[1.02] hover:shadow-3xl transition-all duration-300 animate-fade-in ${isDark ? "bg-white/10 border border-white/20 hover:bg-white/15" : "bg-white/25 border border-white/40 hover:bg-white/35"}`}
          >
            {/* Location Name */}
            <div className="mb-6">
              <h3 className={`text-2xl font-semibold ${textColor} mb-1`}>
                {location.weather.area || "Singapore"}
              </h3>
              <p className={`text-sm ${secondaryTextColor}`}>
                {location.latitude.toFixed(4)}, {location.longitude.toFixed(4)}
              </p>
            </div>

            {/* Massive Temperature Display */}
            <div className="mb-8">
              <div className="flex items-start justify-between mb-4">
                <div
                  className={`text-8xl font-extralight ${textColor} leading-none tracking-tighter`}
                >
                  {temperature}°
                </div>
                {IconComponent && (
                  <IconComponent
                    className={`h-16 w-16 ${textColor} opacity-90`}
                    strokeWidth={1.5}
                  />
                )}
              </div>

              <div className="flex items-center gap-3 mt-4">
                <span className={`text-2xl font-light ${textColor}`}>
                  {location.weather.condition}
                </span>
              </div>
            </div>

            {/* Weather Details */}
            <div
              className={`space-y-3 text-base ${secondaryTextColor} mb-6 pb-6 ${isDark ? "border-b border-white/10" : "border-b border-white/20"}`}
            >
              {location.weather.valid_period_text && (
                <div className="flex justify-between">
                  <span>Valid Period</span>
                  <span className={textColor}>
                    {location.weather.valid_period_text}
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span>Last Updated</span>
                <span className={textColor}>
                  {location.weather.observed_at
                    ? new Date(location.weather.observed_at).toLocaleTimeString(
                        [],
                        {
                          hour: "2-digit",
                          minute: "2-digit",
                        },
                      )
                    : "Not refreshed"}
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3">
              <button
                onClick={() => refresh(location.id)}
                disabled={isPending || isDeleting}
                className={`flex-1 flex items-center justify-center gap-2 rounded-2xl backdrop-blur-sm px-5 py-3.5 text-base font-medium ${textColor} hover:brightness-110 hover:scale-105 active:scale-95 disabled:opacity-50 disabled:hover:scale-100 disabled:hover:brightness-100 transition-all duration-150 shadow-lg ${isDark ? "bg-white/15 border border-white/25 hover:bg-white/20" : "bg-white/30 border border-white/40 hover:bg-white/40"}`}
              >
                <RefreshCw
                  className={`h-5 w-5 ${isPending && refreshingId === location.id ? "animate-spin" : ""}`}
                />
                <span>
                  {isPending && refreshingId === location.id
                    ? "Updating..."
                    : "Refresh"}
                </span>
              </button>
              <button
                onClick={() => deleteLocation(location.id)}
                disabled={isPending || isDeleting}
                className={`rounded-2xl backdrop-blur-sm px-5 py-3.5 text-base font-medium text-white hover:brightness-110 hover:scale-105 active:scale-95 disabled:opacity-50 disabled:hover:scale-100 disabled:hover:brightness-100 transition-all duration-150 shadow-lg ${isDark ? "bg-red-500/50 border border-red-400/60 hover:bg-red-500/70" : "bg-red-500/40 border border-red-400/50 hover:bg-red-500/60"}`}
              >
                <Trash2 className="h-5 w-5" />
              </button>
            </div>

            {refreshError && refreshingId === null && (
              <p
                className={`mt-4 text-sm backdrop-blur-sm rounded-2xl px-4 py-3 ${isDark ? "bg-red-500/40 border border-red-400/50 text-red-100" : "bg-red-500/30 border border-red-400/40 text-red-900"}`}
              >
                {refreshError.message}
              </p>
            )}
          </article>
        );
      })}
    </div>
  );
}
