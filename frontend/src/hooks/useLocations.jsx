import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import {
  listLocations,
  createLocation as apiCreateLocation,
  refreshLocation as apiRefreshLocation,
  deleteLocation as apiDeleteLocation,
} from "../api/locations";

const LocationsContext = createContext(null);

export function LocationsProvider({ children }) {
  const [locations, setLocations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    try {
      const data = await listLocations();
      setLocations(data.locations);
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
  const addLocationFromGeolocation = useCallback(
    async (coords) => {
      try {
        const newLocation = await apiCreateLocation({
          latitude: coords.lat,
          longitude: coords.lng,
        });
        setGeolocationPermissionState("granted");
        await reload();
        return newLocation;
      } catch (err) {
        setError(err);
        throw err;
      }
    },
    [reload],
  );

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
      const newLocation = await apiCreateLocation(payload);
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
      await apiRefreshLocation(locationId);
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
      await apiDeleteLocation(locationId);
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
