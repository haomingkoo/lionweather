/**
 * Radar API Client
 *
 * Provides functions for fetching radar frame data from the backend.
 */

import { API_ORIGIN } from "./base.js";

export async function getRadarFrames(count = 20) {
  try {
    const response = await fetch(
      `${API_ORIGIN}/api/radar/frames?count=${count}`,
    );

    if (!response.ok) {
      if (response.status === 502 || response.status === 429) {
        console.info("Radar data temporarily unavailable (external API issue)");
        return null;
      }
      throw new Error(`Failed to fetch radar frames: ${response.statusText}`);
    }

    return response.json();
  } catch (error) {
    if (
      error.message?.includes("502") ||
      error.message?.includes("Bad Gateway") ||
      error.message?.includes("429") ||
      error.message?.includes("fetch")
    ) {
      console.info("Radar data temporarily unavailable");
      return null;
    }
    console.error("Radar API error:", error.message);
    throw error;
  }
}

export function getRadarImageUrl(timestamp) {
  return `${API_ORIGIN}/api/radar/image/${timestamp}`;
}
