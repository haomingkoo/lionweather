/**
 * Radar API Client
 *
 * Provides functions for fetching radar frame data from the backend.
 */

const _rawBase = import.meta.env.VITE_API_BASE_URL || "";
// Force https — mixed-content errors when served over HTTPS
const _secureBase = _rawBase.replace(/^http:\/\//, "https://");
const API_BASE_URL = _secureBase.startsWith("http") ? _secureBase : "";

/**
 * Fetch radar frames for animation
 *
 * @param {number} count - Number of frames to fetch (default 6)
 * @returns {Promise<Object>} Radar frames data with metadata
 * @throws {Error} If the request fails
 */
export async function getRadarFrames(count = 20) {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/radar/frames?count=${count}`,
    );

    if (!response.ok) {
      // External API failures (502, 429) are expected - don't spam console
      if (response.status === 502 || response.status === 429) {
        console.info("Radar data temporarily unavailable (external API issue)");
        return null;
      }
      throw new Error(`Failed to fetch radar frames: ${response.statusText}`);
    }

    return response.json();
  } catch (error) {
    // Network errors or external API issues - handle gracefully
    if (
      error.message?.includes("502") ||
      error.message?.includes("Bad Gateway") ||
      error.message?.includes("429") ||
      error.message?.includes("Too Many Requests") ||
      error.message?.includes("fetch")
    ) {
      console.info("Radar data temporarily unavailable");
      return null;
    }
    console.error("Radar API error:", error.message);
    throw error;
  }
}

/**
 * Get the URL for a radar image by timestamp
 *
 * @param {number} timestamp - Unix timestamp of the frame
 * @returns {string} Full URL to the radar image
 */
export function getRadarImageUrl(timestamp) {
  return `${API_BASE_URL}/api/radar/image/${timestamp}`;
}
