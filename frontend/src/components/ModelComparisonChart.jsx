import { useState, useEffect } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { BarChart3, RefreshCw, TrendingDown } from "lucide-react";
import { getAccuracyMetrics } from "../api/ml";

const METRICS = [
  { key: "mae", label: "MAE", description: "Mean Absolute Error" },
  { key: "rmse", label: "RMSE", description: "Root Mean Square Error" },
  { key: "mape", label: "MAPE", description: "Mean Absolute Percentage Error" },
];

const MODEL_COLORS = {
  arima: "#3b82f6", // blue
  sarima: "#10b981", // green
  prophet: "#f59e0b", // amber
  lstm: "#8b5cf6", // purple
};

export function ModelComparisonChart({
  isDark = false,
  parameter = "temperature",
}) {
  const [selectedMetric, setSelectedMetric] = useState("mae");
  const [sortOrder, setSortOrder] = useState("asc"); // asc = best to worst
  const [data, setData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [recommendedModel, setRecommendedModel] = useState(null);

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const tertiaryTextColor = isDark ? "text-white/60" : "text-slate-600";
  const bgColor = isDark ? "bg-white/10" : "bg-white/20";
  const borderColor = isDark ? "border-white/20" : "border-white/40";

  useEffect(() => {
    fetchComparisonData();
  }, [parameter]);

  const fetchComparisonData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const metricsData = await getAccuracyMetrics(parameter);

      if (metricsData?.rankings) {
        // Transform data for the chart
        const chartData = metricsData.rankings.map((model) => ({
          name: model.model_name?.toUpperCase() || "UNKNOWN",
          modelKey: model.model_name?.toLowerCase(),
          mae: model.mae || 0,
          rmse: model.rmse || 0,
          mape: model.mape || 0,
          isRecommended: model.is_recommended || false,
        }));

        setData(chartData);

        // Find recommended model
        const recommended = chartData.find((m) => m.isRecommended);
        setRecommendedModel(recommended?.name || null);
      }
    } catch (err) {
      // Silently handle errors - don't spam console
      setError(err.message || "Failed to load model comparison");
      setData([]); // Clear data on error
    } finally {
      setIsLoading(false);
    }
  };

  const getSortedData = () => {
    if (!data || data.length === 0) return [];

    const sorted = [...data].sort((a, b) => {
      const aValue = a[selectedMetric] || 0;
      const bValue = b[selectedMetric] || 0;

      // For error metrics, lower is better
      return sortOrder === "asc" ? aValue - bValue : bValue - aValue;
    });

    return sorted;
  };

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || payload.length === 0) return null;

    const data = payload[0].payload;

    return (
      <div
        className={`rounded-xl ${bgColor} backdrop-blur-xl border ${borderColor} p-3 shadow-lg`}
      >
        <p className={`text-sm font-semibold ${textColor} mb-2`}>
          {data.name}
          {data.isRecommended && (
            <span className="ml-2 text-xs bg-green-500 text-white px-2 py-0.5 rounded-full">
              Recommended
            </span>
          )}
        </p>
        <div className="space-y-1">
          <div className="flex items-center justify-between gap-4 text-xs">
            <span className={secondaryTextColor}>MAE:</span>
            <span className={textColor + " font-medium"}>
              {data.mae?.toFixed(3)}
            </span>
          </div>
          <div className="flex items-center justify-between gap-4 text-xs">
            <span className={secondaryTextColor}>RMSE:</span>
            <span className={textColor + " font-medium"}>
              {data.rmse?.toFixed(3)}
            </span>
          </div>
          <div className="flex items-center justify-between gap-4 text-xs">
            <span className={secondaryTextColor}>MAPE:</span>
            <span className={textColor + " font-medium"}>
              {data.mape?.toFixed(2)}%
            </span>
          </div>
        </div>
      </div>
    );
  };

  const CustomBar = (props) => {
    const { fill, x, y, width, height, payload } = props;
    const isRecommended = payload?.isRecommended;

    return (
      <g>
        <rect
          x={x}
          y={y}
          width={width}
          height={height}
          fill={fill}
          opacity={isRecommended ? 1 : 0.7}
        />
        {isRecommended && (
          <rect
            x={x}
            y={y}
            width={width}
            height={height}
            fill="none"
            stroke="#10b981"
            strokeWidth={3}
            rx={4}
          />
        )}
      </g>
    );
  };

  if (isLoading && data.length === 0) {
    return (
      <div
        className={`rounded-3xl ${bgColor} backdrop-blur-xl border ${borderColor} p-8`}
      >
        <div className={`text-center ${secondaryTextColor}`}>
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2" />
          <p>Loading model comparison...</p>
        </div>
      </div>
    );
  }

  const sortedData = getSortedData();

  return (
    <div
      className={`rounded-3xl ${bgColor} backdrop-blur-xl border ${borderColor} p-6`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BarChart3 className={`h-6 w-6 ${textColor}`} strokeWidth={1.5} />
          <div>
            <h3 className={`text-xl font-semibold ${textColor}`}>
              Model Comparison
            </h3>
            <p className={`text-sm ${tertiaryTextColor}`}>
              Side-by-side performance metrics
            </p>
          </div>
        </div>
        <button
          onClick={fetchComparisonData}
          disabled={isLoading}
          className={`p-2 rounded-full ${bgColor} hover:bg-white/30 transition-all ${isLoading ? "opacity-50" : ""}`}
          aria-label="Refresh comparison"
        >
          <RefreshCw
            className={`h-5 w-5 ${textColor} ${isLoading ? "animate-spin" : ""}`}
          />
        </button>
      </div>

      {/* Metric Selector */}
      <div className="mb-4">
        <span
          className={`text-sm font-medium ${secondaryTextColor} mb-2 block`}
        >
          Metric Type
        </span>
        <div className="flex gap-2 flex-wrap">
          {METRICS.map((metric) => (
            <button
              key={metric.key}
              onClick={() => setSelectedMetric(metric.key)}
              className={`px-4 py-2 rounded-full text-sm transition-all ${
                selectedMetric === metric.key
                  ? "bg-blue-500 text-white"
                  : `${bgColor} hover:bg-white/30 ${textColor}`
              }`}
              title={metric.description}
            >
              {metric.label}
            </button>
          ))}
        </div>
      </div>

      {/* Sort Order Toggle */}
      <div className="mb-6">
        <span
          className={`text-sm font-medium ${secondaryTextColor} mb-2 block`}
        >
          Sort Order
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => setSortOrder("asc")}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm transition-all ${
              sortOrder === "asc"
                ? "bg-blue-500 text-white"
                : `${bgColor} hover:bg-white/30 ${textColor}`
            }`}
          >
            <TrendingDown className="h-4 w-4" />
            Best to Worst
          </button>
          <button
            onClick={() => setSortOrder("desc")}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm transition-all ${
              sortOrder === "desc"
                ? "bg-blue-500 text-white"
                : `${bgColor} hover:bg-white/30 ${textColor}`
            }`}
          >
            <TrendingDown className="h-4 w-4 rotate-180" />
            Worst to Best
          </button>
        </div>
      </div>

      {/* Recommended Model Badge */}
      {recommendedModel && (
        <div className={`mb-4 p-3 rounded-xl ${bgColor} border ${borderColor}`}>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className={`text-sm ${secondaryTextColor}`}>
              Recommended Model:{" "}
              <span className={`font-semibold ${textColor}`}>
                {recommendedModel}
              </span>
            </span>
          </div>
        </div>
      )}

      {/* Chart */}
      {error ? (
        <div className="text-center py-8">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={fetchComparisonData}
            className={`px-6 py-3 rounded-full ${bgColor} hover:bg-white/30 transition-all`}
          >
            Retry
          </button>
        </div>
      ) : sortedData.length > 0 ? (
        <div style={{ width: "100%", height: 400 }}>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart
              data={sortedData}
              margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke={isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)"}
              />
              <XAxis
                dataKey="name"
                stroke={isDark ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)"}
                style={{ fontSize: "12px" }}
              />
              <YAxis
                stroke={isDark ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)"}
                style={{ fontSize: "12px" }}
                label={{
                  value: METRICS.find((m) => m.key === selectedMetric)?.label,
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
              <Bar
                dataKey={selectedMetric}
                fill="#3b82f6"
                radius={[8, 8, 0, 0]}
                shape={<CustomBar />}
              >
                {sortedData.map((entry, index) => (
                  <Bar
                    key={`bar-${index}`}
                    fill={MODEL_COLORS[entry.modelKey] || "#3b82f6"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className={`text-center py-8 ${tertiaryTextColor}`}>
          <p>No comparison data available</p>
        </div>
      )}
    </div>
  );
}
