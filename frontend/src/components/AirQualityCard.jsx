import { useEffect, useState } from "react";
import { Wind } from "lucide-react";
import { getAirQualityHistory, getAirQualityLatest } from "../api/airQuality";
import {
  BAND_STROKE,
  BAND_STYLES,
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
    <span className={`px-2 py-0.5 rounded-full border text-[11px] font-medium ${BAND_STYLES[band.key] || ""}`}>
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

  const shell = "rounded-2xl bg-white/5 border border-white/10 p-4 text-sm";
  const header = (
    <div className="flex items-center gap-1.5 text-white/70 text-xs font-medium mb-2">
      <Wind className="w-3.5 h-3.5" aria-hidden="true" />
      <h2>Air quality / Haze</h2>
    </div>
  );

  if (!latest) {
    return (
      <section className={shell} aria-label="Air quality">
        {header}
        <p className="text-white/50 text-xs">{failed ? "Air quality unavailable right now." : "Loading air quality…"}</p>
      </section>
    );
  }

  const links = (
    <p className="text-white/40 text-[11px] mt-2">
      NEA data.{" "}
      <a href={latest.links?.haze} target="_blank" rel="noopener noreferrer" className="underline hover:text-white/70">
        haze.gov.sg
      </a>{" "}
      ·{" "}
      <a href={latest.links?.nea} target="_blank" rel="noopener noreferrer" className="underline hover:text-white/70">
        NEA advisories
      </a>
    </p>
  );

  if (latest.status === "unavailable") {
    const last = formatSgtTime(latest.last_good_observed_at);
    return (
      <section className={shell} aria-label="Air quality">
        {header}
        <p className="text-amber-200 text-xs" role="status">
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
      <p className="text-white/50 text-[11px] mb-2">{areaLabel}</p>
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-white/50 text-[11px]">24-hr PSI</div>
          <div className="text-white text-2xl font-light leading-tight" data-testid="psi-value">{psiText}</div>
        </div>
        <BandBadge band={psiBand} />
      </div>
      <div className="flex items-center justify-between gap-2 mt-2">
        <div className="text-white/80 text-xs">
          1-hr PM2.5 <span className="text-white font-medium" data-testid="pm25-value">{pm25}</span> µg/m³
        </div>
        <BandBadge band={pm25Band} />
      </div>
      {psiBand && <p className="text-white/70 text-xs mt-2">{psiBand.advice}.</p>}
      {pm25Band && pm25Band.key !== "normal" && (
        <p className="text-white/70 text-xs mt-1">Next hour: {pm25Band.advice.replace(/ for the next hour$/, "")}.</p>
      )}
      <div className="mt-2">
        {series.length > 1 && <div className="text-white/40 text-[10px]">PSI, last 24 h</div>}
        <Sparkline
          values={series}
          stroke={BAND_STROKE[psiBand?.key] || "#94a3b8"}
          label={series.length ? `24-hr PSI over the last 24 hours, from ${series[0]} to ${series[series.length - 1]}` : ""}
        />
      </div>
      <p className={`text-[11px] mt-1 ${latest.status === "stale" ? "text-amber-200" : "text-white/50"}`} role={latest.status === "stale" ? "status" : undefined}>
        {latest.status === "stale" ? `Delayed: last NEA reading ${updated}` : `Updated ${updated}`}
      </p>
      {links}
    </section>
  );
}
