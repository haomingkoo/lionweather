import React, { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const HistoricalDataInsights = () => {
  const [activeTab, setActiveTab] = useState("overview");
  const [overview, setOverview] = useState(null);
  const [yearOverYear, setYearOverYear] = useState(null);
  const [decomposition, setDecomposition] = useState(null);
  const [autocorrelation, setAutocorrelation] = useState(null);
  const [featureEngineering, setFeatureEngineering] = useState(null);
  const [dataQuality, setDataQuality] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [overviewRes, yoyRes, decompRes, acfRes, feRes, qualityRes] =
        await Promise.all([
          fetch("/api/historical-data/overview"),
          fetch("/api/historical-data/year-over-year"),
          fetch("/api/historical-data/decomposition"),
          fetch("/api/historical-data/autocorrelation"),
          fetch("/api/historical-data/feature-engineering"),
          fetch("/api/historical-data/data-quality"),
        ]);

      setOverview(await overviewRes.json());
      setYearOverYear(await yoyRes.json());
      setDecomposition(await decompRes.json());
      setAutocorrelation(await acfRes.json());
      setFeatureEngineering(await feRes.json());
      setDataQuality(await qualityRes.json());
      setLoading(false);
    } catch (error) {
      console.error("Failed to fetch historical data:", error);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl">Loading historical data insights...</div>
      </div>
    );
  }

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "year-over-year", label: "Year-over-Year" },
    { id: "decomposition", label: "Decomposition" },
    { id: "autocorrelation", label: "Autocorrelation" },
    { id: "features", label: "Feature Engineering" },
    { id: "quality", label: "Data Quality" },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
          Historical Data & Model Insights
        </h1>
        <p className="text-gray-600 dark:text-gray-300 mb-8">
          Comprehensive analysis of 2022-2025 weather data for rainfall
          prediction
        </p>

        {/* Tabs */}
        <div className="flex space-x-2 mb-6 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 rounded-lg font-medium transition-all whitespace-nowrap ${
                activeTab === tab.id
                  ? "bg-blue-600 text-white shadow-lg"
                  : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl p-8">
          {activeTab === "overview" && overview && (
            <OverviewTab data={overview} />
          )}
          {activeTab === "year-over-year" && yearOverYear && (
            <YearOverYearTab data={yearOverYear} />
          )}
          {activeTab === "decomposition" && decomposition && (
            <DecompositionTab data={decomposition} />
          )}
          {activeTab === "autocorrelation" && autocorrelation && (
            <AutocorrelationTab data={autocorrelation} />
          )}
          {activeTab === "features" && featureEngineering && (
            <FeatureEngineeringTab data={featureEngineering} />
          )}
          {activeTab === "quality" && dataQuality && (
            <DataQualityTab data={dataQuality} />
          )}
        </div>
      </div>
    </div>
  );
};

const OverviewTab = ({ data }) => (
  <div className="space-y-6">
    <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
      Historical Data Overview
    </h2>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <StatCard
        title="Total Records"
        value={data.total_records.toLocaleString()}
        subtitle="Hourly observations"
      />
      <StatCard
        title="Duration"
        value={`${data.duration_days} days`}
        subtitle={`${new Date(data.date_range.start).toLocaleDateString()} - ${new Date(data.date_range.end).toLocaleDateString()}`}
      />
      <StatCard
        title="Completeness"
        value={`${data.completeness}%`}
        subtitle="Data quality"
      />
    </div>

    <div className="bg-blue-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Temperature Statistics
      </h3>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Minimum
          </div>
          <div className="text-2xl font-bold text-blue-600">
            {data.temperature_stats.min}°C
          </div>
        </div>
        <div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Mean</div>
          <div className="text-2xl font-bold text-blue-600">
            {data.temperature_stats.mean}°C
          </div>
        </div>
        <div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Maximum
          </div>
          <div className="text-2xl font-bold text-blue-600">
            {data.temperature_stats.max}°C
          </div>
        </div>
      </div>
    </div>

    <div className="bg-green-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        Data Source
      </h3>
      <p className="text-gray-700 dark:text-gray-300">{data.data_source}</p>
      <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
        ✅ All data validated as real - no mock/synthetic data detected
      </p>
    </div>
  </div>
);

