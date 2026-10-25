import { createContext, useContext, useEffect, useState } from "react";
import SunCalc from "suncalc";

const ThemeContext = createContext(undefined);

const SINGAPORE = { lat: 1.3521, lng: 103.8198 };
const RECHECK_MS = 60 * 1000;

// Light while the sun is up in Singapore, dark from sunset to sunrise.
export function themeForTime(now = new Date(), { lat, lng } = SINGAPORE) {
  const { sunrise, sunset } = SunCalc.getTimes(now, lat, lng);
  if (Number.isNaN(sunrise?.getTime()) || Number.isNaN(sunset?.getTime())) {
    const hour = now.getHours();
    return hour >= 7 && hour < 19 ? "light" : "dark";
  }
  return now >= sunrise && now < sunset ? "light" : "dark";
}

export function ThemeProvider({ children, now }) {
  const [theme, setTheme] = useState(() => themeForTime(now ?? new Date()));

  useEffect(() => {
    if (now) return undefined;
    const id = setInterval(() => setTheme(themeForTime(new Date())), RECHECK_MS);
    return () => clearInterval(id);
  }, [now]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#0b1220" : "#f4f6f9");
  }, [theme]);

  return <ThemeContext.Provider value={{ theme, isNight: theme === "dark" }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
