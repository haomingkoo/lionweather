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
