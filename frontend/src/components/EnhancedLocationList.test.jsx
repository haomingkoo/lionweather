import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { EnhancedLocationList } from "./EnhancedLocationList";
import { LocationsProvider } from "../hooks/useLocations";
import * as useLocationsHook from "../hooks/useLocations";

/**
 * Unit Tests for EnhancedLocationList Component
 * Feature: apple-weather-ui-redesign
 * Task 4.2: Verify card hover effects
 * Task 4.3: Verify card animations and transitions
 */

describe("EnhancedLocationList - Hover Effects", () => {
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
    // Mock the useLocations hook
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

  /**
   * Requirement 4.7: WHEN the user hovers over a Location_Card,
   * THE Location_Card SHALL increase its background opacity to 30%
   */
  it("should have hover:bg-white/30 class for 30% opacity on hover", () => {
    const { container } = render(
      <LocationsProvider>
        <EnhancedLocationList isDark={false} />
      </LocationsProvider>,
    );

    // Find the location card article element
    const card = container.querySelector("article");
    expect(card).not.toBeNull();

    // Verify the card has the hover:bg-white/30 class
    const className = card.className;
    expect(className).toContain("hover:bg-white/30");

    // Verify base background opacity is 25%
    expect(className).toContain("bg-white/25");
  });

  /**
   * Task 4.2: Verify scale animation to 102%
   */
  it("should have hover:scale-[1.02] class for 102% scale on hover", () => {
    const { container } = render(
      <LocationsProvider>
        <EnhancedLocationList isDark={false} />
      </LocationsProvider>,
    );

    // Find the location card article element
    const card = container.querySelector("article");
    expect(card).not.toBeNull();

    // Verify the card has the hover:scale-[1.02] class
    const className = card.className;
    expect(className).toContain("hover:scale-[1.02]");
  });

  /**
   * Verify smooth transitions are applied
   */
  it("should have transition-all duration-300 for smooth hover effects", () => {
    const { container } = render(
      <LocationsProvider>
        <EnhancedLocationList isDark={false} />
      </LocationsProvider>,
    );

    // Find the location card article element
    const card = container.querySelector("article");
    expect(card).not.toBeNull();

    // Verify the card has transition classes
    const className = card.className;
    expect(className).toContain("transition-all");
    expect(className).toContain("duration-300");
  });

  /**
   * Verify all hover effects are present together
   */
  it("should have all required hover effect classes combined", () => {
    const { container } = render(
      <LocationsProvider>
        <EnhancedLocationList isDark={false} />
      </LocationsProvider>,
    );

    // Find the location card article element
    const card = container.querySelector("article");
    expect(card).not.toBeNull();

    const className = card.className;

    // Verify all required classes are present
    expect(className).toContain("bg-white/25"); // Base opacity 25%
    expect(className).toContain("hover:bg-white/30"); // Hover opacity 30%
    expect(className).toContain("hover:scale-[1.02]"); // Hover scale 102%
    expect(className).toContain("transition-all"); // Smooth transitions
    expect(className).toContain("duration-300"); // 300ms duration
  });

  /**
   * Verify hover effects work with multiple locations
   */
  it("should apply hover effects to all location cards", () => {
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

    // Find all location card article elements
    const cards = container.querySelectorAll("article");
    expect(cards.length).toBe(3);

    // Verify each card has the hover effects
    cards.forEach((card) => {
      const className = card.className;
      expect(className).toContain("hover:bg-white/30");
      expect(className).toContain("hover:scale-[1.02]");
      expect(className).toContain("transition-all");
    });
  });

  /**
   * Verify hover effects work in both light and dark themes
   */
  it("should apply hover effects regardless of theme", () => {
    const themes = [true, false]; // isDark values

    themes.forEach((isDark) => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={isDark} />
        </LocationsProvider>,
      );

      const card = container.querySelector("article");
      expect(card).not.toBeNull();

      const className = card.className;
      expect(className).toContain("hover:bg-white/30");
      expect(className).toContain("hover:scale-[1.02]");
    });
  });
});

/**
 * Task 4.3: Verify card animations and transitions
 * Requirement 5.1: WHEN a Location_Card appears, THE Location_Card SHALL fade in over 300 milliseconds
 */
