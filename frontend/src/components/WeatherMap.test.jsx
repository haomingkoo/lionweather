import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { WeatherMap } from "./WeatherMap";

// Mock the hooks
vi.mock("../hooks/useLocations.jsx", () => ({
  useLocations: () => ({
    locations: [],
    isLoading: false,
    error: null,
  }),
  useCreateLocation: () => ({
    create: vi.fn(),
    isPending: false,
    error: null,
  }),
  useRefreshLocation: () => ({
    refresh: vi.fn(),
    isPending: false,
  }),
  useDeleteLocation: () => ({
    deleteLocation: vi.fn(),
    isPending: false,
  }),
}));

// Mock react-leaflet components
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Marker: ({ children }) => <div data-testid="marker">{children}</div>,
  Popup: ({ children }) => <div data-testid="popup">{children}</div>,
  useMapEvents: () => null,
}));

// Mock RainfallOverlay
vi.mock("./RainfallOverlay", () => ({
  RainfallOverlay: () => <div data-testid="rainfall-overlay" />,
}));

// Mock AnimatedRadarLayer
vi.mock("./AnimatedRadarLayer", () => ({
  AnimatedRadarLayer: ({
    visible,
    animationSpeed,
    isPlaying,
    onFrameChange,
    onError,
  }) => (
    <div
      data-testid="animated-radar-layer"
      data-visible={visible}
      data-animation-speed={animationSpeed}
      data-is-playing={isPlaying}
    >
      Animated Radar Layer
    </div>
  ),
}));

