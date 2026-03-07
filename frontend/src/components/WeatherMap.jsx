import { useState, useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  useLocations,
  useCreateLocation,
  useRefreshLocation,
  useDeleteLocation,
} from "../hooks/useLocations.jsx";
import { RainfallOverlay } from "./RainfallOverlay";
import { AnimatedRadarLayer } from "./AnimatedRadarLayer";
import { Droplets, Play, Pause } from "lucide-react";

// Fix for default marker icons in bundled applications
import icon from "leaflet/dist/images/marker-icon.png";
import iconShadow from "leaflet/dist/images/marker-shadow.png";

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

L.Marker.prototype.options.icon = DefaultIcon;

// Singapore bounds validation
const SINGAPORE_BOUNDS = {
  minLat: 1.1,
  maxLat: 1.5,
  minLng: 103.6,
  maxLng: 104.1,
};

function validateSingaporeBounds(lat, lng) {
  return (
    lat >= SINGAPORE_BOUNDS.minLat &&
    lat <= SINGAPORE_BOUNDS.maxLat &&
    lng >= SINGAPORE_BOUNDS.minLng &&
    lng <= SINGAPORE_BOUNDS.maxLng
  );
}

function MapClickHandler({ onMapClick, isDisabled }) {
  useMapEvents({
    click: (e) => {
      if (!isDisabled) {
        onMapClick(e);
      }
    },
  });
  return null;
}