describe("EnhancedLocationList - Card Animations", () => {
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
    // Mock the useLocations hook
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

  /**
   * Requirement 5.1: Cards fade in over 300ms
   */
  it("should have animate-fade-in class for 300ms fade-in animation", () => {
    const { container } = render(
      <LocationsProvider>
        <EnhancedLocationList isDark={false} />
      </LocationsProvider>,
    );

    const card = container.querySelector("article");
    expect(card).not.toBeNull();

    // Verify the card has the animate-fade-in class
    const className = card.className;
    expect(className).toContain("animate-fade-in");
  });

  /**
   * Requirement 5.1: Cards have staggered delays
   */
  it("should apply staggered animation delays to multiple cards", () => {
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

    // Verify each card has a staggered animation delay
    cards.forEach((card, index) => {
      const style = card.style;
      const expectedDelay = `${index * 50}ms`;
      expect(style.animationDelay).toBe(expectedDelay);
    });
  });

  /**
   * Verify first card has 0ms delay
   */
  it("should have 0ms delay for the first card", () => {
    const { container } = render(
      <LocationsProvider>
        <EnhancedLocationList isDark={false} />
      </LocationsProvider>,
    );

    const firstCard = container.querySelector("article");
    expect(firstCard).not.toBeNull();
    expect(firstCard.style.animationDelay).toBe("0ms");
  });

  /**
   * Verify second card has 50ms delay
   */
  it("should have 50ms delay for the second card", () => {
    const mockLocations = [
      { ...mockLocation, id: 1 },
      { ...mockLocation, id: 2, latitude: 1.4, longitude: 103.9 },
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
    expect(cards[1].style.animationDelay).toBe("50ms");
  });

  /**
   * Verify smooth transitions on state changes
   */
  it("should have transition-all duration-300 for smooth state transitions", () => {
    const { container } = render(
      <LocationsProvider>
        <EnhancedLocationList isDark={false} />
      </LocationsProvider>,
    );

    const card = container.querySelector("article");
    expect(card).not.toBeNull();

    const className = card.className;
    expect(className).toContain("transition-all");
    expect(className).toContain("duration-300");
  });

  /**
   * Verify all animation classes are present together
   */
  it("should have all required animation classes combined", () => {
    const { container } = render(
      <LocationsProvider>
        <EnhancedLocationList isDark={false} />
      </LocationsProvider>,
    );

    const card = container.querySelector("article");
    expect(card).not.toBeNull();

    const className = card.className;

    // Verify all required animation classes
    expect(className).toContain("animate-fade-in"); // Fade-in animation
    expect(className).toContain("transition-all"); // Smooth transitions
    expect(className).toContain("duration-300"); // 300ms duration
  });

  /**
   * Verify animation delay calculation for multiple cards
   */
  it("should calculate animation delays correctly for 5 cards", () => {
    const mockLocations = Array.from({ length: 5 }, (_, i) => ({
      ...mockLocation,
      id: i + 1,
      latitude: 1.3 + i * 0.1,
      longitude: 103.8 + i * 0.1,
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
    expect(cards.length).toBe(5);

    // Verify delays: 0ms, 50ms, 100ms, 150ms, 200ms
    const expectedDelays = [0, 50, 100, 150, 200];
    cards.forEach((card, index) => {
      expect(card.style.animationDelay).toBe(`${expectedDelays[index]}ms`);
    });
  });
});

/**
 * Task 4.4: Verify loading, error, and empty states styling
 * Requirements: 12.1, 12.2, 12.5
 */
describe("EnhancedLocationList - Loading, Error, and Empty States", () => {
  beforeEach(() => {
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

  /**
   * Requirement 12.1: WHEN data is loading, THE Weather_App SHALL display
   * a loading indicator with glassmorphism styling
   */
  describe("Loading State", () => {
    beforeEach(() => {
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [],
        isLoading: true,
        error: null,
      });
    });

    it("should display loading message", () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      expect(screen.getByText("Loading locations...")).toBeInTheDocument();
    });

    it("should use glassmorphism styling with translucent background", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const loadingCard = container.querySelector(".bg-white\\/30");
      expect(loadingCard).not.toBeNull();
      expect(loadingCard.className).toContain("bg-white/30");
    });

    it("should have backdrop blur effect", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const loadingCard = container.querySelector(".backdrop-blur-xl");
      expect(loadingCard).not.toBeNull();
      expect(loadingCard.className).toContain("backdrop-blur-xl");
    });

    it("should have white border with opacity", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const loadingCard = container.querySelector(".border-white\\/40");
      expect(loadingCard).not.toBeNull();
      expect(loadingCard.className).toContain("border-white/40");
    });

    it("should have rounded corners", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const loadingCard = container.querySelector(".rounded-3xl");
      expect(loadingCard).not.toBeNull();
      expect(loadingCard.className).toContain("rounded-3xl");
    });

    it("should use theme-appropriate text color for light theme", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const loadingText = screen.getByText("Loading locations...");
      expect(loadingText.className).toContain("text-slate-900");
    });

    it("should use theme-appropriate text color for dark theme", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={true} />
        </LocationsProvider>,
      );

      const loadingText = screen.getByText("Loading locations...");
      expect(loadingText.className).toContain("text-white");
    });

    it("should have all glassmorphism classes combined", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const loadingCard = screen
        .getByText("Loading locations...")
        .closest("div");
      const className = loadingCard.className;

      expect(className).toContain("bg-white/30");
      expect(className).toContain("backdrop-blur-xl");
      expect(className).toContain("border-white/40");
      expect(className).toContain("rounded-3xl");
      expect(className).toContain("shadow-2xl");
    });
  });

  /**
   * Requirement 12.2: WHEN an error occurs, THE Weather_App SHALL display
   * an error message in a translucent card with backdrop blur
   */
  describe("Error State", () => {
    const mockError = new Error("Failed to fetch locations");

    beforeEach(() => {
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [],
        isLoading: false,
        error: mockError,
      });
    });

    it("should display error message", () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      expect(screen.getByText("Failed to fetch locations")).toBeInTheDocument();
    });

    it("should use red-tinted glassmorphism styling", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const errorCard = container.querySelector(".bg-red-500\\/30");
      expect(errorCard).not.toBeNull();
      expect(errorCard.className).toContain("bg-red-500/30");
    });

    it("should have backdrop blur effect", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const errorCard = container.querySelector(".backdrop-blur-xl");
      expect(errorCard).not.toBeNull();
      expect(errorCard.className).toContain("backdrop-blur-xl");
    });

    it("should have red border with opacity", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const errorCard = container.querySelector(".border-red-400\\/40");
      expect(errorCard).not.toBeNull();
      expect(errorCard.className).toContain("border-red-400/40");
    });

    it("should have rounded corners", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const errorCard = container.querySelector(".rounded-3xl");
      expect(errorCard).not.toBeNull();
      expect(errorCard.className).toContain("rounded-3xl");
    });

    it("should use light text color for error messages", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const errorText = screen.getByText("Failed to fetch locations");
      expect(errorText.className).toContain("text-red-");
    });

    it("should have all error state glassmorphism classes combined", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const errorCard = screen
        .getByText("Failed to fetch locations")
        .closest("div");
      const className = errorCard.className;

      expect(className).toContain("bg-red-500/30");
      expect(className).toContain("backdrop-blur-xl");
      expect(className).toContain("border-red-400/40");
      expect(className).toContain("rounded-3xl");
      expect(className).toContain("shadow-2xl");
    });
  });

  /**
   * Requirement 12.5: WHEN the Weather_App displays "No locations yet",
   * THE message SHALL appear in a glassmorphism-styled card
   */
  describe("Empty State", () => {
    beforeEach(() => {
      vi.spyOn(useLocationsHook, "useLocations").mockReturnValue({
        locations: [],
        isLoading: false,
        error: null,
      });
    });

    it("should display friendly empty state message", () => {
      render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      expect(screen.getByText("No locations yet")).toBeInTheDocument();
      expect(
        screen.getByText("Add your first location above to get started"),
      ).toBeInTheDocument();
    });

    it("should use glassmorphism styling with translucent background", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const emptyCard = container.querySelector(".bg-white\\/30");
      expect(emptyCard).not.toBeNull();
      expect(emptyCard.className).toContain("bg-white/30");
    });

    it("should have backdrop blur effect", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const emptyCard = container.querySelector(".backdrop-blur-xl");
      expect(emptyCard).not.toBeNull();
      expect(emptyCard.className).toContain("backdrop-blur-xl");
    });

    it("should have white border with opacity", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const emptyCard = container.querySelector(".border-white\\/40");
      expect(emptyCard).not.toBeNull();
      expect(emptyCard.className).toContain("border-white/40");
    });

    it("should have rounded corners", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const emptyCard = container.querySelector(".rounded-3xl");
      expect(emptyCard).not.toBeNull();
      expect(emptyCard.className).toContain("rounded-3xl");
    });

    it("should use theme-appropriate text color for light theme", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const primaryText = screen.getByText("No locations yet");
      expect(primaryText.className).toContain("text-slate-900");

      const secondaryText = screen.getByText(
        "Add your first location above to get started",
      );
      expect(secondaryText.className).toContain("text-slate-700");
    });

    it("should use theme-appropriate text color for dark theme", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={true} />
        </LocationsProvider>,
      );

      const primaryText = screen.getByText("No locations yet");
      expect(primaryText.className).toContain("text-white");

      const secondaryText = screen.getByText(
        "Add your first location above to get started",
      );
      expect(secondaryText.className).toContain("text-white/80");
    });

    it("should have all glassmorphism classes combined", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const emptyCard = screen.getByText("No locations yet").closest("div");
      const className = emptyCard.className;

      expect(className).toContain("bg-white/30");
      expect(className).toContain("backdrop-blur-xl");
      expect(className).toContain("border-white/40");
      expect(className).toContain("rounded-3xl");
      expect(className).toContain("shadow-2xl");
    });

    it("should center the empty state message", () => {
      const { container } = render(
        <LocationsProvider>
          <EnhancedLocationList isDark={false} />
        </LocationsProvider>,
      );

      const emptyCard = screen.getByText("No locations yet").closest("div");
      expect(emptyCard.className).toContain("text-center");
    });
  });

  /**
   * Verify all three states use consistent glassmorphism pattern
   */
  describe("Glassmorphism Consistency", () => {
    it("should use consistent rounded corners across all states", () => {
      const states = [
        { isLoading: true, error: null, locations: [] },
        {
          isLoading: false,
          error: new Error("Test error"),
          locations: [],
        },
        { isLoading: false, error: null, locations: [] },
      ];

      states.forEach((state) => {
        vi.spyOn(useLocationsHook, "useLocations").mockReturnValue(state);

        const { container } = render(
          <LocationsProvider>
            <EnhancedLocationList isDark={false} />
          </LocationsProvider>,
        );

        const card = container.querySelector(".rounded-3xl");
        expect(card).not.toBeNull();
      });
    });

    it("should use backdrop blur across all states", () => {
      const states = [
        { isLoading: true, error: null, locations: [] },
        {
          isLoading: false,
          error: new Error("Test error"),
          locations: [],
        },
        { isLoading: false, error: null, locations: [] },
      ];

      states.forEach((state) => {
        vi.spyOn(useLocationsHook, "useLocations").mockReturnValue(state);

        const { container } = render(
          <LocationsProvider>
            <EnhancedLocationList isDark={false} />
          </LocationsProvider>,
        );

        const card = container.querySelector(".backdrop-blur-xl");
        expect(card).not.toBeNull();
      });
    });

    it("should use shadow effect across all states", () => {
      const states = [
        { isLoading: true, error: null, locations: [] },
        {
          isLoading: false,
          error: new Error("Test error"),
          locations: [],
        },
        { isLoading: false, error: null, locations: [] },
      ];

      states.forEach((state) => {
        vi.spyOn(useLocationsHook, "useLocations").mockReturnValue(state);

        const { container } = render(
          <LocationsProvider>
            <EnhancedLocationList isDark={false} />
          </LocationsProvider>,
        );

        const card = container.querySelector(".shadow-2xl");
        expect(card).not.toBeNull();
      });
    });
  });
});
