import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import fixture from "./scene.fixture.json";

vi.mock("../api/haze", () => ({ getHazeScene: vi.fn(), getHazeWindField: vi.fn(() => Promise.resolve({ status: "unavailable" })) }));
vi.mock("./HazeMap", () => ({ HazeMap: () => null }));

import { getHazeScene } from "../api/haze";
import { HazePage } from "./HazePage";

beforeEach(() => {
  getHazeScene.mockReset();
  global.ResizeObserver = class {
    observe() {}
    disconnect() {}
  };
});

describe("HazePage", () => {
  it("opens on the latest hour for the worst region, with plain advice", async () => {
    getHazeScene.mockResolvedValue(fixture);
    render(<HazePage />);

    const card = await screen.findByRole("region", { name: "At cursor" });
    // Latest hour: west PSI 92 is the highest of the five regions.
    expect(within(card).getByRole("combobox")).toHaveValue("west");
    expect(within(card).getByText("92")).toBeInTheDocument();
    expect(within(card).getByText("Moderate")).toBeInTheDocument();
    expect(within(card).getByText("Normal activities are fine.")).toBeInTheDocument();
  });

  it("moves the cursor with the timeline and updates the card", async () => {
    getHazeScene.mockResolvedValue(fixture);
    render(<HazePage />);
    const slider = await screen.findByRole("slider", { name: "Hour" });

    fireEvent.change(slider, { target: { value: "0" } });

    const card = screen.getByRole("region", { name: "At cursor" });
    expect(within(card).getByText("105")).toBeInTheDocument();
    expect(within(card).getByText("Unhealthy")).toBeInTheDocument();
    expect(within(card).getByText("Elevated")).toBeInTheDocument();
  });

  it("says plainly when fire detections and the air path are unavailable, and keeps those toggles off", async () => {
    getHazeScene.mockResolvedValue(fixture);
    render(<HazePage />);

    const fires = await screen.findByRole("checkbox", { name: /Fire detections/ });
    expect(fires).toBeDisabled();
    expect(fires).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Air path/ })).toBeDisabled();
    expect(screen.getByText("The air path is not available right now.")).toBeInTheDocument();
    expect(screen.getByText("NASA fire detections are not available right now.")).toBeInTheDocument();
  });

  it("explains the hour from the data it has, without claiming a cause", async () => {
    getHazeScene.mockResolvedValue(fixture);
    render(<HazePage />);

    const card = await screen.findByRole("region", { name: "At cursor" });
    expect(within(card).getByText("Why this hour looks like this")).toBeInTheDocument();
    expect(card.textContent).not.toMatch(/gets it first/);
  });

  it("shows an error with a retry when the API fails", async () => {
    getHazeScene.mockRejectedValueOnce(new Error("Unable to connect to the server."));
    render(<HazePage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Haze data could not load.");
    getHazeScene.mockResolvedValue(fixture);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("region", { name: "At cursor" })).toBeInTheDocument();
  });

  it("falls back to the flat map without WebGL and never uses an em dash", async () => {
    getHazeScene.mockResolvedValue(fixture);
    const { container } = render(<HazePage />);
    await screen.findByRole("region", { name: "At cursor" });

    expect(screen.getByRole("img", { name: "Flat map of PM2.5 by region" })).toBeInTheDocument();
    expect(container.textContent).not.toContain("\u2014");
  });
});
