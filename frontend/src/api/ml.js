import { request } from "./client";

// Helper to handle expected 404s gracefully (when ML data doesn't exist yet)
async function requestML(url, options = {}) {
  try {
    return await request(url, options);
  } catch (error) {
    // Silently swallow any expected "not ready" responses — 404, "No historical data",
    // "Not Found", missing model files, etc.
    const msg = error.message || "";
    if (
      msg.includes("404") ||
      msg.includes("Not Found") ||
      msg.includes("No historical data") ||
      msg.includes("No data") ||
      msg.includes("not available") ||
      msg.includes("status 404")
    ) {
      console.info(`ML data not available yet: ${url}`);
      return null;
    }
    console.error(`ML API error for ${url}:`, msg);
    throw error;
  }
}

// New ML endpoints
export async function get24HourPredictions(
  country,
  location = null,
  parameter = "temperature",
) {
  const params = new URLSearchParams({ country, parameter });
  if (location) params.append("location", location);
  return requestML(`/ml/predictions/24h?${params}`);
}

export async function get7DayPredictions(
  country,
  location = null,
  parameter = "temperature",
) {
  const params = new URLSearchParams({ country, parameter });
  if (location) params.append("location", location);
  return requestML(`/ml/predictions/7d?${params}`);
}

export async function getCurrentWeather(country, location = null) {
  const params = new URLSearchParams({ country });
  if (location) params.append("location", location);
  return requestML(`/ml/predictions/current?${params}`);
}

export async function getAccuracyMetrics(parameter = "temperature") {
  return requestML(`/ml/metrics/accuracy?parameter=${parameter}`);
}

export async function getModelComparison(
  parameter = "temperature",
  windowDays = 30,
) {
  return requestML(
    `/ml/metrics/comparison?parameter=${parameter}&window_days=${windowDays}`,
  );
}

export async function triggerTraining() {
  return request("/ml/training/trigger", { method: "POST" });
}

export async function getTrainingStatus() {
  return requestML("/ml/training/status");
}

export async function listModels() {
  return requestML("/ml/models/list");
}

export async function getFullAnalysis() {
  return requestML("/ml/full-analysis");
}

export async function getHistoricalMetrics(
  parameter = "temperature",
  startDate = null,
  endDate = null,
  modelTypes = null,
) {
  const params = new URLSearchParams({ parameter });
  if (startDate) params.append("start_date", startDate);
  if (endDate) params.append("end_date", endDate);
  if (modelTypes) params.append("model_types", modelTypes);
  return requestML(`/ml/metrics/historical?${params}`);
}
