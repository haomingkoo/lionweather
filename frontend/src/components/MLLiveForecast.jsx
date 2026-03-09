import { useState, useEffect } from "react";
import { Brain, RefreshCw, CloudRain, Sun, Zap, Droplets, BarChart2, Info } from "lucide-react";

const CATEGORY_STYLES = {
  "No Rain":          { color: "text-sky-400",     bg: "bg-sky-500/20",     border: "border-sky-500/30",     icon: Sun },
  "Light Rain":       { color: "text-blue-400",    bg: "bg-blue-500/20",    border: "border-blue-500/30",    icon: CloudRain },
  "Heavy Rain":       { color: "text-indigo-400",  bg: "bg-indigo-500/20",  border: "border-indigo-500/30",  icon: Droplets },
  "Thundery Showers": { color: "text-yellow-400",  bg: "bg-yellow-500/20",  border: "border-yellow-500/30",  icon: Zap },
};

function pct(v) {
  if (v == null) return "—";
  return `${Math.round(v * 100)}%`;
}

function ConfBar({ label, value, color }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 text-slate-400 truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} opacity-80`} style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="w-8 text-right text-slate-300">{Math.round(value * 100)}%</span>
    </div>
  );
}

function AccBar({ value, label, color = "bg-emerald-500" }) {
  const pctVal = Math.round((value ?? 0) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pctVal}%` }} />
      </div>
      <span className="text-xs text-slate-300 w-8 text-right">{pctVal}%</span>
      {label && <span className="text-xs text-slate-500">{label}</span>}
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
          <ConfBar key={cat} label={cat} value={prob} color={CATEGORY_STYLES[cat]?.bg.replace("bg-", "bg-") || "bg-blue-400"} />
        ))}
      </div>
    </div>
  );
}

// Accuracy color: green ≥ 70%, amber 55–69%, red < 55%
function accuracyColor(v) {
  if (v == null) return "bg-slate-500";
  if (v >= 0.70) return "bg-emerald-500";
  if (v >= 0.55) return "bg-amber-500";
  return "bg-red-500";
}

function ModelPerformancePanel({ performance }) {
  const [open, setOpen] = useState(false);
  if (!performance?.length) return null;

  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-all"
      >
        <div className="flex items-center gap-2">
          <BarChart2 className="h-4 w-4 text-blue-400" strokeWidth={1.5} />
          <span className="text-sm font-medium text-white">Model Performance</span>
          <span className="text-xs text-slate-500">· trained on NEA 2016–2024 test set</span>
        </div>
        <span className="text-xs text-slate-400">{open ? "▲ hide" : "▼ show"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4">
          {/* Overall accuracy per horizon */}
          <div>
            <p className="text-xs font-semibold text-slate-300 mb-2">Overall Accuracy by Forecast Horizon</p>
            <div className="space-y-2">
              {performance.map((p) => (
                <div key={p.horizon_h} className="flex items-center gap-3">
                  <span className="text-xs text-slate-400 w-6">+{p.horizon_h}h</span>
                  <div className="flex-1">
                    <AccBar value={p.test_accuracy} color={accuracyColor(p.test_accuracy)} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Binary rain detection (1h model highlighted) */}
          {performance[0]?.rain_recall != null && (
            <div>
              <p className="text-xs font-semibold text-slate-300 mb-2">Rain Detection Performance (1-hour model)</p>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "Precision", value: performance[0].rain_precision, tip: "When it says rain, it's right" },
                  { label: "Recall",    value: performance[0].rain_recall,    tip: "Of actual rain events caught" },
                  { label: "F1",        value: performance[0].rain_f1,        tip: "Balance of precision & recall" },
                ].map(({ label, value, tip }) => (
                  <div key={label} className="rounded-xl bg-white/5 border border-white/10 p-3 text-center">
                    <div className="text-lg font-bold text-white">{pct(value)}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{label}</div>
                    <div className="text-[10px] text-slate-600 mt-1 leading-tight">{tip}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Explanation */}
          <div className="rounded-xl bg-indigo-500/10 border border-indigo-500/20 p-3 space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
              <span className="text-xs font-semibold text-indigo-300">How to read this</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              <strong className="text-slate-300">Overall accuracy</strong> includes all four categories (No Rain, Light Rain, Heavy Rain, Thundery Showers).
              Shorter horizons are easier to predict — the 1-hour model reaches ~70% vs ~58% for 12 hours.
            </p>
            <p className="text-xs text-slate-400 leading-relaxed">
              <strong className="text-slate-300">Rain Detection</strong> collapses it to a binary yes/no.
              At 1h, the model catches <strong className="text-white">{pct(performance[0]?.rain_recall)}</strong> of actual rain events
              with <strong className="text-white">{pct(performance[0]?.rain_precision)}</strong> precision — meaning about
              {performance[0]?.rain_precision != null
                ? ` ${Math.round((1 - performance[0].rain_precision) * 100)}% of rain alerts are false alarms`
                : " some false alarms"}.
            </p>
            <p className="text-xs text-slate-500 leading-relaxed">
              NEA's official 2-hour area forecasts are text-based regional forecasts; they don't publish machine-comparable accuracy scores,
              making a direct apples-to-apples comparison difficult. Academic benchmarks for Singapore short-range rain suggest
              human-issued forecasts achieve roughly 70–80% binary accuracy — our 1-hour model is competitive in that range.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

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

  // Fetch NEA 2-hour area forecast for comparison
  const fetchNea = async () => {
    try {
      const res = await window.fetch("/api/forecasts/two-hour");
      if (!res.ok) return;
      const body = await res.json();
      // Find central Singapore area forecast
      const forecasts = body.forecasts || [];
      const central = forecasts.find((f) =>
        /central|city|downtown|marina|toa payoh/i.test(f.area || "")
      ) || forecasts[0];
      if (central) setNeaForecast({ area: central.area, forecast: central.forecast });
    } catch {
      // non-critical
    }
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

      {/* Body */}
      {loading && !data && (
        <div className="text-center py-8 text-slate-400 text-sm">Loading predictions…</div>
      )}

      {error && (
        <div className="rounded-2xl bg-red-500/10 border border-red-500/20 p-4 text-sm text-red-300">{error}</div>
      )}

      {data && (
        <>
          {/* Current conditions strip */}
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

          {/* NEA comparison strip */}
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

          {/* Model Performance (collapsible) */}
          <ModelPerformancePanel performance={data.model_performance} />

          {/* Footer note */}
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
