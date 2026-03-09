import { useState, useEffect } from "react";
import { Brain, RefreshCw, CloudRain, Sun, Zap, Droplets } from "lucide-react";

const CATEGORY_STYLES = {
  "No Rain":          { color: "text-sky-400",     bg: "bg-sky-500/20",     border: "border-sky-500/30",     icon: Sun },
  "Light Rain":       { color: "text-blue-400",    bg: "bg-blue-500/20",    border: "border-blue-500/30",    icon: CloudRain },
  "Heavy Rain":       { color: "text-indigo-400",  bg: "bg-indigo-500/20",  border: "border-indigo-500/30",  icon: Droplets },
  "Thundery Showers": { color: "text-yellow-400",  bg: "bg-yellow-500/20",  border: "border-yellow-500/30",  icon: Zap },
};

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

function PredCard({ pred }) {
  const style = CATEGORY_STYLES[pred.predicted_label] || CATEGORY_STYLES["No Rain"];
  const Icon = style.icon;
  const now = new Date();
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

export function MLLiveForecast() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetch = async () => {
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

  useEffect(() => {
    fetch();
    const id = setInterval(fetch, 10 * 60 * 1000); // refresh every 10 min
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
          onClick={fetch}
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

          {/* Prediction cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {data.predictions.map((pred) => (
              <PredCard key={pred.horizon_h} pred={pred} />
            ))}
          </div>

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
