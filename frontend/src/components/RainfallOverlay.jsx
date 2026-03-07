import { useEffect, useState } from "react";
import { CircleMarker, Popup } from "react-leaflet";
import { getRainfallData } from "../api/rainfall";
import { Droplets } from "lucide-react";

// Color scale for rainfall intensity
function getRainfallColor(rainfall) {
  if (rainfall === 0) return "#94a3b8"; // slate-400 - no rain
  if (rainfall < 2) return "#60a5fa"; // blue-400 - light
  if (rainfall < 5) return "#3b82f6"; // blue-500 - moderate
  if (rainfall < 10) return "#2563eb"; // blue-600 - heavy
  if (rainfall < 20) return "#1d4ed8"; // blue-700 - very heavy
  return "#1e3a8a"; // blue-900 - extreme
}

function getRainfallRadius(rainfall) {
  // Scale radius based on intensity
  const baseRadius = 8;
  const scale = Math.min(rainfall / 5, 3); // Cap at 3x
  return baseRadius + scale * 4;
}

export function RainfallOverlay({ visible = true }) {
  const [stations, setStations] = useState([]);
  const [timestamp, setTimestamp] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!visible) return;

    const fetchRainfall = async () => {
      try {
        setIsLoading(true);
        const data = await getRainfallData();
        setStations(data.stations || []);
        setTimestamp(data.timestamp);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchRainfall();

    // Refresh every 5 minutes
    const interval = setInterval(fetchRainfall, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [visible]);

  // Show error message if there's an issue
  if (!visible) {
    return null;
  }

  if (error) {
    // Silently handle errors - don't spam console
    return null;
  }

  if (isLoading) {
    // Silent loading
    return null;
  }

  if (stations.length === 0) {
    // Silently handle no data
    return null;
  }

  // Filter to only show stations with rainfall > 0
  const rainingStations = stations.filter((station) => station.rainfall > 0);

  // If no rain anywhere, show a message
  if (rainingStations.length === 0) {
    // Silently handle no rainfall
    return null;
  }

  return (
    <>
      {rainingStations.map((station) => (
        <CircleMarker
          key={station.id}
          center={[station.latitude, station.longitude]}
          radius={getRainfallRadius(station.rainfall)}
          pathOptions={{
            fillColor: getRainfallColor(station.rainfall),
            fillOpacity: 0.6,
            color: getRainfallColor(station.rainfall),
            weight: 2,
            opacity: 0.8,
          }}
        >
          <Popup>
            <div className="min-w-[180px]">
              <div className="flex items-center gap-2 mb-2">
                <Droplets className="h-5 w-5 text-blue-500" />
                <h3 className="font-semibold">{station.name}</h3>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">Rainfall:</span>
                  <span className="font-medium">{station.rainfall} mm</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">Location:</span>
                  <span className="text-xs">
                    {station.latitude.toFixed(3)},{" "}
                    {station.longitude.toFixed(3)}
                  </span>
                </div>
              </div>
              {timestamp && (
                <p className="text-xs text-slate-500 mt-2">
                  Updated: {new Date(timestamp).toLocaleTimeString()}
                </p>
              )}
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}
