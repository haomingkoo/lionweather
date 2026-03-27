import { useState, useEffect } from "react";
import { API_BASE } from "../api/base.js";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMapEvents,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { getRainfallData } from "../api/rainfall";
import { Play, Pause, X } from "lucide-react";

// Fix marker icons
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

// Precipitation overlay component with animated radar
function PrecipitationOverlay({ timeIndex, radarFrames, isLoading }) {
  const map = useMap();
  const [overlayLayer, setOverlayLayer] = useState(null);

  useEffect(() => {
    if (!map || isLoading || !radarFrames || radarFrames.length === 0) {
      console.log("PrecipitationOverlay: Waiting for data", {
        map: !!map,
        isLoading,
        framesCount: radarFrames?.length,
      });
      return;
    }

    // Remove previous overlay
    if (overlayLayer) {
      map.removeLayer(overlayLayer);
    }

    // Get current frame
    const currentFrame = radarFrames[timeIndex % radarFrames.length];
    if (!currentFrame || !currentFrame.loaded) {
      console.log("PrecipitationOverlay: Frame not loaded", {
        timeIndex,
        currentFrame,
      });
      return;
    }

    console.log("PrecipitationOverlay: Adding overlay", {
      url: currentFrame.url,
      timeIndex,
    });

    // Use bounds from the API response (matches what weather.gov.sg uses)
    const bounds = currentFrame.bounds || [
      [1.1550, 103.565], // Southwest fallback
      [1.4750, 104.130], // Northeast fallback
    ];

    // Create image overlay with 70% opacity for better visibility
    const overlay = L.imageOverlay(currentFrame.url, bounds, {
      opacity: 0.7,
      crossOrigin: true,
    });
    overlay.addTo(map);
    setOverlayLayer(overlay);

    return () => {
      if (overlay) {
        map.removeLayer(overlay);
      }
    };
  }, [map, timeIndex, radarFrames, isLoading, overlayLayer]);

  return null;
}

