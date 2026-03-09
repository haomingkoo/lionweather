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
import { Droplets, Play, Pause, Clock } from "lucide-react";

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
  const [totalFrames, setTotalFrames] = useState(0);
  const [frameTimestamps, setFrameTimestamps] = useState([]);
  const [sliderIndex, setSliderIndex] = useState(null);  // null = free-running

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
      {/* Radar toggle button (top-right) */}
      <button
        onClick={() => setShowRainfall(!showRainfall)}
        className={`absolute right-4 top-4 z-[1000] flex items-center gap-2 rounded-2xl backdrop-blur-md px-4 py-2.5 shadow-xl hover:brightness-110 hover:scale-105 transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-blue-400/60 ${
          showRainfall
            ? "bg-blue-500 border-2 border-blue-300 text-white font-bold"
            : "bg-blue-600/90 border-2 border-blue-400/80 text-white font-semibold"
        }`}
        aria-label={`${showRainfall ? "Hide" : "Show"} radar overlay`}
      >
        <Droplets className="h-4 w-4" strokeWidth={2} />
        <span className="text-sm">
          {showRainfall ? "Hide Radar" : "Show Radar"}
        </span>
      </button>

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
        {/* Bottom radar timeline bar — always visible */}
        <div className="absolute bottom-0 left-0 right-0 z-[1000] bg-gradient-to-t from-black/70 to-transparent px-4 pt-8 pb-4 pointer-events-none">
          <div className="pointer-events-auto flex items-center gap-3">
            {/* Play/Pause */}
            {showRainfall && (
              <button
                onClick={() => setIsAnimationPlaying(!isAnimationPlaying)}
                className="shrink-0 bg-blue-500 hover:bg-blue-600 rounded-full p-2.5 shadow-lg transition-all focus:outline-none focus:ring-2 focus:ring-blue-400"
                aria-label={isAnimationPlaying ? "Pause radar" : "Play radar"}
              >
                {isAnimationPlaying ? (
                  <Pause className="h-4 w-4 text-white" fill="white" />
                ) : (
                  <Play className="h-4 w-4 text-white" fill="white" />
                )}
              </button>
            )}

            {/* Timeline label */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <span className="text-white/80 text-xs font-medium flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {showRainfall
                    ? currentFrameTimestamp
                      ? new Date(currentFrameTimestamp).toLocaleTimeString("en-SG", {
                          hour: "2-digit",
                          minute: "2-digit",
                          hour12: true,
                          timeZone: "Asia/Singapore",
                        })
                      : "Loading radar..."
                    : new Date().toLocaleTimeString("en-SG", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                        hour12: true,
                        timeZone: "Asia/Singapore",
                      })}
                </span>
                {showRainfall && (
                  <span className="text-white/50 text-xs">
                    NEA Radar · Singapore
                  </span>
                )}
              </div>

              {/* Frame scrub slider — only when radar is on and frames loaded */}
              {showRainfall && totalFrames > 0 && (
                <div className="space-y-1">
                  <input
                    type="range"
                    min={0}
                    max={totalFrames - 1}
                    step={1}
                    value={sliderIndex ?? totalFrames - 1}
                    onChange={(e) => {
                      const idx = Number(e.target.value);
                      setSliderIndex(idx);
                      setIsAnimationPlaying(false);
                    }}
                    onMouseUp={() => setSliderIndex(null)}   // release → resume auto-play
                    onTouchEnd={() => setSliderIndex(null)}
                    className="w-full h-1.5 rounded-lg appearance-none cursor-pointer accent-blue-400"
                    aria-label="Radar frame scrub"
                  />
                  {/* Frame tick labels */}
                  {frameTimestamps.length > 0 && (
                    <div className="flex justify-between text-white/40 text-[10px]">
                      {[0, Math.floor(totalFrames / 2), totalFrames - 1].map((i) =>
                        frameTimestamps[i] ? (
                          <span key={i}>
                            {new Date(frameTimestamps[i]).toLocaleTimeString("en-SG", {
                              hour: "2-digit", minute: "2-digit", hour12: true, timeZone: "Asia/Singapore",
                            })}
                          </span>
                        ) : null
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
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
              isPlaying={sliderIndex === null && isAnimationPlaying}
              forcedIndex={sliderIndex}
              onFrameChange={(timestamp) => setCurrentFrameTimestamp(timestamp)}
              onFramesLoaded={(count, timestamps) => {
                setTotalFrames(count);
                setFrameTimestamps(timestamps);
              }}
              onError={() => {}}
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
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteLocation(location.id);
                    }}
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

      {/* Instructions */}
      <p className={`mt-3 text-xs ${isDark ? "text-white/50" : "text-slate-500"}`}>
        Click on the map to pin a location · Toggle Radar to see live NEA rain animation
      </p>
    </div>
  );
}
