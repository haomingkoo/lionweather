import { Shield, Calendar, TrendingUp, AlertCircle } from "lucide-react";

/**
 * ML Methodology Tab Component
 *
 * Displays data leakage prevention techniques, train/test split dates,
 * and temporal validation approach used in the ML forecasting system.
 *
 * **Validates: Requirements 2.7**
 */
export function MLMethodologyTab({ isDark = false }) {
  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const tertiaryTextColor = isDark ? "text-white/60" : "text-slate-600";

  return (
    <div className="space-y-4">
      {/* Data Leakage Prevention */}
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield className={`h-5 w-5 ${tertiaryTextColor}`} />
          <h3 className={`text-lg font-semibold ${textColor}`}>
            Data Leakage Prevention
          </h3>
        </div>
        <div className={`space-y-3 ${secondaryTextColor}`}>
          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              Temporal Causality
            </h4>
            <p className={`text-sm ${tertiaryTextColor}`}>
              All predictions at time <span className="font-mono">t</span> use
              only data from times <span className="font-mono">&lt; t</span>,
              never from <span className="font-mono">t</span> or future times.
              This ensures our models learn patterns that can be applied to
              real-world forecasting.
            </p>
          </div>

          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              Shifted Rolling Features
            </h4>
            <p className={`text-sm ${tertiaryTextColor} mb-2`}>
              Rolling statistics (7-day mean, 30-day mean) are shifted by 1
              period using <span className="font-mono">.shift(1)</span> to
              prevent future data leakage:
            </p>
            <div className="bg-slate-900/50 rounded-lg p-3 font-mono text-xs text-green-400">
              <div>
                # CORRECT: Rolling mean at time t uses data from times &lt; t
              </div>
              <div>
                df['temp_rolling_mean_7'] =
                df['temperature'].rolling(7).mean().shift(1)
              </div>
            </div>
          </div>

          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              Lag Features Only
            </h4>
            <p className={`text-sm ${tertiaryTextColor}`}>
              All features are lagged (e.g., temperature_lag_1,
              temperature_lag_7) to ensure predictions use only historical data.
              No "future" features are included in the training data.
            </p>
          </div>
        </div>
      </div>

      {/* Train/Test Split */}
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6">
        <div className="flex items-center gap-2 mb-4">
          <Calendar className={`h-5 w-5 ${tertiaryTextColor}`} />
          <h3 className={`text-lg font-semibold ${textColor}`}>
            Train/Test Split Strategy
          </h3>
        </div>
        <div className={`space-y-3 ${secondaryTextColor}`}>
          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              Temporal Split (80/20)
            </h4>
            <p className={`text-sm ${tertiaryTextColor} mb-3`}>
              Data is split chronologically to maintain temporal order:
            </p>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                <span className={`text-sm ${textColor}`}>
                  Training Set: First 80% of data (older records)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span className={`text-sm ${textColor}`}>
                  Test Set: Last 20% of data (recent records)
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              Timeline Visualization
            </h4>
            <div className="relative h-12 bg-gradient-to-r from-blue-500/30 via-blue-500/30 to-green-500/30 rounded-lg overflow-hidden">
              <div className="absolute inset-0 flex">
                <div className="w-[80%] border-r-2 border-white/50 flex items-center justify-center">
                  <span className="text-xs font-semibold text-white">
                    Training (80%)
                  </span>
                </div>
                <div className="w-[20%] flex items-center justify-center">
                  <span className="text-xs font-semibold text-white">
                    Test (20%)
                  </span>
                </div>
              </div>
            </div>
            <div className="flex justify-between mt-2">
              <span className={`text-xs ${tertiaryTextColor}`}>
                Oldest Data
              </span>
              <span className={`text-xs ${tertiaryTextColor}`}>
                Most Recent Data
              </span>
            </div>
          </div>

          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              No Random Shuffling
            </h4>
            <p className={`text-sm ${tertiaryTextColor}`}>
              Unlike traditional ML, we never shuffle time-series data. The
              temporal order is preserved to ensure realistic evaluation of
              forecasting performance.
            </p>
          </div>
        </div>
      </div>

      {/* Temporal Validation */}
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className={`h-5 w-5 ${tertiaryTextColor}`} />
          <h3 className={`text-lg font-semibold ${textColor}`}>
            Temporal Validation Approach
          </h3>
        </div>
        <div className={`space-y-3 ${secondaryTextColor}`}>
          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              Walk-Forward Validation
            </h4>
            <p className={`text-sm ${tertiaryTextColor} mb-3`}>
              Models are evaluated using walk-forward validation to simulate
              real-world forecasting:
            </p>
            <ol
              className={`text-sm ${tertiaryTextColor} space-y-2 list-decimal list-inside`}
            >
              <li>Train model on historical data up to time t</li>
              <li>Predict weather for time t+1, t+2, ..., t+24</li>
              <li>Compare predictions to actual observed weather</li>
              <li>Move forward in time and repeat</li>
            </ol>
          </div>

          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              Continuous Retraining
            </h4>
            <p className={`text-sm ${tertiaryTextColor}`}>
              Models are retrained weekly with the latest data to adapt to
              changing weather patterns and maintain accuracy. Each retraining
              cycle uses the most recent 80% of data for training.
            </p>
          </div>

          <div className="rounded-2xl bg-white/20 backdrop-blur-md p-4">
            <h4 className={`font-semibold ${textColor} mb-2`}>
              Multiple Model Evaluation
            </h4>
            <p className={`text-sm ${tertiaryTextColor}`}>
              We train and evaluate multiple models (ARIMA, SARIMA, Prophet) on
              the same test set and select the best performer based on MAE (Mean
              Absolute Error). This ensemble approach ensures robust
              predictions.
            </p>
          </div>
        </div>
      </div>

      {/* Best Practices Summary */}
      <div className="rounded-3xl bg-white/25 backdrop-blur-xl border border-white/40 p-4 md:p-6">
        <div className="flex items-center gap-2 mb-4">
          <AlertCircle className={`h-5 w-5 ${tertiaryTextColor}`} />
          <h3 className={`text-lg font-semibold ${textColor}`}>
            Best Practices Summary
          </h3>
        </div>
        <div className={`space-y-2 ${secondaryTextColor}`}>
          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5"></div>
            <p className={`text-sm ${tertiaryTextColor}`}>
              <span className={`font-semibold ${textColor}`}>
                Temporal Causality:
              </span>{" "}
              All features respect time order
            </p>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5"></div>
            <p className={`text-sm ${tertiaryTextColor}`}>
              <span className={`font-semibold ${textColor}`}>
                Shifted Rolling Features:
              </span>{" "}
              Prevent future data leakage
            </p>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5"></div>
            <p className={`text-sm ${tertiaryTextColor}`}>
              <span className={`font-semibold ${textColor}`}>
                Temporal Split:
              </span>{" "}
              Train on past, test on future
            </p>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5"></div>
            <p className={`text-sm ${tertiaryTextColor}`}>
              <span className={`font-semibold ${textColor}`}>
                Walk-Forward Validation:
              </span>{" "}
              Realistic forecasting simulation
            </p>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5"></div>
            <p className={`text-sm ${tertiaryTextColor}`}>
              <span className={`font-semibold ${textColor}`}>
                Continuous Retraining:
              </span>{" "}
              Adapt to changing patterns
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
