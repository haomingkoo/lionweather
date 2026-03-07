import { Sun, Moon } from "lucide-react";
import { useTheme } from "../contexts/ThemeContext";

/**
 * ThemeToggle component provides a button to switch between light and dark themes
 * @param {Object} props
 * @param {string} [props.className] - Additional CSS classes
 * @param {boolean} [props.showLabel] - Whether to show text label alongside icon
 */
export function ThemeToggle({ className = "", showLabel = false }) {
  const { theme, toggleTheme } = useTheme();

  const isDark = theme === "dark";
  const label = isDark ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button
      onClick={toggleTheme}
      className={`
        flex items-center gap-2 p-2 rounded-lg
        transition-all duration-300 ease-in-out
        hover:bg-gray-200 dark:hover:bg-gray-700
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
        dark:focus:ring-offset-gray-900
        ${className}
      `}
      aria-label={label}
      title={label}
    >
      <div className="relative w-5 h-5">
        {/* Sun icon - visible in light mode */}
        <Sun
          className={`
            absolute inset-0 w-5 h-5 text-yellow-500
            transition-all duration-300 ease-in-out
            ${isDark ? "opacity-0 rotate-90 scale-0" : "opacity-100 rotate-0 scale-100"}
          `}
          aria-hidden="true"
        />
        {/* Moon icon - visible in dark mode */}
        <Moon
          className={`
            absolute inset-0 w-5 h-5 text-blue-400
            transition-all duration-300 ease-in-out
            ${isDark ? "opacity-100 rotate-0 scale-100" : "opacity-0 -rotate-90 scale-0"}
          `}
          aria-hidden="true"
        />
      </div>
      {showLabel && (
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {isDark ? "Dark" : "Light"}
        </span>
      )}
    </button>
  );
}
