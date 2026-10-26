import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import {
  CircleMarker,
  ImageOverlay,
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Tooltip,
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
import { Play, Pause } from "lucide-react";
import { formatClock } from "../utils/currentConditions";
import { getRainGauges } from "../api/rain";
import { useTheme } from "../contexts/ThemeContext";
import { RAIN_BANDS, RAIN_BOUNDS, fieldPixels, gaugesAt, rainField } from "../map3d/rainField";

const RainMap3D = lazy(() => import("./RainMap3D"));

function hasWebGL2() {
  try {
    return !!document.createElement("canvas").getContext("webgl2");
  } catch {
    return false;
  }
}

function prefersReducedMotion() {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

// The rain field as an image for the flat map.
function fieldImage(field) {
  const canvas = document.createElement("canvas");
  canvas.width = field.cols;
  canvas.height = field.rows;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.putImageData(new ImageData(fieldPixels(field), field.cols, field.rows), 0, 0);
  return canvas.toDataURL();
}

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
  const { create, isPending: isCreating, error: createError } = useCreateLocation();
  const { refresh, isPending: isRefreshing } = useRefreshLocation();
  const { deleteLocation, isPending: isDeleting } = useDeleteLocation();
  const { theme } = useTheme();
  const webgl = useMemo(hasWebGL2, []);
  const reduced = useMemo(prefersReducedMotion, []);
  const [mapError, setMapError] = useState(null);
  const [view, setView] = useState(webgl && !reduced ? "3d" : "2d");
  const [rain, setRain] = useState(null);
  const [rainError, setRainError] = useState(false);
  const [frame, setFrame] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      getRainGauges()
        .then((d) => {
          if (!alive) return;
          setRain(d);
          setRainError(false);
          setFrame((f) => (f == null || f >= d.times.length - 1 ? d.times.length - 1 : f));
        })
        .catch(() => alive && setRainError(true));
    load();
    const id = setInterval(load, 5 * 60 * 1000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const last = rain ? rain.times.length - 1 : 0;
  useEffect(() => {
    if (!playing || !rain) return undefined;
    const id = setInterval(() => setFrame((f) => (f >= last ? 0 : f + 1)), 700);
    return () => clearInterval(id);
  }, [playing, rain, last]);

  // Pause the loop when the tab is hidden.
  useEffect(() => {
    const onVis = () => document.hidden && setPlaying(false);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  const gauges = useMemo(() => (rain && frame != null ? gaugesAt(rain, frame) : []), [rain, frame]);
  const field = useMemo(() => rainField(gauges), [gauges]);
  const image = useMemo(() => (view === "2d" && field.max > 0 ? fieldImage(field) : null), [field, view]);
  const reporting = gauges.filter((g) => g.mm5 != null).length;
  const wet = gauges.filter((g) => (g.mm5 ?? 0) > 0).length;

  const handleMapClick = async (event) => {
    const { lat, lng } = event.latlng;
    if (!validateSingaporeBounds(lat, lng)) {
      setMapError("Pick a spot inside Singapore.");
      setTimeout(() => setMapError(null), 5000);
      return;
    }
    setMapError(null);
    try {
      const newLocation = await create({ latitude: lat, longitude: lng });
      if (newLocation && newLocation.id) await refresh(newLocation.id);
    } catch (err) {
      setMapError(err.message || "Could not add that place. Try again.");
      setTimeout(() => setMapError(null), 5000);
    }
  };

  const at = rain && frame != null ? formatClock(rain.times[frame]) : null;
  const status = isCreating ? "Adding this place..." : isRefreshing ? "Updating the weather..." : null;
  const problem = mapError || createError?.message || (error && "Your saved places could not load.");
  const place = locations.find((l) => l.id === selected);

  return (
    <section aria-labelledby="map-heading" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div>
          <h1 id="map-heading" className="text-2xl font-semibold">Rain map</h1>
          <p className="mt-1 text-sm text-muted">Rain at NEA&apos;s gauges over the last two hours. Tap the map to save a place.</p>
        </div>
        {webgl && (
          <div className="flex rounded-control border border-line bg-surface-2 p-0.5" role="group" aria-label="Map style">
            {[["3d", "3D"], ["2d", "2D"]].map(([v, label]) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={`min-h-10 rounded-[5px] px-4 text-sm font-semibold ${view === v ? "bg-accent text-accent-ink" : "text-ink hover:bg-surface"}`}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-card border border-line bg-surface px-3 py-2">
        <button
          type="button"
          onClick={() => setPlaying(!playing)}
          disabled={!rain}
          className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-control border border-line hover:bg-surface-2 disabled:opacity-60"
          aria-label={playing ? "Pause rain loop" : "Play rain loop"}
        >
          {playing ? <Pause className="h-4 w-4" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
        </button>
        <p className="min-w-[7rem] text-sm font-medium tabular-nums" aria-live="polite">
          {rainError && !rain ? "Rain readings not available" : at ? `Rain at ${at}` : "Loading rain readings..."}
        </p>
        {rain && (
          <label className="flex min-w-[10rem] flex-1 items-center gap-2 text-xs text-muted">
            <span className="tabular-nums">{formatClock(rain.times[0])}</span>
            <input
              type="range"
              min={0}
              max={last}
              step={1}
              value={frame ?? last}
              onChange={(e) => {
                setFrame(Number(e.target.value));
                setPlaying(false);
              }}
              className="h-6 w-full cursor-pointer accent-[rgb(var(--accent))]"
              aria-label="Rain time"
            />
            <span className="tabular-nums">{formatClock(rain.times[last])}</span>
          </label>
        )}
      </div>

      {(status || problem) && (
        <p className={`text-sm ${problem ? "text-bad" : "text-muted"}`} role={problem ? "alert" : "status"}>{problem || status}</p>
      )}

      <div className="relative h-[60vh] min-h-[360px] w-full overflow-hidden rounded-panel border border-line md:h-[600px]">
        {isLoading ? (
          <p className="flex h-full items-center justify-center text-sm text-muted">Loading the map...</p>
        ) : view === "3d" ? (
          <Suspense fallback={<p className="flex h-full items-center justify-center text-sm text-muted">Loading the 3D map...</p>}>
            <RainMap3D
              field={field}
              gauges={gauges}
              wind={rain?.wind}
              theme={theme}
              motion={!reduced}
              locations={locations}
              onMapClick={handleMapClick}
              onPlace={setSelected}
            />
          </Suspense>
        ) : (
          <MapContainer center={[1.3521, 103.8198]} zoom={11} style={{ height: "100%", width: "100%" }} scrollWheelZoom={true}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              className="osm-muted-tiles"
            />
            <MapClickHandler onMapClick={handleMapClick} isDisabled={isCreating || isRefreshing} />
            {image && (
              <ImageOverlay url={image} bounds={[[RAIN_BOUNDS[1], RAIN_BOUNDS[0]], [RAIN_BOUNDS[3], RAIN_BOUNDS[2]]]} opacity={0.8} />
            )}
            {gauges.map((g) => (
              <CircleMarker
                key={g.id}
                center={[g.lat, g.lng]}
                radius={(g.mm5 ?? 0) > 0 ? 6 : 4}
                pathOptions={{ color: "rgb(var(--accent))", weight: (g.mm5 ?? 0) > 0 ? 3 : 1.5, fillColor: "rgb(var(--surface))", fillOpacity: 1 }}
              >
                <Tooltip direction="top">
                  <strong>{g.name}</strong>
                  <br />
                  {g.mm5 != null ? `${g.mm5.toFixed(1)} mm in 5 min` : "No reading"}
                  {g.hourMm != null && (
                    <>
                      <br />
                      {g.hourMm.toFixed(1)} mm in the last hour
                    </>
                  )}
                </Tooltip>
              </CircleMarker>
            ))}
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

      {view === "3d" && place && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-surface px-3 py-2 text-sm">
          <p>
            <strong>{place.weather?.area || `${place.latitude.toFixed(4)}, ${place.longitude.toFixed(4)}`}</strong>
            {" "}
            {[typeof place.weather?.temperature === "number" ? `${Math.round(place.weather.temperature)}°` : null, place.weather?.condition].filter(Boolean).join(", ")}
          </p>
          <button
            type="button"
            onClick={() => {
              deleteLocation(place.id);
              setSelected(null);
            }}
            disabled={isDeleting}
            className="min-h-10 rounded-control border border-line px-3 font-medium text-bad hover:bg-surface-2 disabled:opacity-60"
          >
            Remove this place
          </button>
        </div>
      )}

      <div className="space-y-1 text-xs text-muted">
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1" aria-label="Rain colours">
          {RAIN_BANDS.map((b, i) => (
            <li key={b.label} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full ring-1 ring-ink/20" style={{ background: `rgb(${b.color.join(",")})` }} aria-hidden="true" />
              {b.label} <span className="tabular-nums">{i === 0 ? `under ${b.max}` : Number.isFinite(b.max) ? `${RAIN_BANDS[i - 1].max}–${b.max}` : `${RAIN_BANDS[i - 1].max}+`} mm/h</span>
            </li>
          ))}
        </ul>
        <p>
          Rain drawn from NEA rain gauges.{" "}
          {rain ? `${reporting} gauges reporting${wet ? `, ${wet} with rain` : ", all dry"} at ${at}.` : ""} Colour between gauges is
          interpolated{view === "3d" ? "; the falling rain is drawn from it" : ""}.
        </p>
      </div>
    </section>
  );
}
