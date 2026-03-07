import { useState, useEffect } from "react";
import { getRegionalCities } from "../api/regional";
import { useTheme } from "../contexts/ThemeContext";

/**
 * RegionalCityList Component
 *
 * Displays weather information for regional cities in Singapore, Malaysia, and Indonesia.
 * Features:
 * - Card-based layout for city weather data
 * - Real-time search and filtering by city name and country
 * - Debounced search input (300ms) to minimize re-renders
 * - Loading and error states
 * - Data freshness timestamp
 * - Temperature, condition, and city info display
 *
 * @param {Object} props
 * @param {Function} props.onCitySelect - Optional callback when a city is selected
 */
export default function RegionalCityList({ onCitySelect }) {
  const { theme } = useTheme();
  const [cities, setCities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cachedAt, setCachedAt] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");

  useEffect(() => {
    fetchCities();
  }, []);

  // Debounce search query with 300ms delay
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchCities = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getRegionalCities();
      setCities(data.cities || []);
      setCachedAt(data.cachedAt);
    } catch (err) {
      setError(err.message || "Failed to load regional weather data");
      console.error("Error fetching regional cities:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCityClick = (city) => {
    if (onCitySelect) {
      onCitySelect(city);
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    return date.toLocaleString("en-SG", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  };

  // Filter cities based on debounced search query
  const filteredCities = cities.filter((city) => {
    if (!debouncedSearchQuery) return true;
    const query = debouncedSearchQuery.toLowerCase();
    return (
      city.name.toLowerCase().includes(query) ||
      city.country.toLowerCase().includes(query)
    );
  });

  // Sort cities alphabetically by name (default view)
  const sortedCities = [...filteredCities].sort((a, b) =>
    a.name.localeCompare(b.name),
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
          <p className="mt-4 text-gray-600 dark:text-gray-400">
            Loading regional weather data...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 dark:border-red-800 dark:bg-red-900/20">
        <div className="flex items-start">
          <div className="flex-shrink-0">
            <svg
              className="h-5 w-5 text-red-400"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
              Error loading weather data
            </h3>
            <p className="mt-2 text-sm text-red-700 dark:text-red-300">
              {error}
            </p>
            <button
              onClick={fetchCities}
              className="mt-3 rounded-md bg-red-100 px-3 py-2 text-sm font-medium text-red-800 hover:bg-red-200 dark:bg-red-800 dark:text-red-100 dark:hover:bg-red-700"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with data freshness */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Regional Weather
        </h2>
        {cachedAt && (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Updated: {formatTimestamp(cachedAt)}
          </p>
        )}
      </div>

      {/* Search input */}
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
          <svg
            className="h-5 w-5 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search by city name or country..."
          className="block w-full rounded-lg border border-gray-300 bg-white py-2 pl-10 pr-3 text-gray-900 placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:placeholder-gray-400 dark:focus:border-blue-400 dark:focus:ring-blue-400"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            aria-label="Clear search"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>

      {/* City cards grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {sortedCities.map((city) => (
          <div
            key={city.id}
            onClick={() => handleCityClick(city)}
            className={`
              rounded-lg border p-4 transition-all duration-200
              ${onCitySelect ? "cursor-pointer hover:shadow-lg" : ""}
              bg-white dark:bg-gray-800
              border-gray-200 dark:border-gray-700
              hover:border-blue-300 dark:hover:border-blue-600
            `}
          >
            {/* City name and country */}
            <div className="mb-3">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {city.name}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {city.country}
              </p>
            </div>

            {/* Temperature */}
            <div className="mb-2">
              <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                {Math.round(city.temperature)}°C
              </span>
            </div>

            {/* Weather condition */}
            <div className="mb-3">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {city.condition}
              </p>
            </div>

            {/* Additional info */}
            <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
              {city.humidity !== null && city.humidity !== undefined && (
                <span>Humidity: {Math.round(city.humidity)}%</span>
              )}
              {city.windSpeed !== null && city.windSpeed !== undefined && (
                <span>Wind: {Math.round(city.windSpeed)} km/h</span>
              )}
            </div>

            {/* Last updated */}
            {city.lastUpdated && (
              <div className="mt-2 border-t border-gray-100 pt-2 dark:border-gray-700">
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  {formatTimestamp(city.lastUpdated)}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Empty state for filtered results */}
      {sortedCities.length === 0 && cities.length > 0 && !loading && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center dark:border-gray-700 dark:bg-gray-800">
          <p className="text-gray-600 dark:text-gray-400">
            No cities match your search
          </p>
        </div>
      )}

      {/* Empty state for no data */}
      {cities.length === 0 && !loading && !error && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center dark:border-gray-700 dark:bg-gray-800">
          <p className="text-gray-600 dark:text-gray-400">
            No regional weather data available
          </p>
        </div>
      )}
    </div>
  );
}
