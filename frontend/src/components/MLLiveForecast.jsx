import { useState, useEffect } from "react";
import { API_BASE } from "../api/base.js";
import { themeForTime } from "../contexts/ThemeContext";
import {
  RefreshCw, CloudRain, Sun, Moon, Zap, Droplets,
  Activity, Info, CheckCircle2, XCircle, Minus,
} from "lucide-react";

const CATEGORY_STYLES = {
  "No Rain":          { color: "text-accent",     bg: "bg-accent/10",     border: "border-accent/40",     icon: Sun },
  "Light Rain":       { color: "text-accent",    bg: "bg-accent/10",    border: "border-accent/40",    icon: CloudRain },
  "Heavy Rain":       { color: "text-accent",  bg: "bg-accent/10",  border: "border-accent/40",  icon: Droplets },
  "Thundery Showers": { color: "text-warn",  bg: "bg-warn/10",  border: "border-warn/40",  icon: Zap },
};

function pct(v, d = 0) {
  if (v == null) return "n/a";
  return `${(v * 100).toFixed(d)}%`;
}

function accColor(v) {
  if (v == null) return "text-muted";
  if (v >= 0.78) return "text-good";
  if (v >= 0.65) return "text-warn";
  return "text-bad";
}

function AccBar({ value }) {
  const pctVal = Math.round((value ?? 0) * 100);
  const bg = value == null ? "bg-line" : value >= 0.78 ? "bg-good" : value >= 0.65 ? "bg-warn" : "bg-bad";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${bg}`} style={{ width: `${pctVal}%` }} />
      </div>
      <span className={`text-xs w-8 text-right ${accColor(value)}`}>{pctVal}%</span>
    </div>
  );
}

function ProbBar({ label, value, colorBg }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 text-muted truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${colorBg} opacity-80`} style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="w-8 text-right text-ink">{Math.round(value * 100)}%</span>
    </div>
  );
}

// ── Forecast horizon card ────────────────────────────────────────────────────
function PredCard({ pred }) {
  const style = CATEGORY_STYLES[pred.predicted_label] || CATEGORY_STYLES["No Rain"];
  const target = new Date(pred.target_time);
  const Icon = style.icon === Sun && themeForTime(target) === "dark" ? Moon : style.icon;
  const timeLabel = target.toLocaleTimeString("en-SG", { hour: "numeric", minute: "2-digit", hour12: true });

  return (
    <div className={`rounded-panel border p-4 flex flex-col gap-3 ${style.bg} ${style.border}`}>
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold text-ink">+{pred.horizon_h}h</span>
          <span className="text-xs text-muted ml-1.5">{timeLabel}</span>
        </div>
        <Icon className={`h-4 w-4 ${style.color}`} strokeWidth={1.5} />
      </div>
      <div className={`text-base font-semibold ${style.color} leading-tight`}>{pred.predicted_label}</div>
      <div className="text-xs text-muted">{Math.round(pred.confidence * 100)}% confident</div>
      <div className="space-y-1 pt-1 border-t border-line">
        {Object.entries(pred.probabilities).map(([cat, prob]) => (
          <ProbBar key={cat} label={cat} value={prob} colorBg={CATEGORY_STYLES[cat]?.bg || "bg-accent/10"} />
        ))}
      </div>
    </div>
  );
}

