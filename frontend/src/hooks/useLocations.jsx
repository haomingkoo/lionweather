import { API_BASE } from "../api/base.js";
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

// Resolve area name: try NEA snap first, fall back to Nominatim
const resolveAreaName = async (latitude, longitude) => {
  // 1. Try NEA forecast area snap via backend
  try {
    const response = await fetch(
      `/api/locations/areas/nearest?lat=${latitude}&lng=${longitude}`,
    );
    if (response.ok) {
      const data = await response.json();
      if (data.area && data.area !== "Unknown Area") return data.area;
    }
  } catch (_) {}

  // 2. Fallback: Nominatim reverse geocoding
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=16&addressdetails=1`,
      { headers: { "User-Agent": "LionWeather/1.0" } },
    );
    if (response.ok) {
      const data = await response.json();
      const address = data.address || {};
      return (
        address.neighbourhood ||
        address.suburb ||
        address.quarter ||
        address.village ||
        address.town ||
        address.city_district ||
        address.city ||
        "Unknown Area"
      );
    }
  } catch (_) {}

  return "Unknown Area";
};

const isRainy = (condition) => {
  const c = (condition || "").toLowerCase();
  return c.includes("rain") || c.includes("shower") || c.includes("thunder");
};

// Smart rain transition notifications — fires only on state change
const checkWeatherAlerts = (locations, prevLocations = []) => {
  if (!("Notification" in window)) return;
  if (Notification.permission !== "granted") return;

  locations.forEach((location) => {
    const weather = location.weather;
    if (!weather) return;

    const area = weather.area || "Your location";
    const condition = weather.condition || "";
    const prev = prevLocations.find((l) => l.id === location.id);
    const prevCondition = prev?.weather?.condition || "";

    const nowRaining = isRainy(condition);
    const wasRaining = isRainy(prevCondition);

    // Rain just started
    if (nowRaining && !wasRaining && prevCondition) {
      const isThundery = condition.toLowerCase().includes("thunder");
      new Notification(isThundery ? "⛈️ Thundery showers starting" : "🌧️ Rain starting", {
        body: `${area} — ${condition}`,
        icon: "/favicon.ico",
        tag: `rain-start-${location.id}`,
      });
    }

    // Rain just stopped
    if (!nowRaining && wasRaining && prevCondition) {
      new Notification("☀️ Rain clearing up", {
        body: `${area} — now ${condition}`,
        icon: "/favicon.ico",
        tag: `rain-stop-${location.id}`,
      });
    }
  });
};

// Request notification permission (only when user opts in)
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

const RAIN_NOTIFY_KEY = "lionweather_rain_notify";
const RAIN_NOTIFY_LAST_KEY = "lionweather_rain_notify_last";
const RAIN_NOTIFY_COOLDOWN = 60 * 60 * 1000; // 1 hour cooldown between notifications
const RAIN_POLL_INTERVAL = 15 * 60 * 1000; // Poll every 15 minutes

// Fetch ML predictions for next 2 hours and notify if rain likely
const checkMLRainForecast = async () => {
  try {
    const response = await fetch(`${API_BASE}/ml/predict/2`);
    if (!response.ok) return;
    const data = await response.json();
    const predictions = data.predictions || [];

    // Find highest rain probability in next 2 hours
    const highRainPred = predictions.find((p) => p.rain_probability > 50);
    if (!highRainPred) return;

    // Cooldown: don't spam notifications
    const lastNotify = localStorage.getItem(RAIN_NOTIFY_LAST_KEY);
    if (lastNotify && Date.now() - parseInt(lastNotify, 10) < RAIN_NOTIFY_COOLDOWN) return;

    // Fire notification
    if (Notification.permission === "granted") {
      const prob = Math.round(highRainPred.rain_probability);
      new Notification("🌧️ Rain expected soon", {
        body: `${prob}% chance of rain in the next 1–2 hours`,
        icon: "/favicon.ico",
        tag: "ml-rain-forecast",
      });
      localStorage.setItem(RAIN_NOTIFY_LAST_KEY, String(Date.now()));
    }
  } catch (err) {
    console.warn("ML rain forecast check failed:", err);
  }
};

export function LocationsProvider({ children }) {
  const [locations, setLocations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const reorderLocations = useCallback((newOrder) => {
    saveLocations(newOrder);
    setLocations(newOrder);
  }, []);

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

      // Check for weather alerts (pass previous state for transition detection)
      checkWeatherAlerts(updated, stored);

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
          resolveAreaName(coords.lat, coords.lng),
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

  // Auto-add/refresh current location if geolocation permission was previously granted
  useEffect(() => {
    const permState = localStorage.getItem("geolocation_permission");
    if (permState !== "granted") return;
    if (!navigator.geolocation) return;

    const updateCurrentLocation = () => {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const { latitude, longitude } = pos.coords;
          const stored = getStoredLocations();
          const existing = stored.find((loc) => loc.source === "geolocation");

          if (existing) {
            // Refresh weather for the existing geolocation card
            const weatherData = await fetchWeatherForLocation(latitude, longitude);
            const updated = stored.map((loc) =>
              loc.source === "geolocation"
                ? { ...loc, latitude, longitude, weather: weatherData, lastFetched: new Date().toISOString() }
                : loc,
            );
            saveLocations(updated);
            setLocations(updated);
          } else {
            // Add new geolocation card at the front
            const [weatherData, locationName] = await Promise.all([
              fetchWeatherForLocation(latitude, longitude),
              resolveAreaName(latitude, longitude),
            ]);
            if (weatherData.area === "Unknown Area" || !weatherData.area) {
              weatherData.area = locationName;
            }
            const newLocation = {
              id: generateId(),
              latitude,
              longitude,
              weather: weatherData,
              source: "geolocation",
              created_at: new Date().toISOString(),
              lastFetched: new Date().toISOString(),
            };
            const updated = [newLocation, ...stored];
            saveLocations(updated);
            setLocations(updated);
          }
        },
        (err) => console.warn("Geolocation update failed:", err),
        { timeout: 10000 },
      );
    };

    updateCurrentLocation();
    const interval = setInterval(updateCurrentLocation, CACHE_DURATION);
    return () => clearInterval(interval);
  }, []);

  // Rain forecast notifications (opt-in)
  const [rainNotifyEnabled, setRainNotifyEnabledState] = useState(
    () => localStorage.getItem(RAIN_NOTIFY_KEY) === "true",
  );

  const setRainNotifyEnabled = useCallback(async (enabled) => {
    if (enabled) {
      const granted = await requestNotificationPermission();
      if (!granted) return; // browser denied, don't enable
    }
    localStorage.setItem(RAIN_NOTIFY_KEY, String(enabled));
    setRainNotifyEnabledState(enabled);
  }, []);

  // Poll ML predictions when rain notifications are enabled
  useEffect(() => {
    if (!rainNotifyEnabled) return;

    // Check immediately on enable
    checkMLRainForecast();

    const interval = setInterval(checkMLRainForecast, RAIN_POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [rainNotifyEnabled]);

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
        reorderLocations,
        getGeolocationPermissionState,
        setGeolocationPermissionState,
        addLocationFromGeolocation,
        rainNotifyEnabled,
        setRainNotifyEnabled,
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
          : resolveAreaName(payload.latitude, payload.longitude),
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
      const toDelete = stored.find((loc) => loc.id === locationId);
      const updated = stored.filter((loc) => loc.id !== locationId);
      saveLocations(updated);
      // If user explicitly removes their geolocation card, revoke auto-add permission
      if (toDelete?.source === "geolocation") {
        localStorage.removeItem("geolocation_permission");
      }
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
