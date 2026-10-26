import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import fixture from "./scene.fixture.json";

vi.mock("../api/haze", () => ({ getHazeScene: vi.fn(), getHazeWindField: vi.fn(() => Promise.resolve({ status: "unavailable" })) }));
vi.mock("./HazeMap", () => ({ HazeMap: () => null }));

import { getHazeScene } from "../api/haze";
import { HazePage } from "./HazePage";

beforeEach(() => {
  getHazeScene.mockReset();
  localStorage.clear();
  window.history.replaceState(null, "", "/haze");
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
    expect(within(card).getByText("Fine for normal activities.")).toBeInTheDocument();
    expect(within(card).getByText(/Wind [0-9.]+ kn from [NESW]+/)).toBeInTheDocument();
    expect(card.textContent).not.toMatch(/m\/s/);
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

  it("says plainly when fire detections and the wind path are unavailable, and keeps those toggles off", async () => {
    getHazeScene.mockResolvedValue(fixture);
    render(<HazePage />);

    const fires = await screen.findByRole("checkbox", { name: /Fires · size shows intensity/ });
    expect(fires).toBeDisabled();
    expect(fires).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Wind path, last 3 days/ })).toBeDisabled();
    expect(screen.getByText("Wind path not available right now.")).toBeInTheDocument();
    expect(screen.getByText("Fire detections not available right now.")).toBeInTheDocument();
  });

  it("explains the hour from the data it has, without claiming a cause", async () => {
    getHazeScene.mockResolvedValue(fixture);
    render(<HazePage />);

    const card = await screen.findByRole("region", { name: "At cursor" });
    expect(within(card).getByRole("heading", { name: "Why" })).toBeInTheDocument();
    expect(card.textContent).not.toMatch(/Likely smoke/);
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

    expect(screen.getByRole("img", { name: "Flat map of PSI by region" })).toBeInTheDocument();
    expect(container.textContent).not.toContain("\u2014");
  });
});

describe("fire clusters", () => {
  it("lists peatland and fire layers with plain notes", async () => {
    getHazeScene.mockResolvedValue(fixture);
    render(<HazePage />);
    expect(await screen.findByRole("checkbox", { name: /Peatland/ })).toBeInTheDocument();
    expect(screen.getByText("Smoulders for weeks")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Peatland/ }).closest("label")).toHaveAttribute(
      "title",
      "Fires on peat smoulder for weeks and produce the thickest smoke.",
    );
  });
});


describe("PSI or PM2.5", () => {
  it("defaults to PSI, and switching shows the PM2.5 bands and remembers it", async () => {
    getHazeScene.mockResolvedValue(fixture);
    render(<HazePage />);
    const toggle = await screen.findByRole("group", { name: "Reading shown" });
    expect(within(toggle).getByRole("button", { name: "PSI 24-h" })).toHaveAttribute("aria-pressed", "true");
    const key = screen.getByLabelText("Map key");
    expect(within(key).getByText("Good")).toBeInTheDocument();
    expect(within(key).getByText("300+")).toBeInTheDocument();
    expect(document.querySelector(".hz-stats .is-active dt").textContent).toMatch(/^PSI/);

    fireEvent.click(within(toggle).getByRole("button", { name: "PM2.5 1-h" }));
    expect(within(screen.getByLabelText("Map key")).getByText("Elevated")).toBeInTheDocument();
    expect(localStorage.getItem("hz-metric")).toBe("pm25");
    expect(window.location.search).toBe("?metric=pm25");
    expect(document.querySelector(".hz-stats .is-active dt").textContent).toMatch(/^PM2\.5/);
    expect(screen.getByRole("img", { name: "Flat map of PM2.5 by region" })).toBeInTheDocument();
  });

  it("takes ?metric= from the link over the saved choice", async () => {
    localStorage.setItem("hz-metric", "psi");
    window.history.replaceState(null, "", "/haze?metric=pm25");
    getHazeScene.mockResolvedValue(fixture);
    render(<HazePage />);
    const toggle = await screen.findByRole("group", { name: "Reading shown" });
    expect(within(toggle).getByRole("button", { name: "PM2.5 1-h" })).toHaveAttribute("aria-pressed", "true");
  });

  it("lists key changes for the metric shown", async () => {
    getHazeScene.mockResolvedValue(fixture);
    render(<HazePage />);
    const moments = await screen.findByRole("region", { name: "Key changes" });
    expect(moments.textContent).toMatch(/Peak: PSI/);
  });
});

describe("with WebGL 2", () => {
  it("renders the 3D page furniture without errors", async () => {
    const real = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
      return type === "webgl2" ? {} : real.call(this, type, ...rest);
    };
    try {
      getHazeScene.mockResolvedValue(fixture);
      render(<HazePage />);
      expect(await screen.findByRole("region", { name: "At cursor" })).toBeInTheDocument();
      expect(screen.getByRole("note")).toHaveTextContent(/orbit|rotate/i);
      expect(screen.getByRole("group", { name: "Map style" })).toBeInTheDocument();
    } finally {
      HTMLCanvasElement.prototype.getContext = real;
    }
  });
});
