import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { LocationsProvider, useLocations } from "./useLocations.jsx";

const wrapper = ({ children }) => <LocationsProvider>{children}</LocationsProvider>;

describe("live location toggle", () => {
  let getCurrentPosition;

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    getCurrentPosition = vi.fn();
    Object.defineProperty(navigator, "geolocation", {
      value: { getCurrentPosition },
      configurable: true,
    });
    vi.spyOn(global, "fetch").mockResolvedValue({ ok: false, json: async () => ({}) });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("re-reads GPS every 15 minutes while on", () => {
    localStorage.setItem("geolocation_permission", "granted");
    renderHook(() => useLocations(), { wrapper });

    act(() => vi.advanceTimersByTime(15 * 60 * 1000));

    expect(getCurrentPosition).toHaveBeenCalledTimes(2);
  });

  it("stops GPS re-reads and clears the flag when turned off", () => {
    localStorage.setItem("geolocation_permission", "granted");
    const { result } = renderHook(() => useLocations(), { wrapper });
    getCurrentPosition.mockClear();

    act(() => result.current.setLiveLocationEnabled(false));
    act(() => vi.advanceTimersByTime(30 * 60 * 1000));

    expect(getCurrentPosition).not.toHaveBeenCalled();
    expect(localStorage.getItem("geolocation_permission")).toBeNull();
    expect(result.current.liveLocationEnabled).toBe(false);
  });

  it("does not read GPS when live location was never enabled", () => {
    const { result } = renderHook(() => useLocations(), { wrapper });

    act(() => vi.advanceTimersByTime(15 * 60 * 1000));

    expect(getCurrentPosition).not.toHaveBeenCalled();
    expect(result.current.liveLocationEnabled).toBe(false);
  });
});
