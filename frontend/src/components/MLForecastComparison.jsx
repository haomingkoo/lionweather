import { useState, useEffect } from "react";
import { Brain, Cloud, TrendingUp, Award, Activity } from "lucide-react";
import { getModelComparison } from "../api/ml";

export function MLForecastComparison({ isDark = false }) {
  const [mlForecast, setMlForecast] = useState(null);
  const [benchmark, setBenchmark] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showML, setShowML] = useState(false);

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const tertiaryTextColor = isDark ? "text-white/60" : "text-slate-600";

  useEffect(() => {
    const fetchMLData = async () => {
      try {
        setIsLoading(true);
        const [mlRes, benchmarkData] = await Promise.all([
          fetch("/api/ml/predict/24").then((r) => r.ok ? r.json() : null).catch(() => null),
          getModelComparison(),
        ]);
        const mlData = mlRes;
        setMlForecast(mlData);
        setBenchmark(benchmarkData);
      } catch (err) {
        console.error("Failed to fetch ML forecast:", err);
      } finally {
        setIsLoading(false);
      }
    };

    if (showML) {
      fetchMLData();
    }
  }, [showML]);

  const getPerformanceColor = (winRate) => {
    if (winRate > 60) return "text-green-500";
    if (winRate > 50) return "text-blue-500";
    if (winRate > 40) return "text-yellow-500";
    return "text-red-500";
  };

  const getPerformanceIcon = (winRate) => {
    if (winRate > 60) return "🎉";
    if (winRate > 50) return "✅";
    if (winRate > 40) return "📊";
    return "⚠️";
  };

  return (
    <div
      className={`rounded-3xl backdrop-blur-xl p-6 ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Brain className={`h-6 w-6 ${textColor}`} strokeWidth={1.5} />
          <h3 className={`text-lg font-semibold ${textColor}`}>
            ML-Powered Forecast
          </h3>
        </div>
        <button
          onClick={() => setShowML(!showML)}
          className={`px-4 py-2 rounded-full transition-all focus:outline-none focus:ring-2 focus:ring-white/60 focus:ring-offset-2 focus:ring-offset-transparent ${
            showML
              ? "bg-blue-500 text-white"
              : isDark
                ? "bg-white/15 hover:bg-white/25 " + textColor
                : "bg-white/30 hover:bg-white/40 " + textColor
          }`}
          aria-label={`${showML ? "Hide" : "Show"} ML forecast`}
        >
          {showML ? "Hide" : "Show"} ML
        </button>
      </div>

      {showML && (
        <div className="space-y-4">
          {isLoading ? (
            <div className={`text-center py-8 ${secondaryTextColor}`}>
              <Activity className="h-8 w-8 animate-spin mx-auto mb-2" />
              <p>Loading ML predictions...</p>
            </div>
          ) : (
            <>
              {/* Performance Stats */}
              {benchmark?.performance && (
                <div className="grid grid-cols-3 gap-3">
                  <div
                    className={`rounded-2xl backdrop-blur-md p-4 text-center ${isDark ? "bg-white/10" : "bg-white/20"}`}
                  >
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <Award
                        className={`h-4 w-4 ${getPerformanceColor(benchmark.performance.win_rate || 0)}`}
                      />
                      <span
                        className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
                      >
                        Win Rate
                      </span>
                    </div>
                    <div
                      className={`text-2xl font-bold ${getPerformanceColor(benchmark.performance.win_rate || 0)}`}
                    >
                      {benchmark.performance.win_rate?.toFixed(1) || 0}%
                    </div>
                  </div>

                  <div
                    className={`rounded-2xl backdrop-blur-md p-4 text-center ${isDark ? "bg-white/10" : "bg-white/20"}`}
                  >
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <TrendingUp className={`h-4 w-4 ${tertiaryTextColor}`} />
                      <span
                        className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
                      >
                        Improvement
                      </span>
                    </div>
                    <div className={`text-2xl font-bold ${textColor}`}>
                      {benchmark.performance.improvement?.toFixed(1) || 0}°C
                    </div>
                  </div>

                  <div
                    className={`rounded-2xl backdrop-blur-md p-4 text-center ${isDark ? "bg-white/10" : "bg-white/20"}`}
                  >
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <Activity className={`h-4 w-4 ${tertiaryTextColor}`} />
                      <span
                        className={`text-xs ${tertiaryTextColor} uppercase tracking-wide`}
                      >
                        Predictions
                      </span>
                    </div>
                    <div className={`text-2xl font-bold ${textColor}`}>
                      {benchmark.performance.total_predictions || 0}
                    </div>
                  </div>
                </div>
              )}

              {/* Interpretation */}
              {benchmark?.interpretation && (
                <div
                  className={`rounded-2xl bg-gradient-to-r from-blue-500/20 to-purple-500/20 backdrop-blur-md p-4 ${isDark ? "border border-white/20" : "border border-white/30"}`}
                >
                  <p className={`text-sm ${textColor}`}>
                    {getPerformanceIcon(benchmark.performance?.win_rate || 0)}{" "}
                    {benchmark.interpretation}
                  </p>
                </div>
              )}

              {/* ML Predictions Preview */}
              {mlForecast?.predictions && (
                <div
                  className={`rounded-2xl backdrop-blur-md p-4 ${isDark ? "bg-white/10" : "bg-white/20"}`}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <Cloud className={`h-5 w-5 ${tertiaryTextColor}`} />
                    <span
                      className={`text-sm font-semibold ${tertiaryTextColor} uppercase tracking-wide`}
                    >
                      Next 6 Hours (ML)
                    </span>
                  </div>
                  <div className="flex gap-4 overflow-x-auto">
                    {mlForecast.predictions.slice(0, 6).map((pred, i) => (
                      <div
                        key={i}
                        className="flex flex-col items-center gap-2 min-w-[70px]"
                      >
                        <span className={`text-xs ${secondaryTextColor}`}>
                          {new Date(pred.timestamp).toLocaleTimeString(
                            "en-SG",
                            {
                              hour: "numeric",
                              hour12: true,
                              timeZone: "Asia/Singapore",
                            },
                          )}
                        </span>
                        <div className={`text-xl font-semibold ${textColor}`}>
                          {pred.temperature?.toFixed(0)}°
                        </div>
                        <div className="flex flex-col items-center gap-0.5">
                          <span className={`text-xs ${tertiaryTextColor}`}>
                            {(pred.confidence * 100).toFixed(0)}% conf.
                          </span>
                          {pred.rain_probability > 0 && (
                            <span className="text-xs text-sky-400">
                              {pred.rain_probability.toFixed(0)}% rain
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Model Info */}
              {mlForecast?.metadata && (
                <div
                  className={`rounded-2xl backdrop-blur-md p-3 ${isDark ? "bg-white/5" : "bg-white/10"}`}
                >
                  <div className={`text-xs ${tertiaryTextColor} space-y-1`}>
                    <div className="flex justify-between">
                      <span>Model:</span>
                      <span className={secondaryTextColor}>
                        {mlForecast.metadata.model_type}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Features:</span>
                      <span className={secondaryTextColor}>
                        {mlForecast.metadata.features_used?.length || 0} inputs
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Generated:</span>
                      <span className={secondaryTextColor}>
                        {new Date(
                          mlForecast.generated_at || mlForecast.based_on_timestamp,
                        ).toLocaleTimeString("en-SG", { timeZone: "Asia/Singapore", hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
