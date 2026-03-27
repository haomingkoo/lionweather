import { useState, useEffect } from "react";
import { API_BASE } from "../api/base.js";
import {
  Brain, RefreshCw, CloudRain, Sun, Zap, Droplets,
  Activity, Info, CheckCircle2, XCircle, Minus,
} from "lucide-react";

const CATEGORY_STYLES = {
  "No Rain":          { color: "text-sky-400",     bg: "bg-sky-500/20",     border: "border-sky-500/30",     icon: Sun },
  "Light Rain":       { color: "text-blue-400",    bg: "bg-blue-500/20",    border: "border-blue-500/30",    icon: CloudRain },
  "Heavy Rain":       { color: "text-indigo-400",  bg: "bg-indigo-500/20",  border: "border-indigo-500/30",  icon: Droplets },
  "Thundery Showers": { color: "text-yellow-400",  bg: "bg-yellow-500/20",  border: "border-yellow-500/30",  icon: Zap },
};

function pct(v, d = 0) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(d)}%`;
}

function accColor(v) {
  if (v == null) return "text-slate-500";
  if (v >= 0.78) return "text-emerald-400";
  if (v >= 0.65) return "text-amber-400";
  return "text-red-400";
}

function AccBar({ value }) {
  const pctVal = Math.round((value ?? 0) * 100);
  const bg = value == null ? "bg-slate-600" : value >= 0.78 ? "bg-emerald-500" : value >= 0.65 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${bg}`} style={{ width: `${pctVal}%` }} />
      </div>
      <span className={`text-xs w-8 text-right ${accColor(value)}`}>{pctVal}%</span>
    </div>
  );
}

