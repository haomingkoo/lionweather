import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";

const LocationsContext = createContext(null);

const STORAGE_KEY = "lionweather_locations";
const CACHE_DURATION = 15 * 60 * 1000; // 15 minutes in milliseconds
const MAX_LOCATIONS = 10;
const MAX_CONCURRENT_REQUESTS = 5;

// Helper functions for localStorage
const getStoredLocations = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch (err) {
    console.error("Failed to load locations from localStorage:", err);
    return [];
  }
};

const saveLocations = (locations) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(locations));
  } catch (err) {
    console.error("Failed to save locations to localStorage:", err);
  }
};

// Generate unique ID
const generateId = () => {
  return `loc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

// Check if cache is still valid
const isCacheValid = (lastFetched) => {
  if (!lastFetched) return false;
  const now = Date.now();
  const fetchedTime = new Date(lastFetched).getTime();
  return now - fetchedTime < CACHE_DURATION;
};

// Fetch weather data from API
const fetchWeatherForLocation = async (latitude, longitude) => {
  try {
    const response = await fetch(
      `/api/weather?lat=${latitude}&lng=${longitude}`,
    );
    if (!response.ok) {
      throw new Error("Failed to fetch weather data");
    }
    return await response.json();
  } catch (err) {
    console.error("Weather fetch error:", err);
    return {
      condition: "Unknown",
      temperature: null,
      area: "Unknown Area",
    };
  }
};

// Reverse geocode to get location name
const reverseGeocode = async (latitude, longitude) => {
  try {
    // Use OpenStreetMap Nominatim API for reverse geocoding (free, no API key needed)
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=10&addressdetails=1`,
      {
        headers: {
          "User-Agent": "LionWeather/1.0",
        },
      },
    );
    if (!response.ok) {
      throw new Error("Failed to reverse geocode");
    }
    const data = await response.json();

    // Extract meaningful location name
    const address = data.address || {};
    const locationName =
      address.city ||
      address.town ||
      address.village ||
      address.county ||
      address.state ||
      address.country ||
      "Unknown Area";

    return locationName;
  } catch (err) {
    console.error("Reverse geocoding error:", err);
    return "Unknown Area";
  }
};

// Check for weather alerts and show notifications
const checkWeatherAlerts = (locations) => {
  if (!("Notification" in window)) return;
  if (Notification.permission !== "granted") return;

  locations.forEach((location) => {
    const weather = location.weather;
    if (!weather) return;

    // Check for rain
    const condition = weather.condition?.toLowerCase() || "";
    if (
      condition.includes("rain") ||
      condition.includes("shower") ||
      condition.includes("thunderstorm")
    ) {
      new Notification("LionWeather Alert 🌧️", {
        body: `${weather.area || "Your location"}: ${weather.condition}`,
        icon: "/favicon.ico",
        tag: `weather-${location.id}`,
      });
    }

    // Check for extreme temperatures
    if (weather.temperature && weather.temperature > 35) {
      new Notification("LionWeather Alert 🌡️", {
        body: `${weather.area || "Your location"}: Very hot (${weather.temperature}°C)`,
        icon: "/favicon.ico",
        tag: `temp-${location.id}`,
      });
    }
  });
};

// Request notification permission
const requestNotificationPermission = async () => {
  if (!("Notification" in window)) {
    console.log("This browser does not support notifications");
    return false;
  }

  if (Notification.permission === "granted") {
    return true;
  }

  if (Notification.permission !== "denied") {
    const permission = await Notification.requestPermission();
    return permission === "granted";
  }

  return false;
};