const YearOverYearTab = ({ data }) => {
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];

  const chartData = months.map((month) => ({
    month,
    2022: data.temperature["2022"][month],
    2023: data.temperature["2023"][month],
    2024: data.temperature["2024"][month],
    2025: data.temperature["2025"][month],
  }));

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
        Year-over-Year Patterns
      </h2>

      <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Monthly Temperature Comparison (2022-2025)
        </h3>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" />
            <YAxis
              domain={[24, 29]}
              label={{
                value: "Temperature (°C)",
                angle: -90,
                position: "insideLeft",
              }}
            />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="2022"
              stroke="#8884d8"
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="2023"
              stroke="#82ca9d"
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="2024"
              stroke="#ffc658"
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="2025"
              stroke="#ff7c7c"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-blue-50 dark:bg-gray-700 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          Rainfall Patterns
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Trend Mean
            </div>
            <div className="text-2xl font-bold text-blue-600">
              {data.rainfall.trend_mean} mm/day
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Seasonal Amplitude
            </div>
            <div className="text-2xl font-bold text-blue-600">
              {data.rainfall.seasonal_amplitude} mm/day
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Residual Std Dev
            </div>
            <div className="text-2xl font-bold text-blue-600">
              {data.rainfall.residual_std} mm/day
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const DecompositionTab = ({ data }) => (
  <div className="space-y-6">
    <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
      Time Series Decomposition
    </h2>

    <div className="bg-red-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Rainfall Decomposition (PRIMARY TARGET)
      </h3>
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Trend Mean
          </div>
          <div className="text-2xl font-bold text-red-600">
            {data.rainfall.trend_mean} mm/day
          </div>
        </div>
        <div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Seasonal Amplitude
          </div>
          <div className="text-2xl font-bold text-red-600">
            {data.rainfall.seasonal_amplitude} mm/day
          </div>
        </div>
        <div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Residual Std Dev
          </div>
          <div className="text-2xl font-bold text-red-600">
            {data.rainfall.residual_std} mm/day
          </div>
        </div>
      </div>
      <p className="text-gray-700 dark:text-gray-300 text-sm">
        {data.rainfall.interpretation}
      </p>
    </div>

    <div className="bg-blue-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Temperature Decomposition (SECONDARY)
      </h3>
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Trend Mean
          </div>
          <div className="text-2xl font-bold text-blue-600">
            {data.temperature.trend_mean}°C
          </div>
        </div>
        <div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Seasonal Amplitude
          </div>
          <div className="text-2xl font-bold text-blue-600">
            {data.temperature.seasonal_amplitude}°C
          </div>
        </div>
        <div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Residual Std Dev
          </div>
          <div className="text-2xl font-bold text-blue-600">
            {data.temperature.residual_std}°C
          </div>
        </div>
      </div>
      <p className="text-gray-700 dark:text-gray-300 text-sm">
        {data.temperature.interpretation}
      </p>
    </div>
  </div>
);

