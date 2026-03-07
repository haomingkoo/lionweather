import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, act, cleanup } from "@testing-library/react";
import fc from "fast-check";
import { ThemeProvider, useTheme } from "./ThemeContext";

/**
 * Property-Based Tests for Theme System
 * Feature: premium-weather-ui-enhancements
 */

// Test component that exposes theme functions
function TestComponent({ onRender }) {
  const { theme, toggleTheme } = useTheme();

  // Call onRender with current theme and toggle function
  if (onRender) {
    onRender({ theme, toggleTheme });
  }

  return (
    <div>
      <div data-testid="current-theme">{theme}</div>
    </div>
  );
}

describe("Property-Based Tests: Theme System", () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    // Remove dark class from document
    document.documentElement.classList.remove("dark");
  });

  afterEach(() => {
    cleanup();
  });

  /**
   * Property 4: Theme Toggle State Transition
   * **Validates: Requirements 2.2**
   *
   * For any current theme state (light or dark), invoking the toggle function
   * should transition to the opposite theme state.
   */
  describe("Feature: premium-weather-ui-enhancements, Property 4: Theme Toggle State Transition", () => {
    it("should transition to opposite state when toggling from any theme state", () => {
      fc.assert(
        fc.property(
          fc.constantFrom("light", "dark"), // Generate random initial theme state
          (initialTheme) => {
            // Set initial theme in localStorage
            localStorage.setItem(
              "weather-app-theme",
              JSON.stringify({
                mode: initialTheme,
                savedAt: new Date().toISOString(),
              }),
            );

            let capturedTheme = null;
            let capturedToggle = null;

            // Render component and capture theme state and toggle function
            render(
              <ThemeProvider>
                <TestComponent
                  onRender={({ theme, toggleTheme }) => {
                    capturedTheme = theme;
                    capturedToggle = toggleTheme;
                  }}
                />
              </ThemeProvider>,
            );

            // Verify initial theme is loaded correctly
            expect(capturedTheme).toBe(initialTheme);

            // Toggle the theme
            act(() => {
              capturedToggle();
            });

            // Capture the new theme after toggle
            let newTheme = null;
            render(
              <ThemeProvider>
                <TestComponent
                  onRender={({ theme }) => {
                    newTheme = theme;
                  }}
                />
              </ThemeProvider>,
            );

            // Verify theme transitioned to opposite state
            const expectedTheme = initialTheme === "light" ? "dark" : "light";
            expect(newTheme).toBe(expectedTheme);

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should return to original state after toggling twice", () => {
      fc.assert(
        fc.property(
          fc.constantFrom("light", "dark"), // Generate random initial theme state
          (initialTheme) => {
            // Set initial theme in localStorage
            localStorage.setItem(
              "weather-app-theme",
              JSON.stringify({
                mode: initialTheme,
                savedAt: new Date().toISOString(),
              }),
            );

            let capturedToggle = null;

            // Render component and capture toggle function
            render(
              <ThemeProvider>
                <TestComponent
                  onRender={({ toggleTheme }) => {
                    capturedToggle = toggleTheme;
                  }}
                />
              </ThemeProvider>,
            );

            // Toggle twice
            act(() => {
              capturedToggle();
              capturedToggle();
            });

            // Capture the theme after double toggle
            let finalTheme = null;
            render(
              <ThemeProvider>
                <TestComponent
                  onRender={({ theme }) => {
                    finalTheme = theme;
                  }}
                />
              </ThemeProvider>,
            );

            // Verify theme returned to original state
            expect(finalTheme).toBe(initialTheme);

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should always produce valid theme states after toggle", () => {
      fc.assert(
        fc.property(
          fc.constantFrom("light", "dark"), // Generate random initial theme state
          fc.integer({ min: 1, max: 10 }), // Random number of toggles
          (initialTheme, toggleCount) => {
            // Set initial theme in localStorage
            localStorage.setItem(
              "weather-app-theme",
              JSON.stringify({
                mode: initialTheme,
                savedAt: new Date().toISOString(),
              }),
            );

            let capturedToggle = null;

            // Render component and capture toggle function
            render(
              <ThemeProvider>
                <TestComponent
                  onRender={({ toggleTheme }) => {
                    capturedToggle = toggleTheme;
                  }}
                />
              </ThemeProvider>,
            );

            // Toggle multiple times
            act(() => {
              for (let i = 0; i < toggleCount; i++) {
                capturedToggle();
              }
            });

            // Capture the final theme
            let finalTheme = null;
            render(
              <ThemeProvider>
                <TestComponent
                  onRender={({ theme }) => {
                    finalTheme = theme;
                  }}
                />
              </ThemeProvider>,
            );

            // Verify theme is always a valid state
            expect(["light", "dark"]).toContain(finalTheme);

            // Verify theme matches expected state based on toggle count
            const expectedTheme =
              toggleCount % 2 === 0
                ? initialTheme
                : initialTheme === "light"
                  ? "dark"
                  : "light";
            expect(finalTheme).toBe(expectedTheme);

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should persist toggled theme to localStorage", () => {
      fc.assert(
        fc.property(
          fc.constantFrom("light", "dark"), // Generate random initial theme state
          (initialTheme) => {
            // Set initial theme in localStorage
            localStorage.setItem(
              "weather-app-theme",
              JSON.stringify({
                mode: initialTheme,
                savedAt: new Date().toISOString(),
              }),
            );

            let capturedToggle = null;

            // Render component and capture toggle function
            render(
              <ThemeProvider>
                <TestComponent
                  onRender={({ toggleTheme }) => {
                    capturedToggle = toggleTheme;
                  }}
                />
              </ThemeProvider>,
            );

            // Toggle the theme
            act(() => {
              capturedToggle();
            });

            // Check localStorage was updated
            const stored = JSON.parse(
              localStorage.getItem("weather-app-theme"),
            );
            const expectedTheme = initialTheme === "light" ? "dark" : "light";
            expect(stored.mode).toBe(expectedTheme);
            expect(stored.savedAt).toBeDefined();

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should apply correct CSS class to document root after toggle", () => {
      fc.assert(
        fc.property(
          fc.constantFrom("light", "dark"), // Generate random initial theme state
          (initialTheme) => {
            // Set initial theme in localStorage
            localStorage.setItem(
              "weather-app-theme",
              JSON.stringify({
                mode: initialTheme,
                savedAt: new Date().toISOString(),
              }),
            );

            let capturedToggle = null;

            // Render component and capture toggle function
            render(
              <ThemeProvider>
                <TestComponent
                  onRender={({ toggleTheme }) => {
                    capturedToggle = toggleTheme;
                  }}
                />
              </ThemeProvider>,
            );

            // Toggle the theme
            act(() => {
              capturedToggle();
            });

            // Verify document root has correct class
            const expectedTheme = initialTheme === "light" ? "dark" : "light";
            const hasDarkClass =
              document.documentElement.classList.contains("dark");

            if (expectedTheme === "dark") {
              expect(hasDarkClass).toBe(true);
            } else {
              expect(hasDarkClass).toBe(false);
            }

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });
  });
});
