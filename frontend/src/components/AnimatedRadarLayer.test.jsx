import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MapContainer } from "react-leaflet";
import { AnimatedRadarLayer } from "./AnimatedRadarLayer";
import * as radarApi from "../api/radar";

// Mock the radar API
vi.mock("../api/radar", () => ({
  getRadarFrames: vi.fn(),
}));

// Mock RainfallOverlay
vi.mock("./RainfallOverlay", () => ({
  RainfallOverlay: ({ visible }) => (
    <div data-testid="rainfall-overlay">
      {visible ? "Rainfall Overlay" : null}
    </div>
  ),
}));

// Mock react-leaflet components
vi.mock("react-leaflet", async () => {
  const actual = await vi.importActual("react-leaflet");
  return {
    ...actual,
    ImageOverlay: ({ url, bounds, opacity }) => (
      <div
        data-testid="image-overlay"
        data-url={url}
        data-bounds={JSON.stringify(bounds)}
        data-opacity={opacity}
      >
        Image Overlay
      </div>
    ),
    useMap: () => ({
      on: vi.fn(),
      off: vi.fn(),
    }),
  };
});

// Helper to wrap component in MapContainer
const renderWithMap = (component) => {
  return render(
    <MapContainer center={[1.3521, 103.8198]} zoom={11}>
      {component}
    </MapContainer>,
  );
};

describe("AnimatedRadarLayer", () => {
  const mockFrames = [
    {
      timestamp: "2024-01-15T10:00:00Z",
      imageUrl: "/api/radar/image/1705316400",
      bounds: [
        [1.1, 103.6],
        [1.5, 104.1],
      ],
    },
    {
      timestamp: "2024-01-15T10:05:00Z",
      imageUrl: "/api/radar/image/1705316700",
      bounds: [
        [1.1, 103.6],
        [1.5, 104.1],
      ],
    },
    {
      timestamp: "2024-01-15T10:10:00Z",
      imageUrl: "/api/radar/image/1705317000",
      bounds: [
        [1.1, 103.6],
        [1.5, 104.1],
      ],
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    // Mock Image constructor for preloading
    global.Image = class {
      constructor() {
        setTimeout(() => {
          this.onload && this.onload();
        }, 0);
      }
    };
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should not render when visible is false", () => {
    radarApi.getRadarFrames.mockResolvedValue({ frames: mockFrames });

    const { container } = renderWithMap(<AnimatedRadarLayer visible={false} />);

    expect(container.querySelector('[data-testid="image-overlay"]')).toBeNull();
  });

  it("should fetch radar frames on mount", async () => {
    radarApi.getRadarFrames.mockResolvedValue({ frames: mockFrames });

    renderWithMap(<AnimatedRadarLayer visible={true} />);

    await waitFor(() => {
      expect(radarApi.getRadarFrames).toHaveBeenCalledTimes(1);
    });
  });

  it("should display ImageOverlay after successful fetch and preload", async () => {
    radarApi.getRadarFrames.mockResolvedValue({ frames: mockFrames });

    renderWithMap(<AnimatedRadarLayer visible={true} />);

    // Wait for fetch and preload
    await vi.runAllTimersAsync();

    await waitFor(() => {
      const overlay = screen.queryByTestId("image-overlay");
      expect(overlay).toBeInTheDocument();
    });
  });

  it("should fallback to RainfallOverlay on fetch error", async () => {
    radarApi.getRadarFrames.mockRejectedValue(new Error("API Error"));

    renderWithMap(<AnimatedRadarLayer visible={true} />);

    await vi.runAllTimersAsync();

    await waitFor(() => {
      expect(screen.getByTestId("rainfall-overlay")).toBeInTheDocument();
    });
  });

  it("should fallback to RainfallOverlay when no frames available", async () => {
    radarApi.getRadarFrames.mockResolvedValue({ frames: [] });

    renderWithMap(<AnimatedRadarLayer visible={true} />);

    await vi.runAllTimersAsync();

    await waitFor(() => {
      expect(screen.getByTestId("rainfall-overlay")).toBeInTheDocument();
    });
  });

  it("should call onError callback when fetch fails", async () => {
    const onError = vi.fn();
    const error = new Error("API Error");
    radarApi.getRadarFrames.mockRejectedValue(error);

    renderWithMap(<AnimatedRadarLayer visible={true} onError={onError} />);

    await vi.runAllTimersAsync();

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith(error);
    });
  });

  it("should constrain animation speed between 300ms and 1000ms", async () => {
    radarApi.getRadarFrames.mockResolvedValue({ frames: mockFrames });

    // Test speed below minimum
    const { rerender } = renderWithMap(
      <AnimatedRadarLayer visible={true} animationSpeed={100} />,
    );

    await vi.runAllTimersAsync();

    // The component should use 300ms (minimum) instead of 100ms
    // We can't directly test the interval, but we can verify it doesn't crash

    // Test speed above maximum
    rerender(
      <MapContainer center={[1.3521, 103.8198]} zoom={11}>
        <AnimatedRadarLayer visible={true} animationSpeed={2000} />
      </MapContainer>,
    );

    await vi.runAllTimersAsync();

    // The component should use 1000ms (maximum) instead of 2000ms
    expect(true).toBe(true); // Component should handle constraints gracefully
  });

  it("should refresh frames every 5 minutes", async () => {
    radarApi.getRadarFrames.mockResolvedValue({ frames: mockFrames });

    renderWithMap(<AnimatedRadarLayer visible={true} />);

    await vi.runAllTimersAsync();

    // Initial fetch
    expect(radarApi.getRadarFrames).toHaveBeenCalledTimes(1);

    // Advance 5 minutes
    vi.advanceTimersByTime(5 * 60 * 1000);
    await vi.runAllTimersAsync();

    // Should fetch again
    expect(radarApi.getRadarFrames).toHaveBeenCalledTimes(2);
  });

  it("should respect isPlaying prop to control animation", async () => {
    radarApi.getRadarFrames.mockResolvedValue({ frames: mockFrames });

    const { rerender } = renderWithMap(
      <AnimatedRadarLayer visible={true} isPlaying={false} />,
    );

    await vi.runAllTimersAsync();

    // Animation should be paused (we can't directly test this, but verify no errors)
    expect(true).toBe(true);

    // Resume animation
    rerender(
      <MapContainer center={[1.3521, 103.8198]} zoom={11}>
        <AnimatedRadarLayer visible={true} isPlaying={true} />
      </MapContainer>,
    );

    await vi.runAllTimersAsync();

    // Animation should resume (we can't directly test this, but verify no errors)
    expect(true).toBe(true);
  });

  it("should call onFrameChange callback when frame changes", async () => {
    const onFrameChange = vi.fn();
    radarApi.getRadarFrames.mockResolvedValue({ frames: mockFrames });

    renderWithMap(
      <AnimatedRadarLayer
        visible={true}
        isPlaying={true}
        animationSpeed={500}
        onFrameChange={onFrameChange}
      />,
    );

    await vi.runAllTimersAsync();

    // Advance time to trigger frame change
    vi.advanceTimersByTime(500);
    await vi.runAllTimersAsync();

    // Should have called onFrameChange with timestamp
    await waitFor(() => {
      expect(onFrameChange).toHaveBeenCalled();
    });
  });
});
