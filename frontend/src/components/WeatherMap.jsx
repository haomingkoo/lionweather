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
import { Play, Pause } from "lucide-react";
import { formatClock } from "../utils/currentConditions";

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

export function WeatherMap() {
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
  const [radarError, setRadarError] = useState(false);
  const [isAnimationPlaying, setIsAnimationPlaying] = useState(true);
  const animationSpeed = 500;
  const [currentFrameTimestamp, setCurrentFrameTimestamp] = useState(null);
  const [totalFrames, setTotalFrames] = useState(0);
  const [frameTimestamps, setFrameTimestamps] = useState([]);
  const [sliderIndex, setSliderIndex] = useState(null);  // null = free-running
  const [currentFrameIdx, setCurrentFrameIdx] = useState(0);

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

    // Validate Singapore bounds
    if (!validateSingaporeBounds(lat, lng)) {
      setMapError("Pick a spot inside Singapore.");
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
      setMapError(err.message || "Could not add that place. Try again.");
      setTimeout(() => setMapError(null), 5000);
    }
  };

  const frameTime = (ts) => (ts ? formatClock(ts) : null);
  const status = isCreating ? "Adding this place..." : isRefreshing ? "Updating the weather..." : null;
  const problem = mapError || createError?.message || (error && "Your saved places could not load.");

  return (
    <section aria-labelledby="map-heading" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div>
          <h1 id="map-heading" className="text-2xl font-semibold">Rain map</h1>
          <p className="mt-1 text-sm text-muted">Tap the map to save a place. Turn on the radar to see rain over the last hour.</p>
        </div>
        <button
          type="button"
          onClick={() => { setShowRainfall(!showRainfall); setRadarError(false); }}
          aria-pressed={showRainfall}
          className={`inline-flex min-h-11 items-center rounded-control px-4 text-sm font-semibold ${showRainfall ? "border border-line bg-surface text-ink hover:bg-surface-2" : "bg-accent text-accent-ink hover:opacity-90"}`}
        >
          {showRainfall ? "Hide rain radar" : "Show rain radar"}
        </button>
      </div>

      {showRainfall && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-card border border-line bg-surface px-3 py-2">
          <button
            type="button"
            onClick={() => setIsAnimationPlaying(!isAnimationPlaying)}
            disabled={totalFrames === 0}
            className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-control border border-line hover:bg-surface-2 disabled:opacity-60"
            aria-label={isAnimationPlaying ? "Pause radar" : "Play radar"}
          >
            {isAnimationPlaying ? <Pause className="h-4 w-4" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
          </button>
          <p className="min-w-[7rem] text-sm font-medium tabular-nums" aria-live="polite">
            {radarError ? "Radar not available" : frameTime(currentFrameTimestamp) ? `Radar at ${frameTime(currentFrameTimestamp)}` : "Loading radar..."}
          </p>
          {totalFrames > 0 && (
            <label className="flex min-w-[10rem] flex-1 items-center gap-2 text-xs text-muted">
              <span className="tabular-nums">{frameTime(frameTimestamps[0])}</span>
              <input
                type="range"
                min={0}
                max={totalFrames - 1}
                step={1}
                value={sliderIndex ?? currentFrameIdx}
                onChange={(e) => {
                  setSliderIndex(Number(e.target.value));
                  setIsAnimationPlaying(false);
                }}
                onMouseUp={() => setSliderIndex(null)}
                onTouchEnd={() => setSliderIndex(null)}
                className="h-6 w-full cursor-pointer accent-[rgb(var(--accent))]"
                aria-label="Radar time"
              />
              <span className="tabular-nums">{frameTime(frameTimestamps[totalFrames - 1])}</span>
            </label>
          )}
        </div>
      )}

      {(status || problem) && (
        <p className={`text-sm ${problem ? "text-bad" : "text-muted"}`} role={problem ? "alert" : "status"}>{problem || status}</p>
      )}

      <div className="relative h-[60vh] min-h-[360px] w-full overflow-hidden rounded-panel border border-line md:h-[600px]">
        {isLoading ? (
          <p className="flex h-full items-center justify-center text-sm text-muted">Loading the map...</p>
        ) : (
        <MapContainer
          center={[1.3521, 103.8198]}
          zoom={11}
          style={{ height: "100%", width: "100%" }}
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            className="osm-muted-tiles"
          />

          <MapClickHandler
            onMapClick={handleMapClick}
            isDisabled={isCreating || isRefreshing}
          />

          {showRainfall ? (
            <AnimatedRadarLayer
              visible={showRainfall}
              animationSpeed={animationSpeed}
              isPlaying={sliderIndex === null && isAnimationPlaying}
              forcedIndex={sliderIndex}
              onFrameChange={(timestamp, idx) => { setCurrentFrameTimestamp(timestamp); if (idx !== undefined) setCurrentFrameIdx(idx); }}
              onFramesLoaded={(count, timestamps) => {
                setTotalFrames(count);
                setFrameTimestamps(timestamps);
              }}
              onError={() => setRadarError(true)}
            />
          ) : null}

          {locations.map((location) => {
            const w = location.weather || {};
            const temp = typeof w.temperature === "number" ? `${Math.round(w.temperature)}°` : null;
            return (
              <Marker key={location.id} position={[location.latitude, location.longitude]}>
                <Popup>
                  <div className="min-w-[180px] font-sans">
                    <h3 className="text-base font-semibold">
                      {w.area || `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`}
                    </h3>
                    <p className="mt-1 text-sm">{[temp, w.condition].filter(Boolean).join(", ") || "No reading yet"}</p>
                    {formatClock(w.timestamp || location.lastFetched) && (
                      <p className="mt-1 text-xs text-slate-600">Reading at {formatClock(w.timestamp || location.lastFetched)}</p>
                    )}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteLocation(location.id);
                      }}
                      disabled={isDeleting}
                      className="mt-3 min-h-10 w-full rounded-md border border-slate-300 px-3 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-60"
                    >
                      Remove this place
                    </button>
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
        )}
      </div>

      {showRainfall && (
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted" aria-label="Radar colours">
          {[["#4ade80", "Light"], ["#facc15", "Moderate"], ["#fb923c", "Heavy"], ["#ef4444", "Intense"]].map(([c, l]) => (
            <li key={l} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full ring-1 ring-ink/20" style={{ background: c }} aria-hidden="true" />
              {l} rain
            </li>
          ))}
          <li>Radar images from NEA.</li>
        </ul>
      )}
    </section>
  );
}
