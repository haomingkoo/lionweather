import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ThemeToggle } from "./ThemeToggle";
import { ThemeProvider } from "../contexts/ThemeContext";

describe("ThemeToggle", () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    // Remove dark class from document
    document.documentElement.classList.remove("dark");
  });

  it("renders toggle button with sun icon in light mode", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const button = screen.getByRole("button", {
      name: /switch to dark mode/i,
    });
    expect(button).toBeInTheDocument();
  });

  it("renders toggle button with moon icon in dark mode", () => {
    // Set dark mode in localStorage
    localStorage.setItem(
      "weather-app-theme",
      JSON.stringify({ mode: "dark", savedAt: new Date().toISOString() }),
    );

    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const button = screen.getByRole("button", {
      name: /switch to light mode/i,
    });
    expect(button).toBeInTheDocument();
  });

  it("toggles theme when clicked", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const button = screen.getByRole("button");

    // Initially in light mode
    expect(button).toHaveAttribute("aria-label", "Switch to dark mode");

    // Click to switch to dark mode
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-label", "Switch to light mode");

    // Click again to switch back to light mode
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-label", "Switch to dark mode");
  });

  it("applies dark class to document root when toggled to dark mode", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const button = screen.getByRole("button");

    // Initially no dark class
    expect(document.documentElement.classList.contains("dark")).toBe(false);

    // Click to switch to dark mode
    fireEvent.click(button);
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    // Click again to switch back to light mode
    fireEvent.click(button);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("has accessible ARIA label", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const button = screen.getByRole("button");
    expect(button).toHaveAttribute("aria-label");
    expect(button.getAttribute("aria-label")).toBeTruthy();
  });

  it("shows label text when showLabel prop is true", () => {
    render(
      <ThemeProvider>
        <ThemeToggle showLabel={true} />
      </ThemeProvider>,
    );

    expect(screen.getByText("Light")).toBeInTheDocument();
  });

  it("shows 'Dark' label in dark mode when showLabel is true", () => {
    localStorage.setItem(
      "weather-app-theme",
      JSON.stringify({ mode: "dark", savedAt: new Date().toISOString() }),
    );

    render(
      <ThemeProvider>
        <ThemeToggle showLabel={true} />
      </ThemeProvider>,
    );

    expect(screen.getByText("Dark")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    render(
      <ThemeProvider>
        <ThemeToggle className="custom-class" />
      </ThemeProvider>,
    );

    const button = screen.getByRole("button");
    expect(button).toHaveClass("custom-class");
  });

  it("has focus ring styles for accessibility", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const button = screen.getByRole("button");
    expect(button.className).toContain("focus:ring");
  });
});
