/**
 * Preservation Property Test - Card Layout and Apple Weather Polish
 *
 * **Property 2: Preservation** - Core Functionality and Responsiveness
 * **IMPORTANT**: Follow observation-first methodology
 * **EXPECTED OUTCOME**: Tests PASS on unfixed code (confirms baseline behavior to preserve)
 *
 * **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
 *
 * Test Cases:
 * 1. Weather Data Preservation - Temperature, conditions, and forecast display accurately
 * 2. User Interaction Preservation - Expand/collapse, delete, and refresh work correctly
 * 3. Text Readability Preservation - Font sizes and contrast remain accessible
 * 4. Weather Data Fetching Preservation - API calls work correctly
 * 5. Forecast Display Preservation - Hourly and 10-day forecasts show all data
 * 6. Responsive Design Preservation - Layout adapts to different screen sizes
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { EnhancedLocationList } from "../components/EnhancedLocationList.jsx";
import { DetailedWeatherCard } from "../components/DetailedWeatherCard.jsx";
import { LocationsProvider } from "../hooks/useLocations.jsx";
import * as useLocationsHook from "../hooks/useLocations.jsx";
import * as client from "../api/client";
import * as forecasts from "../api/forecasts";

// Mock API modules
vi.mock("../api/client", () => ({
  request: vi.fn(() =>
    Promise.resolve({
      temperature: 28,
      humidity: 75,
      wind_speed: 12,
      wind_direction: 180,
      rainfall: 0,
    }),
  ),
}));

vi.mock("../api/forecasts", () => ({
  get24HourForecast: vi.fn(() =>
    Promise.resolve({
      periods: Array.from({ length: 24 }, (_, i) => ({
        time: `${i}:00`,
        temperature: 28 + Math.floor(Math.random() * 4) - 2,
      })),
    }),
  ),
  get4DayForecast: vi.fn(() =>
    Promise.resolve({
      forecasts: Array.from({ length: 10 }, (_, i) => ({
        date: new Date(Date.now() + i * 86400000).toISOString().split("T")[0],
        temperature: { high: 32, low: 24 },
        forecast: "Partly Cloudy",
      })),
    }),
  ),
}));

describe("Preservation Property Test - Card Layout and Apple Weather Polish", () => {
  const mockLocation = {
    id: 1,
    latitude: 1.3521,
    longitude: 103.8198,
    lastFetched: new Date().toISOString(),
    weather: {
      area: "Singapore",
      condition: "Partly Cloudy",
      temperature: "28",
      observed_at: new Date().toISOString(),
      valid_period_text: "Next 2 hours",
    },
  };

  const mockRefresh = vi.fn();
  const mockDeleteLocation = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock useLocations hook
    vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
      locations: [mockLocation],
      isLoading: false,
      error: null,
    });

    vi.spyOn(useLocationsHook, "useRefreshLocation").mockReturnValue({
      refresh: mockRefresh,
      isPending: false,
      refreshingId: null,
      error: null,
    });

    vi.spyOn(useLocationsHook, "useDeleteLocation").mockReturnValue({
      deleteLocation: mockDeleteLocation,
      isPending: false,
    });
  });

  describe("Test Case 1: Weather Data Preservation - Accurate Display", () => {
    it("should continue to display temperature accurately", () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Verify temperature is displayed
      expect(screen.getByText(/28°/)).toBeInTheDocument();
    });

    it("should continue to display weather condition accurately", () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Verify condition is displayed
      expect(screen.getByText("Partly Cloudy")).toBeInTheDocument();
    });

    it("should continue to display location name accurately", () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Verify location name is displayed
      expect(screen.getByText("Singapore")).toBeInTheDocument();
    });

    it("should continue to display coordinates accurately", () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Verify coordinates are displayed
      expect(screen.getByText(/1.3521, 103.8198/)).toBeInTheDocument();
    });

    it("should continue to display comprehensive weather data in detail card", async () => {
      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Wait for comprehensive data to load
      await waitFor(() => {
        expect(client.request).toHaveBeenCalledWith(
          `/weather/comprehensive/${mockLocation.id}`,
        );
      });

      // Verify humidity is displayed
      expect(screen.getByText(/75%/)).toBeInTheDocument();

      // Verify wind speed is displayed (check for km/h which is unique to wind)
      expect(screen.getByText(/km\/h/)).toBeInTheDocument();

      // Verify wind section exists
      expect(screen.getByText(/wind/i)).toBeInTheDocument();
    });
  });

  describe("Test Case 2: User Interaction Preservation - Expand/Collapse and Delete", () => {
    it("should continue to expand location card on click", async () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Find the expand button
      const expandButton = screen.getByRole("button", {
        name: /expand weather details/i,
      });
      expect(expandButton).toBeInTheDocument();

      // Click to expand
      fireEvent.click(expandButton);

      // Verify expanded content appears
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /collapse weather details/i }),
        ).toBeInTheDocument();
      });
    });

    it("should continue to collapse location card on second click", async () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Expand first
      const expandButton = screen.getByRole("button", {
        name: /expand weather details/i,
      });
      fireEvent.click(expandButton);

      // Wait for expansion
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /collapse weather details/i }),
        ).toBeInTheDocument();
      });

      // Collapse
      const collapseButton = screen.getByRole("button", {
        name: /collapse weather details/i,
      });
      fireEvent.click(collapseButton);

      // Verify collapsed state
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /expand weather details/i }),
        ).toBeInTheDocument();
      });
    });

    it("should continue to call delete function when delete button is clicked", async () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Expand to see delete button
      const expandButton = screen.getByRole("button", {
        name: /expand weather details/i,
      });
      fireEvent.click(expandButton);

      // Wait for delete button to appear
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /delete location/i }),
        ).toBeInTheDocument();
      });

      // Click delete
      const deleteButton = screen.getByRole("button", {
        name: /delete location/i,
      });
      fireEvent.click(deleteButton);

      // Verify delete function was called
      expect(mockDeleteLocation).toHaveBeenCalledWith(mockLocation.id);
    });

    it("should continue to open precipitation map modal", async () => {
      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Wait for component to render
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /open precipitation map/i }),
        ).toBeInTheDocument();
      });

      // Click precipitation map button
      const precipButton = screen.getByRole("button", {
        name: /open precipitation map/i,
      });
      fireEvent.click(precipButton);

      // Verify modal opens (check for modal heading)
      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /precipitation/i }),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Test Case 3: Text Readability Preservation - Accessible Font Sizes", () => {
    it("should continue to use readable font sizes for main temperature", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Find temperature display
      const tempElement = container.querySelector(
        ".text-3xl, .text-4xl, .text-5xl",
      );
      expect(tempElement).toBeInTheDocument();

      // Verify it has readable text size classes
      const hasReadableSize =
        tempElement?.className.includes("text-3xl") ||
        tempElement?.className.includes("text-4xl") ||
        tempElement?.className.includes("text-5xl");
      expect(hasReadableSize).toBe(true);
    });

    it("should continue to use readable font sizes for location name", () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Find location name heading
      const locationHeading = screen.getByRole("heading", {
        name: /singapore/i,
      });
      expect(locationHeading).toBeInTheDocument();

      // Verify it has readable text size
      const className = locationHeading.className;
      expect(className).toMatch(/text-(xl|2xl)/);
    });

    it("should continue to maintain color contrast for text", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Verify text color classes are applied
      const textElements = container.querySelectorAll(
        ".text-slate-900, .text-slate-700, .text-white",
      );
      expect(textElements.length).toBeGreaterThan(0);
    });
  });

  describe("Test Case 4: Weather Data Fetching Preservation - API Calls", () => {
    it("should continue to fetch comprehensive weather data", async () => {
      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Verify API call is made
      await waitFor(() => {
        expect(client.request).toHaveBeenCalledWith(
          `/weather/comprehensive/${mockLocation.id}`,
        );
      });
    });

    it("should continue to fetch 24-hour forecast", async () => {
      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Verify forecast API call is made
      await waitFor(() => {
        expect(forecasts.get24HourForecast).toHaveBeenCalled();
      });
    });

    it("should continue to fetch 4-day forecast", async () => {
      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Verify forecast API call is made
      await waitFor(() => {
        expect(forecasts.get4DayForecast).toHaveBeenCalled();
      });
    });
  });

  describe("Test Case 5: Forecast Display Preservation - Hourly and Daily", () => {
    it("should continue to display hourly forecast section", async () => {
      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Wait for hourly forecast to render
      await waitFor(() => {
        expect(screen.getByText(/hourly forecast/i)).toBeInTheDocument();
      });
    });

    it("should continue to display 10-day forecast section", async () => {
      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Wait for daily forecast to render
      await waitFor(() => {
        expect(screen.getByText(/day forecast/i)).toBeInTheDocument();
      });
    });

    it("should continue to display weather detail cards", async () => {
      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Wait for weather details to render
      await waitFor(() => {
        expect(screen.getByText(/feels like/i)).toBeInTheDocument();
        expect(screen.getByText(/humidity/i)).toBeInTheDocument();
        expect(screen.getByText(/wind/i)).toBeInTheDocument();
        expect(screen.getByText(/rainfall/i)).toBeInTheDocument();
      });
    });

    it("should continue to display sunrise and sunset times", async () => {
      render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

      // Wait for sunrise/sunset to render
      await waitFor(() => {
        expect(screen.getByText(/sunrise/i)).toBeInTheDocument();
        expect(screen.getByText(/sunset/i)).toBeInTheDocument();
      });
    });
  });

  describe("Test Case 6: Responsive Design Preservation - Different Screen Sizes", () => {
    it("should continue to apply responsive classes for mobile", () => {
      // Set viewport to mobile size
      global.innerWidth = 375;

      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Verify responsive classes are present
      const responsiveElements = container.querySelectorAll(
        "[class*='md:'], [class*='lg:'], [class*='xl:']",
      );
      expect(responsiveElements.length).toBeGreaterThan(0);
    });

    it("should continue to apply responsive classes for tablet", () => {
      // Set viewport to tablet size
      global.innerWidth = 768;

      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Verify responsive classes are present
      const responsiveElements = container.querySelectorAll(
        "[class*='md:'], [class*='lg:'], [class*='xl:']",
      );
      expect(responsiveElements.length).toBeGreaterThan(0);
    });

    it("should continue to apply responsive classes for desktop", () => {
      // Set viewport to desktop size
      global.innerWidth = 1440;

      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Verify responsive classes are present
      const responsiveElements = container.querySelectorAll(
        "[class*='md:'], [class*='lg:'], [class*='xl:']",
      );
      expect(responsiveElements.length).toBeGreaterThan(0);
    });

    it("should continue to use max-width constraint for layout", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Verify max-width constraint exists
      const maxWidthContainer = container.querySelector(".max-w-4xl");
      expect(maxWidthContainer).toBeInTheDocument();
    });

    it("should continue to support dark mode styling", () => {
      const { container: lightContainer } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const { container: darkContainer } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={true} />
        </LocationsProvider>,
      );

      // Both should render without errors
      expect(lightContainer.querySelector("article")).toBeInTheDocument();
      expect(darkContainer.querySelector("article")).toBeInTheDocument();

      // Dark mode should have different classes
      const lightCard = lightContainer.querySelector("article");
      const darkCard = darkContainer.querySelector("article");

      expect(lightCard?.className).not.toBe(darkCard?.className);
    });
  });
});
