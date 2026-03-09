import { useState } from "react";
import { useCreateLocation } from "../hooks/useLocations.jsx";
import { MapPin, Plus, Search } from "lucide-react";

// Build a human-readable location name from Nominatim address components.
// Priority: specific area name > postal code suffix > fallback to display_name parts.
function buildLocationName(result, originalQuery) {
  const addr = result.address || {};
  const isSingaporePostal = /^\d{6}$/.test(originalQuery.trim());

  // Most specific first: neighbourhood → suburb → quarter → village → city_district → city
  const areaName =
    addr.neighbourhood ||
    addr.suburb ||
    addr.quarter ||
    addr.village ||
    addr.town ||
    addr.city_district ||
    addr.borough ||
    null;

  // For place-name searches, also try the result's own name attribute
  const resultName = result.name && result.name !== "Singapore" ? result.name : null;

  const base = areaName || resultName;

  if (base) {
    // Append postal code in parentheses if search was by postal code
    return isSingaporePostal ? `${base} (${originalQuery.trim()})` : base;
  }

  // Fallback: pick a meaningful part from display_name (skip bare "Singapore")
  const parts = result.display_name.split(",").map((p) => p.trim()).filter(Boolean);
  const meaningful = parts.find((p) => p !== "Singapore" && !/^\d{6}$/.test(p));
  if (meaningful) return meaningful;

  // Last resort: show postal code itself
  return isSingaporePostal ? `Postal ${originalQuery.trim()}` : parts[0] || "Unknown";
}

// Build a readable name from a OneMap result (BLK_NO + ROAD_NAME or BUILDING).
function buildOneMapName(result, postalCode) {
  const blk = (result.BLK_NO || "").trim();
  const road = toTitleCase(result.ROAD_NAME || "");
  const building = toTitleCase(result.BUILDING || "");

  // Prefer "Blk 123 Road Name" if a block number exists
  if (blk && blk !== "NIL" && road) return `Blk ${blk} ${road}`;
  // Named building (not just the road repeated)
  if (building && building !== "NIL" && building !== road) return building;
  // Road name with postal code
  if (road) return `${road} (${postalCode})`;
  return `Postal ${postalCode}`;
}

function toTitleCase(str) {
  return str.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

// Geocode a Singapore postal code via OneMap (official SG geocoder).
const geocodeSingaporePostal = async (postalCode) => {
  const response = await fetch(
    `https://www.onemap.gov.sg/api/common/elastic/search?searchVal=${postalCode}&returnGeom=Y&getAddrDetails=Y&pageNum=1`,
  );
  if (!response.ok) throw new Error("OneMap request failed");
  const data = await response.json();
  if (!data.results || data.results.length === 0) return null;

  return data.results.map((r) => ({
    lat: parseFloat(r.LATITUDE),
    lon: parseFloat(r.LONGITUDE),
    display_name: r.ADDRESS,
    name: buildOneMapName(r, postalCode),
  }));
};

// Geocode postal code or place name to coordinates
const geocodeLocation = async (query) => {
  try {
    const isSingaporePostal = /^\d{6}$/.test(query.trim());

    // For SG postal codes, try OneMap first (returns proper road/building names)
    if (isSingaporePostal) {
      const oneMapResults = await geocodeSingaporePostal(query.trim()).catch(() => null);
      if (oneMapResults && oneMapResults.length > 0) return oneMapResults;
    }

    const searchQuery = isSingaporePostal ? `${query.trim()}, Singapore` : query;
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&q=${encodeURIComponent(searchQuery)}&countrycodes=sg,my,id&limit=5`,
      { headers: { "User-Agent": "LionWeather/1.0" } },
    );
    if (!response.ok) throw new Error("Failed to geocode location");

    const data = await response.json();
    if (data.length === 0) {
      throw new Error("Location not found. Try a different postal code or place name.");
    }

    return data.map((result) => ({
      lat: parseFloat(result.lat),
      lon: parseFloat(result.lon),
      display_name: result.display_name,
      name: buildLocationName(result, query),
    }));
  } catch (err) {
    console.error("Geocoding error:", err);
    throw err;
  }
};

export function LocationForm({ isDark = false, compact = false }) {
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
      await create({
        latitude: result.lat,
        longitude: result.lon,
        name: result.name || result.display_name.split(",")[0].trim(),
      });
      setSearchQuery("");
      setSearchResults([]);
    } catch {
      // error is already captured in hook state
    }
  };

  const cardPad = compact ? "p-3" : "p-6";
  const cardRadius = compact ? "rounded-2xl" : "rounded-[2rem]";
  const inputPad = compact ? "px-3 py-2 text-sm" : "px-4 py-3 text-base";
  const btnPad = compact ? "px-3 py-2 text-sm" : "px-5 py-3 text-base";

  return (
    <div className="space-y-3">
      {/* Search by Postal Code or Place Name */}
      <form
        onSubmit={handleSearch}
        className={`${cardRadius} backdrop-blur-xl ${cardPad} shadow-lg ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
      >
        {!compact && (
          <div className="flex items-center gap-3 mb-4">
            <div className={`rounded-2xl backdrop-blur-sm p-2.5 ${isDark ? "bg-white/15" : "bg-white/30"} ${textColor}`}>
              <Search className="h-5 w-5" strokeWidth={2} />
            </div>
            <h2 className={`text-xl font-semibold ${textColor}`}>
              Search by Postal Code or Place
            </h2>
          </div>
        )}

        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={`flex-1 rounded-xl ${inputBg} backdrop-blur-sm border ${inputPad} focus:outline-none focus:ring-2 focus:ring-white/60 focus:border-white/60 transition-all`}
            placeholder={compact ? "Postal code or place…" : "e.g. 018956, Orchard Road"}
          />
          <button
            type="submit"
            disabled={isSearching || !searchQuery.trim()}
            className={`rounded-xl backdrop-blur-sm ${btnPad} font-semibold ${textColor} hover:brightness-110 active:scale-[0.99] disabled:opacity-50 transition-all shadow-md focus:outline-none focus:ring-2 focus:ring-white/60 ${isDark ? "bg-white/20 border border-white/35 hover:bg-white/30" : "bg-white/35 border border-white/50 hover:bg-white/45"}`}
          >
            {isSearching ? "…" : "Search"}
          </button>
        </div>

        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className="mt-2 space-y-1">
            {searchResults.map((result, index) => (
              <button
                key={index}
                onClick={() => handleSelectResult(result)}
                disabled={isPending}
                className={`w-full text-left rounded-xl backdrop-blur-sm px-3 py-2 text-sm ${textColor} hover:brightness-110 transition-all ${isDark ? "bg-white/10 border border-white/20 hover:bg-white/15" : "bg-white/30 border border-white/40 hover:bg-white/40"}`}
              >
                <div className="font-medium truncate">{result.display_name}</div>
                <div className={`text-xs ${secondaryTextColor} mt-0.5`}>
                  {result.lat.toFixed(4)}, {result.lon.toFixed(4)}
                </div>
              </button>
            ))}
          </div>
        )}
      </form>

      {/* Manual Coordinates Entry — hidden in compact mode */}
      {!compact && <form
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
      </form>}
    </div>
  );
}
