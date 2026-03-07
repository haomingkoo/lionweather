/**
 * Bug Condition Exploration Test - Radar Animation and UI Polish Issues
 *
 * **Property 1: Bug Condition** - Radar Animation and UI Polish Issues
 * **CRITICAL**: These tests MUST FAIL on unfixed code - failure confirms the bugs exist
 * **NOTE**: These tests encode the expected behavior - they will validate the fix when they pass after implementation
 * **GOAL**: Surface counterexamples that demonstrate the bugs exist
 *
 * **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9**
 *
 * Test Cases:
 * 1. Static Radar - Open precipitation map and verify it shows canvas gradients instead of radar images
 * 2. No Radar Fetch - Monitor network requests when map opens and verify no requests to weather.gov.sg
 * 3. Missing Loading - Open precipitation map and verify no loading spinner appears
 * 4. Backdrop Click - Click outside modal and verify modal doesn't close
 * 5. Desktop Card Size - View on 1440px screen and verify cards use large padding/text
 * 6. No Transition - Open modal and verify instant appearance with no fade-in
 * 7. Console Error - Load page with network error and verify console.error is called
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PrecipitationMap } from "../components/PrecipitationMap.jsx";
import { DetailedWeatherCard } from "../components/DetailedWeatherCard.jsx";
import * as rainfallApi from "../api/rainfall";

// Mock Leaflet
vi.mock("leaflet", () => ({
  default: {
    icon: vi.fn(() => ({})),
    Marker: { prototype: { options: {} } },
    imageOverlay: vi.fn(() => ({
      addTo: vi.fn(),
      remove: vi.fn(),
    })),
  },
}));

// Mock react-leaflet
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Marker: ({ children }) => <div data-testid="marker">{children}</div>,
  Popup: ({ children }) => <div data-testid="popup">{children}</div>,
  useMapEvents: () => null,
  useMap: () => ({
    getBounds: () => ({
      getNorthEast: () => ({ lat: 1.5, lng: 104 }),
      getSouthWest: () => ({ lat: 1.2, lng: 103.6 }),
    }),
    getSize: () => ({ x: 800, y: 600 }),
    latLngToContainerPoint: () => ({ x: 400, y: 300 }),
    removeLayer: vi.fn(),
  }),
}));

// Mock API
vi.mock("../api/client", () => ({
  request: vi.fn(() =>
    Promise.resolve({
      temperature: 28,
      humidity: 75,
      wind_speed: 12,
    }),
  ),
}));

vi.mock("../api/forecasts", () => ({
  get24HourForecast: vi.fn(() => Promise.resolve({ periods: [] })),
  get4DayForecast: vi.fn(() => Promise.resolve({ forecasts: [] })),
}));

describe("Bug Condition Exploration - Radar Animation and UI Polish Issues", () => {
  const mockLocation = {
    id: 1,
    latitude: 1.3521,
    longitude: 103.8198,
    weather: {
      area: "Singapore",
      condition: "Partly Cloudy",
      temperature: "28",
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Test Case 1: Static Radar - Canvas Gradients Instead of Radar Images", () => {
    it("should use radar image fetching instead of canvas (EXPECTED TO PASS after fix)", async () => {
      // Spy on getRainfallData to verify it's not called
      const getRainfallDataSpy = vi.spyOn(rainfallApi, "getRainfallData");

      render(
        <PrecipitationMap
          location={mockLocation}
          onClose={vi.fn()}
          isDark={false}
        />,
      );

      // Verify loading spinner appears (indicates radar fetching logic is active)
      const spinner = screen.getByTestId("loading-spinner");
      expect(spinner).toBeInTheDocument();

      // Verify the component uses the new radar-based approach
      // (no longer calls getRainfallData)
      expect(getRainfallDataSpy).not.toHaveBeenCalled();
    });
  });

  describe("Test Case 2: No Radar Fetch - No Requests to weather.gov.sg", () => {
    it("should implement radar frame fetching (EXPECTED TO PASS after fix)", async () => {
      render(
        <PrecipitationMap
          location={mockLocation}
          onClose={vi.fn()}
          isDark={false}
        />,
      );

      // Verify loading state exists (indicates radar fetching is implemented)
      const spinner = screen.getByTestId("loading-spinner");
      expect(spinner).toBeInTheDocument();

      // Verify play button is disabled during loading
      const playButton = screen.getByRole("button", {
        name: /play animation/i,
      });
      expect(playButton).toBeDisabled();
    });
  });

  describe("Test Case 3: Missing Loading - No Loading Spinner", () => {
    it("should not display loading spinner while fetching (EXPECTED TO FAIL)", async () => {
      vi.spyOn(rainfallApi, "getRainfallData").mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve({ stations: [] }), 100),
          ),
      );

      render(
        <PrecipitationMap
          location={mockLocation}
          onClose={vi.fn()}
          isDark={false}
        />,
      );

      // Expected behavior: Should show loading spinner
      // Current behavior: No loading spinner
      const spinner =
        screen.queryByTestId("loading-spinner") ||
        screen.queryByText(/loading/i) ||
        screen.queryByRole("status");

      expect(spinner).toBeInTheDocument();
    });
  });

  describe("Test Case 4: Backdrop Click - Modal Doesn't Close", () => {
    it("should not close modal when backdrop is clicked (EXPECTED TO FAIL)", () => {
      const onClose = vi.fn();

      const { container } = render(
        <PrecipitationMap
          location={mockLocation}
          onClose={onClose}
          isDark={false}
        />,
      );

      // Find the backdrop (outermost div with fixed positioning)
      const backdrop = container.querySelector(".fixed.inset-0");
      expect(backdrop).toBeInTheDocument();

      // Click the backdrop
      fireEvent.click(backdrop);

      // Expected behavior: Modal should close (onClose called)
      // Current behavior: Modal doesn't close
      expect(onClose).toHaveBeenCalled();
    });
  });

  describe("Test Case 5: Desktop Card Size - Large Padding and Text", () => {
    it("should use large padding and text on desktop (EXPECTED TO FAIL)", () => {
      // Set viewport to desktop size
      global.innerWidth = 1440;

      const { container } = render(
        <DetailedWeatherCard location={mockLocation} isDark={false} />,
      );

      // Find weather detail cards
      const cards = container.querySelectorAll(".rounded-3xl");

      // Expected behavior: Should use compact sizing (xl:p-3, xl:text-2xl)
      // Current behavior: Uses large sizing (p-6, text-3xl)
      // Check for compact desktop classes
      const hasCompactPadding = Array.from(cards).some(
        (card) =>
          card.className.includes("xl:p-3") ||
          card.className.includes("2xl:p-4"),
      );

      expect(hasCompactPadding).toBe(true);
    });
  });

  describe("Test Case 6: No Transition - Instant Modal Appearance", () => {
    it("should show modal instantly without transitions (EXPECTED TO FAIL)", () => {
      const { container } = render(
        <PrecipitationMap
          location={mockLocation}
          onClose={vi.fn()}
          isDark={false}
        />,
      );

      // Find backdrop and modal content
      const backdrop = container.querySelector(".fixed.inset-0");
      const modalContent = container.querySelector(".relative.w-full");

      // Expected behavior: Should have transition classes
      // Current behavior: No transition classes
      expect(backdrop?.className).toMatch(/transition-opacity|duration-/);
      expect(modalContent?.className).toMatch(/transition-transform|duration-/);
    });
  });

  describe("Test Case 7: Console Error - Errors Logged to Console", () => {
    it("should handle errors gracefully without console.error (EXPECTED TO PASS after fix)", async () => {
      const consoleErrorSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});

      // Mock Image to simulate error
      const originalImage = global.Image;
      global.Image = class {
        constructor() {
          setTimeout(() => {
            if (this.onerror) this.onerror();
          }, 10);
        }
      };

      render(
        <PrecipitationMap
          location={mockLocation}
          onClose={vi.fn()}
          isDark={false}
        />,
      );

      await waitFor(
        () => {
          const spinner = screen.queryByTestId("loading-spinner");
          expect(spinner).not.toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      // Expected behavior: Should handle errors gracefully without console.error
      expect(consoleErrorSpy).not.toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
      global.Image = originalImage;
    });
  });
});
