import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import { ThemeProvider } from "../contexts/ThemeContext";
import { LocationsProvider } from "../hooks/useLocations.jsx";
import { Dashboard, geolocationMessage } from "./Dashboard";

const reading = {
  condition: "Partly Cloudy",
  temperature: 29.6,
  humidity: 70,
  wind_speed: 9,
  pressure: 1008,
  visibility: 10,
  uv_index: 5,
  area: "Ang Mo Kio",
  source: "Cached (api-open.data.gov.sg)",
  timestamp: "2026-10-26T14:05:00+08:00",
};

function jsonResponse(body, ok = true) {
  return Promise.resolve({ ok, status: ok ? 200 : 500, json: async () => body });
}

function mockApi() {
  return vi.spyOn(global, "fetch").mockImplementation((url) => {
    const u = String(url);
    if (u.includes("/weather?")) return jsonResponse(reading);
    if (u.includes("/forecasts/hourly")) return jsonResponse([]);
    if (u.includes("/air-quality")) return jsonResponse({ status: "unavailable" });
    return jsonResponse({});
  });
}

const renderApp = () => render(
  <ThemeProvider now={new Date("2026-10-26T14:10:00+08:00")}>
    <LocationsProvider>
      <Dashboard />
    </LocationsProvider>
  </ThemeProvider>,
);

describe("Dashboard", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState(null, "", "/");
  });

  afterEach(() => vi.restoreAllMocks());

  it("opens on the current reading for central Singapore when nothing is saved", async () => {
    mockApi();
    renderApp();
    const heading = await screen.findByRole("heading", { level: 1, name: "Ang Mo Kio" });
    const panel = heading.closest("section");
    expect(within(panel).getByText("30°")).toBeInTheDocument();
    expect(within(panel).getByText("Partly Cloudy")).toBeInTheDocument();
    expect(within(panel).getByText("Central Singapore")).toBeInTheDocument();
    expect(within(panel).getByText("NEA reading at 2:05 pm")).toBeInTheDocument();
  });

  it("shows a saved place first, with no invented values for missing fields", async () => {
    mockApi();
    localStorage.setItem("lionweather_locations", JSON.stringify([{
      id: "loc_1",
      latitude: 1.3,
      longitude: 103.8,
      weather: { condition: "Fair", temperature: 31, area: "Bishan", source: "Open-Meteo", timestamp: "2026-10-26T14:00:00+08:00" },
      lastFetched: new Date().toISOString(),
    }]));
    renderApp();
    const heading = await screen.findByRole("heading", { level: 1, name: "Bishan" });
    const panel = heading.closest("section");
    expect(within(panel).getByText("Saved place")).toBeInTheDocument();
    expect(within(panel).queryByText("Humidity")).not.toBeInTheDocument();
    expect(within(panel).queryByText("—")).not.toBeInTheDocument();
  });

  it("uses three plain section names and the shared footer", async () => {
    mockApi();
    renderApp();
    const nav = screen.getByRole("navigation", { name: "Sections" });
    expect(within(nav).getAllByRole("button").map((b) => b.textContent)).toEqual(["Now", "Rain map", "Forecast model"]);
    const footer = screen.getByRole("navigation", { name: "Site" });
    expect(footer).toHaveTextContent("© 2026 Haoming Koo");
    expect(within(footer).getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms.html");
    expect(within(footer).getByRole("link", { name: "kooexperience.com" })).toBeInTheDocument();
    await screen.findByRole("heading", { level: 1 });
  });

  it("says so when the browser goes offline", async () => {
    mockApi();
    renderApp();
    await screen.findByRole("heading", { level: 1, name: "Ang Mo Kio" });
    act(() => window.dispatchEvent(new Event("offline")));
    expect(screen.getByText(/You are offline\. The page shows the last reading/)).toBeInTheDocument();
    act(() => window.dispatchEvent(new Event("online")));
    expect(screen.queryByText(/You are offline\. The page shows the last reading/)).not.toBeInTheDocument();
  });
});

describe("geolocationMessage", () => {
  it("explains a blocked location and points to search", () => {
    expect(geolocationMessage({ code: 1 })).toMatch(/blocked/);
    expect(geolocationMessage({ code: 3 })).toMatch(/too long/);
    expect(geolocationMessage({ code: 2 })).toMatch(/Search for a place/);
    expect(geolocationMessage(null)).toBeNull();
  });
});
