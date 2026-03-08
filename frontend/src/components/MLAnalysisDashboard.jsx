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

const CATEGORY_COLORS = {
  "No Rain": "#60a5fa",
  "Light Rain": "#34d399",
  "Heavy Rain": "#fbbf24",
  "Thundery Showers": "#f472b6",
};

// ---------------------------------------------------------------------------
// Tiny inline SVG chart primitives (no chart library dep)
// ---------------------------------------------------------------------------
function MiniBarChart({ data, height = 60, color = "#60a5fa", label }) {
  if (!data || data.length === 0) return null;
  const vals = data.map((d) => (typeof d === "object" ? d.value ?? d : d));
  const max = Math.max(...vals, 0.001);
  const barW = Math.max(1, Math.floor(240 / vals.length));

  return (
    <div>
      {label && <p className="text-white/50 text-xs mb-1">{label}</p>}
      <svg width="100%" viewBox={`0 0 ${vals.length * (barW + 1)} ${height}`}
           className="overflow-visible">
        {vals.map((v, i) => (
          <rect
            key={i}
            x={i * (barW + 1)}
            y={height - (v / max) * height}
            width={barW}
            height={(v / max) * height}
            fill={color}
            opacity={0.8}
          />
        ))}
      </svg>
    </div>
  );
}

function LineChart({ series, height = 80, xTicks, xLabel, yLabel }) {
  // series = [{ name, data: [number], color }]
  if (!series || series.length === 0) return null;
  const allVals = series.flatMap((s) => s.data.filter(Number.isFinite));
  if (allVals.length === 0) return null;

  const maxLen = Math.max(...series.map((s) => s.data.length));
  const minY = Math.min(...allVals);
  const maxY = Math.max(...allVals);
  const rangeY = Math.max(maxY - minY, 0.001);
  const W = 360;
  const H = height;
  const PAD = 4;

  const toX = (i) => PAD + (i / (maxLen - 1)) * (W - PAD * 2);
  const toY = (v) => H - PAD - ((v - minY) / rangeY) * (H - PAD * 2);

  return (
    <div>
      {(xLabel || yLabel) && (
        <div className="flex justify-between text-white/40 text-[10px] mb-1">
          <span>{yLabel}</span><span>{xLabel}</span>
        </div>
      )}
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
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
      </div>
    </div>
  );
}

