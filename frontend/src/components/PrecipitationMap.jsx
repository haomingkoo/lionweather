import { useState, useEffect } from "react";
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

// Precipitation overlay component
function PrecipitationOverlay({ timeIndex }) {
  const [rainfallData, setRainfallData] = useState(null);
  const map = useMap();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getRainfallData();
        setRainfallData(data);
      } catch (err) {
        console.error("Failed to fetch rainfall:", err);
      }
    };
    fetchData();
  }, []);

  useEffect(() => {
    if (!rainfallData || !map) return;

    // Create canvas overlay for precipitation
    const canvas = document.createElement("canvas");
    const bounds = map.getBounds();
    const size = map.getSize();

    canvas.width = size.x;
    canvas.height = size.y;

    const ctx = canvas.getContext("2d");

    // Draw precipitation gradient
    rainfallData.stations?.forEach((station) => {
      if (station.rainfall > 0) {
        const point = map.latLngToContainerPoint([
          station.latitude,
          station.longitude,
        ]);
        const radius = Math.min(station.rainfall * 10, 100);

        // Create radial gradient
        const gradient = ctx.createRadialGradient(
          point.x,
          point.y,
          0,
          point.x,
          point.y,
          radius,
        );

        // Color based on intensity
        if (station.rainfall < 2) {
          gradient.addColorStop(0, "rgba(100, 200, 255, 0.6)");
          gradient.addColorStop(1, "rgba(100, 200, 255, 0)");
        } else if (station.rainfall < 5) {
          gradient.addColorStop(0, "rgba(50, 150, 255, 0.7)");
          gradient.addColorStop(1, "rgba(50, 150, 255, 0)");
        } else if (station.rainfall < 10) {
          gradient.addColorStop(0, "rgba(255, 200, 50, 0.8)");
          gradient.addColorStop(1, "rgba(255, 200, 50, 0)");
        } else {
          gradient.addColorStop(0, "rgba(255, 100, 100, 0.9)");
          gradient.addColorStop(1, "rgba(255, 100, 100, 0)");
        }

        ctx.fillStyle = gradient;
        ctx.fillRect(
          point.x - radius,
          point.y - radius,
          radius * 2,
          radius * 2,
        );
      }
    });

    // Add canvas as overlay
    const imageUrl = canvas.toDataURL();
    const overlay = L.imageOverlay(imageUrl, bounds, { opacity: 0.6 });
    overlay.addTo(map);

    return () => {
      map.removeLayer(overlay);
    };
  }, [rainfallData, map, timeIndex]);

  return null;
}

export function PrecipitationMap({ location, onClose, isDark = false }) {
  const [timeIndex, setTimeIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedHour, setSelectedHour] = useState(0);

  const textColor = isDark ? "text-white" : "text-slate-900";
  const hours = Array.from({ length: 24 }, (_, i) => {
    const date = new Date();
    date.setHours(date.getHours() + i);
    return {
      time: date.toLocaleTimeString("en-US", { hour: "numeric", hour12: true }),
      hour: date.getHours(),
    };
  });

  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setTimeIndex((prev) => (prev + 1) % 24);
      setSelectedHour((prev) => (prev + 1) % 24);
    }, 1000);

    return () => clearInterval(interval);
  }, [isPlaying]);

  return (
    <div className="fixed inset-0 z-[2000] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div
        className={`relative w-full max-w-4xl h-[80vh] rounded-3xl backdrop-blur-xl shadow-2xl overflow-hidden ${isDark ? "bg-slate-900/95 border border-slate-700/40" : "bg-white/95 border border-white/40"}`}
      >
        {/* Header */}
        <div
          className={`absolute top-0 left-0 right-0 z-10 p-4 ${isDark ? "bg-gradient-to-b from-slate-900/90 to-transparent" : "bg-gradient-to-b from-white/90 to-transparent"}`}
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
              onClick={onClose}
              className={`rounded-full p-2 hover:brightness-110 transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 ${isDark ? "bg-slate-700/80 hover:bg-slate-600 focus:ring-slate-500" : "bg-slate-200/80 hover:bg-slate-300 focus:ring-slate-400"}`}
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

          <PrecipitationOverlay timeIndex={timeIndex} />

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

        {/* Timeline Controls */}
        <div
          className={`absolute bottom-0 left-0 right-0 z-10 p-6 ${isDark ? "bg-gradient-to-t from-slate-900/95 to-transparent" : "bg-gradient-to-t from-white/95 to-transparent"}`}
        >
          <div
            className={`rounded-2xl backdrop-blur-md p-4 shadow-lg ${isDark ? "bg-slate-800/90" : "bg-white/90"}`}
          >
            <div className="flex items-center gap-4 mb-4">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="rounded-full bg-blue-500 p-3 hover:bg-blue-600 transition-all shadow-lg focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
                aria-label={isPlaying ? "Pause animation" : "Play animation"}
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
                  Forecast: {hours[selectedHour]?.time}
                </div>
                <input
                  type="range"
                  min="0"
                  max="23"
                  value={selectedHour}
                  onChange={(e) => {
                    setSelectedHour(parseInt(e.target.value));
                    setTimeIndex(parseInt(e.target.value));
                    setIsPlaying(false);
                  }}
                  className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${isDark ? "bg-slate-700" : "bg-slate-200"}`}
                  style={{
                    background: `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${(selectedHour / 23) * 100}%, ${isDark ? "#334155" : "#e2e8f0"} ${(selectedHour / 23) * 100}%, ${isDark ? "#334155" : "#e2e8f0"} 100%)`,
                  }}
                />
              </div>

              <div className="flex gap-1">
                <button
                  className="px-3 py-1.5 rounded-lg bg-blue-500 text-white text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
                  aria-label="1 hour view"
                >
                  1h
                </button>
                <button
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-offset-2 ${isDark ? "bg-slate-700 text-slate-300 hover:bg-slate-600 focus:ring-slate-500" : "bg-slate-200 text-slate-700 hover:bg-slate-300 focus:ring-slate-400"}`}
                  aria-label="12 hour view"
                >
                  12h
                </button>
              </div>
            </div>

            {/* Hour markers */}
            <div
              className={`flex justify-between text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}
            >
              {hours
                .filter((_, i) => i % 3 === 0)
                .map((h, i) => (
                  <span key={i}>{h.time}</span>
                ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