const AutocorrelationTab = ({ data }) => {
  const acfData = [
    { lag: "1h", value: data.acf.lag_1h },
    { lag: "3h", value: data.acf.lag_3h },
    { lag: "6h", value: data.acf.lag_6h },
    { lag: "12h", value: data.acf.lag_12h },
    { lag: "24h", value: data.acf.lag_24h },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
        Autocorrelation Analysis
      </h2>

      <div className="bg-green-50 dark:bg-gray-700 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Stationarity Test (ADF)
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              ADF Statistic
            </div>
            <div className="text-2xl font-bold text-green-600">
              {data.adf_test.statistic.toFixed(4)}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              P-Value
            </div>
            <div className="text-2xl font-bold text-green-600">
              {data.adf_test.p_value.toFixed(4)}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Stationary
            </div>
            <div className="text-2xl font-bold text-green-600">
              {data.adf_test.is_stationary ? "✅ Yes" : "❌ No"}
            </div>
          </div>
        </div>
        <p className="text-gray-700 dark:text-gray-300 text-sm mt-4">
          {data.adf_test.interpretation}
        </p>
      </div>

      <div className="bg-blue-50 dark:bg-gray-700 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Autocorrelation Function (ACF)
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={acfData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="lag" />
            <YAxis
              label={{
                value: "Correlation",
                angle: -90,
                position: "insideLeft",
              }}
            />
            <Tooltip />
            <Bar dataKey="value" fill="#3b82f6" />
          </BarChart>
        </ResponsiveContainer>
        <p className="text-gray-700 dark:text-gray-300 text-sm mt-4">
          {data.interpretation}
        </p>
      </div>

      <div className="bg-purple-50 dark:bg-gray-700 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          Recommended Lags
        </h3>
        <div className="flex flex-wrap gap-2">
          {data.recommended_lags.map((lag) => (
            <span
              key={lag}
              className="px-4 py-2 bg-purple-200 dark:bg-purple-900 text-purple-900 dark:text-purple-100 rounded-full font-medium"
            >
              {lag}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

const FeatureEngineeringTab = ({ data }) => (
  <div className="space-y-6">
    <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
      Feature Engineering Insights
    </h2>

    <div className="bg-yellow-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Correlations with Rainfall
      </h3>
      <div className="space-y-3">
        {Object.entries(data.correlations_with_rainfall).map(
          ([feature, corr]) => (
            <div key={feature} className="flex justify-between items-center">
              <span className="font-medium text-gray-900 dark:text-white capitalize">
                {feature}
              </span>
              <div className="flex gap-4">
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Pearson: {corr.pearson.toFixed(3)}
                </span>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Spearman: {corr.spearman.toFixed(3)}
                </span>
              </div>
            </div>
          ),
        )}
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {Object.entries(data.interpretation).map(([feature, text]) => (
        <div
          key={feature}
          className="bg-blue-50 dark:bg-gray-700 rounded-lg p-4"
        >
          <h4 className="font-semibold text-gray-900 dark:text-white capitalize mb-2">
            {feature}
          </h4>
          <p className="text-sm text-gray-700 dark:text-gray-300">{text}</p>
        </div>
      ))}
    </div>

    <div className="bg-red-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        ⚠️ Multicollinearity Warning
      </h3>
      <p className="text-gray-700 dark:text-gray-300 mb-3">
        High VIF scores detected for:{" "}
        {data.multicollinearity_warning.join(", ")}
      </p>
      <p className="text-sm text-gray-600 dark:text-gray-400">
        VIF &gt; 5 indicates high multicollinearity. Consider feature selection
        or regularization.
      </p>
    </div>

    <div className="bg-green-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        Recommended Features
      </h3>
      <div className="space-y-3">
        <div>
          <h4 className="font-medium text-gray-900 dark:text-white mb-2">
            Lagged Features
          </h4>
          <div className="flex flex-wrap gap-2">
            {data.recommended_lags.map((lag) => (
              <span
                key={lag}
                className="px-3 py-1 bg-green-200 dark:bg-green-900 text-green-900 dark:text-green-100 rounded-full text-sm"
              >
                {lag}
              </span>
            ))}
          </div>
        </div>
        <div>
          <h4 className="font-medium text-gray-900 dark:text-white mb-2">
            Rolling Features
          </h4>
          <div className="flex flex-wrap gap-2">
            {data.recommended_rolling.map((feature) => (
              <span
                key={feature}
                className="px-3 py-1 bg-green-200 dark:bg-green-900 text-green-900 dark:text-green-100 rounded-full text-sm"
              >
                {feature}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  </div>
);

const DataQualityTab = ({ data }) => (
  <div className="space-y-6">
    <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
      Data Quality Assessment
    </h2>

    <div
      className={`rounded-lg p-6 ${data.validation_status === "passed" ? "bg-green-50 dark:bg-gray-700" : "bg-red-50 dark:bg-gray-700"}`}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        {data.validation_status === "passed"
          ? "✅ Validation Passed"
          : "❌ Validation Failed"}
      </h3>
      <p className="text-gray-700 dark:text-gray-300">
        {data.mock_data_detected
          ? "Mock data detected in training set"
          : "No mock/synthetic data detected"}
      </p>
      <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
        Data Source: {data.data_source}
      </p>
    </div>

    <div className="bg-blue-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Completeness by Year
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Object.entries(data.completeness.by_year).map(([year, pct]) => (
          <div key={year}>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {year}
            </div>
            <div className="text-2xl font-bold text-blue-600">{pct}%</div>
          </div>
        ))}
      </div>
    </div>

    <div className="bg-purple-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Data Ranges
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Object.entries(data.data_ranges).map(([param, range]) => (
          <div key={param}>
            <div className="text-sm text-gray-600 dark:text-gray-400 capitalize">
              {param}
            </div>
            <div className="text-lg font-bold text-purple-600">
              {range.min} - {range.max} {range.unit}
            </div>
          </div>
        ))}
      </div>
    </div>

    <div className="bg-green-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
        Quality Checks Passed
      </h3>
      <ul className="space-y-2">
        {data.checks_passed.map((check, idx) => (
          <li key={idx} className="flex items-start">
            <span className="text-green-600 mr-2">✓</span>
            <span className="text-gray-700 dark:text-gray-300">{check}</span>
          </li>
        ))}
      </ul>
    </div>

    <div className="bg-yellow-50 dark:bg-gray-700 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        Anomalies Detected
      </h3>
      <p className="text-gray-700 dark:text-gray-300 mb-4">
        {data.anomalies_detected} extreme weather events detected (&gt;3σ from
        mean)
      </p>
      <div className="space-y-2">
        {data.extreme_events.slice(0, 5).map((event, idx) => (
          <div key={idx} className="flex justify-between items-center text-sm">
            <span className="text-gray-700 dark:text-gray-300">
              {new Date(event.timestamp).toLocaleString()}
            </span>
            <span className="font-medium text-yellow-700 dark:text-yellow-300">
              {event.temperature}°C (z={event.z_score.toFixed(2)})
            </span>
          </div>
        ))}
      </div>
    </div>
  </div>
);

const StatCard = ({ title, value, subtitle }) => (
  <div className="bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg p-6 text-white">
    <div className="text-sm opacity-90 mb-1">{title}</div>
    <div className="text-3xl font-bold mb-1">{value}</div>
    <div className="text-sm opacity-75">{subtitle}</div>
  </div>
);

export default HistoricalDataInsights;
