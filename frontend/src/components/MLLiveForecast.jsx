import { useState, useEffect } from "react";
import { Brain, RefreshCw, CloudRain, Sun, Zap, Droplets, BarChart2, Info, Activity } from "lucide-react";

const CATEGORY_STYLES = {
  "No Rain":          { color: "text-sky-400",     bg: "bg-sky-500/20",     border: "border-sky-500/30",     icon: Sun },
  "Light Rain":       { color: "text-blue-400",    bg: "bg-blue-500/20",    border: "border-blue-500/30",    icon: CloudRain },
  "Heavy Rain":       { color: "text-indigo-400",  bg: "bg-indigo-500/20",  border: "border-indigo-500/30",  icon: Droplets },
  "Thundery Showers": { color: "text-yellow-400",  bg: "bg-yellow-500/20",  border: "border-yellow-500/30",  icon: Zap },
};

const HORIZONS = [1, 3, 6, 12];

function pct(v, decimals = 0) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(decimals)}%`;
}

function accColor(v) {
  if (v == null) return "bg-slate-600";
  if (v >= 0.78) return "bg-emerald-500";
  if (v >= 0.65) return "bg-amber-500";
  return "bg-red-500";
}

function ConfBar({ label, value, colorBg }) {
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

function AccBar({ value, thin }) {
  const pctVal = Math.round((value ?? 0) * 100);
  return (
    <div className={`flex items-center gap-2 ${thin ? "" : ""}`}>
      <div className={`flex-1 ${thin ? "h-1" : "h-2"} bg-white/10 rounded-full overflow-hidden`}>
        <div className={`h-full rounded-full ${accColor(value)}`} style={{ width: `${pctVal}%` }} />
      </div>
      <span className={`text-slate-300 w-8 text-right ${thin ? "text-[10px]" : "text-xs"}`}>{pctVal}%</span>
    </div>
  );
}

function PredCard({ pred }) {
  const style = CATEGORY_STYLES[pred.predicted_label] || CATEGORY_STYLES["No Rain"];
  const Icon = style.icon;
  const target = new Date(pred.target_time);
  const label = target.toLocaleTimeString("en-SG", { hour: "numeric", minute: "2-digit", hour12: true });

  return (
    <div className={`rounded-2xl border p-4 flex flex-col gap-3 ${style.bg} ${style.border}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400 font-medium">+{pred.horizon_h}h · {label}</span>
        <Icon className={`h-4 w-4 ${style.color}`} strokeWidth={1.5} />
      </div>
      <div className={`text-lg font-semibold ${style.color}`}>{pred.predicted_label}</div>
      <div className="space-y-1">
        {Object.entries(pred.probabilities).map(([cat, prob]) => (
          <ConfBar key={cat} label={cat} value={prob} colorBg={CATEGORY_STYLES[cat]?.bg || "bg-blue-500/20"} />
        ))}
      </div>
    </div>
  );
}