function StemChart({ lags, values, ci, height = 80, color = "#60a5fa", title }) {
  // ACF / PACF stem plot
  if (!lags || !values) return null;
  const W = 360;
  const H = height;
  const PAD_X = 16;
  const nLags = lags.length;
  const stepX = (W - PAD_X * 2) / (nLags - 1);
  const midY = H / 2;
  const scale = (midY - 4) * 0.95;

  const toX = (i) => PAD_X + i * stepX;
  const toY = (v) => midY - v * scale;
  const ciY = ci ? midY - ci * scale : midY - 1.96 * scale / Math.sqrt(100);

  return (
    <div>
      {title && <p className="text-white/50 text-xs mb-1">{title}</p>}
      <svg width="100%" viewBox={`0 0 ${W} ${H}`}>
        {/* zero line */}
        <line x1={PAD_X} y1={midY} x2={W - PAD_X} y2={midY}
              stroke="#ffffff22" strokeWidth="1" />
        {/* CI bounds */}
        {ci && (
          <>
            <line x1={PAD_X} y1={ciY} x2={W - PAD_X} y2={ciY}
                  stroke="#fbbf2466" strokeWidth="1" strokeDasharray="4,2" />
            <line x1={PAD_X} y1={H - ciY} x2={W - PAD_X} y2={H - ciY}
                  stroke="#fbbf2466" strokeWidth="1" strokeDasharray="4,2" />
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
                    stroke={aboveThreshold ? color : "#ffffff33"}
                    strokeWidth="1.5" />
              <circle cx={x} cy={y} r="2"
                      fill={aboveThreshold ? color : "#ffffff33"} />
            </g>
          );
        })}
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
  const n = matrix.length;
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
                const intensity = Math.round((val / maxVal) * 255);
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
      <div className="flex flex-wrap gap-2">
        {varNames.map((v) => (
          <button
            key={v}
            onClick={() => setSelectedVar(v)}
            className={`text-xs px-3 py-1 rounded-full border transition-colors ${
              selectedVar === v
                ? "bg-blue-500/30 border-blue-400/60 text-blue-200"
                : "bg-white/8 border-white/15 text-white/60 hover:text-white"
            }`}
          >
            {v}
          </button>
        ))}
      </div>

      {/* 1. EDA */}
      <Section icon={BarChart3} title="Exploratory Data Analysis">
        {data.eda?.[selectedVar] && (() => {
          const e = data.eda[selectedVar];
          return (
            <div className="space-y-4">
              {/* Stats grid */}
              <div className="grid grid-cols-3 gap-2">
                {[
                  ["Mean", e.mean],
                  ["Std", e.std],
                  ["Skewness", e.skewness],
                  ["Kurtosis", e.kurtosis],
                  ["P50", e.p50],
                  ["P99", e.p99],
                ].map(([label, val]) => (
                  <div key={label} className="bg-white/5 rounded-xl p-2 text-center">
                    <p className="text-white/40 text-[10px]">{label}</p>
                    <p className="text-white font-semibold text-sm">{val}</p>
                  </div>
                ))}
              </div>

              {/* Distribution histogram */}
              {e.histogram && (
                <div>
                  <p className="text-white/50 text-xs mb-2">Distribution</p>
                  <MiniBarChart
                    data={e.histogram.counts}
                    height={60}
                    color="#60a5fa"
                  />
                </div>
              )}

              {/* Hourly pattern */}
              <LineChart
                series={[{
                  name: `Hourly mean (${selectedVar})`,
                  data: Object.values(e.hourly_pattern),
                  color: "#60a5fa",
                }]}
                height={60}
                xLabel="Hour of day"
                yLabel="Mean"
              />

              {/* Monthly pattern */}
              <LineChart
                series={[{
                  name: `Monthly mean (${selectedVar})`,
                  data: Object.values(e.monthly_pattern),
                  color: "#34d399",
                }]}
                height={60}
                xLabel="Month"
                yLabel="Mean"
              />

              {/* Annual trend */}
              <LineChart
                series={[{
                  name: `Annual mean (${selectedVar})`,
                  data: Object.values(e.annual_trend),
                  color: "#fbbf24",
                }]}
                height={60}
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
            </div>
          );
        })()}
      </Section>

      {/* 2. ACF / PACF */}
      <Section icon={Activity} title="ACF / PACF (Autocorrelation)">
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
            </div>
          );
        })()}
      </Section>

      {/* 3. Spectral / FFT */}
      <Section icon={Waves} title="Frequency Analysis (FFT Periodogram)">
        {data.spectral?.[selectedVar] && (() => {
          const sp = data.spectral[selectedVar];
          const chartData = sp.chart_data || [];
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
                height={70}
                xLabel="Period (hours)"
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

        {/* Classification accuracy */}
        {hr.classification?.accuracy != null && (
          <div className="bg-white/5 rounded-xl p-3 mb-4">
            <p className="text-white/50 text-xs mb-2">
              4-Class Accuracy: <span className="text-emerald-400 font-semibold">
                {(hr.classification.accuracy * 100).toFixed(1)}%
              </span>
            </p>
            {hr.classification.confusion_matrix && (
              <ConfusionMatrix
                matrix={hr.classification.confusion_matrix}
                labels={categories}
              />
            )}
            <p className="text-white/30 text-[10px] mt-2">
              Categories: No Rain / Light Rain (&lt;7.6mm/hr) / Heavy Rain / Thundery Showers (≥30mm/hr)
            </p>
          </div>
        )}

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

      {/* 6. Loss Curves */}
      <Section icon={Activity} title="Training Loss Curves">
        {data.loss_curves?.length > 0 ? (
          <div className="space-y-4">
            {data.loss_curves.slice(0, 4).map((lc, i) => (
              <div key={i}>
                <p className="text-white/50 text-xs mb-1">
                  {lc.task} — {lc.horizon_h}h ahead · best iter={lc.best_iteration}
                </p>
                <LineChart
                  series={[
                    { name: "Train", data: _decimate(lc.train, 100), color: "#60a5fa" },
                    { name: "Val",   data: _decimate(lc.val,   100), color: "#f472b6" },
                  ]}
                  height={60}
                  xLabel="Rounds"
                  yLabel={lc.metric}
                />
              </div>
            ))}
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
