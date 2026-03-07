import { useState, useEffect } from "react";
import { Award, TrendingUp, Target, BarChart3, RefreshCw } from "lucide-react";
import { getAccuracyMetrics, getModelComparison } from "../api/ml";

/**
 * ML Performance Metrics Tab Component
 *
 * Displays MAE, RMSE, MAPE for each model, model rankings,
 * and NEA comparison metrics (ML vs NEA accuracy, win rate).
 *
 * **Validates: Requirements 2.8**
 */
export function MLPerformanceMetricsTab({ isDark = false }) {
  const [metrics, setMetrics] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedParameter, setSelectedParameter] = useState("temperature");

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const tertiaryTextColor = isDark ? "text-white/60" : "text-slate-600";

  useEffect(() => {
    fetchMetrics();
  }, [selectedParameter]);

  const fetchMetrics = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const [metricsData, comparisonData] = await Promise.all([
        getAccuracyMetrics(selectedParameter).catch((err) => {
          console.error("Accuracy metrics error:", err);
          return null;
        }),
        getModelComparison(selectedParameter, 30).catch((err) => {
          console.error("Model comparison error:", err);
          return null;
        }),
      ]);

      setMetrics(metricsData);
      setComparison(comparisonData);
    } catch (err) {
      console.error("Failed to fetch metrics:", err);
      setError(err.message || "Failed to load performance metrics");
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading && !metrics) {
    return (
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-8">
        <div className={`text-center ${secondaryTextColor}`}>
          <RefreshCw className="h-12 w-12 animate-spin mx-auto mb-4" />
          <p className="text-lg">Loading performance metrics...</p>
        </div>
      </div>
    );
  }

  const hasNoData = !metrics && !comparison;

  if (hasNoData && !isLoading) {
    return (
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-8">
        <div className="text-center">
          <BarChart3
            className={`h-16 w-16 mx-auto mb-4 ${tertiaryTextColor}`}
          />
          <h3 className={`text-xl font-semibold ${textColor} mb-2`}>
            No Performance Data Available
          </h3>
          <p className={`${secondaryTextColor} mb-4`}>
            Performance metrics will be available after models are trained and
            evaluated on test data.
          </p>
          <button
            onClick={fetchMetrics}
            className={`mt-4 px-6 py-3 rounded-full bg-white/30 hover:bg-white/40 transition-all ${textColor}`}
          >
            Check Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with Parameter Selector */}
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Award className={`h-5 w-5 ${tertiaryTextColor}`} />
            <h3 className={`text-lg font-semibold ${textColor}`}>
              Model Performance Metrics
            </h3>
          </div>
          <button
            onClick={fetchMetrics}
            disabled={isLoading}
            className={`p-2 rounded-full bg-white/30 hover:bg-white/40 transition-all ${isLoading ? "opacity-50" : ""}`}
            aria-label="Refresh metrics"
          >
            <RefreshCw
              className={`h-4 w-4 ${textColor} ${isLoading ? "animate-spin" : ""}`}
            />
          </button>
        </div>

        {/* Parameter Selector */}
        <div className="flex gap-2 flex-wrap">
          {["temperature", "humidity", "rainfall", "wind_speed"].map(
            (param) => (
              <button
                key={param}
                onClick={() => setSelectedParameter(param)}
                className={`px-4 py-2 rounded-full text-sm transition-all ${
                  selectedParameter === param
                    ? "bg-blue-500 text-white"
                    : "bg-white/20 hover:bg-white/30 " + textColor
                }`}
              >
                {param
                  .replace("_", " ")
                  .replace(/\b\w/g, (l) => l.toUpperCase())}
              </button>
            ),
          )}
        </div>
      </div>

      {/* Model Rankings */}
      {metrics?.rankings && metrics.rankings.length > 0 && (
        <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6">
          <div className="flex items-center gap-2 mb-4">
            <Target className={`h-5 w-5 ${tertiaryTextColor}`} />
            <h3 className={`text-lg font-semibold ${textColor}`}>
              Model Rankings
            </h3>
          </div>
          <div className="space-y-3">
            {metrics.rankings.map((model, index) => (
              <div
                key={index}
                className="rounded-2xl bg-white/20 backdrop-blur-md p-4"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                        index === 0
                          ? "bg-yellow-500 text-white"
                          : index === 1
                            ? "bg-gray-400 text-white"
                            : index === 2
                              ? "bg-orange-600 text-white"
                              : "bg-white/30 " + textColor
                      }`}
                    >
                      {index + 1}
                    </div>
                    <div>
                      <h4 className={`font-semibold ${textColor}`}>
                        {model.model_name}
                      </h4>
                      {index === 0 && (
                        <span className="text-xs text-yellow-500 font-semibold">
                          Best Performer
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center">
                    <div
                      className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
                    >
                      MAE
                    </div>
                    <div className={`text-lg font-bold ${textColor}`}>
                      {model.mae?.toFixed(2) || "N/A"}
                    </div>
                    <div className={`text-xs ${tertiaryTextColor}`}>
                      Mean Absolute Error
                    </div>
                  </div>
                  <div className="text-center">
                    <div
                      className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
                    >
                      RMSE
                    </div>
                    <div className={`text-lg font-bold ${textColor}`}>
                      {model.rmse?.toFixed(2) || "N/A"}
                    </div>
                    <div className={`text-xs ${tertiaryTextColor}`}>
                      Root Mean Squared Error
                    </div>
                  </div>
                  <div className="text-center">
                    <div
                      className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
                    >
                      MAPE
                    </div>
                    <div className={`text-lg font-bold ${textColor}`}>
                      {model.mape?.toFixed(1) || "N/A"}%
                    </div>
                    <div className={`text-xs ${tertiaryTextColor}`}>
                      Mean Absolute % Error
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Metrics Explanation */}
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className={`h-5 w-5 ${tertiaryTextColor}`} />
          <h3 className={`text-lg font-semibold ${textColor}`}>
            Understanding the Metrics
          </h3>
        </div>
        <div className={`space-y-3 ${secondaryTextColor}`}>
          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              MAE (Mean Absolute Error)
            </h4>
            <p className={`text-sm ${tertiaryTextColor}`}>
              Average absolute difference between predicted and actual values.
              Lower is better. For temperature, MAE of 2.0 means predictions are
              off by 2°C on average.
            </p>
          </div>

          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              RMSE (Root Mean Squared Error)
            </h4>
            <p className={`text-sm ${tertiaryTextColor}`}>
              Square root of average squared differences. Penalizes large errors
              more heavily than MAE. Lower is better. RMSE is always ≥ MAE.
            </p>
          </div>

          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              MAPE (Mean Absolute Percentage Error)
            </h4>
            <p className={`text-sm ${tertiaryTextColor}`}>
              Average percentage difference between predicted and actual values.
              Lower is better. MAPE of 5% means predictions are off by 5% on
              average.
            </p>
          </div>
        </div>
      </div>

      {/* NEA Comparison (if available) */}
      {comparison?.nea_comparison && (
        <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className={`h-5 w-5 ${tertiaryTextColor}`} />
            <h3 className={`text-lg font-semibold ${textColor}`}>
              ML vs NEA Forecast Comparison
            </h3>
          </div>
          <div className="space-y-3">
            <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center">
                  <div
                    className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
                  >
                    ML Model MAE
                  </div>
                  <div className={`text-2xl font-bold ${textColor}`}>
                    {comparison.nea_comparison.ml_mae?.toFixed(2) || "N/A"}
                  </div>
                </div>
                <div className="text-center">
                  <div
                    className={`text-xs ${tertiaryTextColor} uppercase tracking-wide mb-1`}
                  >
                    NEA Forecast MAE
                  </div>
                  <div className={`text-2xl font-bold ${textColor}`}>
                    {comparison.nea_comparison.nea_mae?.toFixed(2) || "N/A"}
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
              <div className="flex items-center justify-between mb-2">
                <span className={`text-sm ${secondaryTextColor}`}>
                  ML Model Win Rate
                </span>
                <span className={`text-lg font-bold ${textColor}`}>
                  {comparison.nea_comparison.ml_win_rate?.toFixed(1) || "N/A"}%
                </span>
              </div>
              <div className="w-full bg-white/20 rounded-full h-3 overflow-hidden">
                <div
                  className="bg-blue-500 h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${comparison.nea_comparison.ml_win_rate || 0}%`,
                  }}
                ></div>
              </div>
              <p className={`text-xs ${tertiaryTextColor} mt-2`}>
                Percentage of forecasts where ML model was more accurate than
                NEA official forecast
              </p>
            </div>

            <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
              <h4 className={`font-semibold ${textColor} mb-2`}>
                Comparison Insights
              </h4>
              <p className={`text-sm ${tertiaryTextColor}`}>
                {comparison.nea_comparison.ml_win_rate > 50
                  ? "Our ML models are outperforming NEA official forecasts on average. This demonstrates the value of machine learning for weather prediction."
                  : "NEA official forecasts are currently more accurate. Our models continue to learn and improve with more data and retraining."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Confidence Intervals */}
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6">
        <div className="flex items-center gap-2 mb-4">
          <Target className={`h-5 w-5 ${tertiaryTextColor}`} />
          <h3 className={`text-lg font-semibold ${textColor}`}>
            Uncertainty Quantification
          </h3>
        </div>
        <div className={`space-y-3 ${secondaryTextColor}`}>
          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              Confidence Intervals
            </h4>
            <p className={`text-sm ${tertiaryTextColor}`}>
              All predictions include 95% confidence intervals to quantify
              uncertainty. For example, a prediction of 28°C ± 2°C means we're
              95% confident the actual temperature will be between 26°C and
              30°C.
            </p>
          </div>

          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              Prediction Reliability
            </h4>
            <p className={`text-sm ${tertiaryTextColor}`}>
              Narrower confidence intervals indicate more reliable predictions.
              Intervals widen for longer-term forecasts (7-day vs 24-hour) as
              uncertainty increases with time.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
