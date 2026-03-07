import { request } from "./client";

export async function getRainfallData() {
  try {
    return await request("/rainfall");
  } catch (error) {
    // External API failures (502, 429) are expected - don't spam console
    if (
      error.message?.includes("502") ||
      error.message?.includes("Bad Gateway") ||
      error.message?.includes("429") ||
      error.message?.includes("Too Many Requests")
    ) {
      console.info(
        "Rainfall data temporarily unavailable (external API issue)",
      );
      return null;
    }
    // Log other errors normally
    console.error("Rainfall API error:", error.message);
    throw error;
  }
}