// ── Model accuracy mini-strip ────────────────────────────────────────────────
function PerfStrip({ performance }) {
  if (!performance?.length) return null;
  return (
    <div className="rounded-panel bg-surface-2 border border-line p-3">
      <p className="text-xs text-muted mb-2 font-medium">
        How often it called rain or no rain correctly in 2024, by hours ahead
      </p>
      <div className="grid grid-cols-4 gap-2">
        {performance.map((p) => (
          <div key={p.horizon_h} className="text-center">
            <div className={`text-base font-bold ${accColor(p.binary_accuracy ?? p.test_accuracy)}`}>
              {pct(p.binary_accuracy ?? p.test_accuracy)}
            </div>
            <div className="text-xs text-muted mt-0.5">+{p.horizon_h}h</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Result icon helper ───────────────────────────────────────────────────────
function ResultIcon({ correct }) {
  if (correct === true)  return <CheckCircle2 className="h-3.5 w-3.5 text-good shrink-0" />;
  if (correct === false) return <XCircle      className="h-3.5 w-3.5 text-bad shrink-0" />;
  return                        <Minus        className="h-3.5 w-3.5 text-muted shrink-0" />;
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
    <div className="rounded-panel bg-surface-2 border border-line overflow-hidden">
      <button onClick={toggle} className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface-2 transition-all">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-accent" strokeWidth={1.5} />
          <span className="text-sm font-medium text-ink">How often it was right</span>
          <span className="text-xs text-muted">Our model, NEA and the two combined</span>
        </div>
        <span className="text-xs text-muted">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="px-4 pb-5 space-y-5">
          {loading && <p className="text-xs text-muted text-center py-4">Loading…</p>}

          {data && (
            <>
              {/* ── Historical test set ── */}
              {data.card?.historical?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-ink mb-1">
                    Historical Test Set: 2024 holdout data
                    <span className="font-normal text-muted ml-1">(our model only: NEA doesn't publish comparable scores)</span>
                  </p>
                  <div className="space-y-2">
                    {data.card.historical.map((h) => (
                      <div key={h.horizon_h} className="rounded-card bg-surface-2 border border-line p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-ink">+{h.horizon_h}h</span>
                          <div className="flex gap-3 text-xs">
                            <span className="text-muted">Binary acc</span>
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
                              <div className="text-sm font-bold text-ink">{pct(v)}</div>
                              <div className="text-xs text-muted">{label}</div>
                            </div>
                          ))}
                        </div>
                        {/* Confusion matrix mini */}
                        {h.confusion && (
                          <div className="grid grid-cols-4 gap-1 pt-1 text-center text-xs">
                            {[
                              { l: "True Rain",   v: h.confusion[1]?.[1], c: "text-good" },
                              { l: "Missed",      v: h.confusion[1]?.[0], c: "text-warn" },
                              { l: "False Alarm", v: h.confusion[0]?.[1], c: "text-bad" },
                              { l: "True Dry",    v: h.confusion[0]?.[0], c: "text-accent" },
                            ].map(({ l, v, c }) => (
                              <div key={l}>
                                <div className={`font-bold ${c}`}>{v?.toLocaleString() ?? "n/a"}</div>
                                <div className="text-muted">{l}</div>
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
                  <p className="text-xs font-semibold text-ink mb-1">
                    Live Scoring: ML vs NEA vs Hybrid
                    <span className="font-normal text-muted ml-1">· scored against actual weather observations</span>
                  </p>

                  {data.cmp.total_scored === 0 ? (
                    <div className="rounded-card bg-surface border border-line p-4 text-center">
                      <p className="text-xs text-muted">{data.cmp.message || "No scored predictions yet."}</p>
                      <p className="text-xs text-muted mt-1">
                        Predictions log each time this loads. Once a target time passes, scores are computed automatically.
                      </p>
                    </div>
                  ) : (
                    <>
                      {/* Per-horizon three-way table */}
                      <div className="rounded-card overflow-hidden border border-line">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-surface-2">
                              <th className="text-left px-3 py-2 text-muted font-medium">Horizon</th>
                              <th className="text-center px-2 py-2 text-accent font-medium">ML</th>
                              <th className="text-center px-2 py-2 text-good font-medium">NEA</th>
                              <th className="text-center px-2 py-2 text-accent font-medium">Hybrid</th>
                              <th className="text-right px-3 py-2 text-muted font-medium">n</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-line">
                            {data.cmp.by_horizon.map((row) => (
                              <tr key={row.horizon_h} className="hover:bg-surface-2">
                                <td className="px-3 py-2 text-ink font-semibold">+{row.horizon_h}h</td>
                                <td className={`text-center px-2 py-2 font-bold ${accColor(row.ml_binary_accuracy)}`}>
                                  {pct(row.ml_binary_accuracy)}
                                </td>
                                <td className={`text-center px-2 py-2 font-bold ${accColor(row.nea_binary_accuracy)}`}>
                                  {row.n_with_nea > 0 ? pct(row.nea_binary_accuracy) : <span className="text-muted">n/a</span>}
                                </td>
                                <td className={`text-center px-2 py-2 font-bold ${accColor(row.hybrid_binary_accuracy)}`}>
                                  {pct(row.hybrid_binary_accuracy)}
                                </td>
                                <td className="text-right px-3 py-2 text-muted">{row.n_scored}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Head-to-head when they disagree */}
                      {data.cmp.head_to_head && data.cmp.head_to_head.n_disagreements > 0 && (
                        <div className="rounded-card bg-surface-2 border border-line p-3 mt-2">
                          <p className="text-xs font-semibold text-ink mb-2">
                            Head-to-head when ML and NEA disagreed ({data.cmp.head_to_head.n_disagreements} times)
                          </p>
                          <div className="grid grid-cols-2 gap-3">
                            {[
                              { label: "ML won", v: data.cmp.head_to_head.ml_win_rate, c: "text-accent" },
                              { label: "NEA won", v: data.cmp.head_to_head.nea_win_rate, c: "text-good" },
                            ].map(({ label, v, c }) => (
                              <div key={label} className="text-center">
                                <div className={`text-lg font-bold ${c}`}>{pct(v)}</div>
                                <div className="text-xs text-muted">{label}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Recent examples */}
                      {data.cmp.recent?.length > 0 && (
                        <div>
                          <p className="text-xs text-muted mb-2 mt-2">Most recent scored predictions</p>
                          <div className="space-y-1.5 max-h-64 overflow-y-auto">
                            {data.cmp.recent.slice(0, 20).map((r, i) => {
                              const t = new Date(r.target_time);
                              const tLabel = t.toLocaleString("en-SG", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: true });
                              return (
                                <div key={i} className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-xs">
                                  <span className="text-muted w-28 shrink-0">{tLabel}</span>
                                  <span className="text-muted w-5 shrink-0">+{r.horizon_h}h</span>
                                  {/* ML */}
                                  <div className="flex items-center gap-1">
                                    <ResultIcon correct={r.ml.correct} />
                                    <span className="text-accent">{r.ml.prediction}</span>
                                  </div>
                                  {/* NEA */}
                                  <div className="flex items-center gap-1 ml-1">
                                    <ResultIcon correct={r.nea.correct} />
                                    <span className="text-good truncate max-w-[80px]">
                                      {r.nea.forecast_text || "n/a"}
                                    </span>
                                  </div>
                                  {/* Hybrid */}
                                  <div className="flex items-center gap-1 ml-1">
                                    <ResultIcon correct={r.hybrid.correct} />
                                    <span className="text-accent">H</span>
                                  </div>
                                  {/* Actual */}
                                  <span className="ml-auto text-muted shrink-0">
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
              <div className="rounded-card bg-accent/10 border border-accent/40 p-3 space-y-2">
                <div className="flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-accent shrink-0" />
                  <span className="text-xs font-semibold text-accent">Model & benchmark context</span>
                </div>
                {data.card?.model_info && (
                  <>
                    <p className="text-xs text-muted leading-relaxed">{data.card.model_info.nea_comparison_note}</p>
                    <p className="text-xs text-muted leading-relaxed">{data.card.model_info.why_lightgbm}</p>
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
    <div className="rounded-panel bg-surface border border-line p-5 sm:p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-ink">Rain forecast model</h1>
            <p className="mt-1 max-w-[65ch] text-sm text-muted">
              Our own forecast for the next 12 hours, trained on NEA readings from 2016 to 2024. It covers the whole island, not your exact location.
            </p>
          </div>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="inline-flex h-11 w-11 items-center justify-center rounded-control border border-line hover:bg-surface-2 disabled:opacity-60"
          aria-label="Update the forecast"
        >
          <RefreshCw className={`h-4 w-4 text-ink ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {loading && !data && (
        <div className="text-center py-8 text-muted text-sm">Loading forecast…</div>
      )}
      {error && (
        <div className="rounded-panel bg-bad/10 border border-bad/40 p-4 text-sm text-bad">{error}</div>
      )}

      {data && (
        <>
          {/* NEA 2-hr official comparison */}
          {neaForecast && (
            <div className="flex items-center gap-3 rounded-panel bg-good/10 border border-good/40 px-4 py-3">
              <div className="text-xs text-good font-semibold shrink-0">NEA now</div>
              <div className="text-xs text-ink">{neaForecast.forecast}</div>
              <div className="text-xs text-muted ml-auto shrink-0">{neaForecast.area}</div>
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
          {lastRefresh && (
            <p className="text-xs text-muted">
              Updated {lastRefresh.toLocaleTimeString("en-SG", { hour: "2-digit", minute: "2-digit" })}

            </p>
          )}
        </>
      )}
    </div>
  );
}