export function PrecipitationMap({ location, onClose, isDark = false }) {
  const [timeIndex, setTimeIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedHour, setSelectedHour] = useState(0);
  const [radarFrames, setRadarFrames] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  // Close on Escape key
  useEffect(() => {
    const handleKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const textColor = isDark ? "text-white" : "text-slate-900";

  // Generate timestamps for last 12 frames (1 hour at 5-minute intervals)
  const generateRadarTimestamps = () => {
    const timestamps = [];
    const now = new Date();

    // Round down to nearest 5 minutes
    const minutes = Math.floor(now.getMinutes() / 5) * 5;
    now.setMinutes(minutes);
    now.setSeconds(0);
    now.setMilliseconds(0);

    // Generate 12 timestamps going back 1 hour
    for (let i = 11; i >= 0; i--) {
      const timestamp = new Date(now.getTime() - i * 5 * 60 * 1000);
      const year = timestamp.getFullYear();
      const month = String(timestamp.getMonth() + 1).padStart(2, "0");
      const day = String(timestamp.getDate()).padStart(2, "0");
      const hour = String(timestamp.getHours()).padStart(2, "0");
      const minute = String(timestamp.getMinutes()).padStart(2, "0");

      const formattedTimestamp = `${year}${month}${day}${hour}${minute}`;

      // Use the correct weather.gov.sg radar image URL
      const url = `https://www.weather.gov.sg/files/rainarea/50km/v2/dpsri_70km_${formattedTimestamp}0000dBR.dpsri.png`;

      timestamps.push({
        timestamp: formattedTimestamp,
        date: timestamp,
        url: url,
        loaded: false,
      });
    }

    console.log(
      "Generated radar timestamps:",
      timestamps.map((t) => ({
        time: t.date.toLocaleTimeString(),
        url: t.url,
      })),
    );
    return timestamps;
  };

  // Fetch radar frames on mount
  useEffect(() => {
    const fetchRadarFrames = async () => {
      setIsLoading(true);

      try {
        console.log("Fetching radar frames from backend API...");

        // Fetch from backend API instead of directly from weather.gov.sg
        const response = await fetch(`${API_BASE}/radar/frames?count=20`);

        // Handle fetch errors gracefully
        if (!response || !response.ok) {
          const statusText = response?.statusText || "Network error";
          console.warn(`Radar frames fetch failed: ${statusText}`);
          setRadarFrames([]);
          setIsLoading(false);
          return;
        }

        const data = await response.json();
        console.log("Received radar frames:", data);

        // Check if we actually received frames
        if (!data.frames || data.frames.length === 0) {
          console.warn(
            "Backend returned 0 radar frames - radar data may not be available yet",
          );
          setRadarFrames([]);
          setIsLoading(false);
          return;
        }

        // Transform backend response to our format
        const frames = data.frames.map((frame) => ({
          timestamp: frame.timestamp,
          date: new Date(frame.timestamp),
          url: frame.imageUrl,
          bounds: frame.bounds, // [[lat_sw, lon_sw], [lat_ne, lon_ne]]
          loaded: true, // Backend already has the images
        }));

        console.log(`Loaded ${frames.length} radar frames from backend`);
        setRadarFrames(frames);
      } catch (error) {
        // Log warning instead of error for better UX
        console.warn("Radar frames unavailable:", error.message || error);
        setRadarFrames([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchRadarFrames();
  }, []);

  // Animation loop - 12 frames at 500ms per frame
  useEffect(() => {
    if (!isPlaying || radarFrames.length === 0) return;

    const interval = setInterval(() => {
      setTimeIndex((prev) => (prev + 1) % radarFrames.length);
      setSelectedHour((prev) => (prev + 1) % radarFrames.length);
    }, 500);

    return () => clearInterval(interval);
  }, [isPlaying, radarFrames.length]);

  // Format timestamp for display
  const formatTimestamp = (frame) => {
    if (!frame || !frame.date) return "";
    return frame.date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  };

  const currentFrame = radarFrames[timeIndex] || null;

  return (
    <div
      className="fixed inset-0 z-[2000] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 transition-opacity duration-300"
      onClick={onClose}
    >
      <div
        className={`relative w-full max-w-4xl h-[80vh] rounded-3xl backdrop-blur-xl shadow-2xl overflow-hidden transition-transform duration-300 ${isDark ? "bg-slate-900/95 border border-slate-700/40" : "bg-white/95 border border-white/40"}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className={`absolute top-0 left-0 right-0 z-[1500] p-4 ${isDark ? "bg-gradient-to-b from-slate-900/90 to-transparent" : "bg-gradient-to-b from-white/90 to-transparent"}`}
        >
          <div className="flex items-center justify-between">
            <div>
              <h2 className={`text-2xl font-semibold ${textColor}`}>
                Precipitation
              </h2>
              <p
                className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}
              >
                {location.weather.area || "Singapore"}
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClose();
              }}
              className={`rounded-full p-2 hover:brightness-110 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 ${isDark ? "bg-slate-700/80 hover:bg-slate-600 focus:ring-slate-500" : "bg-slate-200/80 hover:bg-slate-300 focus:ring-slate-400"}`}
              aria-label="Close precipitation map"
            >
              <X
                className={`h-6 w-6 ${isDark ? "text-slate-200" : "text-slate-700"}`}
              />
            </button>
          </div>
        </div>

        {/* Map */}
        <MapContainer
          center={[location.latitude, location.longitude]}
          zoom={12}
          style={{ height: "100%", width: "100%" }}
          zoomControl={false}
          scrollWheelZoom={true}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution="&copy; OpenStreetMap contributors"
          />

          <PrecipitationOverlay
            timeIndex={timeIndex}
            radarFrames={radarFrames}
            isLoading={isLoading}
          />

          <Marker position={[location.latitude, location.longitude]}>
            <Popup>
              <div className="text-center">
                <div className="text-3xl font-light">
                  {location.weather.temperature || "27"}°
                </div>
                <div className="text-sm text-slate-600">My Location</div>
              </div>
            </Popup>
          </Marker>
        </MapContainer>

        {/* Loading Spinner */}
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 backdrop-blur-sm z-10">
            <div
              className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"
              role="status"
              data-testid="loading-spinner"
              aria-label="Loading radar data"
            />
          </div>
        )}

        {/* No Data Message */}
        {!isLoading && radarFrames.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 backdrop-blur-sm z-10">
            <div
              className={`rounded-2xl backdrop-blur-md p-6 shadow-lg text-center max-w-md ${isDark ? "bg-slate-800/90" : "bg-white/90"}`}
            >
              <div className={`text-lg font-semibold mb-2 ${textColor}`}>
                Radar Data Unavailable
              </div>
              <div
                className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}
              >
                The radar animation service is currently unavailable. This may
                be due to the backend server not running or radar data not being
                cached yet. Please try again in a few moments.
              </div>
            </div>
          </div>
        )}

        {/* Legend */}
        <div
          className={`absolute top-20 left-4 z-10 rounded-2xl backdrop-blur-md p-4 shadow-lg ${isDark ? "bg-slate-800/90" : "bg-white/90"}`}
        >
          <div
            className={`text-xs font-semibold mb-2 ${isDark ? "text-slate-300" : "text-slate-700"}`}
          >
            Precipitation
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-gradient-to-r from-blue-300 to-blue-400"></div>
              <span
                className={`text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}
              >
                Light
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-gradient-to-r from-blue-500 to-blue-600"></div>
              <span
                className={`text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}
              >
                Moderate
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-gradient-to-r from-yellow-400 to-orange-400"></div>
              <span
                className={`text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}
              >
                Heavy
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-gradient-to-r from-red-400 to-red-600"></div>
              <span
                className={`text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}
              >
                Extreme
              </span>
            </div>
          </div>
        </div>

        {/* Timeline Controls - Fixed position, always visible */}
        <div
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-[2001] w-[calc(100%-2rem)] max-w-4xl pointer-events-none`}
        >
          <div
            className={`rounded-2xl backdrop-blur-md p-4 shadow-lg pointer-events-auto ${isDark ? "bg-slate-800/90" : "bg-white/90"}`}
          >
            <div className="flex items-center gap-4 mb-4">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="rounded-full bg-blue-500 p-3 hover:bg-blue-600 transition-all duration-200 shadow-lg focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
                aria-label={isPlaying ? "Pause animation" : "Play animation"}
                disabled={isLoading}
              >
                {isPlaying ? (
                  <Pause className="h-5 w-5 text-white" fill="white" />
                ) : (
                  <Play className="h-5 w-5 text-white" fill="white" />
                )}
              </button>

              <div className="flex-1">
                <div
                  className={`text-sm font-semibold mb-2 ${isDark ? "text-slate-300" : "text-slate-700"}`}
                >
                  {isLoading
                    ? "Loading radar data..."
                    : currentFrame
                      ? `${formatTimestamp(currentFrame)} - Radar Animation`
                      : "No radar data available"}
                </div>
                <input
                  type="range"
                  min="0"
                  max={Math.max(0, radarFrames.length - 1)}
                  value={selectedHour}
                  onChange={(e) => {
                    const newIndex = parseInt(e.target.value);
                    setSelectedHour(newIndex);
                    setTimeIndex(newIndex);
                    setIsPlaying(false);
                  }}
                  disabled={isLoading || radarFrames.length === 0}
                  className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${isDark ? "bg-slate-700" : "bg-slate-200"}`}
                  style={{
                    background:
                      radarFrames.length > 0
                        ? `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${(selectedHour / Math.max(1, radarFrames.length - 1)) * 100}%, ${isDark ? "#334155" : "#e2e8f0"} ${(selectedHour / Math.max(1, radarFrames.length - 1)) * 100}%, ${isDark ? "#334155" : "#e2e8f0"} 100%)`
                        : isDark
                          ? "#334155"
                          : "#e2e8f0",
                  }}
                />
                <div
                  className={`text-xs ${isDark ? "text-slate-400" : "text-slate-600"} mt-1`}
                >
                  Drag slider to see different times •{" "}
                  {radarFrames.filter((f) => f.loaded).length}/
                  {radarFrames.length} frames loaded
                </div>
              </div>
            </div>

            {/* Time markers */}
            {radarFrames.length > 0 && (
              <div
                className={`flex justify-between text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}
              >
                {radarFrames
                  .filter((_, i) => i % 3 === 0)
                  .map((frame, i) => (
                    <span key={i}>{formatTimestamp(frame)}</span>
                  ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
