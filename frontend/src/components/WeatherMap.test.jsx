import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen } from "@testing-library/react";

vi.mock("../api/rain", () => ({ getRainGauges: vi.fn() }));
vi.mock("../hooks/useLocations.jsx", () => ({
  useLocations: () => ({ locations: [], isLoading: false, error: null }),
  useCreateLocation: () => ({ create: vi.fn(), isPending: false, error: null }),
  useRefreshLocation: () => ({ refresh: vi.fn(), isPending: false }),
  useDeleteLocation: () => ({ deleteLocation: vi.fn(), isPending: false }),
}));
vi.mock("../contexts/ThemeContext", () => ({ useTheme: () => ({ theme: "light" }) }));
vi.mock("react-leaflet", () => {
  const Pass = ({ children }) => <div>{children}</div>;
  return { MapContainer: Pass, TileLayer: () => null, Marker: Pass, Popup: Pass, Tooltip: Pass, CircleMarker: Pass, ImageOverlay: () => null, useMapEvents: () => null };
});

import { getRainGauges } from "../api/rain";
import { WeatherMap } from "./WeatherMap";

const times = Array.from({ length: 25 }, (_, i) => new Date(Date.UTC(2026, 9, 26, 13, 40 + i * 5)).toISOString());
const stations = Array.from({ length: 89 }, (_, i) => ({ id: `S${i}`, name: `Gauge ${i}`, lat: 1.3 + (i % 9) * 0.02, lng: 103.65 + Math.floor(i / 9) * 0.04 }));
const dry = { times, stations, values: Object.fromEntries(stations.map((s) => [s.id, times.map(() => 0)])), wind: null };

beforeEach(() => {
  getRainGauges.mockReset();
});
afterEach(() => vi.useRealTimers());

describe("rain map states", () => {
  it("shows a dry island as no rain, never as an error", async () => {
    getRainGauges.mockResolvedValue(dry);
    render(<WeatherMap />);
    expect(await screen.findByText(/No rain right now\. 89 NEA gauges, checked/)).toBeInTheDocument();
    expect(screen.queryByText(/could not load/)).not.toBeInTheDocument();
  });

  it("retries a failed load before showing the error, then offers a retry", async () => {
    vi.useFakeTimers();
    getRainGauges.mockRejectedValue(new Error("Request failed with status 503"));
    render(<WeatherMap />);
    await act(async () => {});
    expect(screen.queryByText(/could not load/)).not.toBeInTheDocument();
    for (const ms of [3000, 10000, 30000]) await act(async () => vi.advanceTimersByTimeAsync(ms));
    expect(getRainGauges).toHaveBeenCalledTimes(4);
    expect(screen.getByText(/Rain readings could not load/)).toBeInTheDocument();
    getRainGauges.mockResolvedValue(dry);
    await act(async () => screen.getByRole("button", { name: "Try again" }).click());
    await act(async () => {});
    expect(screen.getByText(/No rain right now/)).toBeInTheDocument();
  });

  it("recovers on a retry after a transient failure without showing an error", async () => {
    vi.useFakeTimers();
    getRainGauges.mockRejectedValueOnce(new Error("503")).mockResolvedValue(dry);
    render(<WeatherMap />);
    await act(async () => vi.advanceTimersByTimeAsync(3000));
    expect(screen.getByText(/No rain right now/)).toBeInTheDocument();
  });
});
