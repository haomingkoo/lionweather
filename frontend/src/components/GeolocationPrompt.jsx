import { useState } from "react";
import { MapPin, X } from "lucide-react";

export function GeolocationPrompt({ onLocationDetected, onDismiss }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleUseLocation = () => {
    setIsLoading(true);
    setError(null);

    if (!navigator.geolocation) {
      setError("Not supported by your browser.");
      setIsLoading(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setIsLoading(false);
        onLocationDetected({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        });
      },
      (err) => {
        setIsLoading(false);
        setError(err.code === 1 ? "Location access denied." : "Unable to get location.");
      },
      { timeout: 10000, maximumAge: 0, enableHighAccuracy: false },
    );
  };

  const handleDismiss = () => {
    localStorage.setItem("geolocation_permission", "denied");
    onDismiss();
  };

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-full max-w-sm px-4">
      <div className="bg-slate-800/95 backdrop-blur border border-slate-700 rounded-2xl p-4 shadow-2xl">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 bg-blue-600/20 rounded-full flex items-center justify-center shrink-0">
              <MapPin className="w-4 h-4 text-blue-400" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-white">Track your location?</p>
              {error ? (
                <p className="text-xs text-red-400 truncate">{error}</p>
              ) : (
                <p className="text-xs text-slate-400">For local weather — stays in your browser.</p>
              )}
            </div>
          </div>
          <button onClick={handleDismiss} className="text-slate-500 hover:text-white transition-colors shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex gap-2 mt-3">
          <button
            onClick={handleUseLocation}
            disabled={isLoading}
            className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-1.5"
          >
            {isLoading ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <MapPin className="w-4 h-4" />
            )}
            {isLoading ? "Detecting..." : "Allow"}
          </button>
          <button
            onClick={handleDismiss}
            className="flex-1 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Not now
          </button>
        </div>
      </div>
    </div>
  );
}
