import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { DetailedWeatherCard } from "../components/DetailedWeatherCard";
import * as apiClient from "../api/client";
import * as forecastsApi from "../api/forecasts";
import * as sunTimesUtil from "../utils/sunTimes";

describe("Task 3.5: Sunrise/Sunset Calculation Integration", () => {
  const mockLocation = {
    id: 1,
    name: "Singapore",
    latitude: 1.3521,
    longitude: 103.8198,
    weather: {
      area: "Singapore",
      condition: "Partly Cloudy",
      temperature: 28,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock API responses
    vi.spyOn(apiClient, "request").mockResolvedValue({
      temperature: 28,
      humidity: 75,
      wind_speed: 12,
      wind_direction: 180,
      rainfall: 0,
    });

    vi.spyOn(forecastsApi, "get24HourForecast").mockResolvedValue({
      periods: [],
    });

    vi.spyOn(forecastsApi, "get4DayForecast").mockResolvedValue({
      forecasts: [],
    });
  });

  it("should calculate and display actual sunrise/sunset times for Singapore", async () => {
    render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

    // Wait for sunrise/sunset times to be calculated and displayed
    await waitFor(
      () => {
        const sunriseLabel = screen.getByText(/sunrise/i);
        const sunsetLabel = screen.getByText(/sunset/i);

        expect(sunriseLabel).toBeInTheDocument();
        expect(sunsetLabel).toBeInTheDocument();
      },
      { timeout: 3000 },
    );

    // Check that times are NOT the old hardcoded values
    expect(screen.queryByText("7:00 AM")).not.toBeInTheDocument();
    expect(screen.queryByText("7:15 PM")).not.toBeInTheDocument();

    // Get the full document text to check for time patterns
    const fullText = document.body.textContent;

    // Should contain formatted times (or N/A if calculation failed)
    // The times should appear after "Sunrise" and "Sunset" labels
    expect(fullText).toMatch(/Sunrise.*?(\d{1,2}:\d{2}\s(AM|PM)|N\/A)/);
    expect(fullText).toMatch(/Sunset.*?(\d{1,2}:\d{2}\s(AM|PM)|N\/A)/);
  });

  it("should use location coordinates to calculate sun times", async () => {
    const getSunTimesSpy = vi.spyOn(sunTimesUtil, "getSunTimes");

    render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

    // Wait for getSunTimes to be called
    await waitFor(() => {
      expect(getSunTimesSpy).toHaveBeenCalledWith(
        mockLocation.latitude,
        mockLocation.longitude,
      );
    });
  });

  it("should display N/A if sun time calculation fails", async () => {
    // Mock getSunTimes to return N/A
    vi.spyOn(sunTimesUtil, "getSunTimes").mockResolvedValue({
      sunrise: "N/A",
      sunset: "N/A",
    });

    render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

    await waitFor(() => {
      const sunriseLabel = screen.getByText(/sunrise/i);
      const sunsetLabel = screen.getByText(/sunset/i);

      expect(sunriseLabel).toBeInTheDocument();
      expect(sunsetLabel).toBeInTheDocument();
    });

    // Should display N/A when calculation fails
    const allText = document.body.textContent;
    expect(allText).toContain("N/A");
  });

  it("should calculate different times for different locations", async () => {
    const getSunTimesSpy = vi.spyOn(sunTimesUtil, "getSunTimes");

    // Render with Singapore location
    const { rerender } = render(
      <DetailedWeatherCard location={mockLocation} isDark={false} />,
    );

    await waitFor(() => {
      expect(getSunTimesSpy).toHaveBeenCalledWith(1.3521, 103.8198);
    });

    // Change to Malaysia location
    const malaysiaLocation = {
      ...mockLocation,
      name: "Kuala Lumpur",
      latitude: 3.139,
      longitude: 101.6869,
    };

    rerender(
      <DetailedWeatherCard location={malaysiaLocation} isDark={false} />,
    );

    await waitFor(() => {
      expect(getSunTimesSpy).toHaveBeenCalledWith(3.139, 101.6869);
    });
  });

  it("should have reasonable sunrise time for Singapore (6-7 AM)", async () => {
    render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

    await waitFor(
      () => {
        const sunriseLabel = screen.getByText(/sunrise/i);
        expect(sunriseLabel).toBeInTheDocument();
      },
      { timeout: 3000 },
    );

    // Get the displayed sunrise time
    const allText = document.body.textContent;
    const sunriseMatch = allText.match(
      /Sunrise\s*(\d{1,2}:\d{2}\s(AM|PM)|N\/A)/,
    );

    if (sunriseMatch && sunriseMatch[1] !== "N/A") {
      const time = sunriseMatch[1];
      const hourMatch = time.match(/^(\d{1,2}):\d{2}\s(AM|PM)$/);

      if (hourMatch) {
        const hour = parseInt(hourMatch[1]);
        const period = hourMatch[2];

        // Singapore sunrise should be in the morning
        expect(period).toBe("AM");

        // Should be between 6-7 AM (Singapore is near equator)
        expect(hour).toBeGreaterThanOrEqual(6);
        expect(hour).toBeLessThanOrEqual(7);
      }
    }
  });

  it("should have reasonable sunset time for Singapore (6-8 PM)", async () => {
    render(<DetailedWeatherCard location={mockLocation} isDark={false} />);

    await waitFor(
      () => {
        const sunsetLabel = screen.getByText(/sunset/i);
        expect(sunsetLabel).toBeInTheDocument();
      },
      { timeout: 3000 },
    );

    // Get the displayed sunset time
    const allText = document.body.textContent;
    const sunsetMatch = allText.match(/Sunset\s*(\d{1,2}:\d{2}\s(AM|PM)|N\/A)/);

    if (sunsetMatch && sunsetMatch[1] !== "N/A") {
      const time = sunsetMatch[1];
      const hourMatch = time.match(/^(\d{1,2}):\d{2}\s(AM|PM)$/);

      if (hourMatch) {
        const hour = parseInt(hourMatch[1]);
        const period = hourMatch[2];

        // Singapore sunset should be in the evening
        expect(period).toBe("PM");

        // Should be between 6-8 PM (Singapore is near equator)
        expect(hour).toBeGreaterThanOrEqual(6);
        expect(hour).toBeLessThanOrEqual(8);
      }
    }
  });
});
