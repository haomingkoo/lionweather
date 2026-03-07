/**
 * Regional Weather API Client
 *
 * Provides functions for fetching regional city weather data from the backend.
 */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Fetch regional city weather data
 *
 * @param {string} searchQuery - Optional search term for filtering cities
 * @returns {Promise<Object>} Regional cities data with metadata
 * @throws {Error} If the request fails
 */
export async function getRegionalCities(searchQuery = "") {
  const params = new URLSearchParams();
  if (searchQuery) {
    params.append("search", searchQuery);
  }

  const url = `${API_BASE_URL}/api/regional/cities${params.toString() ? `?${params}` : ""}`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch regional cities: ${response.statusText}`);
  }

  return response.json();
}
