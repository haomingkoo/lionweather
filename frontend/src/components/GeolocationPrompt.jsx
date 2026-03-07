import { useState } from "react";
import { MapPin, X } from "lucide-react";

export function GeolocationPrompt({ onLocationDetected, onDismiss }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleUseLocation = async () => {
    setIsLoading(true);
    setError(null);

    if (!navigator.geolocation) {
      setError("Geolocation is not supported by your browser.");
      setIsLoading(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      // Success callback
      (position) => {
        setIsLoading(false);
        onLocationDetected({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        });
      },
      // Error callback
      (error) => {
        setIsLoading(false);
        const errorMessages = {
          1: "Location access denied. You can still enter coordinates manually.",
          2: "Unable to determine your location. Please enter coordinates manually.",
          3: "Location request timed out. Please try again or enter coordinates manually.",
        };
        setError(
          errorMessages[error.code] ||
            "Location unavailable. Please enter coordinates manually.",
        );
      },
      // Options
      {
        timeout: 10000,
        maximumAge: 0,
        enableHighAccuracy: false,
      },
    );
  };

  const handleDismiss = () => {
    localStorage.setItem("geolocation_permission", "denied");
    onDismiss();
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl p-8 max-w-md w-full shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-blue-600/20 rounded-full flex items-center justify-center">
              <MapPin className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <h3 className="text-xl font-semibold text-white">
                Use Your Location
              </h3>
              <p className="text-sm text-slate-400">
                Get weather for your area
              </p>
            </div>
          </div>
          <button
            onClick={handleDismiss}
            className="text-slate-400 hover:text-white transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Privacy Message */}
        <div className="mb-6 p-4 bg-slate-900/50 rounded-lg border border-slate-700/50">
          <p className="text-sm text-slate-300">
            🔒{" "}
            <span className="font-medium">We won't store your location.</span>{" "}
            Your coordinates are only used to fetch weather data and are not
            saved on our servers.
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/20 border border-red-700/50 rounded-lg">
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col gap-3">
          <button
            onClick={handleUseLocation}
            disabled={isLoading}
            className="w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Detecting Location...
              </>
            ) : (
              <>
                <MapPin className="w-5 h-5" />
                Use My Location
              </>
            )}
          </button>

          <button
            onClick={handleDismiss}
            className="w-full px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg transition-colors"
          >
            Enter Manually
          </button>
        </div>
      </div>
    </div>
  );
}