// ── Scorecard panel ──────────────────────────────────────────────────────────
function ScorecardPanel() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (data) return; // already loaded
    setLoading(true);
    try {
      const res = await window.fetch("/api/ml/scorecard");
      if (res.ok) setData(await res.json());
    } catch { /* non-critical */ }
    finally { setLoading(false); }
  };

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) load();
  };

  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 overflow-hidden">
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-all"
      >
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-violet-400" strokeWidth={1.5} />
          <span className="text-sm font-medium text-white">Model Scorecard</span>
          <span className="text-xs text-slate-500">· historical + live performance</span>
        </div>
        <span className="text-xs text-slate-400">{open ? "▲ hide" : "▼ show"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-5">
          {loading && <p className="text-xs text-slate-400 text-center py-4">Loading scorecard…</p>}

          {data && (
            <>
              {/* ── Test-set performance (offline) ── */}
              <div>
                <p className="text-xs font-semibold text-slate-300 mb-1">
                  Historical Test-Set Performance
                  <span className="font-normal text-slate-500 ml-1">(2024 holdout · {data.historical?.[0]?.n_test?.toLocaleString()} samples per horizon)</span>
                </p>
                <p className="text-[10px] text-slate-500 mb-3 leading-relaxed">
                  Train 2016–2022 · Validation 2023 · Test 2024. These numbers measure how the model would have done on last year's data — the only honest offline benchmark.
                </p>

                <div className="space-y-3">
                  {(data.historical || []).map((h) => (
                    <div key={h.horizon_h} className="rounded-xl bg-white/5 border border-white/10 p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-white">+{h.horizon_h}h forecast</span>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                          h.binary_accuracy >= 0.78 ? "bg-emerald-500/20 text-emerald-300"
                          : h.binary_accuracy >= 0.65 ? "bg-amber-500/20 text-amber-300"
                          : "bg-red-500/20 text-red-300"
                        }`}>
                          {pct(h.binary_accuracy)} binary acc
                        </span>
                      </div>
                      <AccBar value={h.binary_accuracy} />
                      <div className="grid grid-cols-3 gap-2 pt-1">
                        {[
                          { label: "Rain precision", value: h.rain_precision, tip: "When it predicts rain, it's right X% of the time" },
                          { label: "Rain recall",    value: h.rain_recall,    tip: "Of actual rain events, it catches X%" },
                          { label: "Rain F1",        value: h.rain_f1,        tip: "Harmonic mean of precision & recall" },
                        ].map(({ label, value, tip }) => (
                          <div key={label} className="text-center" title={tip}>
                            <div className="text-sm font-bold text-white">{pct(value)}</div>
                            <div className="text-[10px] text-slate-500 mt-0.5">{label}</div>
                          </div>
                        ))}
                      </div>
                      {/* Confusion matrix summary */}
                      {h.confusion && (
                        <div className="grid grid-cols-4 gap-1 pt-1 text-center text-[10px]">
                          {[
                            { label: "True Rain",   v: h.confusion[1]?.[1], c: "text-emerald-400" },
                            { label: "Missed Rain", v: h.confusion[1]?.[0], c: "text-amber-400" },
                            { label: "False Alarm", v: h.confusion[0]?.[1], c: "text-red-400" },
                            { label: "True Dry",    v: h.confusion[0]?.[0], c: "text-sky-400" },
                          ].map(({ label, v, c }) => (
                            <div key={label}>
                              <div className={`font-bold ${c}`}>{v?.toLocaleString() ?? "—"}</div>
                              <div className="text-slate-600">{label}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* ── Live scoring ── */}
              <div>
                <p className="text-xs font-semibold text-slate-300 mb-1">
                  Live Scoring
                  <span className="font-normal text-slate-500 ml-1">· predictions scored against actual observations since deployment</span>
                </p>
                {data.live_total_scored === 0 ? (
                  <div className="rounded-xl bg-slate-800/50 border border-white/10 p-4 text-center">
                    <p className="text-xs text-slate-400">No scored predictions yet.</p>
                    <p className="text-[10px] text-slate-600 mt-1">
                      Predictions are logged each time this page loads and scored against actual weather data once the target time passes.
                      Check back after a few hours.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <p className="text-[10px] text-slate-500">{data.live_total_scored.toLocaleString()} predictions scored so far</p>
                    {(data.live || []).map((h) => (
                      <div key={h.horizon_h} className="flex items-center gap-3 rounded-xl bg-white/5 border border-white/10 px-3 py-2">
                        <span className="text-xs text-slate-400 w-8 shrink-0">+{h.horizon_h}h</span>
                        <div className="flex-1">
                          <AccBar value={h.binary_accuracy} thin />
                        </div>
                        <span className="text-xs text-slate-500 shrink-0">n={h.n_scored}</span>
                        <span className="text-xs text-slate-400 shrink-0">P={pct(h.rain_precision)} R={pct(h.rain_recall)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* ── Model rationale + NEA comparison ── */}
              <div className="rounded-xl bg-indigo-500/10 border border-indigo-500/20 p-3 space-y-2">
                <div className="flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                  <span className="text-xs font-semibold text-indigo-300">How we compare to NEA & why LightGBM</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">{data.model_info?.nea_comparison_note}</p>
                <p className="text-xs text-slate-500 leading-relaxed">{data.model_info?.why_lightgbm}</p>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Model performance mini-strip (always visible) ────────────────────────────
function PerfStrip({ performance }) {
  if (!performance?.length) return null;
  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 p-3">
      <p className="text-[10px] text-slate-500 mb-2 font-medium uppercase tracking-wide">Model accuracy on 2024 test set</p>
      <div className="grid grid-cols-4 gap-2">
        {performance.map((p) => (
          <div key={p.horizon_h} className="text-center">
            <div className={`text-sm font-bold ${p.binary_accuracy >= 0.78 ? "text-emerald-400" : p.binary_accuracy >= 0.65 ? "text-amber-400" : "text-red-400"}`}>
              {pct(p.binary_accuracy ?? p.test_accuracy)}
            </div>
            <div className="text-[10px] text-slate-500">+{p.horizon_h}h</div>
          </div>
        ))}
      </div>
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
      const res = await window.fetch("/api/ml/rain-forecast");
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
      const res = await window.fetch("/api/forecasts/two-hour");
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
            <h3 className="text-base font-semibold text-white">Live Rain Forecast</h3>
            <p className="text-xs text-slate-400">LightGBM · trained on NEA 2016–2024</p>
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
        <div className="text-center py-8 text-slate-400 text-sm">Loading predictions…</div>
      )}

      {error && (
        <div className="rounded-2xl bg-red-500/10 border border-red-500/20 p-4 text-sm text-red-300">{error}</div>
      )}

      {data && (
        <>
          {/* Current conditions */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Temp", value: `${data.current.temperature}°C` },
              { label: "Humidity", value: `${data.current.humidity}%` },
              { label: "Rain now", value: `${data.current.rainfall} mm` },
              { label: "Wind", value: `${data.current.wind_speed} km/h` },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-2xl bg-white/5 border border-white/10 p-3 text-center">
                <div className="text-xs text-slate-400 mb-1">{label}</div>
                <div className="text-sm font-semibold text-white">{value}</div>
              </div>
            ))}
          </div>

          {/* NEA 2-hr comparison */}
          {neaForecast && (
            <div className="flex items-center gap-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 px-4 py-3">
              <div className="text-xs text-emerald-400 font-semibold shrink-0">NEA 2-hr</div>
              <div className="text-xs text-slate-300">{neaForecast.forecast}</div>
              <div className="text-xs text-slate-600 ml-auto shrink-0">{neaForecast.area}</div>
            </div>
          )}

          {/* Prediction cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {data.predictions.map((pred) => (
              <PredCard key={pred.horizon_h} pred={pred} />
            ))}
          </div>

          {/* Mini accuracy strip */}
          <PerfStrip performance={data.model_performance} />

          {/* Scorecard (full, collapsible) */}
          <ScorecardPanel />

          {/* Footer */}
          <p className="text-xs text-slate-500 leading-relaxed">{data.data_note}</p>
          {lastRefresh && (
            <p className="text-xs text-slate-600">
              Updated {lastRefresh.toLocaleTimeString("en-SG", { hour: "2-digit", minute: "2-digit" })}
              {" · "}{data.current.hours_of_data}h of live data collected
            </p>
          )}
        </>
      )}
    </div>
  );
}
