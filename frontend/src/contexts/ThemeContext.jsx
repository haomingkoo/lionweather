import { createContext, useContext, useEffect, useState } from "react";

const ThemeContext = createContext(undefined);

const STORAGE_KEY = "weather-app-theme";
const DEFAULT_THEME = "light";

/**
 * Load theme preference from localStorage
 * @returns {'light' | 'dark'} The stored theme or default
 */
function loadTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return DEFAULT_THEME;

    const config = JSON.parse(stored);
    if (config.mode === "light" || config.mode === "dark") {
      return config.mode;
    }
  } catch (e) {
    console.warn("Failed to load theme preference:", e);
  }
  return DEFAULT_THEME;
}

/**
 * Save theme preference to localStorage
 * @param {'light' | 'dark'} theme - The theme to save
 */
function saveTheme(theme) {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        mode: theme,
        savedAt: new Date().toISOString(),
      }),
    );
  } catch (e) {
    console.warn("Failed to save theme preference:", e);
    // Continue with in-memory state
  }
}

/**
 * ThemeProvider component that manages theme state and persistence
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components
 */
export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(loadTheme);

  // Apply theme class to document root
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  // Persist theme to localStorage
  useEffect(() => {
    saveTheme(theme);
  }, [theme]);

  const setTheme = (newTheme) => {
    if (newTheme === "light" || newTheme === "dark") {
      setThemeState(newTheme);
    }
  };

  const toggleTheme = () => {
    setThemeState((current) => (current === "light" ? "dark" : "light"));
  };

  const value = {
    theme,
    setTheme,
    toggleTheme,
  };

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

/**
 * Hook to access theme context
 * @returns {{theme: 'light' | 'dark', setTheme: (theme: 'light' | 'dark') => void, toggleTheme: () => void}}
 * @throws {Error} If used outside ThemeProvider
 */
export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
