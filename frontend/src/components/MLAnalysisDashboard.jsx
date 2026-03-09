/**
 * MLAnalysisDashboard
 *
 * Full ML analysis view: EDA, ACF/PACF, FFT, spurious correlations,
 * SHAP, training loss curves, and classification performance.
 *
 * Data comes from GET /api/ml/full-analysis (populated after running
 * `python -m ml.train_full_analysis` in the backend).
 */
import { useState, useEffect } from "react";
import {
  Brain,
  Activity,
  BarChart3,
  TrendingUp,
  Waves,
  GitCompare,
  RefreshCw,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Thermometer,
  Droplets,
  Wind,
  Trophy,
} from "lucide-react";
import { getFullAnalysis } from "../api/ml";

// ---------------------------------------------------------------------------
// Colour palette for chart lines
// ---------------------------------------------------------------------------
const PALETTE = [
  "#60a5fa", // blue-400
  "#34d399", // emerald-400
  "#f472b6", // pink-400
  "#fbbf24", // amber-400
  "#a78bfa", // violet-400
];


// ---------------------------------------------------------------------------
// Tiny inline SVG chart primitives (no chart library dep)
// ---------------------------------------------------------------------------
function MiniBarChart({ data, height = 60, color = "#60a5fa", label, xTicks = null, showYAxis = false }) {
  if (!data || data.length === 0) return null;
  const vals = data.map((d) => (typeof d === "object" ? d.value ?? d : d));
  const max = Math.max(...vals, 0.001);
  const barW = Math.max(1, Math.floor(240 / vals.length));
  const PAD_B = xTicks && xTicks.length > 0 ? 14 : 0;
  const PAD_L = showYAxis ? 30 : 0;
  const plotH = height - PAD_B;
  const W = Math.max(PAD_L + vals.length * (barW + 1), 60);

  const fmtY = (v) => v >= 10000 ? `${(v/1000).toFixed(0)}K` : v >= 1000 ? `${(v/1000).toFixed(1)}K` : v >= 100 ? Math.round(v) : v.toFixed(0);
  const yLabels = showYAxis ? [
    { val: fmtY(max), y: 1 },
    { val: fmtY(max / 2), y: plotH / 2 },
    { val: "0", y: plotH },
  ] : [];

  return (
    <div style={{ maxWidth: `${W}px` }}>
      {label && <p className="text-white/50 text-xs mb-1">{label}</p>}
      <svg width="100%" viewBox={`0 0 ${W} ${height}`} className="overflow-visible">
        {yLabels.map(({ val, y }, i) => (
          <g key={i}>
            <line x1={PAD_L} y1={y} x2={W} y2={y} stroke="#ffffff0a" strokeWidth="0.5" />
            <text x={PAD_L - 3} y={y + 3} fontSize="6" fill="#ffffff40" textAnchor="end" fontFamily="monospace">{val}</text>
          </g>
        ))}
        {vals.map((v, i) => (
          <rect
            key={i}
            x={PAD_L + i * (barW + 1)}
            y={plotH - (v / max) * plotH}
            width={barW}
            height={(v / max) * plotH}
            fill={color}
            opacity={0.8}
          />
        ))}
        {xTicks && xTicks.map(({ label: tickLabel, index }, i) => (
          <text
            key={i}
            x={PAD_L + index * (barW + 1) + barW / 2}
            y={height - 2}
            fontSize="6"
            fill="#ffffff40"
            textAnchor="middle"
            fontFamily="monospace"
          >
            {tickLabel}
          </text>
        ))}
      </svg>
    </div>
  );
}

