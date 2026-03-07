import { useState, useEffect } from "react";
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Brush,
} from "recharts";
import { Activity, RefreshCw, Calendar, Maximize2 } from "lucide-react";
import { get24HourPredictions, getCurrentWeather } from "../api/ml";

const PARAMETERS = [
  { key: "temperature", label: "Temperature", unit: "°C" },
  { key: "rainfall", label: "Rainfall", unit: "mm" },
  { key: "humidity", label: "Humidity", unit: "%" },
  { key: "wind_speed", label: "Wind Speed", unit: "km/h" },
];

const DATE_RANGES = [
  { label: "6 Hours", value: 6 },
  { label: "12 Hours", value: 12 },
  { label: "24 Hours", value: 24 },
];

export function ConfidenceIntervalChart({
  isDark = false,
  country = "Singapore",
  location = null,
}) {
  const [selectedParameter, setSelectedParameter] = useState("temperature");
  const [selectedRange, setSelectedRange] = useState(24);
  const [data, setData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [zoomEnabled, setZoomEnabled] = useState(true);

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const tertiaryTextColor = isDark ? "text-white/60" : "text-slate-600";
  const bgColor = isDark ? "bg-white/10" : "bg-white/20";
  const borderColor = isDark ? "border-white/20" : "border-white/40";

  useEffect(() => {
    fetchPredictionData();
  }, [selectedParameter, country, location]);

  const fetchPredictionData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Fetch predictions and current weather
      const [predictions, currentWeather] = await Promise.all([
        get24HourPredictions(country, location, selectedParameter),
        getCurrentWeather(country, location).catch(() => null),
      ]);

      if (predictions?.forecasts) {
        // Transform data for the chart
        const chartData = predictions.forecasts.map((forecast) => {
          const timestamp = new Date(forecast.timestamp).getTime();
          return {
            timestamp,
            dateStr: forecast.timestamp,
            predicted: forecast.predicted_value,
            confidenceLower: forecast.confidence_lower,
            confidenceUpper: forecast.confidence_upper,
            // For demo purposes, we'll simulate actual values
            // In production, this would come from historical data
            actual: null, // Will be populated with real data when available
          };
        });

        // Add current weather as the first "actual" data point if available
        if (currentWeather?.current) {
          const currentValue = currentWeather.current[selectedParameter];
          if (currentValue !== undefined) {
            chartData.unshift({
              timestamp: new Date().getTime(),
              dateStr: new Date().toISOString(),
              predicted: currentValue,
              confidenceLower: currentValue,
              confidenceUpper: currentValue,
              actual: currentValue,
            });
          }
        }

        setData(chartData);
      }
    } catch (err) {
      // Silently handle errors - don't spam console
      setError(err.message || "Failed to load predictions");
      setData([]); // Clear data on error
    } finally {
      setIsLoading(false);
    }
  };

  const getFilteredData = () => {
    if (!data || data.length === 0) return [];
    return data.slice(0, selectedRange + 1); // +1 to include current value
  };

  const formatDate = (timestamp) => {
    const date = new Date(timestamp);
    if (selectedRange <= 6) {
      return date.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      });
    } else if (selectedRange <= 12) {
      return date.toLocaleTimeString("en-US", {
        hour: "numeric",
        hour12: true,
      });
    } else {
      return date.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        hour12: true,
      });
    }
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null;

    const data = payload[0]?.payload;
    if (!data) return null;

    const parameterInfo = PARAMETERS.find((p) => p.key === selectedParameter);

    return (
      <div
        className={`rounded-xl ${bgColor} backdrop-blur-xl border ${borderColor} p-3 shadow-lg`}
      >
        <p className={`text-sm font-semibold ${textColor} mb-2`}>
          {formatDate(data.timestamp)}
        </p>
        <div className="space-y-1">
          {data.actual !== null && (
            <div className="flex items-center justify-between gap-4 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <span className={secondaryTextColor}>Actual:</span>
              </div>
              <span className={textColor + " font-medium"}>
                {data.actual?.toFixed(2)} {parameterInfo?.unit}
              </span>
            </div>
          )}
          <div className="flex items-center justify-between gap-4 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <span className={secondaryTextColor}>Predicted:</span>
            </div>
            <span className={textColor + " font-medium"}>
              {data.predicted?.toFixed(2)} {parameterInfo?.unit}
            </span>
          </div>
          <div className="flex items-center justify-between gap-4 text-xs">
            <span className={secondaryTextColor}>95% CI:</span>
            <span className={textColor + " font-medium"}>
              [{data.confidenceLower?.toFixed(2)},{" "}
              {data.confidenceUpper?.toFixed(2)}]
            </span>
          </div>
          <div className="flex items-center justify-between gap-4 text-xs">
            <span className={secondaryTextColor}>Uncertainty:</span>
            <span className={textColor + " font-medium"}>
              ±{((data.confidenceUpper - data.confidenceLower) / 2).toFixed(2)}{" "}
              {parameterInfo?.unit}
            </span>
          </div>
        </div>
      </div>
    );
  };

  if (isLoading && data.length === 0) {
    return (
      <div
        className={`rounded-3xl ${bgColor} backdrop-blur-xl border ${borderColor} p-8`}
      >
        <div className={`text-center ${secondaryTextColor}`}>
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2" />
          <p>Loading predictions...</p>
        </div>
      </div>
    );
  }

  const filteredData = getFilteredData();
  const parameterInfo = PARAMETERS.find((p) => p.key === selectedParameter);

  return (
    <div
      className={`rounded-3xl ${bgColor} backdrop-blur-xl border ${borderColor} p-6`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Activity className={`h-6 w-6 ${textColor}`} strokeWidth={1.5} />
          <div>
            <h3 className={`text-xl font-semibold ${textColor}`}>
              Confidence Intervals
            </h3>
            <p className={`text-sm ${tertiaryTextColor}`}>
              Predictions with 95% confidence bands
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoomEnabled(!zoomEnabled)}
            className={`p-2 rounded-full ${bgColor} hover:bg-white/30 transition-all ${zoomEnabled ? "bg-blue-500 text-white" : textColor}`}
            aria-label="Toggle zoom"
            title={zoomEnabled ? "Disable zoom" : "Enable zoom"}
          >
            <Maximize2 className="h-5 w-5" />
          </button>
          <button
            onClick={fetchPredictionData}
            disabled={isLoading}
            className={`p-2 rounded-full ${bgColor} hover:bg-white/30 transition-all ${isLoading ? "opacity-50" : ""}`}
            aria-label="Refresh predictions"
          >
            <RefreshCw
              className={`h-5 w-5 ${textColor} ${isLoading ? "animate-spin" : ""}`}
            />
          </button>
        </div>
      </div>

      {/* Parameter Selector */}
      <div className="mb-4">
        <span
          className={`text-sm font-medium ${secondaryTextColor} mb-2 block`}
        >
          Weather Parameter
        </span>
        <div className="flex gap-2 flex-wrap">
          {PARAMETERS.map((param) => (
            <button
              key={param.key}
              onClick={() => setSelectedParameter(param.key)}
              className={`px-4 py-2 rounded-full text-sm transition-all ${
                selectedParameter === param.key
                  ? "bg-blue-500 text-white"
                  : `${bgColor} hover:bg-white/30 ${textColor}`
              }`}
            >
              {param.label}
            </button>
          ))}
        </div>
      </div>

      {/* Date Range Selector */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <Calendar className={`h-4 w-4 ${tertiaryTextColor}`} />
          <span className={`text-sm font-medium ${secondaryTextColor}`}>
            Time Range
          </span>
        </div>
        <div className="flex gap-2 flex-wrap">
          {DATE_RANGES.map((range) => (
            <button
              key={range.value}
              onClick={() => setSelectedRange(range.value)}
              className={`px-4 py-2 rounded-full text-sm transition-all ${
                selectedRange === range.value
                  ? "bg-blue-500 text-white"
                  : `${bgColor} hover:bg-white/30 ${textColor}`
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      {error ? (
        <div className="text-center py-8">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={fetchPredictionData}
            className={`px-6 py-3 rounded-full ${bgColor} hover:bg-white/30 transition-all`}
          >
            Retry
          </button>
        </div>
      ) : filteredData.length > 0 ? (
        <div style={{ width: "100%", height: 450 }}>
          <ResponsiveContainer width="100%" height={450}>
            <ComposedChart
              data={filteredData}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <defs>
                <linearGradient
                  id="confidenceGradient"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="5%"
                    stopColor="#3b82f6"
                    stopOpacity={isDark ? 0.3 : 0.2}
                  />
                  <stop
                    offset="95%"
                    stopColor="#3b82f6"
                    stopOpacity={isDark ? 0.1 : 0.05}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)"}
              />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatDate}
                stroke={isDark ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)"}
                style={{ fontSize: "12px" }}
              />
              <YAxis
                stroke={isDark ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)"}
                style={{ fontSize: "12px" }}
                label={{
                  value: `${parameterInfo?.label} (${parameterInfo?.unit})`,
                  angle: -90,
                  position: "insideLeft",
                  style: {
                    fill: isDark ? "rgba(255,255,255,0.8)" : "rgba(0,0,0,0.8)",
                  },
                }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{
                  paddingTop: "20px",
                  fontSize: "12px",
                  color: isDark ? "rgba(255,255,255,0.8)" : "rgba(0,0,0,0.8)",
                }}
              />
              {/* Confidence interval as shaded area */}
              <Area
                type="monotone"
                dataKey="confidenceUpper"
                stroke="none"
                fill="url(#confidenceGradient)"
                fillOpacity={1}
                name="95% Confidence Interval"
              />
              <Area
                type="monotone"
                dataKey="confidenceLower"
                stroke="none"
                fill="#ffffff"
                fillOpacity={isDark ? 0.05 : 0.1}
              />
              {/* Predicted values line */}
              <Line
                type="monotone"
                dataKey="predicted"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ r: 3, fill: "#3b82f6" }}
                activeDot={{ r: 5 }}
                name="Predicted"
              />
              {/* Actual values line (when available) */}
              <Line
                type="monotone"
                dataKey="actual"
                stroke="#10b981"
                strokeWidth={2}
                dot={{ r: 4, fill: "#10b981" }}
                activeDot={{ r: 6 }}
                name="Actual"
                connectNulls={false}
              />
              {/* Zoom and pan brush */}
              {zoomEnabled && filteredData.length > 10 && (
                <Brush
                  dataKey="timestamp"
                  height={30}
                  stroke={isDark ? "rgba(255,255,255,0.3)" : "rgba(0,0,0,0.3)"}
                  fill={isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)"}
                  tickFormatter={formatDate}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className={`text-center py-8 ${tertiaryTextColor}`}>
          <p>No prediction data available</p>
        </div>
      )}

      {/* Info Footer */}
      <div
        className={`mt-4 p-3 rounded-xl ${bgColor} border ${borderColor} text-xs ${tertiaryTextColor}`}
      >
        <p>
          <strong className={secondaryTextColor}>Note:</strong> The shaded area
          represents the 95% confidence interval. There is a 95% probability
          that the actual value will fall within this range. Wider bands
          indicate higher uncertainty in the prediction.
        </p>
      </div>
    </div>
  );
}