export function LocationsProvider({ children }) {
  const [locations, setLocations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load locations and refresh stale data
  const reload = useCallback(async () => {
    try {
      setIsLoading(true);
      const stored = getStoredLocations();

      // Check which locations need refresh
      const locationsToRefresh = stored.filter(
        (loc) => !isCacheValid(loc.lastFetched),
      );

      if (locationsToRefresh.length === 0) {
        // All cached, no API calls
        setLocations(stored);
        setError(null);
        setIsLoading(false);
        return;
      }

      // Show stale data immediately
      setLocations(stored);
      setIsLoading(false);

      // Batch refresh stale locations
      const refreshPromises = [];
      for (
        let i = 0;
        i < locationsToRefresh.length;
        i += MAX_CONCURRENT_REQUESTS
      ) {
        const batch = locationsToRefresh.slice(i, i + MAX_CONCURRENT_REQUESTS);
        const batchPromises = batch.map(async (loc) => {
          const weatherData = await fetchWeatherForLocation(
            loc.latitude,
            loc.longitude,
          );
          return {
            ...loc,
            weather: weatherData,
            lastFetched: new Date().toISOString(),
          };
        });
        refreshPromises.push(...batchPromises);
      }

      const refreshedLocations = await Promise.all(refreshPromises);

      // Merge refreshed data
      const updated = stored.map((loc) => {
        const refreshed = refreshedLocations.find((r) => r.id === loc.id);
        return refreshed || loc;
      });

      saveLocations(updated);
      setLocations(updated);

      // Check for weather alerts
      checkWeatherAlerts(updated);

      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getGeolocationPermissionState = useCallback(() => {
    return localStorage.getItem("geolocation_permission");
  }, []);

  const setGeolocationPermissionState = useCallback((state) => {
    localStorage.setItem("geolocation_permission", state);
  }, []);

  const addLocationFromGeolocation = useCallback(
    async (coords) => {
      try {
        const stored = getStoredLocations();

        if (stored.length >= MAX_LOCATIONS) {
          throw new Error(
            `Maximum ${MAX_LOCATIONS} locations allowed. Please delete a location first.`,
          );
        }

        // Fetch weather data and location name in parallel
        const [weatherData, locationName] = await Promise.all([
          fetchWeatherForLocation(coords.lat, coords.lng),
          reverseGeocode(coords.lat, coords.lng),
        ]);

        // Override area with reverse geocoded name if weather API didn't provide one
        if (weatherData.area === "Unknown Area" || !weatherData.area) {
          weatherData.area = locationName;
        }

        const newLocation = {
          id: generateId(),
          latitude: coords.lat,
          longitude: coords.lng,
          weather: weatherData,
          source: "geolocation",
          created_at: new Date().toISOString(),
          lastFetched: new Date().toISOString(),
        };

        const updated = [...stored, newLocation];
        saveLocations(updated);
        setLocations(updated);
        setGeolocationPermissionState("granted");

        return newLocation;
      } catch (err) {
        setError(err);
        throw err;
      }
    },
    [setGeolocationPermissionState],
  );

  // Request notification permission on mount
  useEffect(() => {
    requestNotificationPermission();
  }, []);

  // Auto-refresh on mount
  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <LocationsContext.Provider
      value={{
        locations,
        isLoading,
        error,
        reload,
        getGeolocationPermissionState,
        setGeolocationPermissionState,
        addLocationFromGeolocation,
      }}
    >
      {children}
    </LocationsContext.Provider>
  );
}

export function useLocations() {
  return useContext(LocationsContext);
}

export function useCreateLocation() {
  const { reload } = useContext(LocationsContext);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState(null);

  const create = async (payload) => {
    setIsPending(true);
    setError(null);
    try {
      const stored = getStoredLocations();

      if (stored.length >= MAX_LOCATIONS) {
        throw new Error(
          `Maximum ${MAX_LOCATIONS} locations allowed. Please delete a location first.`,
        );
      }

      // Fetch weather data and location name in parallel
      const [weatherData, locationName] = await Promise.all([
        fetchWeatherForLocation(payload.latitude, payload.longitude),
        payload.name
          ? Promise.resolve(payload.name)
          : reverseGeocode(payload.latitude, payload.longitude),
      ]);

      // Use provided name or reverse geocoded name
      if (payload.name) {
        weatherData.area = payload.name;
      } else if (weatherData.area === "Unknown Area" || !weatherData.area) {
        weatherData.area = locationName;
      }

      console.log("Creating location with name:", weatherData.area);

      const newLocation = {
        id: generateId(),
        latitude: payload.latitude,
        longitude: payload.longitude,
        weather: weatherData,
        created_at: new Date().toISOString(),
        lastFetched: new Date().toISOString(),
      };

      const updated = [...stored, newLocation];
      saveLocations(updated);
      await reload();

      return newLocation;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsPending(false);
    }
  };

  return { create, isPending, error };
}

export function useRefreshLocation() {
  const { reload } = useContext(LocationsContext);
  const [isPending, setIsPending] = useState(false);
  const [refreshingId, setRefreshingId] = useState(null);
  const [error, setError] = useState(null);

  const refresh = async (locationId) => {
    setIsPending(true);
    setRefreshingId(locationId);
    setError(null);
    try {
      const stored = getStoredLocations();
      const location = stored.find((loc) => loc.id === locationId);

      if (!location) {
        throw new Error("Location not found");
      }

      const weatherData = await fetchWeatherForLocation(
        location.latitude,
        location.longitude,
      );

      const updated = stored.map((loc) =>
        loc.id === locationId
          ? {
              ...loc,
              weather: weatherData,
              lastFetched: new Date().toISOString(),
            }
          : loc,
      );

      saveLocations(updated);
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setIsPending(false);
      setRefreshingId(null);
    }
  };

  return { refresh, isPending, refreshingId, error };
}

export function useDeleteLocation() {
  const { reload } = useContext(LocationsContext);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState(null);

  const deleteLocation = async (locationId) => {
    setIsPending(true);
    setError(null);
    try {
      const stored = getStoredLocations();
      const updated = stored.filter((loc) => loc.id !== locationId);
      saveLocations(updated);
      await reload();
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsPending(false);
    }
  };

  return { deleteLocation, isPending, error };
}