export function WeatherMap({ isDark = false }) {
  const { locations, isLoading, error } = useLocations();
  const {
    create,
    isPending: isCreating,
    error: createError,
  } = useCreateLocation();
  const { refresh, isPending: isRefreshing } = useRefreshLocation();
  const { deleteLocation, isPending: isDeleting } = useDeleteLocation();
  const [mapError, setMapError] = useState(null);
  const [showRainfall, setShowRainfall] = useState(false);
  const [ripples, setRipples] = useState([]);
  const [isAnimationPlaying, setIsAnimationPlaying] = useState(true);
  const [animationSpeed, setAnimationSpeed] = useState(500);
  const [currentFrameTimestamp, setCurrentFrameTimestamp] = useState(null);

  const textColor = isDark ? "text-white" : "text-slate-900";

  // Pause animation when page is not visible (Requirement 6.5)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        setIsAnimationPlaying(false);
      } else {
        setIsAnimationPlaying(true);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  const handleMapClick = async (event) => {
    const { lat, lng } = event.latlng;
    const { containerPoint } = event;

    // Add ripple effect at click location
    const rippleId = Date.now();
    setRipples((prev) => [
      ...prev,
      { id: rippleId, x: containerPoint.x, y: containerPoint.y },
    ]);

    // Remove ripple after animation completes
    setTimeout(() => {
      setRipples((prev) => prev.filter((r) => r.id !== rippleId));
    }, 600);

    // Validate Singapore bounds
    if (!validateSingaporeBounds(lat, lng)) {
      setMapError(
        "Location must be within Singapore (lat 1.1–1.5, lon 103.6–104.1)",
      );
      setTimeout(() => setMapError(null), 5000);
      return;
    }

    setMapError(null);

    try {
      // Create location
      const newLocation = await create({ latitude: lat, longitude: lng });

      // Immediately refresh weather data
      if (newLocation && newLocation.id) {
        await refresh(newLocation.id);
      }
    } catch (err) {
      // Error is already captured in hook state
      setMapError(err.message || "Failed to add location");
      setTimeout(() => setMapError(null), 5000);
    }
  };

  if (isLoading) {
    return (
      <div
        className={`flex h-[500px] items-center justify-center rounded-3xl backdrop-blur-md shadow-xl md:h-[600px] ${isDark ? "bg-white/10 border border-white/20" : "bg-white/20 border border-white/30"}`}
      >
        <p className={`${textColor} animate-pulse`}>Loading map...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className={`flex h-[500px] items-center justify-center rounded-3xl backdrop-blur-md shadow-xl md:h-[600px] ${isDark ? "bg-white/10 border border-white/20" : "bg-white/20 border border-white/30"}`}
      >
        <div className="text-center">
          <p className={isDark ? "text-red-300" : "text-red-200"}>
            Failed to load locations
          </p>
          <p
            className={`mt-2 text-sm ${isDark ? "text-red-200" : "text-red-900"}`}
          >
            {error.message}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Rainfall Toggle */}
      <button
        onClick={() => setShowRainfall(!showRainfall)}
        className={`absolute right-4 top-4 z-[1000] flex items-center gap-2 rounded-2xl backdrop-blur-md px-5 py-3 shadow-xl hover:brightness-110 hover:scale-105 transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-white/60 focus:ring-offset-2 focus:ring-offset-transparent ${
          showRainfall
            ? isDark
              ? "bg-blue-500/60 border-blue-400/80"
              : "bg-blue-500/50 border-blue-400/70"
            : isDark
              ? "bg-white/15 border-white/25"
              : "bg-white/30 border-white/40"
        } border`}
        aria-label={`${showRainfall ? "Hide" : "Show"} rainfall overlay`}
      >
        <Droplets
          className={`h-5 w-5 ${showRainfall ? "text-white" : textColor}`}
          strokeWidth={2}
        />
        <span
          className={`text-sm font-semibold ${showRainfall ? "text-white" : textColor}`}
        >
          {showRainfall ? "Hide" : "Show"} Rainfall
        </span>
      </button>

      {/* Radar Animation Controls */}
      {showRainfall && (
        <div
          className={`absolute right-4 top-20 z-[1000] flex flex-col gap-2 rounded-2xl backdrop-blur-md p-3 shadow-xl ${isDark ? "bg-white/15 border border-white/25" : "bg-white/30 border border-white/40"}`}
        >
          {/* Play/Pause Button */}
          <button
            onClick={() => setIsAnimationPlaying(!isAnimationPlaying)}
            className={`flex items-center justify-center gap-2 rounded-xl px-3 py-2 transition-all duration-150 hover:brightness-110 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-white/60 ${
              isDark
                ? "bg-white/20 hover:bg-white/30"
                : "bg-white/40 hover:bg-white/50"
            }`}
            aria-label={
              isAnimationPlaying ? "Pause animation" : "Play animation"
            }
          >
            {isAnimationPlaying ? (
              <Pause className={`h-4 w-4 ${textColor}`} strokeWidth={2} />
            ) : (
              <Play className={`h-4 w-4 ${textColor}`} strokeWidth={2} />
            )}
            <span className={`text-xs font-medium ${textColor}`}>
              {isAnimationPlaying ? "Pause" : "Play"}
            </span>
          </button>

          {/* Animation Speed Slider */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="animation-speed"
              className={`text-xs font-medium ${textColor}`}
            >
              Speed
            </label>
            <input
              id="animation-speed"
              type="range"
              min="300"
              max="1000"
              step="100"
              value={animationSpeed}
              onChange={(e) => setAnimationSpeed(Number(e.target.value))}
              className="w-full h-1 rounded-lg appearance-none cursor-pointer bg-white/30"
              aria-label="Animation speed"
            />
            <span
              className={`text-xs ${isDark ? "text-white/70" : "text-slate-600"}`}
            >
              {animationSpeed}ms
            </span>
          </div>

          {/* Current Frame Timestamp */}
          {currentFrameTimestamp && (
            <div
              className={`text-xs ${isDark ? "text-white/70" : "text-slate-600"} mt-1`}
            >
              {new Date(currentFrameTimestamp).toLocaleTimeString()}
            </div>
          )}
        </div>
      )}

      {/* Loading indicator */}
      {(isCreating || isRefreshing) && (
        <div
          className={`absolute left-4 top-4 z-[1000] rounded-2xl backdrop-blur-md px-4 py-3 shadow-xl ${isDark ? "bg-white/15 border border-white/25" : "bg-white/30 border border-white/40"}`}
        >
          <p className={`text-sm font-medium ${textColor}`}>
            {isCreating ? "Adding location..." : "Refreshing weather..."}
          </p>
        </div>
      )}

      {/* Error messages */}
      {(mapError || createError) && (
        <div
          className={`absolute left-4 top-4 z-[1000] rounded-2xl backdrop-blur-md px-4 py-3 shadow-xl ${isDark ? "bg-red-500/40 border border-red-500/50" : "bg-red-500/30 border border-red-500/40"}`}
        >
          <p
            className={`text-sm font-medium ${isDark ? "text-red-100" : "text-red-900"}`}
          >
            {mapError || createError?.message}
          </p>
        </div>
      )}

      {/* Map container */}
      <div
        className={`h-[500px] w-full overflow-hidden rounded-3xl shadow-2xl md:h-[600px] relative ${isDark ? "border border-white/20" : "border border-white/30"}`}
      >
        {/* Ripple effects */}
        {ripples.map((ripple) => (
          <div
            key={ripple.id}
            className="absolute pointer-events-none z-[1001]"
            style={{
              left: ripple.x,
              top: ripple.y,
              transform: "translate(-50%, -50%)",
            }}
          >
            <div className="absolute inset-0 rounded-full bg-white/40 animate-ping" />
            <div className="absolute inset-0 rounded-full bg-white/20 animate-pulse" />
          </div>
        ))}

        <MapContainer
          center={[1.3521, 103.8198]}
          zoom={11}
          style={{ height: "100%", width: "100%" }}
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MapClickHandler
            onMapClick={handleMapClick}
            isDisabled={isCreating || isRefreshing}
          />

          {/* Rainfall/Radar Overlay */}
          {showRainfall ? (
            <AnimatedRadarLayer
              visible={showRainfall}
              animationSpeed={animationSpeed}
              isPlaying={isAnimationPlaying}
              onFrameChange={(timestamp) => setCurrentFrameTimestamp(timestamp)}
              onError={() => {
                // Silently handle errors - fallback is automatic
              }}
            />
          ) : null}

          {locations.map((location) => (
            <Marker
              key={location.id}
              position={[location.latitude, location.longitude]}
            >
              <Popup>
                <div className="min-w-[200px]">
                  <h3 className="mb-2 font-semibold">
                    {location.weather.area ||
                      `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`}
                  </h3>

                  <dl className="space-y-1 text-sm">
                    <div>
                      <dt className="text-slate-500">Condition</dt>
                      <dd className="font-medium">
                        {location.weather.condition}
                      </dd>
                    </div>

                    {location.weather.observed_at && (
                      <div>
                        <dt className="text-slate-500">Updated</dt>
                        <dd className="font-medium">
                          {new Date(
                            location.weather.observed_at,
                          ).toLocaleString()}
                        </dd>
                      </div>
                    )}

                    {location.weather.valid_period_text && (
                      <div>
                        <dt className="text-slate-500">Valid Period</dt>
                        <dd className="font-medium">
                          {location.weather.valid_period_text}
                        </dd>
                      </div>
                    )}

                    <div>
                      <dt className="text-slate-500">Source</dt>
                      <dd className="text-xs">{location.weather.source}</dd>
                    </div>
                  </dl>

                  <button
                    onClick={() => deleteLocation(location.id)}
                    disabled={isDeleting}
                    className="mt-3 w-full rounded-lg bg-red-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-600 hover:brightness-110 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 disabled:hover:brightness-100 transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-2"
                    aria-label="Delete location"
                  >
                    Delete Location
                  </button>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      {/* Instructions and Legend */}
      <div className="mt-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <p className={`text-sm ${isDark ? "text-white/70" : "text-slate-600"}`}>
          Click anywhere on the map to add a new location
        </p>
        {showRainfall && (
          <div className="flex items-center gap-4 text-sm">
            <span
              className={`font-medium ${isDark ? "text-white/80" : "text-slate-700"}`}
            >
              Rainfall:
            </span>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-slate-400 border border-slate-500"></div>
              <span className={isDark ? "text-white/70" : "text-slate-600"}>
                None
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-blue-400 border border-blue-500"></div>
              <span className={isDark ? "text-white/70" : "text-slate-600"}>
                Light
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-blue-600 border border-blue-700"></div>
              <span className={isDark ? "text-white/70" : "text-slate-600"}>
                Heavy
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-blue-900 border border-blue-950"></div>
              <span className={isDark ? "text-white/70" : "text-slate-600"}>
                Extreme
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
