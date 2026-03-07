import { useState } from "react";
import { useCreateLocation } from "../hooks/useLocations.jsx";
import { MapPin, Plus, Search } from "lucide-react";

// Geocode postal code or place name to coordinates
const geocodeLocation = async (query) => {
  try {
    // Use Nominatim for geocoding (supports postal codes and place names)
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&countrycodes=sg,my,id&limit=5`,
      {
        headers: {
          "User-Agent": "LionWeather/1.0",
        },
      },
    );
    if (!response.ok) {
      throw new Error("Failed to geocode location");
    }
    const data = await response.json();

    if (data.length === 0) {
      throw new Error(
        "Location not found. Try a different postal code or place name.",
      );
    }

    return data.map((result) => ({
      lat: parseFloat(result.lat),
      lon: parseFloat(result.lon),
      display_name: result.display_name,
    }));
  } catch (err) {
    console.error("Geocoding error:", err);
    throw err;
  }
};

export function LocationForm({ isDark = false }) {
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const { create, isPending, error } = useCreateLocation();

  const textColor = isDark ? "text-white" : "text-slate-900";
  const secondaryTextColor = isDark ? "text-white/80" : "text-slate-700";
  const inputBg = isDark
    ? "bg-white/15 border-white/30 text-white placeholder-white/60"
    : "bg-white/40 border-white/50 text-slate-900 placeholder-slate-600";

  const onSubmit = async (event) => {
    event.preventDefault();
    try {
      await create({
        latitude: Number(latitude),
        longitude: Number(longitude),
      });
      setLatitude("");
      setLongitude("");
    } catch {
      // error is already captured in hook state
    }
  };

  const handleSearch = async (event) => {
    event.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const results = await geocodeLocation(searchQuery);
      setSearchResults(results);
    } catch (err) {
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectResult = async (result) => {
    try {
      // Extract location name from display_name
      const locationName = result.display_name.split(",")[0].trim();

      await create({
        latitude: result.lat,
        longitude: result.lon,
        name: locationName,
      });
      setSearchQuery("");
      setSearchResults([]);
    } catch {
      // error is already captured in hook state
    }
  };

  return (
    <div className="space-y-4">
      {/* Search by Postal Code or Place Name */}
      <form
        onSubmit={handleSearch}
        className={`rounded-[2rem] backdrop-blur-xl p-6 shadow-2xl ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
      >
        <div className="flex items-center gap-3 mb-4">
          <div
            className={`rounded-2xl backdrop-blur-sm p-2.5 ${isDark ? "bg-white/15" : "bg-white/30"} ${textColor}`}
          >
            <Search className="h-5 w-5" strokeWidth={2} />
          </div>
          <h2 className={`text-xl font-semibold ${textColor}`}>
            Search by Postal Code or Place
          </h2>
        </div>

        <div className="flex gap-3">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={`flex-1 rounded-2xl ${inputBg} backdrop-blur-sm border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-white/60 focus:border-white/60 transition-all`}
            placeholder="e.g. 018956, Orchard Road, Kuala Lumpur"
          />
          <button
            type="submit"
            disabled={isSearching || !searchQuery.trim()}
            className={`rounded-2xl backdrop-blur-sm px-5 py-3 text-base font-semibold ${textColor} hover:brightness-110 hover:scale-105 active:scale-[0.99] disabled:opacity-50 disabled:hover:scale-100 disabled:hover:brightness-100 transition-all duration-150 shadow-xl focus:outline-none focus:ring-2 focus:ring-white/60 ${isDark ? "bg-white/20 border border-white/35 hover:bg-white/30" : "bg-white/35 border border-white/50 hover:bg-white/45"}`}
          >
            {isSearching ? "Searching..." : "Search"}
          </button>
        </div>

        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className="mt-4 space-y-2">
            {searchResults.map((result, index) => (
              <button
                key={index}
                onClick={() => handleSelectResult(result)}
                disabled={isPending}
                className={`w-full text-left rounded-xl backdrop-blur-sm px-4 py-3 text-sm ${textColor} hover:brightness-110 transition-all ${isDark ? "bg-white/10 border border-white/20 hover:bg-white/15" : "bg-white/30 border border-white/40 hover:bg-white/40"}`}
              >
                <div className="font-medium">{result.display_name}</div>
                <div className={`text-xs ${secondaryTextColor} mt-1`}>
                  {result.lat.toFixed(4)}, {result.lon.toFixed(4)}
                </div>
              </button>
            ))}
          </div>
        )}
      </form>

      {/* Manual Coordinates Entry */}
      <form
        onSubmit={onSubmit}
        className={`rounded-[2rem] backdrop-blur-xl p-6 shadow-2xl ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
      >
        <div className="flex items-center gap-3 mb-4">
          <div
            className={`rounded-2xl backdrop-blur-sm p-2.5 ${isDark ? "bg-white/15" : "bg-white/30"} ${textColor}`}
          >
            <MapPin className="h-5 w-5" strokeWidth={2} />
          </div>
          <h2 className={`text-xl font-semibold ${textColor}`}>
            Add by Coordinates
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          <label className="grid gap-2">
            <span className={`text-sm font-medium ${secondaryTextColor}`}>
              Latitude
            </span>
            <input
              type="number"
              step="any"
              value={latitude}
              onChange={(event) => setLatitude(event.target.value)}
              className={`rounded-2xl ${inputBg} backdrop-blur-sm border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-white/60 focus:border-white/60 transition-all`}
              placeholder="1.3508"
              required
            />
          </label>

          <label className="grid gap-2">
            <span className={`text-sm font-medium ${secondaryTextColor}`}>
              Longitude
            </span>
            <input
              type="number"
              step="any"
              value={longitude}
              onChange={(event) => setLongitude(event.target.value)}
              className={`rounded-2xl ${inputBg} backdrop-blur-sm border px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-white/60 focus:border-white/60 transition-all`}
              placeholder="103.8390"
              required
            />
          </label>
        </div>

        <button
          type="submit"
          disabled={isPending}
          className={`w-full flex items-center justify-center gap-2 rounded-2xl backdrop-blur-sm px-5 py-3 text-base font-semibold ${textColor} hover:brightness-110 hover:scale-105 active:scale-[0.99] disabled:opacity-50 disabled:hover:scale-100 disabled:hover:brightness-100 transition-all duration-150 shadow-xl focus:outline-none focus:ring-2 focus:ring-white/60 ${isDark ? "bg-white/20 border border-white/35 hover:bg-white/30" : "bg-white/35 border border-white/50 hover:bg-white/45"}`}
        >
          <Plus className="h-5 w-5" strokeWidth={2.5} />
          <span>{isPending ? "Adding..." : "Add Location"}</span>
        </button>

        {error && (
          <p
            className={`mt-3 text-sm backdrop-blur-sm rounded-2xl px-4 py-2.5 ${isDark ? "bg-red-500/40 border border-red-400/50 text-red-100" : "bg-red-500/30 border border-red-400/40 text-red-900"}`}
          >
            {error.message}
          </p>
        )}
      </form>
    </div>
  );
}
