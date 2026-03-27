import { useState, useEffect } from "react";
import { API_BASE } from "../api/base.js";
import {
  Brain,
  TrendingUp,
  Award,
  Activity,
  RefreshCw,
  Calendar,
} from "lucide-react";
import {
  get24HourPredictions,
  get7DayPredictions,
  getAccuracyMetrics,
  getModelComparison,
} from "../api/ml";
import { MetricsTrendChart } from "./MetricsTrendChart";
import { ModelComparisonChart } from "./ModelComparisonChart";
import { ConfidenceIntervalChart } from "./ConfidenceIntervalChart";
import { ErrorBoundary } from "./ErrorBoundary";

export function MLDashboard({ isDark = false }) {
  const [predictions24h, setPredictions24h] = useState(null);
  const [predictions7d, setPredictions7d] = useState(null);
  const [accuracy, setAccuracy] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [dataHealth, setDataHealth] = useState(null);
  const [forecastComparison, setForecastComparison] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [timeframe, setTimeframe] = useState("24h");

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const tertiaryTextColor = isDark ? "text-white/60" : "text-slate-600";

  useEffect(() => {
    fetchMLData();
  }, [timeframe]);

  const fetchMLData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const [pred24h, pred7d, acc, comp, health, forecastComp] =
        await Promise.all([
          get24HourPredictions("Singapore").catch((err) => {
            console.error("24h predictions error:", err);
            return null;
          }),
          get7DayPredictions("Singapore").catch((err) => {
            console.error("7d predictions error:", err);
            return null;
          }),
          getAccuracyMetrics("temperature").catch((err) => {
            console.error("Accuracy metrics error:", err);
            return null;
          }),
          getModelComparison("temperature", 30).catch((err) => {
            console.error("Model comparison error:", err);
            return null;
          }),
          fetch(`${API_BASE}/data-health/status`)
            .then((res) => res.json())
            .catch((err) => {
              console.error("Data health error:", err);
              return null;
            }),
          fetch(`${API_BASE}/forecasts/compare?country=singapore&days_back=7`)
            .then((res) => res.json())
            .catch((err) => {
              console.error("Forecast comparison error:", err);
              return null;
            }),
        ]);

      setPredictions24h(pred24h);
      setPredictions7d(pred7d);
      setAccuracy(acc);
      setComparison(comp);
      setDataHealth(health);
      setForecastComparison(forecastComp);
    } catch (err) {
      console.error("Failed to fetch ML data:", err);
      setError(err.message || "Failed to load ML forecasts");
    } finally {
      setIsLoading(false);
    }
  };

  const currentPredictions =
    timeframe === "24h" ? predictions24h : predictions7d;

  if (isLoading && !currentPredictions) {
    return (
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-8">
        <div className={`text-center ${secondaryTextColor}`}>
          <Activity className="h-12 w-12 animate-spin mx-auto mb-4" />
          <p className="text-lg">Loading ML predictions...</p>
        </div>
      </div>
    );
  }

  // Show friendly message if no data available
  const hasNoData =
    !predictions24h && !predictions7d && !accuracy && !comparison;

  if (hasNoData && !isLoading) {
    return (
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-8">
        <div className="text-center">
          <Brain className={`h-16 w-16 mx-auto mb-4 ${tertiaryTextColor}`} />
          <h3 className={`text-xl font-semibold ${textColor} mb-2`}>
            ML Forecasting Not Ready
          </h3>
          <p className={`${secondaryTextColor} mb-4`}>
            The ML forecasting system needs to collect weather data and train
            models before predictions are available.
          </p>
          <div
            className={`text-sm ${tertiaryTextColor} space-y-2 max-w-md mx-auto text-left`}
          >
            <p>• Weather data collection runs hourly</p>
            <p>• Model training runs weekly (or can be triggered manually)</p>
            <p>
              • First predictions will be available after initial training
              completes
            </p>
          </div>
          <button
            onClick={fetchMLData}
            className={`mt-6 px-6 py-3 rounded-full bg-white/30 hover:bg-white/40 transition-all ${textColor}`}
          >
            Check Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 xl:space-y-3 max-w-4xl">
      {/* Header */}
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6 xl:p-4 2xl:p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Brain className={`h-7 w-7 ${textColor}`} strokeWidth={1.5} />
            <div>
              <h2 className={`text-2xl xl:text-xl font-semibold ${textColor}`}>
                ML Forecasting
              </h2>
              <p className={`text-sm ${tertiaryTextColor}`}>
                AI-powered weather predictions
              </p>
            </div>
          </div>
          <button
            onClick={fetchMLData}
            disabled={isLoading}
            className={`p-3 rounded-full bg-white/30 hover:bg-white/40 transition-all ${isLoading ? "opacity-50" : ""}`}
            aria-label="Refresh predictions"
          >
            <RefreshCw
              className={`h-5 w-5 ${textColor} ${isLoading ? "animate-spin" : ""}`}
            />
          </button>
        </div>

        {/* Timeframe Toggle */}
        <div className="flex gap-2">
          <button
            onClick={() => setTimeframe("24h")}
            className={`flex-1 px-4 py-2 rounded-full transition-all ${
              timeframe === "24h"
                ? "bg-blue-500 text-white"
                : "bg-white/20 hover:bg-white/30 " + textColor
            }`}
          >
            24 Hours
          </button>
          <button
            onClick={() => setTimeframe("7d")}
            className={`flex-1 px-4 py-2 rounded-full transition-all ${
              timeframe === "7d"
                ? "bg-blue-500 text-white"
                : "bg-white/20 hover:bg-white/30 " + textColor
            }`}
          >
            7 Days
          </button>
        </div>
      </div>

      {/* Data Collection Status */}
      {dataHealth && (
        <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6 xl:p-4 2xl:p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className={`h-5 w-5 ${tertiaryTextColor}`} />
            <h3 className={`text-lg font-semibold ${textColor}`}>
              Data Collection Status
            </h3>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-2xl bg-white/20 backdrop-blur-md p-3 text-center">
              <div
                className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
              >
                Singapore
              </div>
              <div className={`text-2xl font-bold ${textColor}`}>
                {dataHealth.by_country?.singapore?.toLocaleString() || 0}
              </div>
              <div className={`text-xs ${tertiaryTextColor}`}>records</div>
            </div>
            <div className="rounded-2xl bg-white/20 backdrop-blur-md p-3 text-center">
              <div
                className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
              >
                Malaysia
              </div>
              <div className={`text-2xl font-bold ${textColor}`}>
                {dataHealth.by_country?.malaysia?.toLocaleString() || 0}
              </div>
              <div className={`text-xs ${tertiaryTextColor}`}>records</div>
            </div>
            <div className="rounded-2xl bg-white/20 backdrop-blur-md p-3 text-center">
              <div
                className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
              >
                Indonesia
              </div>
              <div className={`text-2xl font-bold ${textColor}`}>
                {dataHealth.by_country?.indonesia?.toLocaleString() || 0}
              </div>
              <div className={`text-xs ${tertiaryTextColor}`}>records</div>
            </div>
          </div>
          <div className={`mt-3 text-xs ${tertiaryTextColor} text-center`}>
            Total: {dataHealth.total_records?.toLocaleString() || 0} records •
            Last updated:{" "}
            {dataHealth.latest_timestamp
              ? new Date(dataHealth.latest_timestamp).toLocaleString()
              : "N/A"}
          </div>
        </div>
      )}

      {/* Model Performance */}
      {accuracy?.rankings && accuracy.rankings.length > 0 && (
        <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6 xl:p-4 2xl:p-5">
          <div className="flex items-center gap-2 mb-4">
            <Award className={`h-5 w-5 ${tertiaryTextColor}`} />
            <h3 className={`text-lg font-semibold ${textColor}`}>
              Model Performance
            </h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3">
            {accuracy.rankings.slice(0, 4).map((model, i) => (
              <div
                key={i}
                className="rounded-2xl bg-white/20 backdrop-blur-md p-3 text-center"
              >
                <div
                  className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
                >
                  {model.model_name}
                </div>
                <div className={`text-lg md:text-xl font-bold ${textColor}`}>
                  {model.mae?.toFixed(2) || "N/A"}
                </div>
                <div className={`text-xs ${tertiaryTextColor}`}>MAE</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Forecast Comparison - ML vs Official */}
      {forecastComparison && forecastComparison.official_forecast_count > 0 && (
        <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6 xl:p-4 2xl:p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className={`h-5 w-5 ${tertiaryTextColor}`} />
            <h3 className={`text-lg font-semibold ${textColor}`}>
              ML vs Official Forecasts
            </h3>
          </div>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-2xl bg-white/20 backdrop-blur-md p-3">
                <div
                  className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
                >
                  Official Forecasts
                </div>
                <div className={`text-2xl font-bold ${textColor}`}>
                  {forecastComparison.official_forecast_count}
                </div>
                <div className={`text-xs ${tertiaryTextColor}`}>
                  Last {forecastComparison.days_analyzed} days
                </div>
              </div>
              <div className="rounded-2xl bg-white/20 backdrop-blur-md p-3">
                <div
                  className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
                >
                  ML Predictions
                </div>
                <div className={`text-2xl font-bold ${textColor}`}>
                  {forecastComparison.ml_prediction_count || "N/A"}
                </div>
                <div className={`text-xs ${tertiaryTextColor}`}>
                  {forecastComparison.ml_prediction_count > 0
                    ? "Available"
                    : "Coming soon"}
                </div>
              </div>
            </div>

            {forecastComparison.comparison_metrics && (
              <div className="rounded-2xl bg-white/20 backdrop-blur-md p-3">
                <div className={`text-sm font-semibold ${textColor} mb-2`}>
                  Comparison Metrics
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className={`text-xs ${tertiaryTextColor}`}>
                      Temperature
                    </div>
                    <div className={`text-sm font-semibold ${textColor}`}>
                      {forecastComparison.comparison_metrics.temperature?.mae?.toFixed(
                        2,
                      ) || "N/A"}
                    </div>
                    <div className={`text-xs ${tertiaryTextColor}`}>MAE</div>
                  </div>
                  <div>
                    <div className={`text-xs ${tertiaryTextColor}`}>
                      Humidity
                    </div>
                    <div className={`text-sm font-semibold ${textColor}`}>
                      {forecastComparison.comparison_metrics.humidity?.mae?.toFixed(
                        2,
                      ) || "N/A"}
                    </div>
                    <div className={`text-xs ${tertiaryTextColor}`}>MAE</div>
                  </div>
                  <div>
                    <div className={`text-xs ${tertiaryTextColor}`}>
                      Wind Speed
                    </div>
                    <div className={`text-sm font-semibold ${textColor}`}>
                      {forecastComparison.comparison_metrics.wind_speed?.mae?.toFixed(
                        2,
                      ) || "N/A"}
                    </div>
                    <div className={`text-xs ${tertiaryTextColor}`}>MAE</div>
                  </div>
                </div>
              </div>
            )}

            <div className={`text-xs ${tertiaryTextColor} text-center`}>
              {forecastComparison.note ||
                "Comparing ML predictions against official weather forecasts"}
            </div>
          </div>
        </div>
      )}

      {/* Predictions */}
      {currentPredictions?.forecasts &&
        currentPredictions.forecasts.length > 0 && (
          <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6 xl:p-4 2xl:p-5">
            <div className="flex items-center gap-2 mb-4">
              <Calendar className={`h-5 w-5 ${tertiaryTextColor}`} />
              <h3 className={`text-lg font-semibold ${textColor}`}>
                {timeframe === "24h" ? "Hourly Forecast" : "Daily Forecast"}
              </h3>
            </div>
            <div className="flex gap-2 md:gap-3 overflow-x-auto pb-2">
              {currentPredictions.forecasts
                .slice(0, timeframe === "24h" ? 12 : 7)
                .map((forecast, i) => (
                  <div
                    key={i}
                    className="flex flex-col items-center gap-1 md:gap-2 min-w-[70px] md:min-w-[80px] rounded-2xl bg-white/20 backdrop-blur-md p-3"
                  >
                    <span
                      className={`text-xs ${secondaryTextColor} font-medium`}
                    >
                      {new Date(forecast.timestamp).toLocaleString(
                        "en-US",
                        timeframe === "24h"
                          ? { hour: "numeric", hour12: true }
                          : {
                              weekday: "short",
                              month: "short",
                              day: "numeric",
                            },
                      )}
                    </span>
                    <div
                      className={`text-xl md:text-2xl font-bold ${textColor}`}
                    >
                      {forecast.predicted_value?.toFixed(1)}°
                    </div>
                    <div className={`text-xs ${tertiaryTextColor}`}>
                      ±
                      {(
                        (forecast.confidence_upper -
                          forecast.confidence_lower) /
                        2
                      ).toFixed(1)}
                      °
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

      {/* Model Comparison */}
      {comparison && (
        <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6 xl:p-4 2xl:p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className={`h-5 w-5 ${tertiaryTextColor}`} />
            <h3 className={`text-lg font-semibold ${textColor}`}>
              Model Insights
            </h3>
          </div>
          <div className={`text-sm ${secondaryTextColor} space-y-2`}>
            <p>
              Best performing model:{" "}
              <span className={`font-semibold ${textColor}`}>
                {comparison.best_model || "Training in progress"}
              </span>
            </p>
            <p className={tertiaryTextColor}>
              Models are continuously evaluated and retrained weekly for optimal
              accuracy.
            </p>
          </div>
        </div>
      )}

      {/* Metrics Trend Chart */}
      <ErrorBoundary>
        <MetricsTrendChart isDark={isDark} parameter="temperature" />
      </ErrorBoundary>

      {/* Model Comparison Chart */}
      <ErrorBoundary>
        <ModelComparisonChart isDark={isDark} parameter="temperature" />
      </ErrorBoundary>

      {/* Confidence Interval Chart */}
      <ErrorBoundary>
        <ConfidenceIntervalChart isDark={isDark} country="Singapore" />
      </ErrorBoundary>
    </div>
  );
}
