import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AirQualityCard } from "./AirQualityCard";
import * as api from "../api/airQuality";
import { nearestRegion, psiSeries, formatSgtTime } from "../utils/airQuality";

vi.mock("../api/airQuality");

const band = (key, label, advice = "Normal activities") => ({ key, label, advice });

const regions = [
  { region: "north", lat: 1.41803, lng: 103.82, psi_24h: 97, psi_band: band("moderate", "Moderate"), pm25_1h: 22, pm25_band: band("normal", "Normal") },
  { region: "south", lat: 1.29587, lng: 103.82, psi_24h: 96, psi_band: band("moderate", "Moderate"), pm25_1h: 30, pm25_band: band("normal", "Normal") },
  { region: "east", lat: 1.35735, lng: 103.94, psi_24h: 105, psi_band: band("unhealthy", "Unhealthy", "Reduce prolonged or strenuous outdoor physical exertion"), pm25_1h: 26, pm25_band: band("normal", "Normal") },
  { region: "west", lat: 1.35735, lng: 103.7, psi_24h: 119, psi_band: band("unhealthy", "Unhealthy", "Reduce prolonged or strenuous outdoor physical exertion"), pm25_1h: 60, pm25_band: band("elevated", "Elevated", "Reduce strenuous outdoor activities for the next hour") },
  { region: "central", lat: 1.35735, lng: 103.82, psi_24h: 102, psi_band: band("unhealthy", "Unhealthy", "Reduce prolonged or strenuous outdoor physical exertion"), pm25_1h: 27, pm25_band: band("normal", "Normal") },
];

const okLatest = {
  status: "ok",
  observed_at: "2026-10-25T15:00:00+08:00",
  last_good_observed_at: "2026-10-25T15:00:00+08:00",
  regions,
  national: { psi_24h_min: 96, psi_24h_max: 119, psi_band: regions[3].psi_band, pm25_1h_max: 60, pm25_band: regions[3].pm25_band },
  links: { haze: "https://www.haze.gov.sg/", nea: "https://www.nea.gov.sg/" },
};

const history = {
  points: [
    { timestamp: "2026-10-25T13:00:00+08:00", regions: { west: { psi_24h: 110 }, north: { psi_24h: 90 } } },
    { timestamp: "2026-10-25T14:00:00+08:00", regions: { west: { psi_24h: 115 }, north: { psi_24h: 95 } } },
  ],
};

beforeEach(() => {
  vi.mocked(api.getAirQualityHistory).mockResolvedValue(history);
});

describe("AirQualityCard", () => {
  it("shows national PSI range, band label and update time with no saved location", async () => {
    vi.mocked(api.getAirQualityLatest).mockResolvedValue(okLatest);

    render(<AirQualityCard />);

    expect(await screen.findByText("National")).toBeInTheDocument();
    expect(screen.getByTestId("psi-value")).toHaveTextContent("96–119");
    expect(screen.getAllByText("Unhealthy").length).toBeGreaterThan(0);
    expect(screen.getByText("Updated 15:00 SGT")).toBeInTheDocument();
  });

  it("uses the nearest region to the saved location", async () => {
    vi.mocked(api.getAirQualityLatest).mockResolvedValue(okLatest);

    render(<AirQualityCard location={{ latitude: 1.34, longitude: 103.71 }} />);

    expect(await screen.findByText("West region")).toBeInTheDocument();
    expect(screen.getByTestId("psi-value")).toHaveTextContent("119");
    expect(screen.getByTestId("pm25-value")).toHaveTextContent("60");
    expect(screen.getByText("Elevated")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /from 110 to 115/ })).toBeInTheDocument();
  });

  it("states unavailability with the last good time instead of showing numbers", async () => {
    vi.mocked(api.getAirQualityLatest).mockResolvedValue({
      ...okLatest,
      status: "unavailable",
      regions: [],
      national: null,
      last_good_observed_at: "2026-10-25T14:00:00+08:00",
    });

    render(<AirQualityCard />);

    expect(await screen.findByRole("status")).toHaveTextContent("Last good reading: 14:00 SGT");
    expect(screen.queryByTestId("psi-value")).not.toBeInTheDocument();
  });

  it("labels a stale reading as delayed", async () => {
    vi.mocked(api.getAirQualityLatest).mockResolvedValue({ ...okLatest, status: "stale" });

    render(<AirQualityCard />);

    expect(await screen.findByRole("status")).toHaveTextContent("Delayed: last NEA reading 15:00 SGT");
  });

  it("links to official haze advisories", async () => {
    vi.mocked(api.getAirQualityLatest).mockResolvedValue(okLatest);

    render(<AirQualityCard />);

    expect(await screen.findByRole("link", { name: "haze.gov.sg" })).toHaveAttribute("href", "https://www.haze.gov.sg/");
  });
});

describe("air quality utils", () => {
  it("nearestRegion returns null without a location", () => {
    expect(nearestRegion(null, regions)).toBeNull();
  });

  it("psiSeries takes the national max per hour", () => {
    expect(psiSeries(history.points)).toEqual([110, 115]);
  });

  it("formatSgtTime renders Singapore time from a UTC timestamp", () => {
    expect(formatSgtTime("2026-10-25T07:05:00Z")).toBe("15:05 SGT");
  });
});
