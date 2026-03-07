import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ThemeProvider, useTheme } from "./ThemeContext";

// Test component that uses the theme hook
function TestComponent() {
  const { theme, setTheme, toggleTheme } = useTheme();
  return (
    <div>
      <div data-testid="current-theme">{theme}</div>
      <button onClick={() => setTheme("dark")} data-testid="set-dark">
        Set Dark
      </button>
      <button onClick={() => setTheme("light")} data-testid="set-light">
        Set Light
      </button>
      <button onClick={toggleTheme} data-testid="toggle">
        Toggle
      </button>
    </div>
  );
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    // Remove dark class from document
    document.documentElement.classList.remove("dark");
    // Clear all mocks
    vi.clearAllMocks();
  });

  it("initializes with light theme by default", () => {
    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("current-theme").textContent).toBe("light");
  });

  it("loads saved theme from localStorage on mount", () => {
    localStorage.setItem(
      "weather-app-theme",
      JSON.stringify({ mode: "dark", savedAt: new Date().toISOString() }),
    );

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("current-theme").textContent).toBe("dark");
  });

  it("applies dark class to document root when theme is dark", () => {
    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    );

    act(() => {
      screen.getByTestId("set-dark").click();
    });

    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("removes dark class from document root when theme is light", () => {
    // Start with dark theme
    localStorage.setItem(
      "weather-app-theme",
      JSON.stringify({ mode: "dark", savedAt: new Date().toISOString() }),
    );

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    );

    expect(document.documentElement.classList.contains("dark")).toBe(true);

    act(() => {
      screen.getByTestId("set-light").click();
    });

    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("persists theme to localStorage when changed", () => {
    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    );

    act(() => {
      screen.getByTestId("set-dark").click();
    });

    const stored = JSON.parse(localStorage.getItem("weather-app-theme"));
    expect(stored.mode).toBe("dark");
    expect(stored.savedAt).toBeDefined();
  });

  it("toggles between light and dark themes", () => {
    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("current-theme").textContent).toBe("light");

    act(() => {
      screen.getByTestId("toggle").click();
    });

    expect(screen.getByTestId("current-theme").textContent).toBe("dark");

    act(() => {
      screen.getByTestId("toggle").click();
    });

    expect(screen.getByTestId("current-theme").textContent).toBe("light");
  });

  it("handles localStorage unavailable gracefully", () => {
    // Mock localStorage to throw error
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
    setItemSpy.mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    );

    // Should not throw error
    act(() => {
      screen.getByTestId("set-dark").click();
    });

    // Theme should still change in memory
    expect(screen.getByTestId("current-theme").textContent).toBe("dark");

    setItemSpy.mockRestore();
  });

  it("handles invalid stored theme value", () => {
    localStorage.setItem(
      "weather-app-theme",
      JSON.stringify({ mode: "invalid", savedAt: new Date().toISOString() }),
    );

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    );

    // Should default to light theme
    expect(screen.getByTestId("current-theme").textContent).toBe("light");
  });

  it("handles corrupted localStorage data", () => {
    localStorage.setItem("weather-app-theme", "invalid json");

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    );

    // Should default to light theme
    expect(screen.getByTestId("current-theme").textContent).toBe("light");
  });

  it("throws error when useTheme is used outside ThemeProvider", () => {
    // Suppress console.error for this test
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    expect(() => {
      render(<TestComponent />);
    }).toThrow("useTheme must be used within a ThemeProvider");

    consoleError.mockRestore();
  });
});
