import { useEffect, useRef, useState } from "react";
import { BAND_COLORS, REGIONS, capitalise, compass, fmtDay, fmtTime } from "./hazeData";

const H = 118;
const PAD = { top: 10, right: 10, bottom: 20, left: 30 };

function useWidth() {
  const ref = useRef(null);
  const [width, setWidth] = useState(300);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(200, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

function linePath(values, x, y) {
  let d = "";
  let pen = false;
  values.forEach((v, i) => {
    if (v == null) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    pen = true;
  });
  return d;
}

function areaPath(values, x, y, base) {
  const parts = [];
  let run = [];
  const flush = () => {
    if (run.length > 1) {
      parts.push(
        `M${x(run[0][0]).toFixed(1)},${base}` +
          run.map(([i, v]) => `L${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("") +
          `L${x(run[run.length - 1][0]).toFixed(1)},${base}Z`,
      );
    }
    run = [];
  };
  values.forEach((v, i) => (v == null ? flush() : run.push([i, v])));
  flush();
  return parts.join("");
}

function Frame({ title, unit, readout, children, width, n, cursor, onScrub, hours, yTicks, y }) {
  const plotW = width - PAD.left - PAD.right;
  const x = (i) => PAD.left + (n > 1 ? (i / (n - 1)) * plotW : 0);
  const scrub = (e) => {
    if (e.type === "pointermove" && e.buttons !== 1) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const f = (e.clientX - rect.left - PAD.left) / plotW;
    onScrub(Math.max(0, Math.min(n - 1, Math.round(f * (n - 1)))));
  };
  const dayTicks = hours
    .map((h, i) => ({ h, i }))
    .filter(({ h, i }) => fmtTime(h) === "00:00" && x(i) < width - PAD.right - 34);
  return (
    <figure className="hz-chart">
      <figcaption>
        <span className="hz-chart-title">{title}</span>
        {unit && <span className="hz-chart-unit">{unit}</span>}
        <span className="hz-chart-readout">{readout}</span>
      </figcaption>
      <svg
        width={width}
        height={H}
        onPointerDown={scrub}
        onPointerMove={scrub}
        role="img"
        aria-label={`${title}. ${readout}`}
      >
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} className="hz-grid" />
            <text x={PAD.left - 6} y={y(t) + 3} className="hz-axis" textAnchor="end">{t}</text>
          </g>
        ))}
        {dayTicks.map(({ h, i }) => (
          <g key={h}>
            <line x1={x(i)} x2={x(i)} y1={PAD.top} y2={H - PAD.bottom} className="hz-grid hz-grid-day" />
            <text x={x(i) + 3} y={H - 6} className="hz-axis">{fmtDay(h)}</text>
          </g>
        ))}
        {children(x)}
        <line x1={x(cursor)} x2={x(cursor)} y1={PAD.top - 4} y2={H - PAD.bottom} className="hz-cursor" />
      </svg>
    </figure>
  );
}

function niceMax(v, step) {
  return Math.max(step, Math.ceil(v / step) * step);
}

export function PsiChart({ scene, cursor, region, onScrub }) {
  const [ref, width] = useWidth();
  const n = scene.hours.length;
  const all = REGIONS.flatMap((r) => scene.psi[r]).filter((v) => v != null);
  const max = niceMax(Math.max(110, ...all), 50);
  const y = (v) => PAD.top + (1 - v / max) * (H - PAD.top - PAD.bottom);
  const value = scene.psi[region]?.[cursor];
  const guides = [50, 100, 200, 300].filter((g) => g < max);
  return (
    <div ref={ref} className="hz-chart-wrap">
      <Frame
        title="PSI by region"
        unit="24-hour"
        readout={value != null ? `${capitalise(region)} ${value}` : "No reading"}
        width={width}
        n={n}
        cursor={cursor}
        onScrub={onScrub}
        hours={scene.hours}
        yTicks={[0, ...guides.filter((g) => g !== 300 || max > 300)]}
        y={y}
      >
        {(x) => (
          <>
            {guides.map((g) => (
              <line key={g} x1={PAD.left} x2={width - PAD.right} y1={y(g)} y2={y(g)} className="hz-guide" />
            ))}
            {REGIONS.filter((r) => r !== region).map((r) => (
              <path key={r} d={linePath(scene.psi[r], x, y)} className="hz-line-quiet" />
            ))}
            <path d={linePath(scene.psi[region], x, y)} className="hz-line-main" />
            {value != null && <circle cx={x(cursor)} cy={y(value)} r="3.5" className="hz-dot" />}
          </>
        )}
      </Frame>
    </div>
  );
}

const PM_BANDS = [
  { from: 0, to: 55, key: "normal" },
  { from: 55, to: 150, key: "elevated" },
  { from: 150, to: 250, key: "high" },
  { from: 250, to: 500, key: "very_high" },
];

export function Pm25Chart({ scene, cursor, region, onScrub }) {
  const [ref, width] = useWidth();
  const n = scene.hours.length;
  const series = scene.pm25[region] || [];
  const all = REGIONS.flatMap((r) => scene.pm25[r]).filter((v) => v != null);
  const max = niceMax(Math.max(80, ...all) * 1.1, 20);
  const y = (v) => PAD.top + (1 - Math.min(v, max) / max) * (H - PAD.top - PAD.bottom);
  const value = series[cursor];
  const base = H - PAD.bottom;
  return (
    <div ref={ref} className="hz-chart-wrap">
      <Frame
        title="PM2.5 against health bands"
        unit="µg/m³, 1-hour"
        readout={value != null ? `${capitalise(region)} ${value}` : "No reading"}
        width={width}
        n={n}
        cursor={cursor}
        onScrub={onScrub}
        hours={scene.hours}
        yTicks={[0, 55, 150].filter((t) => t < max)}
        y={y}
      >
        {(x) => (
          <>
            {PM_BANDS.filter((b) => b.from < max).map((b) => (
              <rect
                key={b.key}
                x={PAD.left}
                width={width - PAD.left - PAD.right}
                y={y(Math.min(b.to, max))}
                height={y(b.from) - y(Math.min(b.to, max))}
                fill={BAND_COLORS[b.key]}
                opacity="0.11"
              />
            ))}
            <path d={areaPath(series, x, y, base)} className="hz-area" />
            <path d={linePath(series, x, y)} className="hz-line-main" />
            {value != null && <circle cx={x(cursor)} cy={y(value)} r="3.5" className="hz-dot" />}
          </>
        )}
      </Frame>
    </div>
  );
}

export function WindChart({ scene, cursor, onScrub }) {
  const [ref, width] = useWidth();
  const n = scene.hours.length;
  const speeds = scene.wind.mean.map((w) => (w ? w.speed_kn : null));
  const max = niceMax(Math.max(6, ...speeds.filter((v) => v != null)) * 1.15, 2);
  const y = (v) => PAD.top + (1 - v / max) * (H - PAD.top - PAD.bottom);
  const w = scene.wind.mean[cursor];
  const step = Math.max(1, Math.round(n / 18));
  return (
    <div ref={ref} className="hz-chart-wrap">
      <Frame
        title="Wind"
        unit="knots, Singapore average"
        readout={w ? `${w.speed_kn.toFixed(1)} from the ${compass(w.dir_deg)}` : "No reading"}
        width={width}
        n={n}
        cursor={cursor}
        onScrub={onScrub}
        hours={scene.hours}
        yTicks={[0, Math.round(max / 2), max]}
        y={y}
      >
        {(x) => (
          <>
            <path d={linePath(speeds, x, y)} className="hz-line-main hz-line-wind" />
            {scene.wind.mean.map((m, i) =>
              m && i % step === 0 ? (
                <g key={i} transform={`translate(${x(i)},${PAD.top + 8}) rotate(${m.dir_deg + 180})`}>
                  <path d="M0,-5 L3,3 L0,1.5 L-3,3 Z" className="hz-arrow" />
                </g>
              ) : null,
            )}
            {w && <circle cx={x(cursor)} cy={y(w.speed_kn)} r="3.5" className="hz-dot" />}
          </>
        )}
      </Frame>
    </div>
  );
}