function ProbBar({ label, value, colorBg }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 text-slate-400 truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${colorBg} opacity-80`} style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="w-8 text-right text-slate-300">{Math.round(value * 100)}%</span>
    </div>
  );
}

// ── Forecast horizon card ────────────────────────────────────────────────────
function PredCard({ pred }) {
  const style = CATEGORY_STYLES[pred.predicted_label] || CATEGORY_STYLES["No Rain"];
  const Icon = style.icon;
  const target = new Date(pred.target_time);
  const timeLabel = target.toLocaleTimeString("en-SG", { hour: "numeric", minute: "2-digit", hour12: true });

  return (
    <div className={`rounded-2xl border p-4 flex flex-col gap-3 ${style.bg} ${style.border}`}>
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold text-white">+{pred.horizon_h}h</span>
          <span className="text-[10px] text-slate-400 ml-1.5">{timeLabel}</span>
        </div>
        <Icon className={`h-4 w-4 ${style.color}`} strokeWidth={1.5} />
      </div>
      <div className={`text-base font-semibold ${style.color} leading-tight`}>{pred.predicted_label}</div>
      <div className="text-xs text-slate-400">{Math.round(pred.confidence * 100)}% confident</div>
      <div className="space-y-1 pt-1 border-t border-white/5">
        {Object.entries(pred.probabilities).map(([cat, prob]) => (
          <ProbBar key={cat} label={cat} value={prob} colorBg={CATEGORY_STYLES[cat]?.bg || "bg-blue-500/20"} />
        ))}
      </div>
    </div>
  );
}

// ── Model accuracy mini-strip ────────────────────────────────────────────────
function PerfStrip({ performance }) {
  if (!performance?.length) return null;
  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 p-3">
      <p className="text-[10px] text-slate-500 mb-2 font-medium uppercase tracking-wide">
        Model accuracy on 2024 test set (binary rain/no-rain)
      </p>
      <div className="grid grid-cols-4 gap-2">
        {performance.map((p) => (
          <div key={p.horizon_h} className="text-center">
            <div className={`text-base font-bold ${accColor(p.binary_accuracy ?? p.test_accuracy)}`}>
              {pct(p.binary_accuracy ?? p.test_accuracy)}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">+{p.horizon_h}h</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Result icon helper ───────────────────────────────────────────────────────
function ResultIcon({ correct }) {
  if (correct === true)  return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />;
  if (correct === false) return <XCircle      className="h-3.5 w-3.5 text-red-400 shrink-0" />;
  return                        <Minus        className="h-3.5 w-3.5 text-slate-600 shrink-0" />;
}

// ── Three-way comparison panel ───────────────────────────────────────────────
function ComparisonPanel() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (data) return;
    setLoading(true);
    try {
      const [cmpRes, cardRes] = await Promise.all([
        window.fetch(`${API_BASE}/ml/comparison`),
        window.fetch(`${API_BASE}/ml/scorecard`),
      ]);
      const cmp  = cmpRes.ok  ? await cmpRes.json()  : null;
      const card = cardRes.ok ? await cardRes.json() : null;
      setData({ cmp, card });
    } catch { /* non-critical */ }
    finally { setLoading(false); }
  };

  const toggle = () => { const n = !open; setOpen(n); if (n) load(); };

  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 overflow-hidden">
      <button onClick={toggle} className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-all">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-violet-400" strokeWidth={1.5} />
          <span className="text-sm font-medium text-white">Performance vs Ground Truth</span>
          <span className="text-xs text-slate-500">· ML · NEA · Hybrid</span>
        </div>
        <span className="text-xs text-slate-400">{open ? "▲ hide" : "▼ show"}</span>
      </button>

      {open && (
        <div className="px-4 pb-5 space-y-5">
          {loading && <p className="text-xs text-slate-400 text-center py-4">Loading…</p>}

          {data && (
            <>
              {/* ── Historical test set ── */}
              {data.card?.historical?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-300 mb-1">
                    Historical Test Set — 2024 holdout data
                    <span className="font-normal text-slate-500 ml-1">(our model only — NEA doesn't publish comparable scores)</span>
                  </p>
                  <div className="space-y-2">
                    {data.card.historical.map((h) => (
                      <div key={h.horizon_h} className="rounded-xl bg-white/5 border border-white/10 p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-white">+{h.horizon_h}h</span>
                          <div className="flex gap-3 text-xs">
                            <span className="text-slate-500">Binary acc</span>
                            <span className={`font-bold ${accColor(h.binary_accuracy)}`}>{pct(h.binary_accuracy)}</span>
                          </div>
                        </div>
                        <AccBar value={h.binary_accuracy} />
                        <div className="grid grid-cols-3 gap-2 text-center pt-1">
                          {[
                            { label: "Precision", v: h.rain_precision, tip: "Alerts that were real rain" },
                            { label: "Recall",    v: h.rain_recall,    tip: "Rain events caught" },
                            { label: "F1",        v: h.rain_f1 },
                          ].map(({ label, v, tip }) => (
                            <div key={label} title={tip}>
                              <div className="text-sm font-bold text-white">{pct(v)}</div>
                              <div className="text-[10px] text-slate-500">{label}</div>
                            </div>
                          ))}
                        </div>
                        {/* Confusion matrix mini */}
                        {h.confusion && (
                          <div className="grid grid-cols-4 gap-1 pt-1 text-center text-[10px]">
                            {[
                              { l: "True Rain",   v: h.confusion[1]?.[1], c: "text-emerald-400" },
                              { l: "Missed",      v: h.confusion[1]?.[0], c: "text-amber-400" },
                              { l: "False Alarm", v: h.confusion[0]?.[1], c: "text-red-400" },
                              { l: "True Dry",    v: h.confusion[0]?.[0], c: "text-sky-400" },
                            ].map(({ l, v, c }) => (
                              <div key={l}>
                                <div className={`font-bold ${c}`}>{v?.toLocaleString() ?? "—"}</div>
                                <div className="text-slate-600">{l}</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ── Live three-way comparison ── */}
              {data.cmp && (
                <div>
                  <p className="text-xs font-semibold text-slate-300 mb-1">
                    Live Scoring — ML vs NEA vs Hybrid
                    <span className="font-normal text-slate-500 ml-1">· scored against actual weather observations</span>
                  </p>

                  {data.cmp.total_scored === 0 ? (
                    <div className="rounded-xl bg-slate-800/50 border border-white/10 p-4 text-center">
                      <p className="text-xs text-slate-400">{data.cmp.message || "No scored predictions yet."}</p>
                      <p className="text-[10px] text-slate-600 mt-1">
                        Predictions log each time this loads. Once a target time passes, scores are computed automatically.
                      </p>
                    </div>
                  ) : (
                    <>
                      {/* Per-horizon three-way table */}
                      <div className="rounded-xl overflow-hidden border border-white/10">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-white/5">
                              <th className="text-left px-3 py-2 text-slate-400 font-medium">Horizon</th>
                              <th className="text-center px-2 py-2 text-blue-400 font-medium">ML</th>
                              <th className="text-center px-2 py-2 text-emerald-400 font-medium">NEA</th>
                              <th className="text-center px-2 py-2 text-violet-400 font-medium">Hybrid</th>
                              <th className="text-right px-3 py-2 text-slate-500 font-medium">n</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/5">
                            {data.cmp.by_horizon.map((row) => (
                              <tr key={row.horizon_h} className="hover:bg-white/5">
                                <td className="px-3 py-2 text-white font-semibold">+{row.horizon_h}h</td>
                                <td className={`text-center px-2 py-2 font-bold ${accColor(row.ml_binary_accuracy)}`}>
                                  {pct(row.ml_binary_accuracy)}
                                </td>
                                <td className={`text-center px-2 py-2 font-bold ${accColor(row.nea_binary_accuracy)}`}>
                                  {row.n_with_nea > 0 ? pct(row.nea_binary_accuracy) : <span className="text-slate-600">—</span>}
                                </td>
                                <td className={`text-center px-2 py-2 font-bold ${accColor(row.hybrid_binary_accuracy)}`}>
                                  {pct(row.hybrid_binary_accuracy)}
                                </td>
                                <td className="text-right px-3 py-2 text-slate-500">{row.n_scored}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Head-to-head when they disagree */}
                      {data.cmp.head_to_head && data.cmp.head_to_head.n_disagreements > 0 && (
                        <div className="rounded-xl bg-white/5 border border-white/10 p-3 mt-2">
                          <p className="text-xs font-semibold text-slate-300 mb-2">
                            Head-to-head when ML and NEA disagreed ({data.cmp.head_to_head.n_disagreements} times)
                          </p>
                          <div className="grid grid-cols-2 gap-3">
                            {[
                              { label: "ML won", v: data.cmp.head_to_head.ml_win_rate, c: "text-blue-400" },
                              { label: "NEA won", v: data.cmp.head_to_head.nea_win_rate, c: "text-emerald-400" },
                            ].map(({ label, v, c }) => (
                              <div key={label} className="text-center">
                                <div className={`text-lg font-bold ${c}`}>{pct(v)}</div>
                                <div className="text-[10px] text-slate-500">{label}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Recent examples */}
                      {data.cmp.recent?.length > 0 && (
                        <div>
                          <p className="text-xs text-slate-500 mb-2 mt-2">Most recent scored predictions</p>
                          <div className="space-y-1.5 max-h-64 overflow-y-auto">
                            {data.cmp.recent.slice(0, 20).map((r, i) => {
                              const t = new Date(r.target_time);
                              const tLabel = t.toLocaleString("en-SG", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: true });
                              return (
                                <div key={i} className="flex items-center gap-2 rounded-lg bg-white/5 px-3 py-2 text-[11px]">
                                  <span className="text-slate-500 w-28 shrink-0">{tLabel}</span>
                                  <span className="text-slate-400 w-5 shrink-0">+{r.horizon_h}h</span>
                                  {/* ML */}
                                  <div className="flex items-center gap-1">
                                    <ResultIcon correct={r.ml.correct} />
                                    <span className="text-blue-300">{r.ml.prediction}</span>
                                  </div>
                                  {/* NEA */}
                                  <div className="flex items-center gap-1 ml-1">
                                    <ResultIcon correct={r.nea.correct} />
                                    <span className="text-emerald-300 truncate max-w-[80px]">
                                      {r.nea.forecast_text || "—"}
                                    </span>
                                  </div>
                                  {/* Hybrid */}
                                  <div className="flex items-center gap-1 ml-1">
                                    <ResultIcon correct={r.hybrid.correct} />
                                    <span className="text-violet-300">H</span>
                                  </div>
                                  {/* Actual */}
                                  <span className="ml-auto text-slate-400 shrink-0">
                                    Actual: {r.actual.rainfall_mm != null ? `${r.actual.rainfall_mm} mm` : r.actual.label}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* ── Context ── */}
              <div className="rounded-xl bg-indigo-500/10 border border-indigo-500/20 p-3 space-y-2">
                <div className="flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                  <span className="text-xs font-semibold text-indigo-300">Model & benchmark context</span>
                </div>
                {data.card?.model_info && (
                  <>
                    <p className="text-xs text-slate-400 leading-relaxed">{data.card.model_info.nea_comparison_note}</p>
                    <p className="text-xs text-slate-500 leading-relaxed">{data.card.model_info.why_lightgbm}</p>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────
export function MLLiveForecast() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [neaForecast, setNeaForecast] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await window.fetch(`${API_BASE}/ml/rain-forecast`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `${res.status}`);
      }
      setData(await res.json());
      setLastRefresh(new Date());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchNea = async () => {
    try {
      const res = await window.fetch(`${API_BASE}/forecasts/two-hour`);
      if (!res.ok) return;
      const body = await res.json();
      const forecasts = body.forecasts || [];
      const central = forecasts.find((f) =>
        /central|city|downtown|marina|toa payoh/i.test(f.area || "")
      ) || forecasts[0];
      if (central) setNeaForecast({ area: central.area, forecast: central.forecast });
    } catch { /* non-critical */ }
  };

  useEffect(() => {
    fetchData();
    fetchNea();
    const id = setInterval(() => { fetchData(); fetchNea(); }, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="rounded-3xl bg-white/5 border border-white/10 p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-blue-500/20 border border-blue-500/30">
            <Brain className="h-5 w-5 text-blue-400" strokeWidth={1.5} />
          </div>
          <div>
            <h3 className="text-base font-semibold text-white">Rain Forecast</h3>
            <p className="text-xs text-slate-400">LightGBM · NEA 2016–2024 · 1h to 12h ahead</p>
            <p className="text-[10px] text-slate-500 mt-0.5">
              Island-wide average · all NEA stations, not your specific location
            </p>
          </div>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="p-2 rounded-xl bg-white/10 hover:bg-white/20 transition-all disabled:opacity-40"
          aria-label="Refresh"
        >
          <RefreshCw className={`h-4 w-4 text-slate-300 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {loading && !data && (
        <div className="text-center py-8 text-slate-400 text-sm">Loading forecast…</div>
      )}
      {error && (
        <div className="rounded-2xl bg-red-500/10 border border-red-500/20 p-4 text-sm text-red-300">{error}</div>
      )}

      {data && (
        <>
          {/* NEA 2-hr official comparison */}
          {neaForecast && (
            <div className="flex items-center gap-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 px-4 py-3">
              <div className="text-xs text-emerald-400 font-semibold shrink-0">NEA 2-hr</div>
              <div className="text-xs text-slate-300">{neaForecast.forecast}</div>
              <div className="text-xs text-slate-600 ml-auto shrink-0">{neaForecast.area}</div>
            </div>
          )}

          {/* Forecast horizon cards — the main content */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {data.predictions.map((pred) => (
              <PredCard key={pred.horizon_h} pred={pred} />
            ))}
          </div>

          {/* Mini accuracy strip */}
          <PerfStrip performance={data.model_performance} />

          {/* Full performance vs ground truth (collapsible) */}
          <ComparisonPanel />

          {/* Footer */}
          <p className="text-xs text-slate-500 leading-relaxed">{data.data_note}</p>
          {lastRefresh && (
            <p className="text-xs text-slate-600">
              Updated {lastRefresh.toLocaleTimeString("en-SG", { hour: "2-digit", minute: "2-digit" })}
              {" · "}{data.current.hours_of_data}h of live data used for features
            </p>
          )}
        </>
      )}
    </div>
  );
}
