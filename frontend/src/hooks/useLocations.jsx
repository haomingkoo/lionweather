import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";

const LocationsContext = createContext(null);

const STORAGE_KEY = "lionweather_locations";

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

// Fetch weather data from API (still needed for actual weather info)
const fetchWeatherForLocation = async (latitude, longitude) => {
  try {
    // Call your weather API endpoint
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

export function LocationsProvider({ children }) {
  const [locations, setLocations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load locations from localStorage on mount
  const reload = useCallback(async () => {
    try {
      setIsLoading(true);
      const stored = getStoredLocations();
      setLocations(stored);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Geolocation permission state management
  const getGeolocationPermissionState = useCallback(() => {
    return localStorage.getItem("geolocation_permission");
  }, []);

  const setGeolocationPermissionState = useCallback((state) => {
    localStorage.setItem("geolocation_permission", state);
  }, []);

  // Add location from geolocation coordinates
  const addLocationFromGeolocation = useCallback(async (coords) => {
    try {
      // Fetch weather data for the coordinates
      const weatherData = await fetchWeatherForLocation(coords.lat, coords.lng);

      const newLocation = {
        id: generateId(),
        latitude: coords.lat,
        longitude: coords.lng,
        weather: weatherData,
        created_at: new Date().toISOString(),
      };

      const stored = getStoredLocations();
      const updated = [...stored, newLocation];
      saveLocations(updated);
      setLocations(updated);
      setGeolocationPermissionState("granted");

      return newLocation;
    } catch (err) {
      setError(err);
      throw err;
    }
  }, []);

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
      // Fetch weather data for the new location
      const weatherData = await fetchWeatherForLocation(
        payload.latitude,
        payload.longitude,
      );

      const newLocation = {
        id: generateId(),
        latitude: payload.latitude,
        longitude: payload.longitude,
        weather: weatherData,
        created_at: new Date().toISOString(),
      };

      const stored = getStoredLocations();
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

      // Fetch fresh weather data
      const weatherData = await fetchWeatherForLocation(
        location.latitude,
        location.longitude,
      );

      // Update the location with new weather data
      const updated = stored.map((loc) =>
        loc.id === locationId
          ? {
              ...loc,
              weather: weatherData,
              updated_at: new Date().toISOString(),
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
