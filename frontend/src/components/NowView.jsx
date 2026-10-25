import { useEffect, useState } from "react";
import { Bell, BellOff, MapPin, MapPinOff, Navigation, X } from "lucide-react";
import { useDeleteLocation, useLocations, useRefreshLocation } from "../hooks/useLocations.jsx";
import { useForecasts } from "../hooks/useForecasts";
import { getCurrentWeather } from "../api/backend";
import { pickLocation } from "../utils/airQuality";
import { AirQualityCard } from "./AirQualityCard";
import { LocationForm } from "./LocationForm";
import { CurrentConditions, DailyForecast, DetailsList, HourlyForecast, WeatherIcon } from "./NowPanel";

const CENTRAL = { id: "central-singapore", latitude: 1.3521, longitude: 103.8198, source: "default" };

// Island-wide reading shown before the visitor saves a place, so the page never opens empty.
function useCentralReading(enabled) {
  const [state, setState] = useState({ status: "idle", location: null });
  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    setState({ status: "loading", location: null });
    getCurrentWeather(CENTRAL.latitude, CENTRAL.longitude)
      .then((weather) => !cancelled && setState({ status: "ready", location: { ...CENTRAL, weather, lastFetched: new Date().toISOString() } }))
      .catch(() => !cancelled && setState({ status: "error", location: null }));
    return () => { cancelled = true; };
  }, [enabled]);
  return state;
}

function LocationControls({ geo }) {
  const { locations, rainNotifyEnabled, setRainNotifyEnabled, liveLocationEnabled, setLiveLocationEnabled } = useLocations();
  const hasCurrent = locations.some((l) => l.source === "geolocation");
  const toggle = "flex min-h-11 w-full items-center justify-center gap-2 rounded-control border px-4 text-sm font-medium transition-colors";

  return (
    <section aria-labelledby="places-heading" className="rounded-panel border border-line bg-surface p-4">
      <h2 id="places-heading" className="text-base font-semibold">Places</h2>
      <div className="mt-3 space-y-3">
        <LocationForm compact />
        {!hasCurrent ? (
          <div>
            <button
              type="button"
              onClick={geo.request}
              disabled={geo.loading}
              className={`${toggle} border-accent bg-accent text-accent-ink hover:opacity-90 disabled:opacity-60`}
            >
              <Navigation className="h-4 w-4" aria-hidden="true" />
              {geo.loading ? "Finding you..." : "Use my location"}
            </button>
            {geo.error ? (
              <p className="mt-2 text-sm text-bad" role="alert">{geo.error}</p>
            ) : (
              <p className="mt-2 text-xs text-muted">
                Your coordinates go to our server, Open-Meteo and OpenStreetMap to get the weather. We do not save them.{" "}
                <a href="/privacy.html" className="underline underline-offset-2 hover:text-ink">Privacy</a>
              </p>
            )}
          </div>
        ) : (
          <div>
            <button
              type="button"
              onClick={() => setLiveLocationEnabled(!liveLocationEnabled)}
              aria-pressed={liveLocationEnabled}
              className={`${toggle} ${liveLocationEnabled ? "border-accent bg-accent/10 text-ink" : "border-line bg-surface text-ink hover:bg-surface-2"}`}
            >
              {liveLocationEnabled ? <MapPin className="h-4 w-4" aria-hidden="true" /> : <MapPinOff className="h-4 w-4" aria-hidden="true" />}
              {liveLocationEnabled ? "Following my location" : "Location paused"}
            </button>
            <p className="mt-2 text-xs text-muted">
              {liveLocationEnabled ? "Checks where you are every 15 minutes while this tab is open." : "Keeps the last place we found. Turn on to follow you again."}
            </p>
          </div>
        )}
        <div>
          <button
            type="button"
            onClick={() => setRainNotifyEnabled(!rainNotifyEnabled)}
            aria-pressed={rainNotifyEnabled}
            className={`${toggle} ${rainNotifyEnabled ? "border-accent bg-accent/10 text-ink" : "border-line bg-surface text-ink hover:bg-surface-2"}`}
          >
            {rainNotifyEnabled ? <Bell className="h-4 w-4" aria-hidden="true" /> : <BellOff className="h-4 w-4" aria-hidden="true" />}
            {rainNotifyEnabled ? "Rain alerts on" : "Turn on rain alerts"}
          </button>
          {rainNotifyEnabled && <p className="mt-2 text-xs text-muted">We will notify you when rain is likely in the next one to two hours.</p>}
        </div>
      </div>
    </section>
  );
}

