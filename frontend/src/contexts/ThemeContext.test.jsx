import { describe, it, expect, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThemeProvider, themeForTime, useTheme } from "./ThemeContext";

const sgt = (hhmm) => new Date(`2026-10-26T${hhmm}:00+08:00`);

function Probe() {
  const { theme, isNight } = useTheme();
  return <p>{theme} {String(isNight)}</p>;
}

describe("theme follows the sun in Singapore", () => {
  afterEach(() => document.documentElement.classList.remove("dark"));

  it("is light between sunrise and sunset", () => {
    expect(themeForTime(sgt("07:30"))).toBe("light");
    expect(themeForTime(sgt("14:00"))).toBe("light");
    expect(themeForTime(sgt("18:30"))).toBe("light");
  });

  it("is dark before sunrise and after sunset", () => {
    expect(themeForTime(sgt("05:30"))).toBe("dark");
    expect(themeForTime(sgt("19:30"))).toBe("dark");
    expect(themeForTime(sgt("23:59"))).toBe("dark");
  });

  it("sets the dark class on the document at night only", () => {
    const { unmount } = render(<ThemeProvider now={sgt("22:00")}><Probe /></ThemeProvider>);
    expect(screen.getByText("dark true")).toBeInTheDocument();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    unmount();
    render(<ThemeProvider now={sgt("12:00")}><Probe /></ThemeProvider>);
    expect(screen.getByText("light false")).toBeInTheDocument();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
