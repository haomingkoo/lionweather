import SunCalc from "suncalc";
import {
  Cloud, CloudFog, CloudLightning, CloudMoon, CloudRain, CloudSun, Cloudy, Moon, Navigation, RefreshCw, Sun,
} from "lucide-react";
import { getWeatherIcon } from "../utils/weatherTheme";
import { getSunTimesSync } from "../utils/sunTimes";
import {
  compassPoint, feelsLike, formatClock, formatHour, generateCommentary, rainOutlook, readingSource, uvBand,
} from "../utils/currentConditions";

const ICONS = { Cloud, CloudFog, CloudLightning, CloudMoon, CloudRain, CloudSun, Cloudy, Moon, Sun };

export function WeatherIcon({ condition, isNight = false, className = "h-5 w-5" }) {
  const Icon = ICONS[getWeatherIcon(condition, isNight)] || Cloud;
  return <Icon className={className} strokeWidth={1.75} aria-hidden="true" />;
}

const round = (v) => (typeof v === "number" && !Number.isNaN(v) ? Math.round(v) : null);
const isNightAtTime = (date, lat, lng) => {
  const { sunrise, sunset } = SunCalc.getTimes(date, lat, lng);
  return !(date >= sunrise && date < sunset);
};

const PLACE_LABEL = { geolocation: "Your location", default: "Central Singapore" };