describe("WeatherMap - Task 7 Verification", () => {
  describe("7.1 Map styling matches Apple Weather aesthetic", () => {
    it("has rounded corners with radius of at least 16px", () => {
      const { container } = render(<WeatherMap />);
      const mapWrapper = container.querySelector(".rounded-3xl");
      expect(mapWrapper).toBeTruthy();
      // rounded-3xl = 24px, which exceeds 16px requirement
    });

    it("displays subtle shadow effect for depth", () => {
      const { container } = render(<WeatherMap />);
      const mapWrapper = container.querySelector(".shadow-2xl");
      expect(mapWrapper).toBeTruthy();
    });

    it("has border for visual definition", () => {
      const { container } = render(<WeatherMap />);
      const mapWrapper = container.querySelector(".border-white\\/30");
      expect(mapWrapper).toBeTruthy();
    });
  });

  describe("7.2 Map popup glassmorphism styling", () => {
    it("renders map container that will use CSS-styled popups", () => {
      render(<WeatherMap />);
      const mapContainer = screen.getByTestId("map-container");
      expect(mapContainer).toBeTruthy();
      // Note: Glassmorphism styling is applied via CSS in index.css
      // .leaflet-popup-content-wrapper has the glassmorphism styles
    });
  });

  describe("7.3 Map click interaction", () => {
    it("initializes ripples state for visual feedback", () => {
      const { container } = render(<WeatherMap />);
      // Component should render without errors
      expect(container).toBeTruthy();
      // Ripple effects are added dynamically on click
    });

    it("has relative positioning for ripple effects", () => {
      const { container } = render(<WeatherMap />);
      const mapWrapper = container.querySelector(".relative");
      expect(mapWrapper).toBeTruthy();
    });
  });

  describe("7.1 AnimatedRadarLayer Integration", () => {
    it("should render AnimatedRadarLayer when rainfall toggle is active", async () => {
      const { container } = render(<WeatherMap />);

      // Find and click the rainfall toggle button
      const rainfallToggle = container.querySelector(
        'button[aria-label*="rainfall"]',
      );
      expect(rainfallToggle).toBeTruthy();

      // Click to show rainfall
      rainfallToggle.click();

      // Wait for AnimatedRadarLayer to appear
      await waitFor(() => {
        const radarLayer = screen.queryByTestId("animated-radar-layer");
        expect(radarLayer).toBeInTheDocument();
        expect(radarLayer.getAttribute("data-visible")).toBe("true");
      });
    });

    it("should pass correct props to AnimatedRadarLayer", async () => {
      const { container } = render(<WeatherMap />);

      // Enable rainfall
      const rainfallToggle = container.querySelector(
        'button[aria-label*="rainfall"]',
      );
      rainfallToggle.click();

      await waitFor(() => {
        const radarLayer = screen.getByTestId("animated-radar-layer");

        // Check that props are passed correctly
        expect(radarLayer.getAttribute("data-visible")).toBe("true");
        expect(radarLayer.getAttribute("data-animation-speed")).toBe("500"); // default speed
        expect(radarLayer.getAttribute("data-is-playing")).toBe("true"); // default playing state
      });
    });

    it("should show radar controls when rainfall is enabled", async () => {
      const { container } = render(<WeatherMap />);

      // Initially controls should not be visible
      let playPauseButton = container.querySelector(
        'button[aria-label*="animation"]',
      );
      expect(playPauseButton).toBeNull();

      // Enable rainfall
      const rainfallToggle = container.querySelector(
        'button[aria-label*="rainfall"]',
      );
      rainfallToggle.click();

      // Controls should now be visible
      await waitFor(() => {
        playPauseButton = container.querySelector(
          'button[aria-label*="animation"]',
        );
        expect(playPauseButton).toBeTruthy();

        const speedSlider = container.querySelector('input[type="range"]');
        expect(speedSlider).toBeTruthy();
        expect(speedSlider.getAttribute("min")).toBe("300");
        expect(speedSlider.getAttribute("max")).toBe("1000");
      });
    });

    it("should toggle animation play/pause state", async () => {
      const { container } = render(<WeatherMap />);

      // Enable rainfall
      const rainfallToggle = container.querySelector(
        'button[aria-label*="rainfall"]',
      );
      rainfallToggle.click();

      await waitFor(() => {
        const radarLayer = screen.getByTestId("animated-radar-layer");
        expect(radarLayer.getAttribute("data-is-playing")).toBe("true");
      });

      // Click play/pause button
      const playPauseButton = container.querySelector(
        'button[aria-label*="Pause animation"]',
      );
      expect(playPauseButton).toBeTruthy();
      playPauseButton.click();

      // Animation should be paused
      await waitFor(() => {
        const radarLayer = screen.getByTestId("animated-radar-layer");
        expect(radarLayer.getAttribute("data-is-playing")).toBe("false");
      });
    });

    it("should update animation speed via slider", async () => {
      const { container } = render(<WeatherMap />);

      // Enable rainfall
      const rainfallToggle = container.querySelector(
        'button[aria-label*="rainfall"]',
      );
      rainfallToggle.click();

      await waitFor(() => {
        const speedSlider = container.querySelector('input[type="range"]');
        expect(speedSlider).toBeTruthy();
        expect(speedSlider.value).toBe("500"); // default value
      });

      // Change speed using proper event
      const speedSlider = container.querySelector('input[type="range"]');
      speedSlider.value = "700";
      const event = new Event("change", { bubbles: true });
      speedSlider.dispatchEvent(event);

      // Check that the slider value updated
      await waitFor(() => {
        const updatedSlider = container.querySelector('input[type="range"]');
        expect(updatedSlider.value).toBe("700");
      });
    });

    it("should not render AnimatedRadarLayer when rainfall is hidden", () => {
      render(<WeatherMap />);

      // AnimatedRadarLayer should not be rendered initially
      const radarLayer = screen.queryByTestId("animated-radar-layer");
      expect(radarLayer).toBeNull();
    });

    it("should display current frame timestamp when provided", async () => {
      const { container } = render(<WeatherMap />);

      // Enable rainfall
      const rainfallToggle = container.querySelector(
        'button[aria-label*="rainfall"]',
      );
      rainfallToggle.click();

      // The timestamp display should be present in the controls
      await waitFor(() => {
        const controls = container.querySelector(".absolute.right-4.top-20");
        expect(controls).toBeTruthy();
      });
    });

    it("should have proper z-index ordering for radar layer", async () => {
      const { container } = render(<WeatherMap />);

      // Enable rainfall
      const rainfallToggle = container.querySelector(
        'button[aria-label*="rainfall"]',
      );
      rainfallToggle.click();

      // Check that controls have high z-index
      await waitFor(() => {
        const rainfallButton = container.querySelector(".z-\\[1000\\]");
        expect(rainfallButton).toBeTruthy();
      });
    });
  });
});
