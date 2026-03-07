import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import RegionalCityList from "./RegionalCityList";
import { ThemeProvider } from "../contexts/ThemeContext";
import * as regionalApi from "../api/regional";

// Mock the regional API
vi.mock("../api/regional");

const mockCities = {
  cities: [
    {
      id: "singapore",
      name: "Singapore",
      country: "Singapore",
      temperature: 28.5,
      condition: "Partly Cloudy",
      humidity: 75,
      windSpeed: 12,
      lastUpdated: "2024-01-15T10:00:00Z",
    },
    {
      id: "kuala-lumpur",
      name: "Kuala Lumpur",
      country: "Malaysia",
      temperature: 27.0,
      condition: "Thunderstorms",
      humidity: 82,
      windSpeed: 8,
      lastUpdated: "2024-01-15T10:00:00Z",
    },
    {
      id: "jakarta",
      name: "Jakarta",
      country: "Indonesia",
      temperature: 29.5,
      condition: "Sunny",
      humidity: 70,
      windSpeed: 10,
      lastUpdated: "2024-01-15T10:00:00Z",
    },
  ],
  cachedAt: "2024-01-15T09:45:00Z",
};

function renderWithTheme(component) {
  return render(<ThemeProvider>{component}</ThemeProvider>);
}

describe("RegionalCityList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("displays loading state during fetch", () => {
    regionalApi.getRegionalCities.mockImplementation(
      () => new Promise(() => {}),
    );

    renderWithTheme(<RegionalCityList />);

    expect(
      screen.getByText(/loading regional weather data/i),
    ).toBeInTheDocument();
  });

  it("displays city data after successful fetch", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    expect(screen.getByText("Kuala Lumpur")).toBeInTheDocument();
    expect(screen.getByText("Jakarta")).toBeInTheDocument();
    expect(screen.getByText("29°C")).toBeInTheDocument();
    expect(screen.getByText("Sunny")).toBeInTheDocument();
  });

  it("displays error message when fetch fails", async () => {
    regionalApi.getRegionalCities.mockRejectedValue(new Error("Network error"));

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(
        screen.getByText(/error loading weather data/i),
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it("displays data freshness timestamp", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText(/updated:/i)).toBeInTheDocument();
    });
  });

  it("calls onCitySelect when city card is clicked", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);
    const onCitySelect = vi.fn();

    renderWithTheme(<RegionalCityList onCitySelect={onCitySelect} />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    const cityCards = screen.getAllByText("Singapore");
    const cityCard = cityCards[0].closest("div[class*='rounded-lg']");
    fireEvent.click(cityCard);

    expect(onCitySelect).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "singapore",
        name: "Singapore",
      }),
    );
  });

  it("displays humidity and wind speed when available", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText(/humidity: 75%/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/wind: 12 km\/h/i)).toBeInTheDocument();
  });

  it("handles empty city list", async () => {
    regionalApi.getRegionalCities.mockResolvedValue({
      cities: [],
      cachedAt: "2024-01-15T09:45:00Z",
    });

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(
        screen.getByText(/no regional weather data available/i),
      ).toBeInTheDocument();
    });
  });

  it("allows retry after error", async () => {
    regionalApi.getRegionalCities
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(
        screen.getByText(/error loading weather data/i),
      ).toBeInTheDocument();
    });

    const retryButton = screen.getByText(/try again/i);
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
      expect(screen.getByText("Kuala Lumpur")).toBeInTheDocument();
    });
  });

  it("displays temperature rounded to nearest integer", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("29°C")).toBeInTheDocument();
    });

    expect(screen.getByText("27°C")).toBeInTheDocument();
  });

  it("displays city country information", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Malaysia")).toBeInTheDocument();
    });

    expect(screen.getByText("Indonesia")).toBeInTheDocument();
  });

  it("displays search input", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(
      /search by city name or country/i,
    );
    expect(searchInput).toBeInTheDocument();
  });

  it("filters cities by name in real-time", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    // Initially all cities are visible
    expect(screen.getAllByText("Singapore").length).toBeGreaterThan(0);
    expect(screen.getByText("Kuala Lumpur")).toBeInTheDocument();
    expect(screen.getByText("Jakarta")).toBeInTheDocument();

    // Type in search input
    const searchInput = screen.getByPlaceholderText(
      /search by city name or country/i,
    );
    fireEvent.change(searchInput, { target: { value: "Jakarta" } });

    // Wait for debounce and filter to apply
    await waitFor(
      () => {
        expect(screen.getByText("Jakarta")).toBeInTheDocument();
        expect(screen.queryByText("Singapore")).not.toBeInTheDocument();
        expect(screen.queryByText("Kuala Lumpur")).not.toBeInTheDocument();
      },
      { timeout: 1000 },
    );
  });

  it("filters cities by country in real-time", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(
      /search by city name or country/i,
    );
    fireEvent.change(searchInput, { target: { value: "Malaysia" } });

    // Wait for debounce and filter to apply
    await waitFor(
      () => {
        expect(screen.getByText("Kuala Lumpur")).toBeInTheDocument();
        expect(screen.queryByText("Singapore")).not.toBeInTheDocument();
        expect(screen.queryByText("Jakarta")).not.toBeInTheDocument();
      },
      { timeout: 1000 },
    );
  });

  it("performs case-insensitive search", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(
      /search by city name or country/i,
    );
    fireEvent.change(searchInput, { target: { value: "JAKARTA" } });

    // Wait for debounce and filter to apply
    await waitFor(
      () => {
        expect(screen.getByText("Jakarta")).toBeInTheDocument();
        expect(screen.queryByText("Singapore")).not.toBeInTheDocument();
      },
      { timeout: 1000 },
    );
  });

  it("shows empty state when no cities match search", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(
      /search by city name or country/i,
    );
    fireEvent.change(searchInput, { target: { value: "NonExistentCity" } });

    // Wait for debounce and empty state to appear
    await waitFor(
      () => {
        expect(
          screen.getByText(/no cities match your search/i),
        ).toBeInTheDocument();
      },
      { timeout: 1000 },
    );
  });

  it("clears search when clear button is clicked", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(
      /search by city name or country/i,
    );
    fireEvent.change(searchInput, { target: { value: "Jakarta" } });

    // Wait for filter to apply
    await waitFor(
      () => {
        expect(screen.getByText("Jakarta")).toBeInTheDocument();
        expect(screen.queryByText("Singapore")).not.toBeInTheDocument();
      },
      { timeout: 1000 },
    );

    // Click clear button
    const clearButton = screen.getByLabelText(/clear search/i);
    fireEvent.click(clearButton);

    // Wait for all cities to reappear
    await waitFor(
      () => {
        expect(screen.getAllByText("Singapore").length).toBeGreaterThan(0);
        expect(screen.getByText("Kuala Lumpur")).toBeInTheDocument();
        expect(screen.getByText("Jakarta")).toBeInTheDocument();
      },
      { timeout: 1000 },
    );
  });

  it("debounces search input with 300ms delay", async () => {
    regionalApi.getRegionalCities.mockResolvedValue(mockCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(
      /search by city name or country/i,
    );

    // Type multiple characters quickly
    fireEvent.change(searchInput, { target: { value: "J" } });
    fireEvent.change(searchInput, { target: { value: "Ja" } });
    fireEvent.change(searchInput, { target: { value: "Jak" } });

    // Immediately after typing, all cities should still be visible
    expect(screen.getAllByText("Singapore").length).toBeGreaterThan(0);
    expect(screen.getByText("Kuala Lumpur")).toBeInTheDocument();
    expect(screen.getByText("Jakarta")).toBeInTheDocument();

    // After debounce delay, filter should apply
    await waitFor(
      () => {
        expect(screen.getByText("Jakarta")).toBeInTheDocument();
        expect(screen.queryByText("Singapore")).not.toBeInTheDocument();
        expect(screen.queryByText("Kuala Lumpur")).not.toBeInTheDocument();
      },
      { timeout: 1000 },
    );
  });

  it("sorts cities alphabetically by name by default", async () => {
    const unsortedCities = {
      cities: [
        {
          id: "singapore",
          name: "Singapore",
          country: "Singapore",
          temperature: 28.5,
          condition: "Partly Cloudy",
          humidity: 75,
          windSpeed: 12,
          lastUpdated: "2024-01-15T10:00:00Z",
        },
        {
          id: "jakarta",
          name: "Jakarta",
          country: "Indonesia",
          temperature: 29.5,
          condition: "Sunny",
          humidity: 70,
          windSpeed: 10,
          lastUpdated: "2024-01-15T10:00:00Z",
        },
        {
          id: "kuala-lumpur",
          name: "Kuala Lumpur",
          country: "Malaysia",
          temperature: 27.0,
          condition: "Thunderstorms",
          humidity: 82,
          windSpeed: 8,
          lastUpdated: "2024-01-15T10:00:00Z",
        },
      ],
      cachedAt: "2024-01-15T09:45:00Z",
    };

    regionalApi.getRegionalCities.mockResolvedValue(unsortedCities);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    // Get all city name elements
    const cityCards = screen.getAllByRole("heading", { level: 3 });
    const cityNames = cityCards.map((card) => card.textContent);

    // Verify alphabetical order: Jakarta, Kuala Lumpur, Singapore
    expect(cityNames).toEqual(["Jakarta", "Kuala Lumpur", "Singapore"]);
  });

  it("maintains alphabetical sorting after filtering", async () => {
    const citiesWithMultipleMatches = {
      cities: [
        {
          id: "singapore",
          name: "Singapore",
          country: "Singapore",
          temperature: 28.5,
          condition: "Partly Cloudy",
          humidity: 75,
          windSpeed: 12,
          lastUpdated: "2024-01-15T10:00:00Z",
        },
        {
          id: "surabaya",
          name: "Surabaya",
          country: "Indonesia",
          temperature: 30.0,
          condition: "Sunny",
          humidity: 68,
          windSpeed: 15,
          lastUpdated: "2024-01-15T10:00:00Z",
        },
        {
          id: "semarang",
          name: "Semarang",
          country: "Indonesia",
          temperature: 29.0,
          condition: "Cloudy",
          humidity: 72,
          windSpeed: 11,
          lastUpdated: "2024-01-15T10:00:00Z",
        },
        {
          id: "kuala-lumpur",
          name: "Kuala Lumpur",
          country: "Malaysia",
          temperature: 27.0,
          condition: "Thunderstorms",
          humidity: 82,
          windSpeed: 8,
          lastUpdated: "2024-01-15T10:00:00Z",
        },
      ],
      cachedAt: "2024-01-15T09:45:00Z",
    };

    regionalApi.getRegionalCities.mockResolvedValue(citiesWithMultipleMatches);

    renderWithTheme(<RegionalCityList />);

    await waitFor(() => {
      expect(screen.getByText("Regional Weather")).toBeInTheDocument();
    });

    // Filter by 'Indonesia' to get Surabaya and Semarang
    const searchInput = screen.getByPlaceholderText(
      /search by city name or country/i,
    );
    fireEvent.change(searchInput, { target: { value: "Indonesia" } });

    // Wait for debounce and filter to apply
    await waitFor(
      () => {
        const cityCards = screen.getAllByRole("heading", { level: 3 });
        const cityNames = cityCards.map((card) => card.textContent);

        // Verify alphabetical order: Semarang, Surabaya
        expect(cityNames).toEqual(["Semarang", "Surabaya"]);
      },
      { timeout: 1000 },
    );
  });
});