export function CurrentConditions({ location, hourly, isNight, offline, onRefresh, refreshing, onRemove }) {
  const w = location.weather || {};
  const temp = round(w.temperature);
  const feels = feelsLike(w.temperature, w.humidity);
  const source = readingSource(w.source);
  const readAt = formatClock(w.timestamp || location.lastFetched);
  const sunTimes = getSunTimesSync(location.latitude, location.longitude);
  const summary = generateCommentary({ condition: w.condition, temperature: w.temperature, humidity: w.humidity, uv_index: w.uv_index, sunTimes }).slice(0, 1);
  const rain = rainOutlook(hourly);
  const stale = offline || location.refreshFailed;
  const wind = round(w.wind_speed);

  const facts = [
    w.humidity != null && ["Humidity", `${round(w.humidity)}%`],
    wind != null && ["Wind", `${wind} km/h`],
    hourly[0]?.rainChance != null && ["Rain this hour", `${hourly[0].rainChance}%`],
    !isNight && typeof w.uv_index === "number" && ["UV", `${round(w.uv_index)} ${uvBand(w.uv_index)}`],
  ].filter(Boolean);

  return (
    <section aria-labelledby="now-heading" className="rounded-panel border border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-sm text-muted">
            {location.source === "geolocation" && <Navigation className="h-3.5 w-3.5" aria-hidden="true" />}
            {PLACE_LABEL[location.source] || "Saved place"}
          </p>
          <h1 id="now-heading" className="text-2xl font-semibold leading-tight [overflow-wrap:anywhere]">
            {w.area || location.name || "Singapore"}
          </h1>
        </div>
        <div className="flex items-center gap-1">
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="inline-flex min-h-11 items-center rounded-control px-2 text-sm font-medium text-muted hover:bg-surface-2 hover:text-bad"
          >
            Remove
          </button>
        )}
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-control px-2 text-sm font-medium text-accent hover:bg-surface-2 disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" />
            {refreshing ? "Updating" : "Update"}
          </button>
        )}
        </div>
      </div>

      {temp == null ? (
        <p className="mt-6 text-base">No reading for this place yet. Try Update in a minute.</p>
      ) : (
        <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2">
          <WeatherIcon condition={w.condition} isNight={isNight} className="h-12 w-12 text-accent" />
          <p className="text-[56px] font-medium leading-none tracking-[-0.02em] tabular-nums" aria-label={`${temp} degrees`}>
            {temp}°
          </p>
          <div>
            <p className="text-base font-medium">{w.condition || "Conditions not reported"}</p>
            {feels != null && feels !== temp && <p className="text-sm text-muted tabular-nums">Feels like {feels}°</p>}
          </div>
        </div>
      )}

      {(summary.length > 0 || rain) && (
        <p className="mt-4 max-w-[65ch] text-base">{[...summary, rain].filter(Boolean).join(" ")}</p>
      )}

      {facts.length > 0 && (
        <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-line pt-4 sm:grid-cols-4">
          {facts.map(([label, value]) => (
            <div key={label}>
              <dt className="text-sm text-muted">{label}</dt>
              <dd className="text-base font-medium tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {readAt && (
        <p className={`mt-4 text-sm ${stale ? "text-warn" : "text-muted"}`} role={stale ? "status" : undefined}>
          {stale
            ? `${offline ? "You are offline." : "Could not update."} Showing the reading from ${readAt}.`
            : `${source ? `${source} reading` : "Reading"} at ${readAt}`}
        </p>
      )}
    </section>
  );
}

export function HourlyForecast({ hourly, status, location }) {
  return (
    <section aria-labelledby="hourly-heading" className="rounded-panel border border-line bg-surface p-5">
      <h2 id="hourly-heading" className="text-base font-semibold">Next 12 hours</h2>
      {status === "loading" && <p className="mt-3 text-sm text-muted">Loading the hourly forecast...</p>}
      {status !== "loading" && hourly.length === 0 && (
        <p className="mt-3 text-sm text-muted">The hourly forecast is not available right now.</p>
      )}
      {hourly.length > 0 && (
        <div className="relative -mx-2 mt-3 overflow-x-auto pb-2" tabIndex={0} aria-label="Hourly forecast, scroll sideways for more">
          <ol className="flex min-w-max gap-1 px-2">
            {hourly.map((h) => (
              <li key={h.time.toISOString()} className="flex w-14 flex-col items-center gap-1.5 rounded-card py-2 text-center">
                <span className="text-sm text-muted">{formatHour(h.time)}</span>
                <WeatherIcon condition={h.condition} isNight={isNightAtTime(h.time, location.latitude, location.longitude)} className="h-5 w-5" />
                <span className="text-base font-medium tabular-nums">{round(h.temperature) != null ? `${round(h.temperature)}°` : "n/a"}</span>
                <span className={`text-xs tabular-nums ${h.rainChance >= 50 ? "font-semibold text-rain" : "text-muted"}`}>
                  {h.rainChance != null ? `${h.rainChance}%` : ""}
                  <span className="sr-only"> chance of rain</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {hourly.length > 0 && <p className="mt-1 text-xs text-muted">Percentages are the chance of rain. Hourly forecast from Open-Meteo.</p>}
    </section>
  );
}

const DAY = new Intl.DateTimeFormat("en-SG", { weekday: "short", timeZone: "UTC" });
const dayName = (iso, i) => (i === 0 && iso === new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Singapore" }) ? "Today" : DAY.format(new Date(`${iso}T00:00:00Z`)));

export function DailyForecast({ daily, status }) {
  const lows = daily.map((d) => d.low).filter((v) => v != null);
  const highs = daily.map((d) => d.high).filter((v) => v != null);
  const min = lows.length ? Math.min(...lows) : 0;
  const max = highs.length ? Math.max(...highs) : 1;
  const span = Math.max(max - min, 1);
  return (
    <section aria-labelledby="daily-heading" className="rounded-panel border border-line bg-surface p-5">
      <h2 id="daily-heading" className="text-base font-semibold">Next {daily.length || 7} days</h2>
      {status === "loading" && <p className="mt-3 text-sm text-muted">Loading the daily forecast...</p>}
      {status !== "loading" && daily.length === 0 && <p className="mt-3 text-sm text-muted">The daily forecast is not available right now.</p>}
      {daily.length > 0 && (
        <ul className="mt-2 divide-y divide-line">
          {daily.map((d, i) => {
            const lo = round(d.low);
            const hi = round(d.high);
            return (
              <li key={d.date} className="grid grid-cols-[3rem_1.5rem_minmax(0,1fr)_2.5rem_minmax(3rem,8rem)_2.5rem] items-center gap-x-2 py-2.5 sm:gap-x-3">
                <span className="text-sm font-medium">{dayName(d.date, i)}</span>
                <WeatherIcon condition={d.condition} className="h-5 w-5 text-muted" />
                <span className="truncate text-sm text-muted">{d.condition}</span>
                <span className="text-right text-sm tabular-nums text-muted">{lo != null ? `${lo}°` : "n/a"}</span>
                <span className="relative h-1.5 rounded-full bg-surface-2" aria-hidden="true">
                  {lo != null && hi != null && (
                    <span className="absolute inset-y-0 rounded-full bg-muted/70" style={{ left: `${((lo - min) / span) * 100}%`, width: `${Math.max(((hi - lo) / span) * 100, 6)}%` }} />
                  )}
                </span>
                <span className="text-sm font-medium tabular-nums">{hi != null ? `${hi}°` : "n/a"}</span>
              </li>
            );
          })}
        </ul>
      )}
      {daily.length > 0 && <p className="mt-2 text-xs text-muted">NEA four-day outlook, extended with Open-Meteo.</p>}
    </section>
  );
}

export function DetailsList({ location, extra }) {
  const w = location.weather || {};
  const sun = getSunTimesSync(location.latitude, location.longitude);
  const dir = compassPoint(extra?.wind_direction);
  const rows = [
    ["Feels like", feelsLike(w.temperature, w.humidity) != null && `${feelsLike(w.temperature, w.humidity)}°`, "Heat index from temperature and humidity"],
    ["Humidity", w.humidity != null && `${round(w.humidity)}%`],
    ["Wind", w.wind_speed != null && `${round(w.wind_speed)} km/h${dir ? ` from the ${dir}` : ""}`],
    ["Rainfall", typeof extra?.rainfall === "number" && `${extra.rainfall} mm`, "Measured at the nearest NEA station"],
    ["Visibility", typeof w.visibility === "number" && `${w.visibility} km`],
    ["Pressure", typeof w.pressure === "number" && `${round(w.pressure)} hPa`],
    ["UV index", typeof w.uv_index === "number" && `${round(w.uv_index)}, ${uvBand(w.uv_index).toLowerCase()}`],
    ["Sunrise", sun.sunrise !== "N/A" && sun.sunrise.toLowerCase()],
    ["Sunset", sun.sunset !== "N/A" && sun.sunset.toLowerCase()],
  ].filter(([, value]) => value);

  return (
    <section aria-labelledby="details-heading" className="rounded-panel border border-line bg-surface p-5">
      <h2 id="details-heading" className="text-base font-semibold">Details</h2>
      <dl className="mt-2 grid gap-x-8 sm:grid-cols-2">
        {rows.map(([label, value, note]) => (
          <div key={label} className="flex items-baseline justify-between gap-4 border-b border-line py-2.5">
            <dt className="text-sm text-muted" title={note}>{label}</dt>
            <dd className="text-right text-sm font-medium tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