function LineChart({ series, height = 80, xTicks, xTickIndices, xLabel, yLabel, showYAxis = true, bandSeries = null }) {
  // series = [{ name, data: [number], color }]
  // bandSeries = { min: [number], max: [number], color } — optional shaded band
  if (!series || series.length === 0) return null;
  const allVals = [
    ...series.flatMap((s) => s.data.filter(Number.isFinite)),
    ...(bandSeries ? [...bandSeries.min, ...bandSeries.max].filter(Number.isFinite) : []),
  ];
  if (allVals.length === 0) return null;

  const maxLen = Math.max(...series.map((s) => s.data.length));
  const rawMinY = Math.min(...allVals);
  const rawMaxY = Math.max(...allVals);
  const rangePad = Math.max((rawMaxY - rawMinY) * 0.12, 0.5);
  const minY = rawMinY - rangePad;
  const maxY = rawMaxY + rangePad;
  const rangeY = Math.max(maxY - minY, 0.001);

  const W = 360;
  const H = height;
  const PAD_L = showYAxis ? 38 : 6;
  const PAD_R = 6;
  const PAD_T = 6;
  const PAD_B = xTicks && xTicks.length > 0 ? 20 : 6;
  const PLOT_W = W - PAD_L - PAD_R;
  const PLOT_H = H - PAD_T - PAD_B;

  const toX = (i) => PAD_L + (i / Math.max(maxLen - 1, 1)) * PLOT_W;
  const toY = (v) => PAD_T + PLOT_H - ((v - minY) / rangeY) * PLOT_H;

  // Y gridlines — nicely rounded values
  const nGridlines = 4;
  const yGridlines = Array.from({ length: nGridlines }, (_, i) => {
    const val = rawMinY + (i / (nGridlines - 1)) * (rawMaxY - rawMinY);
    return { val, y: toY(val) };
  });

  // Optional band polygon points
  const bandPoints = bandSeries
    ? [
        ...bandSeries.max.map((v, i) => `${toX(i)},${toY(v)}`),
        ...[...bandSeries.min].reverse().map((v, i) => `${toX(bandSeries.min.length - 1 - i)},${toY(v)}`),
      ].join(" ")
    : null;

  return (
    <div style={{ maxWidth: "480px" }}>
      {(xLabel || yLabel) && (
        <div className="flex justify-between text-white/40 text-[10px] mb-0.5">
          <span>{yLabel}</span><span>{xLabel}</span>
        </div>
      )}
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
        {/* Gridlines + Y labels */}
        {yGridlines.map(({ val, y }, i) => (
          <g key={i}>
            <line x1={PAD_L} y1={y} x2={W - PAD_R} y2={y}
                  stroke="#ffffff12" strokeWidth="1" />
            {showYAxis && (
              <text x={PAD_L - 4} y={y + 3.5}
                    fontSize="6.5" fill="#ffffff50" textAnchor="end" fontFamily="monospace">
                {(() => {
                  const abs = Math.abs(val);
                  const sign = val < 0 ? "−" : "";
                  if (abs >= 1000) return `${sign}${(abs / 1000).toFixed(abs >= 10000 ? 0 : 1)}K`;
                  if (abs < 10) return val.toFixed(1);
                  return `${sign}${Math.round(abs)}`;
                })()}
              </text>
            )}
          </g>
        ))}
        {/* Optional band */}
        {bandPoints && (
          <polygon points={bandPoints}
            fill={bandSeries.color || "#60a5fa"} opacity={0.12} />
        )}
        {/* X tick labels — positions either at specific data indices or evenly spaced */}
        {xTicks && xTicks.map((tick, i) => {
          const x = xTickIndices
            ? toX(xTickIndices[i])
            : PAD_L + (i / Math.max(xTicks.length - 1, 1)) * PLOT_W;
          return (
            <text key={i} x={x} y={H - 3}
                  fontSize="6.5" fill="#ffffff35" textAnchor="middle" fontFamily="monospace">
              {tick}
            </text>
          );
        })}
        {/* Series lines */}
        {series.map((s, si) => {
          const pts = s.data
            .map((v, i) => `${toX(i)},${toY(v)}`)
            .join(" ");
          return (
            <polyline
              key={si}
              points={pts}
              fill="none"
              stroke={s.color || PALETTE[si % PALETTE.length]}
              strokeWidth="1.5"
              strokeLinejoin="round"
              opacity={0.9}
            />
          );
        })}
      </svg>
      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-1">
        {series.map((s, i) => (
          <div key={i} className="flex items-center gap-1">
            <span className="w-4 h-1 inline-block rounded"
              style={{ background: s.color || PALETTE[i % PALETTE.length] }} />
            <span className="text-white/60 text-[10px]">{s.name}</span>
          </div>
        ))}
        {bandSeries && (
          <div className="flex items-center gap-1">
            <span className="w-4 h-3 inline-block rounded opacity-40"
              style={{ background: bandSeries.color || "#60a5fa" }} />
            <span className="text-white/60 text-[10px]">{bandSeries.name || "Range"}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function StemChart({ lags, values, ci, height = 90, color = "#60a5fa", title }) {
  // ACF / PACF stem plot with x/y axis labels
  if (!lags || !values) return null;
  const W = 360;
  const H = height;
  const PAD_L = 28;  // y-axis labels
  const PAD_R = 8;
  const PAD_B = 14; // x-axis labels
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_B;
  const nLags = lags.length;
  const stepX = plotW / Math.max(nLags - 1, 1);
  const midY = plotH / 2;
  const scale = (midY - 6) * 0.9;

  const toX = (i) => PAD_L + i * stepX;
  const toY = (v) => midY - v * scale;
  const ciY = ci ? midY - ci * scale : midY - 1.96 * scale / Math.sqrt(100);

  // Y-axis: -1, 0, +1
  const yLabels = [
    { val: "1.0",  y: toY(1.0) },
    { val: "0",    y: midY },
    { val: "-1",   y: toY(-1.0) },
  ];

  // X-axis: show ~6 evenly spaced lag numbers
  const xStep = Math.max(1, Math.floor(nLags / 6));
  const xLabelIdxs = [...Array.from({ length: Math.ceil(nLags / xStep) }, (_, j) => j * xStep), nLags - 1]
    .filter((v, i, a) => a.indexOf(v) === i && v < nLags);

  return (
    <div style={{ maxWidth: "480px" }}>
      {title && <p className="text-white/50 text-xs mb-1">{title}</p>}
      <svg width="100%" viewBox={`0 0 ${W} ${H}`}>
        {/* Y-axis labels + gridlines */}
        {yLabels.map(({ val, y }) => (
          <g key={val}>
            <line x1={PAD_L} y1={y} x2={W - PAD_R} y2={y}
                  stroke="#ffffff08" strokeWidth="0.5" strokeDasharray="2,3" />
            <text x={PAD_L - 3} y={y + 3} fontSize="6" fill="#ffffff40"
                  textAnchor="end" fontFamily="monospace">{val}</text>
          </g>
        ))}
        {/* zero line (slightly stronger) */}
        <line x1={PAD_L} y1={midY} x2={W - PAD_R} y2={midY}
              stroke="#ffffff25" strokeWidth="1" />
        {/* CI bounds */}
        {ci && (
          <>
            <line x1={PAD_L} y1={ciY} x2={W - PAD_R} y2={ciY}
                  stroke="#fbbf2455" strokeWidth="1" strokeDasharray="4,2" />
            <line x1={PAD_L} y1={toY(-ci)} x2={W - PAD_R} y2={toY(-ci)}
                  stroke="#fbbf2455" strokeWidth="1" strokeDasharray="4,2" />
          </>
        )}
        {/* stems */}
        {lags.map((lag, i) => {
          const x = toX(i);
          const y = toY(values[i]);
          const aboveThreshold = Math.abs(values[i]) > (ci || 0);
          return (
            <g key={lag}>
              <line x1={x} y1={midY} x2={x} y2={y}
                    stroke={aboveThreshold ? color : "#ffffff22"}
                    strokeWidth="1.2" />
              <circle cx={x} cy={y} r="1.8"
                      fill={aboveThreshold ? color : "#ffffff22"} />
            </g>
          );
        })}
        {/* X-axis lag labels */}
        {xLabelIdxs.map((idx) => (
          <text key={idx} x={toX(idx)} y={H - 2} fontSize="6"
                fill="#ffffff30" textAnchor="middle" fontFamily="monospace">
            {lags[idx]}
          </text>
        ))}
      </svg>
    </div>
  );
}

function HorizontalBar({ items, nameKey = "feature", valueKey = "mean_abs_shap",
                          color = "#60a5fa", maxItems = 12 }) {
  if (!items || items.length === 0) return null;
  const top = items.slice(0, maxItems);
  const maxVal = Math.max(...top.map((d) => Math.abs(d[valueKey])), 0.001);

  return (
    <div className="space-y-1.5">
      {top.map((d, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-white/60 text-[10px] w-36 truncate text-right shrink-0">
            {d[nameKey]}
          </span>
          <div className="flex-1 bg-white/10 rounded-full h-3 relative overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${100 * Math.abs(d[valueKey]) / maxVal}%`,
                background: color,
                opacity: 0.85,
              }}
            />
          </div>
          <span className="text-white/50 text-[10px] w-14 shrink-0">
            {typeof d[valueKey] === "number" ? d[valueKey].toFixed(4) : d[valueKey]}
          </span>
        </div>
      ))}
    </div>
  );
}

function ConfusionMatrix({ matrix, labels }) {
  if (!matrix) return null;
  const maxVal = Math.max(...matrix.flat());

  return (
    <div className="overflow-x-auto">
      <table className="text-[10px] border-collapse">
        <thead>
          <tr>
            <th className="text-white/40 p-1">P↓ A→</th>
            {labels.map((l) => (
              <th key={l} className="text-white/60 p-1 text-center max-w-[60px] truncate">
                {l.split(" ")[0]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <td className="text-white/60 p-1 pr-2 text-right">{labels[i]?.split(" ")[0]}</td>
              {row.map((val, j) => {
                const bg = i === j
                  ? `rgba(52, 211, 153, ${val / maxVal})`
                  : `rgba(248, 113, 113, ${val / maxVal * 0.8})`;
                return (
                  <td key={j} className="p-1 text-center font-mono text-white/90 rounded"
                      style={{ background: bg }}>
                    {val}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Educational commentary panel shown below each section
function CommentaryBox({ points, tip, variant = "indigo" }) {
  const colors = {
    indigo: { bg: "bg-indigo-500/8", border: "border-indigo-400/15", title: "text-indigo-300/80", bullet: "text-indigo-400/60", body: "text-white/60", foot: "text-indigo-300/35" },
    blue:   { bg: "bg-blue-500/8",   border: "border-blue-400/15",   title: "text-blue-300/80",   bullet: "text-blue-400/60",   body: "text-white/60", foot: "text-blue-300/35" },
    amber:  { bg: "bg-amber-500/8",  border: "border-amber-400/15",  title: "text-amber-300/80",  bullet: "text-amber-400/60",  body: "text-white/60", foot: "text-amber-300/35" },
  };
  const c = colors[variant] || colors.indigo;
  return (
    <div className={`mt-3 ${c.bg} border ${c.border} rounded-xl p-3 space-y-1.5`}>
      <p className={`${c.title} text-[10px] font-semibold uppercase tracking-wide`}>How to read this</p>
      <ul className="space-y-1.5">
        {points.map((p, i) => (
          <li key={i} className={`flex gap-2 ${c.body} text-[11px] leading-relaxed`}>
            <span className={`${c.bullet} shrink-0 mt-0.5`}>›</span>
            <span>{p}</span>
          </li>
        ))}
      </ul>
      {tip && <p className={`${c.foot} text-[10px] italic mt-1`}>{tip}</p>}
    </div>
  );
}

function StackedBarChart({ years, stacks, height = 70 }) {
  // stacks = [{ key, color, label }]
  if (!years || years.length === 0) return null;
  const BAR_W = 28;
  const W = years.length * BAR_W;
  const LABEL_H = 12;
  const SVG_H = height + LABEL_H;
  return (
    <div style={{ maxWidth: `${W}px` }}>
      <svg width="100%" viewBox={`0 0 ${W} ${SVG_H}`} className="overflow-visible">
        {years.map((_y, xi) => {
          let cumY = height;
          return stacks.map((s) => {
            const pct = s.data[xi] ?? 0;
            const barH = (pct / 100) * height;
            cumY -= barH;
            return (
              <rect
                key={s.key}
                x={xi * BAR_W + 2}
                y={cumY}
                width={BAR_W - 4}
                height={barH}
                fill={s.color}
                opacity={0.85}
              />
            );
          });
        })}
        {years.map((y, xi) => (
          <text
            key={y}
            x={xi * BAR_W + BAR_W / 2}
            y={SVG_H - 1}
            fontSize="7"
            fill="#ffffff35"
            textAnchor="middle"
            fontFamily="monospace"
          >
            {y}
          </text>
        ))}
      </svg>
    </div>
  );
}

function AnalysisSummary({ ct }) {
  const years = ct.years_covered || [];
  const annual = ct.annual || {};
  const trends = ct.long_term_trends || {};
  const rec = ct.all_time_records || {};

  if (years.length < 2) return null;

  // Wettest and driest year
  const byRain = years
    .map((y) => ({ year: y, total: annual[y]?.rainfall?.total_mm ?? 0 }))
    .sort((a, b) => b.total - a.total);
  const wettest = byRain[0];
  const driest  = byRain[byRain.length - 1];

  // Hottest year
  const byTemp = years
    .map((y) => ({ year: y, mean: annual[y]?.temperature?.mean_c ?? 0 }))
    .sort((a, b) => b.mean - a.mean);
  const hottestYear = byTemp[0];

  // Thundery trend
  const thundery2016 = annual["2016"]?.rainfall?.thundery_events ?? null;
  const thundery2024 = annual["2024"]?.rainfall?.thundery_events ?? null;
  const thunderyChange = (thundery2016 != null && thundery2024 != null)
    ? thundery2024 - thundery2016 : null;

  const tTrend = trends.temperature_mean;
  const rTrend = trends.rainfall_total;

  const bullets = [];

  // Rainfall
  if (wettest && driest) {
    bullets.push(`${wettest.year} was the wettest year on record (${wettest.total.toLocaleString()} mm island-wide), while ${driest.year} was the driest (${driest.total.toLocaleString()} mm) — a ${((wettest.total / driest.total - 1) * 100).toFixed(0)}% swing.`);
  }

  // Temperature trend
  if (tTrend?.significant) {
    bullets.push(`Temperatures are rising at +${tTrend.slope_per_year.toFixed(3)}°C per year (p=${tTrend.p_value}, R²=${tTrend.r_squared}) — consistent with Singapore's urban heat island effect and broader regional warming.`);
  } else if (tTrend) {
    bullets.push(`No statistically significant warming trend detected over the study period (p=${tTrend.p_value}), though year-to-year variability exists. Longer time series are needed to confirm.`);
  }

  // Hottest year
  if (hottestYear) {
    bullets.push(`${hottestYear.year} was the warmest on average (${hottestYear.mean.toFixed(1)}°C mean). The all-time record was ${rec.hottest_hour?.value_c}°C on ${rec.hottest_hour?.date}.`);
  }

  // Thundery events
  if (thunderyChange != null) {
    const dir = thunderyChange > 0 ? "increased" : "decreased";
    bullets.push(`Thundery shower hours ${dir} from ${thundery2016} in 2016 to ${thundery2024} in 2024, suggesting ${thunderyChange > 0 ? "more intense convective activity" : "fewer but potentially more intense storm episodes"}.`);
  }

  // Rainfall trend
  if (rTrend?.significant) {
    bullets.push(`Annual rainfall shows a statistically significant ${rTrend.trend} trend (${rTrend.slope_per_year > 0 ? "+" : ""}${rTrend.slope_per_year.toFixed(0)} mm/yr).`);
  }

  // All-time records
  if (rec.wettest_hour) {
    bullets.push(`The single wettest hour recorded was ${rec.wettest_hour.value_mm} mm on ${rec.wettest_hour.date} — likely a severe convective storm. The windiest hour hit ${rec.windiest_hour?.value_kmh} km/h on ${rec.windiest_hour?.date}.`);
  }

  if (bullets.length === 0) return null;

  return (
    <div className="bg-blue-500/5 border border-blue-400/15 rounded-xl p-3 space-y-2">
      <p className="text-blue-300/80 text-[10px] font-semibold uppercase tracking-wide">Analysis</p>
      <ul className="space-y-2">
        {bullets.map((b, i) => (
          <li key={i} className="flex gap-2 text-white/60 text-[11px] leading-relaxed">
            <span className="text-blue-400/60 shrink-0 mt-0.5">›</span>
            <span>{b}</span>
          </li>
        ))}
      </ul>
      <p className="text-white/20 text-[10px]">
        Based on NEA station data 2016–2024 · island-wide aggregate · {years.length} years
      </p>
    </div>
  );
}

function ClimateTrendsSection({ ct }) {
  const years = ct.years_covered || [];
  const annual = ct.annual || {};
  const trends = ct.long_term_trends || {};
  const stl = ct.stl_decomposition || {};
  const rec = ct.all_time_records || {};

  const rainfallTotals = years.map((y) => annual[y]?.rainfall?.total_mm ?? 0);
  // Drop years with effectively no data (< 100 mm total is clearly incomplete)
  const validYearMask = years.map((_, i) => rainfallTotals[i] >= 100);
  const displayYears = years.filter((_, i) => validYearMask[i]);
  const displayRainfallTotals = rainfallTotals.filter((_, i) => validYearMask[i]);
  const tempMeans = displayYears.map((y) => annual[y]?.temperature?.mean_c ?? 0);
  const rainCatStacks = [
    { key: "no_rain",    color: "#60a5fa", label: "No Rain",    data: displayYears.map((y) => annual[y]?.rainfall?.rain_category_pct?.no_rain ?? 0) },
    { key: "light_rain", color: "#34d399", label: "Light Rain", data: displayYears.map((y) => annual[y]?.rainfall?.rain_category_pct?.light_rain ?? 0) },
    { key: "heavy_rain", color: "#fbbf24", label: "Heavy Rain", data: displayYears.map((y) => annual[y]?.rainfall?.rain_category_pct?.heavy_rain ?? 0) },
    { key: "thundery",   color: "#f472b6", label: "Thundery",   data: displayYears.map((y) => annual[y]?.rainfall?.rain_category_pct?.thundery ?? 0) },
  ];

  const tTrend = trends.temperature_mean;
  const rTrend = trends.rainfall_total;

  const records = [
    { icon: Droplets, label: "Wettest Hour",    value: rec.wettest_hour  ? `${rec.wettest_hour.value_mm} mm`  : "—", date: rec.wettest_hour?.date,  color: "text-sky-400" },
    { icon: Thermometer, label: "Hottest Hour", value: rec.hottest_hour  ? `${rec.hottest_hour.value_c}°C`   : "—", date: rec.hottest_hour?.date,  color: "text-orange-400" },
    { icon: Thermometer, label: "Coolest Hour", value: rec.coolest_hour  ? `${rec.coolest_hour.value_c}°C`   : "—", date: rec.coolest_hour?.date,  color: "text-blue-300" },
    { icon: Wind,        label: "Windiest Hour",value: rec.windiest_hour ? `${rec.windiest_hour.value_kmh} km/h` : "—", date: rec.windiest_hour?.date, color: "text-teal-400" },
  ];

  return (
    <div className="space-y-5">
      {/* All-time records */}
      <div>
        <p className="text-white/50 text-xs font-medium mb-2 flex items-center gap-1">
          <Trophy className="w-3 h-3" /> All-time records (2016–2024)
        </p>
        <div className="grid grid-cols-2 gap-2">
          {records.map((r) => (
            <div key={r.label} className="bg-white/5 rounded-xl p-3 flex items-start gap-2">
              <r.icon className={`w-4 h-4 mt-0.5 shrink-0 ${r.color}`} />
              <div>
                <p className="text-white/40 text-[10px]">{r.label}</p>
                <p className={`font-semibold text-sm ${r.color}`}>{r.value}</p>
                <p className="text-white/30 text-[10px]">{r.date}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Annual rainfall totals */}
      <div>
        <p className="text-white/50 text-xs mb-2">Annual Rainfall Total (mm) — each bar = one year</p>
        <p className="text-white/25 text-[10px] mb-1.5 italic">
          ⚠ Island-wide station aggregate — sum of all NEA rain gauge readings, not depth at a single point. Values are proportional; relative differences between years are meaningful.
        </p>
        <MiniBarChart
          data={displayRainfallTotals}
          height={84}
          color="#60a5fa"
          xTicks={displayYears.map((y, i) => ({ label: String(y), index: i }))}
        />
        {rTrend?.significant && (
          <p className="text-amber-300 text-[10px] mt-1">
            Trend: {rTrend.trend} {rTrend.slope_per_year > 0 ? "+" : ""}{rTrend.slope_per_year.toFixed(0)} mm/yr
            · R²={rTrend.r_squared} · p={rTrend.p_value}
          </p>
        )}
        <CommentaryBox
          variant="blue"
          points={[
            `Each bar = total rainfall for that entire year (all rain stations aggregated). Singapore averages about 2,300 mm/year — more than London gets in 5 years.`,
            "Taller bar = wetter year. Short bar = drier year. The differences are driven by large-scale weather patterns like El Niño (drier) and La Niña (wetter).",
            rTrend?.significant
              ? `The trend line shows rainfall is ${rTrend.trend} by ${Math.abs(rTrend.slope_per_year).toFixed(0)} mm per year — statistically significant (p=${rTrend.p_value}). This means Singapore is getting wetter over time.`
              : "There is no strong long-term trend in annual totals — Singapore's rainfall varies year to year but isn't systematically getting wetter or drier yet.",
          ]}
          tip="Singapore's wettest months are Nov–Jan (NE Monsoon) and Mar–Apr (inter-monsoon). Driest are Jun–Aug (SW Monsoon)."
        />
      </div>

      {/* Rain category breakdown */}
      <div>
        <p className="text-white/50 text-xs mb-2">Rain Category Breakdown (% of hours)</p>
        <StackedBarChart years={displayYears} stacks={rainCatStacks} height={70} />
        <div className="flex flex-wrap gap-3 mt-2">
          {rainCatStacks.map((s) => (
            <div key={s.key} className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-sm inline-block" style={{ background: s.color }} />
              <span className="text-white/50 text-[10px]">{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Temperature trend */}
      <div>
        <p className="text-white/50 text-xs mb-2">Mean Temperature by Year (°C)</p>
        <LineChart
          series={[{ name: "Mean temp", data: tempMeans, color: "#fb923c" }]}
          bandSeries={{
            name: "Min–Max range",
            color: "#fb923c",
            min: displayYears.map((y) => annual[y]?.temperature?.min_c ?? tempMeans[displayYears.indexOf(y)]),
            max: displayYears.map((y) => annual[y]?.temperature?.max_c ?? tempMeans[displayYears.indexOf(y)]),
          }}
          height={80}
          xTicks={displayYears}
          yLabel="°C"
          showYAxis={true}
        />
        {tTrend?.significant && (
          <p className="text-orange-300 text-[10px] mt-1">
            Warming trend: +{tTrend.slope_per_year.toFixed(3)}°C/yr
            · R²={tTrend.r_squared} · p={tTrend.p_value}
          </p>
        )}
        {tTrend && !tTrend.significant && (
          <p className="text-white/30 text-[10px] mt-1">
            No statistically significant temperature trend (p={tTrend.p_value})
          </p>
        )}
        <CommentaryBox
          variant="amber"
          points={[
            `The orange line shows the mean (average) temperature for each year. ${years.length > 0 ? `Values range from ${Math.min(...tempMeans).toFixed(1)}°C to ${Math.max(...tempMeans).toFixed(1)}°C across the dataset.` : ""}`,
            "The shaded band shows the full temperature range (coldest to hottest recorded hour) within each year — Singapore's daily swing is typically 5–8°C.",
            tTrend?.significant
              ? `There IS a statistically significant warming trend of +${tTrend.slope_per_year?.toFixed(3)}°C per year (p=${tTrend.p_value}). Over 9 years that adds up to roughly +${(tTrend.slope_per_year * 9).toFixed(1)}°C — consistent with Singapore's urban heat island and global warming.`
              : "There is NO statistically significant warming trend in this dataset period. Weather is naturally variable year to year — a longer dataset (20+ years) would give more certainty.",
            "Singapore's temperature doesn't vary much seasonally because it is near the equator — the sun is always roughly overhead. Year-to-year differences are driven by El Niño/La Niña cycles and urban development.",
          ]}
          tip="Tip: A statistically significant trend means the pattern is unlikely to be random chance (p < 0.05)."
        />
      </div>

      {/* Analysis write-up */}
      <AnalysisSummary ct={ct} />

      {/* STL decomposition */}
      {stl.observed?.length > 0 && (
        <div>
          <p className="text-white/50 text-xs mb-2">
            STL Decomposition — Monthly Rainfall
          </p>
          <LineChart
            series={[
              { name: "Observed", data: stl.observed, color: "#60a5fa" },
              { name: "Trend",    data: stl.trend,    color: "#f472b6" },
            ]}
            height={80}
            xLabel="Month"
            yLabel="mm"
          />
          <LineChart
            series={[{ name: "Residual", data: stl.residual, color: "#fbbf24" }]}
            height={50}
            xLabel=""
            yLabel="Residual"
          />
          <p className="text-white/30 text-[10px] mt-1">{stl.note}</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------
function Section({ icon: Icon, title, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-2xl bg-white/8 border border-white/10 overflow-hidden">
      <button
        className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-blue-400" />
          <span className="text-white font-semibold text-sm">{title}</span>
        </div>
        {open ? <ChevronDown className="h-4 w-4 text-white/40" /> : <ChevronRight className="h-4 w-4 text-white/40" />}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function MLAnalysisDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedVar, setSelectedVar] = useState("rainfall");
  const [selectedHorizon, setSelectedHorizon] = useState(0);

  useEffect(() => {
    getFullAnalysis()
      .then((res) => {
        if (res?.status === "ok") setData(res.data);
        else if (res?.status === "not_trained") setData(null);
        else setError("Unexpected response from server");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <RefreshCw className="h-8 w-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl bg-red-500/20 border border-red-400/30 p-6 flex items-center gap-3">
        <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
        <p className="text-red-200 text-sm">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-2xl bg-white/8 border border-white/15 p-8 text-center space-y-3">
        <Brain className="h-12 w-12 text-white/30 mx-auto" />
        <p className="text-white/70 font-medium">ML Analysis Not Trained Yet</p>
        <p className="text-white/40 text-sm">
          Run the training pipeline to generate the full analysis:
        </p>
        <code className="block text-xs text-blue-300 bg-black/30 rounded-xl px-4 py-2 text-left">
          cd backend<br />
          python -m ml.train_full_analysis
        </code>
      </div>
    );
  }

  const varNames = Object.keys(data.eda || {});
  const horizons = data.model_results || [];
  const hr = horizons[selectedHorizon] || {};
  const categories = Object.values(data.rain_categories || {});

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-white font-bold text-lg flex items-center gap-2">
            <Brain className="h-5 w-5 text-blue-400" /> ML Analysis
          </h2>
          <p className="text-white/40 text-xs mt-0.5">
            Trained: {data.generated_at?.slice(0, 10)} ·{" "}
            {data.description?.slice(0, 60)}…
          </p>
        </div>
      </div>

      {/* Variable selector */}
      <div className="space-y-1">
        <div className="flex flex-wrap gap-2">
          {varNames.map((v) => (
            <button
              key={v}
              onClick={() => setSelectedVar(v)}
              className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-all ${
                selectedVar === v
                  ? "bg-blue-500 border-blue-400 text-white shadow-lg shadow-blue-500/25"
                  : "bg-white/5 border-white/15 text-white/50 hover:text-white hover:bg-white/10"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
        <p className="text-white/30 text-[10px]">
          Selected variable filters: <span className="text-white/50">EDA · ACF/PACF · Frequency Analysis</span>
          {" "}— Climate Trends and Model Performance always show rainfall.
        </p>
      </div>

      {/* 0. Climate Trends */}
      {data.climate_trends && (
        <Section icon={TrendingUp} title="Singapore Climate Trends">
          <ClimateTrendsSection ct={data.climate_trends} />
        </Section>
      )}

      {/* 1. EDA */}
      <Section key={`eda-${selectedVar}`} icon={BarChart3} title="Exploratory Data Analysis">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {varNames.map((v) => (
            <button key={v} onClick={() => setSelectedVar(v)}
              className={`text-[10px] px-2.5 py-1 rounded-full border font-medium transition-all ${selectedVar === v ? "bg-blue-500 border-blue-400 text-white" : "bg-white/5 border-white/15 text-white/40 hover:text-white hover:bg-white/10"}`}>
              {v}
            </button>
          ))}
        </div>
        {data.eda?.[selectedVar] && (() => {
          const e = data.eda[selectedVar];
          return (
            <div className="space-y-4">
              {/* Stats grid */}
              <div className="grid grid-cols-3 gap-2">
                {[
                  ["Mean",     e.mean],
                  ["Std",      e.std],
                  ["Skewness", e.skewness],
                  ["Kurtosis", e.kurtosis],
                  ["P50",      e.p50],
                  ["P99",      e.p99],
                ].map(([label, val]) => {
                  const num = parseFloat(val);
                  const display = Number.isFinite(num)
                    ? (Math.abs(num) >= 100 ? num.toFixed(1) : num.toFixed(2))
                    : (val ?? "—");
                  return (
                  <div key={label} className="bg-white/5 rounded-xl px-2 py-2 text-center">
                    <p className="text-white/40 text-[10px] mb-0.5">{label}</p>
                    <p className="text-white font-semibold text-xs tabular-nums">{display}</p>
                  </div>
                  );
                })}
              </div>

              {/* Distribution histogram */}
              {e.histogram && (
                <div>
                  <p className="text-white/50 text-xs mb-2">Distribution (value → frequency)</p>
                  <MiniBarChart
                    data={e.histogram.counts}
                    height={80}
                    color="#60a5fa"
                    showYAxis={true}
                    xTicks={(() => {
                      const edges = e.histogram.bin_edges;
                      if (!edges || edges.length < 2) return null;
                      const n = e.histogram.counts.length;
                      // Show ~5 evenly-spaced tick labels
                      const step = Math.max(1, Math.floor(n / 4));
                      return [0, step, step * 2, step * 3, n - 1]
                        .filter((idx) => idx < n)
                        .map((idx) => ({
                          index: idx,
                          label: (() => {
                            const v = edges[idx];
                            return Math.abs(v) >= 100
                              ? v.toFixed(0)
                              : Math.abs(v) >= 10
                              ? v.toFixed(1)
                              : v.toFixed(2);
                          })(),
                        }));
                    })()}
                  />
                </div>
              )}

              {/* Hourly pattern — 24 points, label every 6 hours */}
              <LineChart
                series={[{
                  name: `Hourly mean (${selectedVar})`,
                  data: Object.values(e.hourly_pattern),
                  color: "#60a5fa",
                }]}
                height={70}
                xTicks={["0h", "6h", "12h", "18h", "23h"]}
                xTickIndices={[0, 6, 12, 18, 23]}
                xLabel="Hour of day"
                yLabel="Mean"
              />

              {/* Monthly pattern — 12 points */}
              <LineChart
                series={[{
                  name: `Monthly mean (${selectedVar})`,
                  data: Object.values(e.monthly_pattern),
                  color: "#34d399",
                }]}
                height={70}
                xTicks={["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]}
                xLabel="Month"
                yLabel="Mean"
              />

              {/* Annual trend — dynamic year keys */}
              <LineChart
                series={[{
                  name: `Annual mean (${selectedVar})`,
                  data: Object.values(e.annual_trend),
                  color: "#fbbf24",
                }]}
                height={70}
                xTicks={Object.keys(e.annual_trend)}
                xLabel="Year"
                yLabel="Mean"
              />

              {/* Stationarity */}
              {data.stationarity?.[selectedVar] && (() => {
                const s = data.stationarity[selectedVar];
                return (
                  <div className="flex items-center gap-3 bg-white/5 rounded-xl px-3 py-2">
                    <div className={`w-2 h-2 rounded-full shrink-0 ${
                      s.is_stationary ? "bg-emerald-400" : "bg-amber-400"
                    }`} />
                    <span className="text-white/70 text-xs">
                      ADF test: p={s.p_value} — {s.is_stationary ? "Stationary ✓" : "Non-stationary (consider differencing)"}
                    </span>
                  </div>
                );
              })()}

              {/* EDA Commentary */}
              <CommentaryBox
                variant="indigo"
                points={(() => {
                  const e = data.eda[selectedVar] || {};
                  const varLabels = { rainfall: "rainfall (mm/hr)", temperature: "temperature (°C)", humidity: "relative humidity (%)", wind_speed: "wind speed (km/h)" };
                  const label = varLabels[selectedVar] || selectedVar;
                  const pts = [];
                  pts.push(`Mean = ${e.mean} means the average hourly ${label} across all 8,760+ hours of data. Std = ${e.std} is how much values typically vary around that mean — higher = more volatile.`);
                  pts.push(`Skewness = ${e.skewness}: A value close to 0 means a symmetric distribution. ${parseFloat(e.skewness) > 1 ? `Positive skewness (${e.skewness}) means most hours are low but a few extreme highs (like a heavy downpour) pull the average up.` : parseFloat(e.skewness) < -1 ? `Negative skewness means most values are high but occasional very low readings exist.` : "Near-zero skewness means the data is roughly bell-shaped and symmetric."}`);
                  pts.push(`P50 = ${e.p50} means half of all hourly readings are below this value. P99 = ${e.p99} is the 99th percentile — only 1% of hours exceed this, representing extreme events.`);
                  pts.push(`The "Distribution" histogram shows how often each value occurs. A peak on the left with a long tail to the right means: mostly no/low ${selectedVar} with rare extreme spikes.`);
                  pts.push(`The hourly pattern chart (blue) shows the typical daily cycle — X-axis is hour of day (0=midnight, 12=noon). ${selectedVar === "temperature" ? "Temperature peaks at ~2pm and is lowest at ~6am — the classic day/night cycle." : selectedVar === "rainfall" ? "Rainfall peaks in the afternoon (convective storms forming from daytime heating) and again after midnight." : selectedVar === "humidity" ? "Humidity is highest at night/early morning and lowest in the afternoon when temperature peaks." : "Wind speed typically peaks in the afternoon when thermal heating drives sea breezes inland."}`);
                  pts.push(`The monthly pattern (green) shows seasonal variation. ${selectedVar === "rainfall" ? "Singapore has two monsoon seasons — NE Monsoon (Nov–Jan, wetter) and SW Monsoon (Jun–Aug, drier)." : selectedVar === "temperature" ? "Temperature is remarkably stable year-round (equatorial climate) — variation between months is only 1–2°C." : "Seasonal differences reflect Singapore's monsoon cycle."}`);
                  pts.push(`ADF (Augmented Dickey-Fuller) stationarity test: "Stationary" means the data has consistent statistical properties over time (no systematic drift), which is ideal for machine learning. "Non-stationary" means trends or changing variance exist.`);
                  return pts;
                })()}
                tip={`Switch the tab above to compare ${selectedVar} patterns against other variables (temperature, humidity, wind speed).`}
              />
            </div>
          );
        })()}
      </Section>

      {/* 2. ACF / PACF */}
      <Section key={`acf-${selectedVar}`} icon={Activity} title="ACF / PACF (Autocorrelation)">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {varNames.map((v) => (
            <button key={v} onClick={() => setSelectedVar(v)}
              className={`text-[10px] px-2.5 py-1 rounded-full border font-medium transition-all ${selectedVar === v ? "bg-blue-500 border-blue-400 text-white" : "bg-white/5 border-white/15 text-white/40 hover:text-white hover:bg-white/10"}`}>
              {v}
            </button>
          ))}
        </div>
        {data.acf_pacf?.[selectedVar] && (() => {
          const ap = data.acf_pacf[selectedVar];
          return (
            <div className="space-y-4">
              <div className="text-white/50 text-xs">
                N={ap.n_samples} · Sparsity={ap.sparsity_pct}% ·{" "}
                Sig ACF lags: {ap.significant_acf_lags?.slice(0, 6).join(", ")}
              </div>
              <StemChart
                lags={ap.lags}
                values={ap.acf}
                ci={ap.ci_bound}
                height={80}
                color="#60a5fa"
                title="ACF"
              />
              <StemChart
                lags={ap.lags}
                values={ap.pacf}
                ci={ap.ci_bound}
                height={80}
                color="#a78bfa"
                title="PACF"
              />
              <p className="text-white/30 text-[10px]">
                Dashed lines = 95% CI. Lags outside bounds indicate significant autocorrelation.
              </p>
              <CommentaryBox
                variant="blue"
                points={[
                  "ACF (AutoCorrelation Function): Each vertical bar shows how much the current value correlates with a value from X hours ago. A tall bar at lag 1 means 'if it rained an hour ago, it's likely still raining.'",
                  "PACF (Partial ACF): Like ACF but removes the indirect effect of intermediate lags. A tall bar at lag 2 in PACF means there's a DIRECT 2-hour memory, not just because lag 1 is correlated.",
                  `The dashed yellow lines are the 95% confidence interval. Any bar extending BEYOND the dashes is statistically significant — the value at that lag genuinely predicts the current value.`,
                  `Significant ACF lags for ${selectedVar}: ${data.acf_pacf?.[selectedVar]?.significant_acf_lags?.slice(0, 8).join(", ") || "loading..."}. This tells us the model should use these past hours as input features.`,
                  "A slowly decaying ACF (each bar only slightly smaller than the last) suggests strong persistence — conditions tend to last a long time. A sharp drop after lag 1 means quick changes.",
                  "These charts directly inform which 'lag features' are built into the ML model — e.g., rain_lag_1h, hum_lag_6h.",
                ]}
                tip="Expert tip: If both ACF and PACF cut off sharply after lag p, an AR(p) model is appropriate. Slowly decaying ACF with sharp PACF cutoff → MA model."
              />
            </div>
          );
        })()}
      </Section>

      {/* 3. Spectral / FFT */}
      <Section key={`fft-${selectedVar}`} icon={Waves} title="Frequency Analysis (FFT Periodogram)">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {varNames.map((v) => (
            <button key={v} onClick={() => setSelectedVar(v)}
              className={`text-[10px] px-2.5 py-1 rounded-full border font-medium transition-all ${selectedVar === v ? "bg-blue-500 border-blue-400 text-white" : "bg-white/5 border-white/15 text-white/40 hover:text-white hover:bg-white/10"}`}>
              {v}
            </button>
          ))}
        </div>
        {data.spectral?.[selectedVar] && (() => {
          const sp = data.spectral[selectedVar];
          const chartData = sp.chart_data || [];
          // Build x-axis ticks at key periods (6h, 12h, 24h, 72h, 168h)
          const keyPeriods = [6, 12, 24, 48, 168];
          const fftTicks = [], fftTickIndices = [];
          keyPeriods.forEach((p) => {
            const idx = chartData.findIndex((d) => d.period_h >= p);
            if (idx >= 0) { fftTicks.push(`${p}h`); fftTickIndices.push(idx); }
          });
          return (
            <div className="space-y-3">
              <div className="text-white/50 text-xs">
                Top dominant periods:{" "}
                {sp.top_dominant_periods?.slice(0, 5).map((p) => `${p.period_h}h`).join(", ")}
              </div>
              <LineChart
                series={[{
                  name: "Power spectral density",
                  data: chartData.map((d) => d.power),
                  color: "#34d399",
                }]}
                height={80}
                xTicks={fftTicks}
                xTickIndices={fftTickIndices}
                yLabel="Power"
              />
              {/* Top periods table */}
              <div className="grid grid-cols-2 gap-1">
                {sp.top_dominant_periods?.slice(0, 6).map((p, i) => (
                  <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-1.5 text-xs">
                    <span className="text-white/60">{p.period_h}h period</span>
                    <span className="text-emerald-400 font-mono text-[10px]">
                      {p.power.toExponential(2)}
                    </span>
                  </div>
                ))}
              </div>
              <p className="text-white/30 text-[10px]">
                Peaks at 24h and 12h confirm daily cycles. Peaks at 168h (7 days) = weekly pattern.
              </p>
              <CommentaryBox
                variant="indigo"
                points={[
                  "The FFT Periodogram reveals hidden cycles in the data by converting time-series data into frequency components — like a prism splitting white light into a rainbow.",
                  "The X-axis shows 'period' (how long a cycle takes in hours). The Y-axis shows 'power' — how strong that cycle is. A tall spike = a very consistent, repeating pattern.",
                  `A dominant spike at 24h means ${selectedVar} has a strong daily cycle (rises and falls once every 24 hours). The 12h spike is the twice-daily harmonic — also very common in tropical climates.`,
                  `Spikes around 168h (7 days) would indicate a weekly pattern — common for wind speed and humidity due to different urban activity patterns on weekdays vs weekends.`,
                  `Spikes at 300–400h range correspond to roughly monthly cycles, likely driven by Singapore's monsoon transitions.`,
                  "These cycles become features in the ML model — the model 'knows' what time of day and month it is, which dramatically improves forecasting accuracy.",
                ]}
                tip="Fun fact: The same mathematical technique (FFT) is used in JPEG image compression and your phone's noise cancellation."
              />
            </div>
          );
        })()}
      </Section>

      {/* 4. Spurious Correlations */}
      <Section icon={GitCompare} title="Spurious Correlation Analysis" defaultOpen={false}>
        <div className="space-y-4">
          {/* Cross-correlations */}
          {Object.entries(data.spurious_correlations?.cross_correlation || {}).map(([key, cc]) => (
            <div key={key} className="space-y-1">
              <div className="flex items-center gap-2">
                <p className="text-white/70 text-xs font-medium">{key.replace("_vs_", " vs ")}</p>
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                  cc.potentially_spurious
                    ? "bg-red-500/20 text-red-300"
                    : "bg-emerald-500/20 text-emerald-300"
                }`}>
                  {cc.potentially_spurious ? "⚠ Possibly spurious" : "r=" + cc.pearson_r}
                </span>
              </div>
              <StemChart
                lags={cc.lags}
                values={cc.cross_correlation}
                ci={cc.ci_bound}
                height={60}
                color="#f472b6"
              />
            </div>
          ))}

          {/* Granger causality */}
          <div>
            <p className="text-white/60 text-xs font-medium mb-2">Granger Causality → rainfall</p>
            <div className="space-y-1">
              {Object.entries(data.spurious_correlations?.granger_causality || {}).map(([key, gc]) => (
                <div key={key} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-1.5 text-xs">
                  <span className="text-white/70">{key.replace("_causes_rainfall", "")}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-white/50 font-mono">p={gc.min_p}</span>
                    <span className={`${gc.significant ? "text-emerald-400" : "text-white/30"}`}>
                      {gc.significant ? "✓ significant" : "✗ not significant"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <CommentaryBox
            variant="amber"
            points={[
              "The stem plots show cross-correlation between two variables at different time lags. Each vertical bar = correlation at that lag. Bars outside the dashed lines are statistically significant.",
              "r=-0.90 between temperature and humidity is extremely strong and NEGATIVE — as temperature rises, humidity falls sharply. This makes physical sense: hot air can hold more water vapor, so relative humidity drops.",
              "r=0.17 between rainfall and humidity is a weak POSITIVE link — slightly more rain when humid. Correlation does not imply causation: both are driven by the same weather system.",
              "Granger Causality tests whether PAST values of one variable help predict the FUTURE of another. 'Temperature Granger-causes rainfall' (p=0) means: knowing yesterday's temperature genuinely helps predict today's rainfall — beyond just using rainfall history alone.",
              "All three variables (temperature, humidity, wind speed) Granger-cause rainfall at p≈0, confirming they are all legitimate predictive features for the ML model.",
              "Spurious correlation warning: Two variables can appear correlated because they're both driven by a THIRD hidden variable (the monsoon cycle, for example). Granger causality helps distinguish real predictive relationships from coincidence.",
            ]}
            tip="The r values (Pearson correlation) range from -1 (perfect inverse) to +1 (perfect positive). Values near 0 mean no linear relationship."
          />
        </div>
      </Section>

      {/* 5. Model Results */}
      <Section icon={TrendingUp} title="Model Performance by Horizon">
        {/* Horizon tabs */}
        <div className="flex gap-2 mb-4 flex-wrap">
          {horizons.map((h, i) => (
            <button
              key={h.horizon_h}
              onClick={() => setSelectedHorizon(i)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                selectedHorizon === i
                  ? "bg-blue-500/30 border-blue-400/60 text-blue-200"
                  : "bg-white/8 border-white/15 text-white/60 hover:text-white"
              }`}
            >
              {h.horizon_h}h ahead
            </button>
          ))}
        </div>

        {hr.regression && (
          <div className="grid grid-cols-2 gap-2 mb-4">
            {[
              ["MAE (mm)", hr.regression.mae],
              ["RMSE (mm)", hr.regression.rmse],
              ["Train samples", hr.n_train?.toLocaleString()],
              ["Test samples", hr.n_test?.toLocaleString()],
            ].map(([label, val]) => (
              <div key={label} className="bg-white/5 rounded-xl p-3 text-center">
                <p className="text-white/40 text-[10px]">{label}</p>
                <p className="text-white font-semibold text-sm">{val}</p>
              </div>
            ))}
          </div>
        )}

        {/* Classification results */}
        {hr.classification?.accuracy != null && (() => {
          const cls = hr.classification;
          const report = cls.report || {};
          const classNames = ["No Rain", "Light Rain", "Heavy Rain", "Thundery Showers"];
          const macroF1 = report["macro avg"]?.["f1-score"];
          // Identify worst false-negative: rain missed as No Rain
          const rainRecalls = classNames.slice(1).map((n) => report[n]?.recall ?? 0);
          const minRainRecall = Math.min(...rainRecalls);

          return (
            <div className="space-y-3 mb-4">
              {/* Summary row */}
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-white/5 rounded-xl p-2.5 text-center">
                  <p className="text-white/40 text-[10px]">Accuracy</p>
                  <p className="text-emerald-400 font-bold text-base">{(cls.accuracy * 100).toFixed(1)}%</p>
                </div>
                <div className="bg-white/5 rounded-xl p-2.5 text-center">
                  <p className="text-white/40 text-[10px]">Macro F1</p>
                  <p className="text-blue-300 font-bold text-base">{macroF1 ? (macroF1 * 100).toFixed(1) + "%" : "—"}</p>
                </div>
                <div className="bg-white/5 rounded-xl p-2.5 text-center">
                  <p className="text-white/40 text-[10px]">Min Rain Recall</p>
                  <p className={`font-bold text-base ${minRainRecall < 0.3 ? "text-red-400" : minRainRecall < 0.5 ? "text-amber-400" : "text-emerald-400"}`}>
                    {(minRainRecall * 100).toFixed(1)}%
                  </p>
                </div>
              </div>

              {/* Per-class table */}
              <div>
                <p className="text-white/50 text-[10px] font-medium mb-1.5">Per-class metrics — recall is most important (missing rain = wet user)</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-[10px] border-collapse">
                    <thead>
                      <tr className="text-white/40">
                        <th className="text-left py-1 pr-2">Class</th>
                        <th className="text-right px-2">Precision</th>
                        <th className="text-right px-2">Recall</th>
                        <th className="text-right px-2">F1</th>
                        <th className="text-right pl-2">Support</th>
                      </tr>
                    </thead>
                    <tbody>
                      {classNames.map((name, ci) => {
                        const row = report[name] || {};
                        const recall = row.recall ?? null;
                        const isRain = ci > 0;
                        const recallColor = recall == null ? "text-white/30"
                          : isRain && recall < 0.3 ? "text-red-400"
                          : isRain && recall < 0.5 ? "text-amber-400"
                          : "text-emerald-400";
                        return (
                          <tr key={name} className="border-t border-white/5">
                            <td className="py-1.5 pr-2 text-white/70 font-medium">{name}</td>
                            <td className="text-right px-2 text-white/60 font-mono">
                              {row.precision != null ? (row.precision * 100).toFixed(1) + "%" : "—"}
                            </td>
                            <td className={`text-right px-2 font-mono font-semibold ${recallColor}`}>
                              {recall != null ? (recall * 100).toFixed(1) + "%" : "—"}
                            </td>
                            <td className="text-right px-2 text-white/60 font-mono">
                              {row["f1-score"] != null ? (row["f1-score"] * 100).toFixed(1) + "%" : "—"}
                            </td>
                            <td className="text-right pl-2 text-white/40 font-mono">
                              {row.support?.toLocaleString() ?? "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Confusion matrix */}
              {cls.confusion_matrix && (
                <div>
                  <p className="text-white/50 text-[10px] font-medium mb-1.5">
                    Confusion matrix — rows=actual, cols=predicted
                  </p>
                  <ConfusionMatrix
                    matrix={cls.confusion_matrix}
                    labels={categories}
                  />
                  <p className="text-white/30 text-[10px] mt-1.5">
                    Green diagonal = correct. Red off-diagonal = errors. Top-right cells = rain missed as dry (costly).
                  </p>
                </div>
              )}

              {/* Binary classification */}
              {hr.binary_classification && (() => {
                const bin = hr.binary_classification;
                const binCm = bin.confusion_matrix; // [[TN, FP], [FN, TP]]
                return (
                  <div className="space-y-2">
                    <p className="text-white/60 text-xs font-medium">Binary: Rain vs No-Rain</p>
                    <div className="grid grid-cols-4 gap-2">
                      {[
                        { label: "Accuracy", val: bin.accuracy, color: "text-white" },
                        { label: "Rain Precision", val: bin.rain_precision, color: "text-sky-300" },
                        { label: "Rain Recall", val: bin.rain_recall, color: bin.rain_recall < 0.5 ? "text-red-400" : bin.rain_recall < 0.7 ? "text-amber-400" : "text-emerald-400" },
                        { label: "Rain F1", val: bin.rain_f1, color: "text-blue-300" },
                      ].map(({ label, val, color }) => (
                        <div key={label} className="bg-white/5 rounded-xl p-2 text-center">
                          <p className="text-white/40 text-[10px]">{label}</p>
                          <p className={`font-bold text-sm ${color}`}>{val != null ? (val * 100).toFixed(1) + "%" : "—"}</p>
                        </div>
                      ))}
                    </div>
                    {binCm && (
                      <div className="text-[10px] text-white/50 space-y-1">
                        <p className="font-medium text-white/60">Confusion matrix</p>
                        <div className="grid grid-cols-3 gap-px text-center">
                          <div />
                          <div className="bg-white/5 rounded px-1 py-0.5">Pred No Rain</div>
                          <div className="bg-white/5 rounded px-1 py-0.5">Pred Rain</div>
                          <div className="bg-white/5 rounded px-1 py-0.5 text-left">True No Rain</div>
                          <div className="bg-emerald-500/20 rounded px-1 py-0.5 text-emerald-300 font-bold">{binCm[0]?.[0]}</div>
                          <div className="bg-red-500/10 rounded px-1 py-0.5 text-red-300">{binCm[0]?.[1]}</div>
                          <div className="bg-white/5 rounded px-1 py-0.5 text-left">True Rain</div>
                          <div className="bg-red-500/20 rounded px-1 py-0.5 text-red-400 font-bold">{binCm[1]?.[0]}</div>
                          <div className="bg-emerald-500/20 rounded px-1 py-0.5 text-emerald-300 font-bold">{binCm[1]?.[1]}</div>
                        </div>
                        <p className="text-white/30">Bold red = missed rain (false negatives) — the costly errors.</p>
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Cost-weighting note */}
              <div className="bg-amber-500/10 border border-amber-400/20 rounded-xl px-3 py-2">
                <p className="text-amber-200/80 text-[10px]">
                  Cost-weighted training: Thundery Showers 6× · Heavy Rain 4× · Light Rain 2× · No Rain 1×.
                  The model is biased toward predicting rain when uncertain — false alarms are acceptable,
                  missed rain is not.
                </p>
              </div>
              <CommentaryBox
                variant="blue"
                points={[
                  "Accuracy (overall %) tells you what fraction of all predictions were correct. But accuracy is misleading for imbalanced data — if 60% of hours are dry, guessing 'no rain' always achieves 60% without being useful.",
                  "Precision = 'of all times the model predicted rain, how often was it right?' High precision = fewer false alarms.",
                  "Recall = 'of all actual rain events, how many did the model catch?' High recall = fewer missed rain events. For a weather app, RECALL is more important — being caught in unexpected rain is worse than carrying an umbrella unnecessarily.",
                  "F1 Score is the harmonic mean of precision and recall. It balances both — useful when you care about both false alarms and missed events.",
                  "The confusion matrix grid shows where the model makes mistakes. The GREEN diagonal = correct predictions. RED cells = errors. The most costly cell is 'Heavy Rain predicted as No Rain' (top-right area) — that's a missed warning.",
                  "Why is Heavy Rain recall so low (3.8%)? Heavy rain hours are rare (only 476 out of 8,765), so the model has fewer examples to learn from. Cost-weighting (4×) partially compensates, but heavy rain remains the hardest to forecast.",
                  "The Binary classifier (Rain vs No-Rain) is simpler and achieves 80% accuracy with 72% rain recall — a much easier task than distinguishing 4 rain categories.",
                ]}
                tip="Practical interpretation: At 1h ahead, the model correctly warns about rain 72% of the time. For 3h ahead, this drops further. Always check the hourly forecast!"
              />
            </div>
          );
        })()}

        {/* Feature importance */}
        {hr.feature_importance?.length > 0 && (
          <div>
            <p className="text-white/60 text-xs font-medium mb-2">Feature Importance (LightGBM gain)</p>
            <HorizontalBar
              items={hr.feature_importance}
              nameKey="feature"
              valueKey="gain"
              color="#fbbf24"
            />
          </div>
        )}
      </Section>

      {/* 5b. NEA Benchmark */}
      {data.nea_benchmark && (() => {
        const nb = data.nea_benchmark;
        const c3 = nb.overall?.class3 || {};

        // 6h — per-region (native NEA granularity)
        const prNea = c3.nea || {};
        const prMl  = c3.ml_island_wide || {};
        const hasPR = prNea.accuracy != null;

        // 6h — island-wide (fair ML comparison)
        const iw = c3.island_wide || {};
        const iwNea = iw.nea || {};
        const iwMl  = iw.ml_island_wide || {};
        const nSamples6h = iw.n_samples;
        const hasIW = iwNea.accuracy != null;

        // 2h area benchmark
        const nb2 = data.nea_2h_benchmark;
        const c3_2h = nb2?.overall?.class3 || {};
        const paNea = c3_2h.per_area_nea || {};
        const paMl  = c3_2h.per_area_ml  || {};
        const paEns = c3_2h.per_area_ensemble || {};
        const hasPerArea = paNea.accuracy != null;
        const iw2 = c3_2h.island_wide || {};
        const iwNea2 = iw2.nea || {};
        const iwMl2  = iw2.ml_island_wide || {};
        const has2hIW = iwNea2.accuracy != null;

        // Best-in-column helpers
        const bestF2_6h  = Math.max(prNea.rain_f2 ?? 0, prMl.rain_f2 ?? 0, iwNea.rain_f2 ?? 0, iwMl.rain_f2 ?? 0);
        const bestF2_2h  = Math.max(paNea.rain_f2 ?? 0, paMl.rain_f2 ?? 0, paEns.rain_f2 ?? 0);
        const bestAcc_2h = Math.max(paNea.accuracy ?? 0, paMl.accuracy ?? 0, paEns.accuracy ?? 0);

        return (
          <Section icon={Trophy} title="NEA Benchmark Comparison" defaultOpen={true}>
            <div className="space-y-4">

              {/* Why F2 */}
              <div className="bg-violet-500/8 border border-violet-400/20 rounded-xl p-3 space-y-1.5">
                <p className="text-violet-300/80 text-[10px] font-semibold uppercase tracking-wide">Primary metric: Rain F2 score (β = 2)</p>
                <p className="text-[11px] text-white/55 leading-relaxed">
                  F2 weighs <strong className="text-white/70">recall twice as much as precision</strong> — because missing a rain event (user gets soaked) is worse than a false alarm (user carries umbrella). Accuracy is shown for context, but F2 is the decision metric. F2 is computed only on rain classes (Light Rain + Heavy/Thundery), macro-averaged.
                </p>
              </div>

              {/* Methodology */}
              <div className="bg-amber-500/8 border border-amber-400/20 rounded-xl p-3 space-y-1.5">
                <p className="text-amber-300/80 text-[10px] font-semibold uppercase tracking-wide">Granularity-matched comparison</p>
                <div className="space-y-1 text-[11px] text-white/55 leading-relaxed">
                  <p>NEA publishes at two levels. We compare at each level separately:</p>
                  <ul className="space-y-0.5 ml-2">
                    <li><span className="text-amber-300/60">›</span> <strong className="text-white/70">6-hour by region</strong> (5 regions) — compared at per-region level, then also aggregated to island-wide via majority vote</li>
                    <li><span className="text-amber-300/60">›</span> <strong className="text-white/70">2-hour by area</strong> (47 areas) — compared at native per-area level; ML island-wide prediction applied uniformly to all areas</li>
                  </ul>
                </div>
              </div>

              {/* 6h benchmark */}
              <div>
                <p className="text-white/50 text-[10px] font-semibold uppercase tracking-wide mb-2">
                  6-hour forecast benchmark · {nSamples6h?.toLocaleString()} periods · 2024 holdout
                </p>
                {(hasPR || hasIW) ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr className="text-white/40 text-[10px]">
                          <th className="text-left py-1.5 pr-3">Granularity · Model</th>
                          <th className="text-right px-2">Accuracy</th>
                          <th className="text-right px-2 text-violet-300/70">Rain F2 ↑</th>
                          <th className="text-right pl-2"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {hasPR && <>
                          <tr className="border-t border-white/5">
                            <td className="py-1.5 pr-3 font-medium text-[11px] text-white/70">Per-region · NEA 6h forecast</td>
                            <td className="text-right px-2 font-mono text-white/60">{(prNea.accuracy * 100).toFixed(1)}%</td>
                            <td className="text-right px-2 font-mono text-violet-300">{prNea.rain_f2 != null ? (prNea.rain_f2 * 100).toFixed(1) + "%" : "—"}</td>
                            <td className="text-right pl-2">{prNea.rain_f2 === bestF2_6h ? <span className="text-emerald-400 text-[10px] font-semibold">✓ Best</span> : null}</td>
                          </tr>
                          <tr className="border-t border-white/5">
                            <td className="py-1.5 pr-3 font-medium text-[11px] text-blue-300">Per-region · ML (island-wide applied)</td>
                            <td className="text-right px-2 font-mono text-blue-300/70">{prMl.accuracy != null ? (prMl.accuracy * 100).toFixed(1) + "%" : "—"}</td>
                            <td className="text-right px-2 font-mono text-blue-300">{prMl.rain_f2 != null ? (prMl.rain_f2 * 100).toFixed(1) + "%" : "—"}</td>
                            <td className="text-right pl-2">{prMl.rain_f2 === bestF2_6h ? <span className="text-emerald-400 text-[10px] font-semibold">✓ Best</span> : null}</td>
                          </tr>
                        </>}
                        {hasIW && <>
                          <tr className="border-t border-white/10">
                            <td className="py-1.5 pr-3 font-medium text-[11px] text-white/50 italic">Island-wide · NEA → majority vote</td>
                            <td className="text-right px-2 font-mono text-white/45">{(iwNea.accuracy * 100).toFixed(1)}%</td>
                            <td className="text-right px-2 font-mono text-violet-300/60">{iwNea.rain_f2 != null ? (iwNea.rain_f2 * 100).toFixed(1) + "%" : "—"}</td>
                            <td className="text-right pl-2 text-[10px] text-white/25 italic">fair vs ML</td>
                          </tr>
                          <tr className="border-t border-white/5">
                            <td className="py-1.5 pr-3 font-medium text-[11px] text-blue-200/70 italic">Island-wide · ML model</td>
                            <td className="text-right px-2 font-mono text-blue-200/60">{(iwMl.accuracy * 100).toFixed(1)}%</td>
                            <td className="text-right px-2 font-mono text-blue-200/80">{iwMl.rain_f2 != null ? (iwMl.rain_f2 * 100).toFixed(1) + "%" : "—"}</td>
                            <td className="text-right pl-2">{iwMl.rain_f2 === bestF2_6h ? <span className="text-emerald-400 text-[10px] font-semibold">✓ Best</span> : null}</td>
                          </tr>
                        </>}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-white/40 text-sm text-center py-4">Retraining in progress...</p>
                )}
              </div>

              {/* 2h area benchmark */}
              <div>
                <p className="text-white/50 text-[10px] font-semibold uppercase tracking-wide mb-2">
                  2-hour per-area forecast · {c3_2h.n_area_period_samples?.toLocaleString()} area-period samples · 2024 holdout
                </p>
                {hasPerArea ? (
                  <>
                    <p className="text-white/35 text-[10px] mb-1.5">
                      47 areas matched to nearest rain gauge (≤10 km) · ML prediction applied uniformly island-wide
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs border-collapse">
                        <thead>
                          <tr className="text-white/40 text-[10px]">
                            <th className="text-left py-1.5 pr-3">Model</th>
                            <th className="text-right px-2">Accuracy</th>
                            <th className="text-right px-2 text-violet-300/70">Rain F2 ↑</th>
                            <th className="text-right pl-2"></th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr className="border-t border-white/5">
                            <td className="py-1.5 pr-3 font-medium text-[11px] text-white/70">NEA 2h per-area (native)</td>
                            <td className="text-right px-2 font-mono text-white/60">{(paNea.accuracy * 100).toFixed(1)}%</td>
                            <td className="text-right px-2 font-mono text-violet-300">{paNea.rain_f2 != null ? (paNea.rain_f2 * 100).toFixed(1) + "%" : "—"}</td>
                            <td className="text-right pl-2">{paNea.rain_f2 === bestF2_2h ? <span className="text-emerald-400 text-[10px] font-semibold">✓ Best F2</span> : (paNea.accuracy === bestAcc_2h ? <span className="text-emerald-400 text-[10px] font-semibold">✓ Best Acc</span> : null)}</td>
                          </tr>
                          {paMl.accuracy != null && (
                            <tr className="border-t border-white/5">
                              <td className="py-1.5 pr-3 font-medium text-[11px] text-blue-300">ML island-wide → per-area</td>
                              <td className="text-right px-2 font-mono text-blue-300/70">{(paMl.accuracy * 100).toFixed(1)}%</td>
                              <td className="text-right px-2 font-mono text-blue-300">{paMl.rain_f2 != null ? (paMl.rain_f2 * 100).toFixed(1) + "%" : "—"}</td>
                              <td className="text-right pl-2">{paMl.rain_f2 === bestF2_2h ? <span className="text-emerald-400 text-[10px] font-semibold">✓ Best F2</span> : null}</td>
                            </tr>
                          )}
                          {paEns.accuracy != null && (
                            <tr className="border-t border-white/5">
                              <td className="py-1.5 pr-3 font-medium text-[11px] text-emerald-300">Ensemble (60% ML + 40% NEA)</td>
                              <td className="text-right px-2 font-mono text-emerald-300/70">{(paEns.accuracy * 100).toFixed(1)}%</td>
                              <td className="text-right px-2 font-mono text-emerald-300">{paEns.rain_f2 != null ? (paEns.rain_f2 * 100).toFixed(1) + "%" : "—"}</td>
                              <td className="text-right pl-2">{paEns.rain_f2 === bestF2_2h ? <span className="text-emerald-400 text-[10px] font-semibold">✓ Best F2</span> : null}</td>
                            </tr>
                          )}
                          {has2hIW && (
                            <>
                              <tr className="border-t border-white/10">
                                <td className="py-1.5 pr-3 font-medium text-[11px] text-white/40 italic">Island-wide · NEA → majority vote</td>
                                <td className="text-right px-2 font-mono text-white/35">{(iwNea2.accuracy * 100).toFixed(1)}%</td>
                                <td className="text-right px-2 font-mono text-white/35">—</td>
                                <td className="text-right pl-2 text-[10px] text-white/20 italic">fair vs ML</td>
                              </tr>
                              <tr className="border-t border-white/5">
                                <td className="py-1.5 pr-3 font-medium text-[11px] text-blue-200/50 italic">Island-wide · ML model</td>
                                <td className="text-right px-2 font-mono text-blue-200/45">{(iwMl2.accuracy * 100).toFixed(1)}%</td>
                                <td className="text-right px-2 font-mono text-blue-200/45">—</td>
                                <td className="text-right pl-2"></td>
                              </tr>
                            </>
                          )}
                        </tbody>
                      </table>
                    </div>
                    <p className="text-white/25 text-[10px] mt-1.5 italic">
                      ML island-wide label applied to all 47 areas — this reveals the "local knowledge gap" vs NEA's area-specific forecasts.
                    </p>
                  </>
                ) : (
                  <p className="text-white/30 text-[10px] text-center py-2">2h area benchmark computing during retrain...</p>
                )}
              </div>

              {/* Commentary */}
              {(hasIW || hasPerArea) && (
                <CommentaryBox
                  variant="indigo"
                  points={[
                    `6h island-wide: ML Rain F2 ${iwMl.rain_f2 != null ? (iwMl.rain_f2 * 100).toFixed(1) + "%" : "—"} vs NEA ${iwNea.rain_f2 != null ? (iwNea.rain_f2 * 100).toFixed(1) + "%" : "—"} — ML catches significantly more rain events despite similar accuracy. NEA is conservative; ML has higher recall.`,
                    `2h per-area: NEA leads accuracy (${paNea.accuracy != null ? (paNea.accuracy * 100).toFixed(1) + "%" : "—"}) because it has local area knowledge — our ML applies one island-wide label to all 47 areas. Ensemble blends both, trading some accuracy for better rain recall.`,
                    "Accuracy is misleading here — Singapore is dry ~70% of the time, so predicting 'No Rain' always gives high accuracy. F2 penalises models that miss rain events.",
                    "Next step: per-area ML using each station's local sensor readings + spatial neighbour features — this should close the accuracy gap with NEA.",
                  ]}
                  tip="F2 = 5×precision×recall / (4×precision + recall). β=2 means recall counts twice as much — reflecting that missing rain is more costly than a false alarm."
                />
              )}
            </div>
          </Section>
        );
      })()}

      {/* 5c. How we improved */}
      <Section icon={TrendingUp} title="How Accuracy Was Improved" defaultOpen={false}>
        <div className="space-y-3">
          <p className="text-white/60 text-xs leading-relaxed">
            The model went through several iterations of feature engineering and training improvements:
          </p>
          <div className="space-y-3">
            {[
              {
                step: "1. Baseline (station lag features only)",
                detail: "Initial model used only historical station observations: rain_lag_1h, temp_lag_1h, hum_lag_1h, wind_lag_1h. Binary F1 ~0.68.",
                color: "border-white/20",
              },
              {
                step: "2. Engineered meteorological features",
                detail: "Added dry_spell_hours, rain_streak_hours, hum_deficit (gap to saturation), wind_accel_3h, time-of-day sine/cosine encoding, month encoding. These capture physical processes (atmospheric instability, storm persistence). F1 improved to ~0.73.",
                color: "border-blue-400/30",
              },
              {
                step: "3. Extended lags and rolling windows",
                detail: "Added 3h, 6h, 12h lags plus 3h/6h rolling means and standard deviations for each variable. This gives the model 'memory' of how conditions evolved, not just the current snapshot.",
                color: "border-blue-400/40",
              },
              {
                step: "4. External features: cloud cover, solar radiation, wind direction",
                detail: "Open-Meteo archive data (2016–2024) added hourly cloud cover, shortwave radiation (daytime heating driver), and surface wind direction encoded cyclically (sin/cos). Cloud cover is the most direct convective signal available without a radiosonde.",
                color: "border-blue-400/50",
              },
              {
                step: "5. MJO (Madden-Julian Oscillation) phase",
                detail: "Added daily MJO RMM indices from BOM (Bureau of Meteorology), interpolated to hourly. The MJO is a planetary-scale wave that modulates Singapore's wet/dry cycles on a 30–60 day period. Phase encoded cyclically.",
                color: "border-emerald-400/40",
              },
              {
                step: "6. Cost-weighted training",
                detail: "Thundery Showers penalised 6×, Heavy Rain 4×, Light Rain 2× vs No Rain 1× during training. This forces the model to prioritise catching rain events over simply predicting 'no rain' (which would achieve 60% accuracy by ignoring all rain).",
                color: "border-amber-400/40",
              },
              {
                step: "7. 8-year training set (2016–2023), 2024 holdout",
                detail: "Tripling the training data from earlier versions. More years = more examples of rare events (heavy storms, La Niña, El Niño). The model saw 48,000+ training samples vs earlier ~15,000.",
                color: "border-emerald-400/50",
              },
            ].map(({ step, detail, color }) => (
              <div key={step} className={`border-l-2 ${color} pl-3 space-y-0.5`}>
                <p className="text-white/80 text-xs font-medium">{step}</p>
                <p className="text-white/45 text-[11px] leading-relaxed">{detail}</p>
              </div>
            ))}
          </div>
          <div className="bg-emerald-500/8 border border-emerald-400/15 rounded-xl p-3 mt-2">
            <p className="text-emerald-300/80 text-[10px] font-semibold uppercase tracking-wide mb-1.5">Next improvements (planned)</p>
            <ul className="space-y-1">
              {[
                "ERA5 CAPE/CIN data from Copernicus CDS — direct convective instability index, likely strongest single feature for thunderstorm prediction.",
                "Walk-forward cross-validation across all years (2016–2024) for more robust performance estimates.",
                "Separate model per region (East/West/Central) rather than island-wide average.",
              ].map((p, i) => (
                <li key={i} className="flex gap-2 text-white/50 text-[10px]">
                  <span className="text-emerald-400/60 shrink-0">›</span>
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      {/* 6. Loss Curves */}
      <Section icon={Activity} title="Training Loss Curves">
        {data.loss_curves?.length > 0 ? (
          <div className="space-y-4">
            {data.loss_curves.slice(0, 4).map((lc, i) => {
              const totalRounds = lc.train?.length || 0;
              const xTicks = totalRounds > 0
                ? [0, 1, 2, 3, 4].map((j) => {
                    const r = Math.round((j / 4) * totalRounds);
                    return r >= 1000 ? `${(r / 1000).toFixed(1)}K` : String(r);
                  })
                : [];
              return (
              <div key={i}>
                <p className="text-white/50 text-xs mb-1">
                  {lc.task} — {lc.horizon_h}h ahead · best iter={lc.best_iteration}
                </p>
                <LineChart
                  series={[
                    { name: "Train", data: _decimate(lc.train, 100), color: "#60a5fa" },
                    { name: "Val",   data: _decimate(lc.val,   100), color: "#f472b6" },
                  ]}
                  height={65}
                  xTicks={xTicks}
                  xLabel="Rounds"
                  yLabel={lc.metric}
                />
              </div>
              );
            })}
          </div>
        ) : (
          <p className="text-white/40 text-sm text-center py-4">No loss curves available yet</p>
        )}
      </Section>

      {/* 7. SHAP */}
      <Section icon={Brain} title="SHAP Feature Importance">
        {Object.keys(data.shap || {}).length > 0 ? (
          <div className="space-y-5">
            {Object.entries(data.shap).map(([key, sv]) => (
              sv?.global_importance?.length > 0 && (
                <div key={key}>
                  <p className="text-white/60 text-xs font-medium mb-2">
                    {key.replace("_", " — ")}
                  </p>
                  <HorizontalBar
                    items={sv.global_importance}
                    nameKey="feature"
                    valueKey="mean_abs_shap"
                    color="#a78bfa"
                    maxItems={10}
                  />
                  <p className="text-white/30 text-[10px] mt-2">
                    Mean |SHAP| across {sv.n_samples_used} test samples.
                    Longer bar = more impact on model output.
                  </p>
                  {key.includes("1h") && (
                    <CommentaryBox
                      variant="indigo"
                      points={[
                        "SHAP (SHapley Additive exPlanations) measures HOW MUCH each input feature contributes to each prediction — unlike feature importance which only measures average effect, SHAP explains individual predictions.",
                        "dry_spell_hours (top feature): How many consecutive dry hours before this reading. The longer the dry spell, the more the atmosphere can build up heat and instability — making the next rain more intense when it comes.",
                        "hum_lag_6h: Humidity 6 hours ago. If humidity was high 6 hours ago and has been rising, conditions are becoming favorable for precipitation.",
                        "rain_streak_hours: Consecutive hours of ongoing rain. Rain systems in Singapore typically last 1–3 hours, so knowing the streak helps predict whether rain will continue or stop.",
                        "cos_hour: The cosine-transformed hour of day. This captures the time-of-day cycle in a mathematically clean way — afternoon hours have higher convective rainfall risk.",
                        "wind_accel_3h: Rate of wind speed change over 3 hours. Rapidly increasing winds can signal an approaching storm system.",
                        "hum_deficit: Gap between actual humidity and saturation point. When this approaches zero, the air is close to condensation — rain becomes likely.",
                        "The longer the bar, the more that feature influences the model's rain forecasts. Features not listed have negligible impact and were excluded to prevent overfitting.",
                      ]}
                      tip="SHAP values tell a story: 'Given this exact combination of dry spell + humidity + time of day + wind, the model predicts rain with X% probability.'"
                    />
                  )}
                </div>
              )
            ))}
          </div>
        ) : (
          <p className="text-white/40 text-sm text-center py-4">No SHAP values available yet</p>
        )}
      </Section>
    </div>
  );
}

// Downsample an array to at most n points
function _decimate(arr, n) {
  if (!arr || arr.length <= n) return arr || [];
  const step = Math.ceil(arr.length / n);
  return arr.filter((_, i) => i % step === 0);
}
