import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import { NowView } from "../components/NowView";
import { WeatherMap } from "../components/WeatherMap";
import { MLAnalysisDashboard } from "../components/MLAnalysisDashboard";
import { MLLiveForecast } from "../components/MLLiveForecast";
import { useLocations } from "../hooks/useLocations";
import { useTheme } from "../contexts/ThemeContext";

const VIEWS = [
  { id: "now", label: "Now" },
  { id: "map", label: "Rain map" },
  { id: "model", label: "Forecast model" },
];

const viewFromHash = () => {
  const id = window.location.hash.replace("#", "");
  return VIEWS.some((v) => v.id === id) ? id : "now";
};

// Browser geolocation errors, in words that say what to do next.
export function geolocationMessage(error) {
  if (!error) return null;
  if (error.code === 1) return "Location is blocked for this site. Allow it in your browser settings, or search for a place above.";
  if (error.code === 3) return "Finding your location took too long. Try again, or search for a place above.";
  return "We could not find your location. Search for a place or postal code above.";
}

function useOnline() {
  const [online, setOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine !== false));
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  return online;
}

export function Dashboard() {
  const [view, setView] = useState(viewFromHash);
  const [geoLoading, setGeoLoading] = useState(false);
  const [geoError, setGeoError] = useState(null);
  const { addLocationFromGeolocation, reload } = useLocations();
  const { isNight } = useTheme();
  const online = useOnline();

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (online) reload();
  }, [online, reload]);

  const go = (id) => {
    setView(id);
    window.history.replaceState(null, "", id === "now" ? window.location.pathname : `#${id}`);
  };

  const requestLocation = () => {
    if (!navigator.geolocation) {
      setGeoError("Your browser cannot share its location. Search for a place or postal code above.");
      return;
    }
    setGeoLoading(true);
    setGeoError(null);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          await addLocationFromGeolocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        } catch (err) {
          setGeoError(err.message || "Could not load the weather for your location.");
        } finally {
          setGeoLoading(false);
        }
      },
      (err) => {
        setGeoError(geolocationMessage(err));
        setGeoLoading(false);
      },
      { timeout: 10000, maximumAge: 300000, enableHighAccuracy: false },
    );
  };

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50 focus:rounded-control focus:bg-surface focus:px-3 focus:py-2 focus:text-sm">
        Skip to content
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 px-4 sm:px-6">
          <a href="/" onClick={(e) => { e.preventDefault(); go("now"); }} className="flex min-h-14 items-center text-lg font-semibold tracking-[-0.01em]">
            LionWeather
          </a>
          <nav aria-label="Sections" className="-mx-2 w-full sm:mx-0 sm:w-auto">
            <ul className="flex">
              {VIEWS.map((v) => (
                <li key={v.id} className="flex-1 sm:flex-none">
                  <button
                    type="button"
                    onClick={() => go(v.id)}
                    aria-current={view === v.id ? "page" : undefined}
                    className={`relative flex min-h-12 w-full items-center justify-center whitespace-nowrap px-3 text-sm font-medium transition-colors focus-visible:-outline-offset-2 ${view === v.id ? "text-ink" : "text-muted hover:text-ink"}`}
                  >
                    {v.label}
                    {view === v.id && <span aria-hidden="true" className="absolute inset-x-3 bottom-0 h-0.5 bg-accent" />}
                  </button>
                </li>
              ))}
              <li className="flex-1 sm:flex-none">
                <a
                  href="/haze"
                  className="relative flex min-h-12 w-full items-center justify-center whitespace-nowrap px-3 text-sm font-medium text-muted transition-colors hover:text-ink focus-visible:-outline-offset-2"
                >
                  Haze
                </a>
              </li>
            </ul>
          </nav>
        </div>
      </header>

      {!online && (
        <div className="border-b border-line bg-surface-2" role="status">
          <p className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2 text-sm sm:px-6">
            <WifiOff className="h-4 w-4 shrink-0 text-warn" aria-hidden="true" />
            You are offline. The page shows the last reading it got and will update when you reconnect.
          </p>
        </div>
      )}

      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        {view === "now" && (
          <NowView geo={{ request: requestLocation, loading: geoLoading, error: geoError }} isNight={isNight} offline={!online} />
        )}
        {view === "map" && <WeatherMap />}
        {view === "model" && (
          <div className="space-y-8">
            <MLLiveForecast />
            <MLAnalysisDashboard isDark={isNight} />
          </div>
        )}
      </main>

      <footer className="border-t border-line bg-surface">
        <nav aria-label="Site" className="mx-auto max-w-6xl px-4 py-5 text-sm text-muted sm:px-6">
          <ul className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <li>© 2026 Haoming Koo</li>
            <li aria-hidden="true">·</li>
            <li><a href="/privacy.html" className="inline-flex min-h-6 items-center underline-offset-2 hover:text-ink hover:underline">Privacy</a></li>
            <li aria-hidden="true">·</li>
            <li><a href="/terms.html" className="inline-flex min-h-6 items-center underline-offset-2 hover:text-ink hover:underline">Terms</a></li>
            <li aria-hidden="true">·</li>
            <li>Contact (<a href="mailto:privacy@kooexperience.com" className="inline-flex min-h-6 items-center underline-offset-2 hover:text-ink hover:underline">privacy@kooexperience.com</a>)</li>
            <li aria-hidden="true">·</li>
            <li>More projects → <a href="https://kooexperience.com/" className="inline-flex min-h-6 items-center underline-offset-2 hover:text-ink hover:underline">kooexperience.com</a></li>
          </ul>
        </nav>
      </footer>
    </div>
  );
}
