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

  // result.name is the specific place name (e.g. "ION Orchard", "Paragon").
  // Prefer it over the generic neighbourhood/suburb (e.g. "Boulevard").
  const resultName = result.name && result.name !== "Singapore" ? result.name : null;

  // Prioritise the specific named place over the area/neighbourhood label.
  const base = resultName || areaName;

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

// Detect "lat, lon" input (e.g. "1.3521, 103.8198")
function parseLatLon(query) {
  const m = query.trim().match(/^(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)$/);
  if (!m) return null;
  const lat = parseFloat(m[1]);
  const lon = parseFloat(m[2]);
  // Rough bounding box: SG/MY/ID region
  if (lat < -11 || lat > 8 || lon < 95 || lon > 142) return null;
  return { lat, lon };
}

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

export function LocationForm({ compact = false }) {
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const { create, isPending, error } = useCreateLocation();

  const input = "min-h-11 w-full min-w-0 rounded-control border border-line bg-surface px-3 text-base text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30";
  const button = "inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-control border border-line bg-surface-2 px-4 text-sm font-medium text-ink hover:bg-line/60 disabled:opacity-60";

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
    setSearchError("");

    // If input looks like "lat, lon", add directly
    const coords = parseLatLon(searchQuery);
    if (coords) {
      try {
        await create({ latitude: coords.lat, longitude: coords.lon });
        setSearchQuery("");
        setSearchResults([]);
      } catch { /* captured in hook */ }
      return;
    }

    setIsSearching(true);
    try {
      const results = await geocodeLocation(searchQuery);
      setSearchResults(results);
    } catch (err) {
      setSearchResults([]);
      setSearchError(/not found/i.test(err.message || "") ? err.message : "Search is not working right now. Check your connection and try again.");
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

  return (
    <div className="space-y-3">
      <form onSubmit={handleSearch} role="search">
        <label htmlFor="place-search" className={compact ? "sr-only" : "mb-1 block text-sm font-medium"}>
          Postal code or place
        </label>
        <div className="flex gap-2">
          <input
            id="place-search"
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={input}
            placeholder="Postal code or place"
            enterKeyHint="search"
          />
          <button type="submit" disabled={isSearching || !searchQuery.trim()} className={`${button} ${compact ? "w-11 px-0" : ""}`} aria-label={compact ? (isSearching ? "Searching" : "Search") : undefined}>
            <Search className="h-4 w-4" aria-hidden="true" />
            {!compact && (isSearching ? "Searching" : "Search")}
          </button>
        </div>

        {searchError && <p className="mt-2 text-sm text-bad" role="alert">{searchError}</p>}

        {searchResults.length > 0 && (
          <ul className="mt-2 divide-y divide-line overflow-hidden rounded-card border border-line" aria-label="Search results">
            {searchResults.map((result, index) => (
              <li key={index}>
                <button
                  type="button"
                  onClick={() => handleSelectResult(result)}
                  disabled={isPending}
                  className="block min-h-11 w-full px-3 py-2 text-left hover:bg-surface-2 disabled:opacity-60"
                >
                  <span className="block truncate text-sm font-medium">{result.name}</span>
                  <span className="mt-0.5 block truncate text-xs text-muted">{result.display_name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {error && compact && <p className="mt-2 text-sm text-bad" role="alert">{error.message}</p>}
      </form>

      {!compact && (
        <form onSubmit={onSubmit} className="rounded-panel border border-line bg-surface p-5">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <MapPin className="h-4 w-4" aria-hidden="true" />
            Add by coordinates
          </h2>
          <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="grid gap-1">
              <span className="text-sm font-medium">Latitude</span>
              <input type="number" step="any" value={latitude} onChange={(event) => setLatitude(event.target.value)} className={input} placeholder="1.3508" required />
            </label>
            <label className="grid gap-1">
              <span className="text-sm font-medium">Longitude</span>
              <input type="number" step="any" value={longitude} onChange={(event) => setLongitude(event.target.value)} className={input} placeholder="103.8390" required />
            </label>
          </div>
          <button type="submit" disabled={isPending} className={`${button} w-full`}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            {isPending ? "Adding..." : "Add place"}
          </button>
          {error && <p className="mt-3 text-sm text-bad" role="alert">{error.message}</p>}
        </form>
      )}
    </div>
  );
}
