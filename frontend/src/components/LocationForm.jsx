import { useState } from "react";
import { useCreateLocation } from "../hooks/useLocations.jsx";
import { MapPin, Plus } from "lucide-react";

export function LocationForm({ isDark = false }) {
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
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

  return (
    <form
      onSubmit={onSubmit}
      className={`rounded-[2rem] backdrop-blur-xl p-8 shadow-2xl ${isDark ? "bg-white/10 border border-white/20" : "bg-white/25 border border-white/40"}`}
    >
      <div className="flex items-center gap-3 mb-6">
        <div
          className={`rounded-2xl backdrop-blur-sm p-3 ${isDark ? "bg-white/15" : "bg-white/30"} ${textColor}`}
        >
          <MapPin className="h-6 w-6" strokeWidth={2} />
        </div>
        <h2 className={`text-2xl font-semibold ${textColor}`}>
          Add New Location
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <label className="grid gap-3">
          <span className={`text-base font-medium ${secondaryTextColor}`}>
            Latitude
          </span>
          <input
            type="number"
            step="any"
            value={latitude}
            onChange={(event) => setLatitude(event.target.value)}
            className={`rounded-2xl ${inputBg} backdrop-blur-sm border px-5 py-4 text-lg focus:outline-none focus:ring-2 focus:ring-white/60 focus:border-white/60 transition-all`}
            placeholder="1.3508"
            required
          />
        </label>

        <label className="grid gap-3">
          <span className={`text-base font-medium ${secondaryTextColor}`}>
            Longitude
          </span>
          <input
            type="number"
            step="any"
            value={longitude}
            onChange={(event) => setLongitude(event.target.value)}
            className={`rounded-2xl ${inputBg} backdrop-blur-sm border px-5 py-4 text-lg focus:outline-none focus:ring-2 focus:ring-white/60 focus:border-white/60 transition-all`}
            placeholder="103.8390"
            required
          />
        </label>
      </div>

      <button
        type="submit"
        disabled={isPending}
        className={`w-full flex items-center justify-center gap-3 rounded-2xl backdrop-blur-sm px-6 py-4 text-lg font-semibold ${textColor} hover:brightness-110 hover:scale-105 active:scale-[0.99] disabled:opacity-50 disabled:hover:scale-100 disabled:hover:brightness-100 transition-all duration-150 shadow-xl focus:outline-none focus:ring-2 focus:ring-white/60 focus:ring-offset-2 focus:ring-offset-transparent ${isDark ? "bg-white/20 border border-white/35 hover:bg-white/30" : "bg-white/35 border border-white/50 hover:bg-white/45"}`}
      >
        <Plus className="h-6 w-6" strokeWidth={2.5} />
        <span>{isPending ? "Adding Location..." : "Add Location"}</span>
      </button>

      {error && (
        <p
          className={`mt-4 text-base backdrop-blur-sm rounded-2xl px-5 py-3 ${isDark ? "bg-red-500/40 border border-red-400/50 text-red-100" : "bg-red-500/30 border border-red-400/40 text-red-900"}`}
        >
          {error.message}
        </p>
      )}
    </form>
  );
}
