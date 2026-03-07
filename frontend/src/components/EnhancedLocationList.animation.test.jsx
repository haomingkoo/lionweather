import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { EnhancedLocationList } from "./EnhancedLocationList";
import { LocationsProvider } from "../hooks/useLocations";
import * as useLocationsHook from "../hooks/useLocations";

/**
 * Animation Verification Tests for EnhancedLocationList Component
 * Feature: apple-weather-ui-redesign
 * Task 4.3: Verify card animations and transitions
 * Requirement 5.1: WHEN a Location_Card appears, THE Location_Card SHALL fade in over 300 milliseconds
 *
 * This test suite verifies that:
 * 1. Cards fade in over 300ms (defined in CSS as 0.3s)
 * 2. Cards have staggered delays (50ms per card)
 * 3. Smooth transitions on state changes (300ms duration)
 */

describe("EnhancedLocationList - Animation Requirements Verification", () => {
  const mockLocation = {
    id: 1,
    latitude: 1.3521,
    longitude: 103.8198,
    weather: {
      area: "Singapore",
      condition: "Partly Cloudy",
      temperature: "29",
      valid_period_text: "Today",
      observed_at: new Date().toISOString(),
      source: "weather.gov.sg",
    },
  };

  beforeEach(() => {
    vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
      locations: [mockLocation],
      isLoading: false,
      error: null,
    });

    vi.spyOn(useLocationsHook, "useRefreshLocation").mockReturnValue({
      refresh: vi.fn(),
      isPending: false,
      refreshingId: null,
      error: null,
    });

    vi.spyOn(useLocationsHook, "useDeleteLocation").mockReturnValue({
      deleteLocation: vi.fn(),
      isPending: false,
    });
  });

  describe("Requirement 5.1: 300ms Fade-in Animation", () => {
    it("should apply animate-fade-in class which triggers 300ms fade-in", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const card = container.querySelector("article");
      expect(card).not.toBeNull();

      // Verify the animate-fade-in class is present
      // This class is defined in index.css as: animation: fadeIn 0.3s ease-out forwards;
      expect(card.className).toContain("animate-fade-in");
    });

    it("should verify CSS animation properties are correctly applied", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const card = container.querySelector("article");

      // The animate-fade-in class should be present
      // CSS definition: animation: fadeIn 0.3s ease-out forwards;
      // This ensures:
      // - Duration: 300ms (0.3s)
      // - Timing: ease-out
      // - Fill mode: forwards (maintains final state)
      expect(card.className).toContain("animate-fade-in");
    });
  });

  describe("Requirement 5.1: Staggered Animation Delays", () => {
    it("should apply 50ms staggered delays to multiple cards", () => {
      const mockLocations = [
        { ...mockLocation, id: 1 },
        { ...mockLocation, id: 2, latitude: 1.4, longitude: 103.9 },
        { ...mockLocation, id: 3, latitude: 1.3, longitude: 103.7 },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const cards = container.querySelectorAll("article");
      expect(cards.length).toBe(3);

      // Verify staggered delays: 0ms, 50ms, 100ms
      expect(cards[0].style.animationDelay).toBe("0ms");
      expect(cards[1].style.animationDelay).toBe("50ms");
      expect(cards[2].style.animationDelay).toBe("100ms");
    });

    it("should calculate correct delays for 10 cards", () => {
      const mockLocations = Array.from({ length: 10 }, (_, i) => ({
        ...mockLocation,
        id: i + 1,
        latitude: 1.3 + i * 0.01,
        longitude: 103.8 + i * 0.01,
      }));

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const cards = container.querySelectorAll("article");
      expect(cards.length).toBe(10);

      // Verify delays: 0ms, 50ms, 100ms, ..., 450ms
      cards.forEach((card, index) => {
        const expectedDelay = index * 50;
        expect(card.style.animationDelay).toBe(`${expectedDelay}ms`);
      });
    });

    it("should maintain stagger pattern regardless of location data", () => {
      const mockLocations = [
        {
          ...mockLocation,
          id: 100,
          weather: { ...mockLocation.weather, condition: "Sunny" },
        },
        {
          ...mockLocation,
          id: 200,
          weather: { ...mockLocation.weather, condition: "Rainy" },
        },
        {
          ...mockLocation,
          id: 300,
          weather: { ...mockLocation.weather, condition: "Cloudy" },
        },
      ];

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const cards = container.querySelectorAll("article");

      // Stagger pattern should be based on array index, not location data
      expect(cards[0].style.animationDelay).toBe("0ms");
      expect(cards[1].style.animationDelay).toBe("50ms");
      expect(cards[2].style.animationDelay).toBe("100ms");
    });
  });

  describe("Requirement 5.1: Smooth Transitions on State Changes", () => {
    it("should have transition-all for smooth state changes", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const card = container.querySelector("article");
      expect(card.className).toContain("transition-all");
    });

    it("should have 300ms duration for transitions", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const card = container.querySelector("article");
      expect(card.className).toContain("duration-300");
    });

    it("should apply transitions to all cards", () => {
      const mockLocations = Array.from({ length: 5 }, (_, i) => ({
        ...mockLocation,
        id: i + 1,
      }));

      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: mockLocations,
        isLoading: false,
        error: null,
      });

      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const cards = container.querySelectorAll("article");

      cards.forEach((card) => {
        expect(card.className).toContain("transition-all");
        expect(card.className).toContain("duration-300");
      });
    });
  });

  describe("Complete Animation Package Verification", () => {
    it("should have all animation classes together", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const card = container.querySelector("article");
      const className = card.className;

      // Verify all required animation classes
      expect(className).toContain("animate-fade-in"); // 300ms fade-in
      expect(className).toContain("transition-all"); // Smooth transitions
      expect(className).toContain("duration-300"); // 300ms transition duration
    });

    it("should verify animation delay is set via inline style", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const card = container.querySelector("article");

      // Animation delay should be set via inline style, not class
      expect(card.style.animationDelay).toBeDefined();
      expect(card.style.animationDelay).toBe("0ms");
    });

    it("should work correctly in both light and dark themes", () => {
      const themes = [
        { isDark: false, name: "light" },
        { isDark: true, name: "dark" },
      ];

      themes.forEach(({ isDark, name }) => {
        const { container } = render(
          <LocationsProvider>
            <EnhancedLocationList isDark={isDark} />
          </LocationsProvider>,
        );

        const card = container.querySelector("article");

        // Animation classes should be present regardless of theme
        expect(card.className).toContain("animate-fade-in");
        expect(card.className).toContain("transition-all");
        expect(card.className).toContain("duration-300");
        expect(card.style.animationDelay).toBe("0ms");
      });
    });
  });

  describe("Edge Cases", () => {
    it("should handle single location correctly", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const cards = container.querySelectorAll("article");
      expect(cards.length).toBe(1);
      expect(cards[0].style.animationDelay).toBe("0ms");
    });

    it("should handle empty locations array (no cards to animate)", () => {
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [],
        isLoading: false,
        error: null,
      });

      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const cards = container.querySelectorAll("article");
      expect(cards.length).toBe(0);
    });

    it("should not apply animation classes to loading state", () => {
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [],
        isLoading: true,
        error: null,
      });

      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Loading state should not have article elements
      const cards = container.querySelectorAll("article");
      expect(cards.length).toBe(0);
    });

    it("should not apply animation classes to error state", () => {
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [],
        isLoading: false,
        error: new Error("Test error"),
      });

      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      // Error state should not have article elements
      const cards = container.querySelectorAll("article");
      expect(cards.length).toBe(0);
    });
  });
});
