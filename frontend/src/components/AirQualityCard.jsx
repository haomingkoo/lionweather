import { useEffect, useState } from "react";
import { Wind } from "lucide-react";
import { getAirQualityHistory, getAirQualityLatest } from "../api/airQuality";
import {
  BAND_STROKE,
  BAND_TEXT,
  formatSgtTime,
  nearestRegion,
  psiSeries,
} from "../utils/airQuality";

const REFRESH_MS = 15 * 60 * 1000;

function capitalise(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function BandBadge({ band }) {
  if (!band) return null;
  return (
    <span className={`text-sm font-semibold ${BAND_TEXT[band.key] || "text-ink"}`}>
      {band.label}
    </span>
  );
}

function Sparkline({ values, stroke, label }) {
  if (values.length < 2) return null;
  const w = 240;
  const h = 32;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values
    .map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(h - 2 - ((v - min) / span) * (h - 4)).toFixed(1)}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-8" role="img" aria-label={label} preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function AirQualityCard({ location = null }) {
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [l, h] = await Promise.all([
          getAirQualityLatest(),
          getAirQualityHistory(24).catch(() => ({ points: [] })),
        ]);
        if (cancelled) return;
        setLatest(l);
        setHistory(h.points || []);
        setFailed(false);
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const shell = "rounded-panel border border-line bg-surface p-4 text-sm";
  const header = (
    <h2 className="mb-2 flex items-center gap-1.5 text-base font-semibold">
      <Wind className="h-4 w-4 text-muted" aria-hidden="true" />
      Air quality
    </h2>
  );

  if (!latest) {
    return (
      <section className={shell} aria-label="Air quality">
        {header}
        <p className="text-sm text-muted">{failed ? "Air quality is not available right now." : "Loading air quality..."}</p>
      </section>
    );
  }

  const links = (
    <p className="mt-3 flex flex-wrap items-center gap-x-1 text-xs text-muted">
      From NEA.
      <a href={latest.links?.haze} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-6 items-center underline underline-offset-2 hover:text-ink">
        haze.gov.sg
      </a>
      <span aria-hidden="true">·</span>
      <a href={latest.links?.nea} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-6 items-center underline underline-offset-2 hover:text-ink">
        NEA advisories
      </a>
    </p>
  );

  if (latest.status === "unavailable") {
    const last = formatSgtTime(latest.last_good_observed_at);
    return (
      <section className={shell} aria-label="Air quality">
        {header}
        <p className="text-sm text-warn" role="status">
          Air quality unavailable from NEA right now.
          {last ? ` Last good reading: ${last}.` : ""}
        </p>
        {links}
      </section>
    );
  }

  const region = nearestRegion(location, latest.regions);
  const psi = region ? region.psi_24h : latest.national.psi_24h_max;
  const psiText = region
    ? String(region.psi_24h)
    : latest.national.psi_24h_min === latest.national.psi_24h_max
      ? String(psi)
      : `${latest.national.psi_24h_min}–${latest.national.psi_24h_max}`;
  const psiBand = region ? region.psi_band : latest.national.psi_band;
  const pm25 = region ? region.pm25_1h : latest.national.pm25_1h_max;
  const pm25Band = region ? region.pm25_band : latest.national.pm25_band;
  const areaLabel = region ? `${capitalise(region.region)} region` : "National";
  const series = psiSeries(history, region?.region);
  const updated = formatSgtTime(latest.observed_at);

  return (
    <section className={shell} aria-label="Air quality">
      {header}
      <p className="mb-2 text-sm text-muted">{areaLabel}</p>
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-sm text-muted">24-hour PSI</div>
          <div className="text-2xl font-medium leading-tight tabular-nums" data-testid="psi-value">{psiText}</div>
        </div>
        <BandBadge band={psiBand} />
      </div>
      <div className="flex items-center justify-between gap-2 mt-2">
        <div className="text-sm text-muted">
          1-hour PM2.5 <span className="font-medium tabular-nums text-ink" data-testid="pm25-value">{pm25}</span> µg/m³
        </div>
        <BandBadge band={pm25Band} />
      </div>
      {psiBand && <p className="mt-2 text-sm">{psiBand.advice}.</p>}
      {pm25Band && pm25Band.key !== "normal" && (
        <p className="mt-1 text-sm">Next hour: {pm25Band.advice.replace(/ for the next hour$/, "")}.</p>
      )}
      <div className="mt-2">
        {series.length > 1 && <div className="text-xs text-muted">PSI over the last 24 hours</div>}
        <Sparkline
          values={series}
          stroke={BAND_STROKE[psiBand?.key] || "rgb(var(--muted))"}
          label={series.length ? `24-hr PSI over the last 24 hours, from ${series[0]} to ${series[series.length - 1]}` : ""}
        />
      </div>
      <p className={`mt-1 text-xs ${latest.status === "stale" ? "text-warn" : "text-muted"}`} role={latest.status === "stale" ? "status" : undefined}>
        {latest.status === "stale" ? `Delayed: last NEA reading ${updated}` : `Updated ${updated}`}
      </p>
      <a href="/haze" className="mt-2 inline-flex min-h-6 items-center text-sm font-medium text-accent underline underline-offset-2 hover:text-ink">
        See the haze hour by hour on a 3D map
      </a>
      {links}
    </section>
  );
}