function SavedPlaces({ locations, selectedId, onSelect, onDelete, isNight }) {
  if (locations.length < 2) return null;
  return (
    <section aria-labelledby="saved-heading" className="rounded-panel border border-line bg-surface p-2">
      <h2 id="saved-heading" className="px-2 pb-1 pt-2 text-base font-semibold">Saved places</h2>
      <ul>
        {locations.map((loc) => {
          const selected = loc.id === selectedId;
          const temp = typeof loc.weather?.temperature === "number" ? `${Math.round(loc.weather.temperature)}°` : "n/a";
          const name = loc.weather?.area || loc.name || "Saved place";
          return (
            <li key={loc.id} className={`flex items-center rounded-card ${selected ? "bg-surface-2" : ""}`}>
              <button
                type="button"
                onClick={() => onSelect(loc.id)}
                aria-current={selected ? "true" : undefined}
                className="flex min-h-12 min-w-0 flex-1 items-center gap-3 rounded-card px-2 text-left hover:bg-surface-2"
              >
                <WeatherIcon condition={loc.weather?.condition} isNight={isNight} className="h-5 w-5 shrink-0 text-muted" />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1 truncate text-sm font-medium">
                    {loc.source === "geolocation" && <Navigation className="h-3 w-3 shrink-0" aria-label="Your location" />}
                    <span className="truncate">{name}</span>
                  </span>
                  <span className="block truncate text-xs text-muted">{loc.weather?.condition || "No reading yet"}</span>
                </span>
                <span className="text-base font-medium tabular-nums">{temp}</span>
              </button>
              <button
                type="button"
                onClick={() => onDelete(loc.id)}
                className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-control text-muted hover:bg-surface-2 hover:text-bad"
                aria-label={`Remove ${name}`}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function NowView({ geo, isNight, offline }) {
  const { locations, isLoading } = useLocations();
  const { refresh, isPending, refreshingId, error: refreshError } = useRefreshLocation();
  const { deleteLocation } = useDeleteLocation();
  const [selectedId, setSelectedId] = useState(null);
  const central = useCentralReading(!isLoading && locations.length === 0);

  const selected = locations.find((l) => l.id === selectedId) || locations[0] || central.location;
  const forecasts = useForecasts(selected);

  const main = () => {
    if (isLoading || (!selected && central.status === "loading")) {
      return (
        <section className="rounded-panel border border-line bg-surface p-6" aria-busy="true">
          <p className="text-base text-muted">Getting the latest reading...</p>
        </section>
      );
    }
    if (!selected) {
      return (
        <section aria-labelledby="empty-heading" className="rounded-panel border border-line bg-surface p-6">
          <h1 id="empty-heading" className="text-2xl font-semibold">Weather for where you are</h1>
          <p className="mt-2 max-w-[60ch] text-base text-muted">
            {offline
              ? "You are offline, so there is no reading to show. Reconnect and the page will update."
              : "We could not reach the weather service just now. Use your location or search for a place to try again."}
          </p>
        </section>
      );
    }
    return (
      <>
        <CurrentConditions
          location={selected}
          hourly={forecasts.hourly}
          isNight={isNight}
          offline={offline}
          onRefresh={selected.source === "default" ? null : () => refresh(selected.id)}
          refreshing={isPending && refreshingId === selected.id}
          onRemove={locations.length === 1 && selected.source !== "default" ? () => { deleteLocation(selected.id); setSelectedId(null); } : null}
        />
        {refreshError && <p className="text-sm text-bad" role="alert">{refreshError.message}</p>}
        {selected.source === "default" && (
          <p className="text-sm text-muted">
            This is the reading for central Singapore. Use your location or search for a place to see your own.
          </p>
        )}
        <HourlyForecast hourly={forecasts.hourly} status={forecasts.status} location={selected} />
        <DailyForecast daily={forecasts.daily} status={forecasts.status} />
        <DetailsList location={selected} extra={forecasts.extra} />
      </>
    );
  };

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,1fr)_20rem] lg:gap-6">
      <div className="min-w-0 space-y-4">{main()}</div>
      <aside className="min-w-0 space-y-4" aria-label="Places and air quality">
        <SavedPlaces
          locations={locations}
          selectedId={selected?.id}
          onSelect={setSelectedId}
          onDelete={(id) => { deleteLocation(id); if (id === selectedId) setSelectedId(null); }}
          isNight={isNight}
        />
        <LocationControls geo={geo} />
        <AirQualityCard location={pickLocation(locations) || selected} />
      </aside>
    </div>
  );
}
