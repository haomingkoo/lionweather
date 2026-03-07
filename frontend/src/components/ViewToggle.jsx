import { List, Map, Brain } from "lucide-react";

export function ViewToggle({ view, onViewChange, isDark = false }) {
  const baseClasses =
    "rounded-2xl px-6 py-3 text-base font-semibold transition-all duration-200 flex items-center gap-2";
  const activeClasses = isDark
    ? "bg-white/35 backdrop-blur-md shadow-xl text-white scale-105"
    : "bg-white/60 backdrop-blur-md shadow-xl text-slate-900 scale-105";
  const inactiveClasses = isDark
    ? "text-white/70 hover:text-white hover:bg-white/15"
    : "text-slate-700 hover:text-slate-900 hover:bg-white/30";

  return (
    <div className="flex gap-2 rounded-[1.5rem] bg-white/15 backdrop-blur-xl p-2 border border-white/30 shadow-lg">
      <button
        onClick={() => onViewChange("list")}
        className={`${baseClasses} ${view === "list" ? activeClasses : inactiveClasses} focus:outline-none focus:ring-2 focus:ring-white/60 focus:ring-offset-2 focus:ring-offset-transparent`}
        aria-label="List view"
      >
        <List className="h-5 w-5" strokeWidth={2.5} />
        <span>List</span>
      </button>
      <button
        onClick={() => onViewChange("map")}
        className={`${baseClasses} ${view === "map" ? activeClasses : inactiveClasses} focus:outline-none focus:ring-2 focus:ring-white/60 focus:ring-offset-2 focus:ring-offset-transparent`}
        aria-label="Map view"
      >
        <Map className="h-5 w-5" strokeWidth={2.5} />
        <span>Map</span>
      </button>
      <button
        onClick={() => onViewChange("ml")}
        className={`${baseClasses} ${view === "ml" ? activeClasses : inactiveClasses} focus:outline-none focus:ring-2 focus:ring-white/60 focus:ring-offset-2 focus:ring-offset-transparent`}
        aria-label="ML view"
      >
        <Brain className="h-5 w-5" strokeWidth={2.5} />
        <span>ML</span>
      </button>
    </div>
  );
}
