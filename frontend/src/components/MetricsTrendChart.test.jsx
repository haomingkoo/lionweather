import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MetricsTrendChart } from "./MetricsTrendChart";
import * as mlApi from "../api/ml";

vi.mock("../api/ml");

describe("MetricsTrendChart", () => {
  const mockMetricsData = {
    rankings: [
      {
        model_name: "arima",
        mae: 1.5,
        rmse: 2.0,
        mape: 5.0,
      },
      {
        model_name: "sarima",
        mae: 1.3,
        rmse: 1.8,
        mape: 4.5,
      },
      {
        model_name: "prophet",
        mae: 1.4,
        rmse: 1.9,
        mape: 4.8,
      },
      {
        model_name: "lstm",
        mae: 1.2,
        rmse: 1.7,
        mape: 4.2,
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mlApi.getAccuracyMetrics.mockResolvedValue(mockMetricsData);
  });

  it("renders the component with title", async () => {
    render(<MetricsTrendChart />);

    await waitFor(() => {
      expect(screen.getByText("Metrics Trend")).toBeInTheDocument();
    });
    expect(screen.getByText("Model performance over time")).toBeInTheDocument();
  });

  it("displays all date range options", async () => {
    render(<MetricsTrendChart />);

    await waitFor(() => {
      expect(screen.getByText("7 Days")).toBeInTheDocument();
    });
    expect(screen.getByText("30 Days")).toBeInTheDocument();
    expect(screen.getByText("90 Days")).toBeInTheDocument();
    expect(screen.getByText("1 Year")).toBeInTheDocument();
  });

  it("displays all metric type options", async () => {
    render(<MetricsTrendChart />);

    await waitFor(() => {
      expect(screen.getByText("MAE")).toBeInTheDocument();
    });
    expect(screen.getByText("RMSE")).toBeInTheDocument();
    expect(screen.getByText("MAPE")).toBeInTheDocument();
  });

  it("displays all model options", async () => {
    render(<MetricsTrendChart />);

    await waitFor(() => {
      expect(screen.getByText("ARIMA")).toBeInTheDocument();
    });
    expect(screen.getByText("SARIMA")).toBeInTheDocument();
    expect(screen.getByText("PROPHET")).toBeInTheDocument();
    expect(screen.getByText("LSTM")).toBeInTheDocument();
  });

  it("fetches metrics data on mount", async () => {
    render(<MetricsTrendChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledWith("temperature");
    });
  });

  it("allows changing date range", async () => {
    const user = userEvent.setup();
    render(<MetricsTrendChart />);

    await waitFor(() => {
      expect(screen.getByText("7 Days")).toBeInTheDocument();
    });

    const sevenDaysButton = screen.getByText("7 Days");
    await user.click(sevenDaysButton);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledTimes(2); // Initial + after click
    });
  });

  it("allows changing metric type", async () => {
    const user = userEvent.setup();
    render(<MetricsTrendChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalled();
    });

    const rmseButton = screen.getByText("RMSE");
    await user.click(rmseButton);

    // Should not trigger new fetch, just update display
    expect(mlApi.getAccuracyMetrics).toHaveBeenCalledTimes(1);
  });

  it("allows toggling model visibility", async () => {
    const user = userEvent.setup();
    render(<MetricsTrendChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalled();
    });

    const arimaButton = screen.getByText("ARIMA");
    await user.click(arimaButton);

    // Button should still be present (just toggled)
    expect(arimaButton).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    mlApi.getAccuracyMetrics.mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    render(<MetricsTrendChart />);

    expect(screen.getByText("Loading metrics...")).toBeInTheDocument();
  });

  it("handles error state", async () => {
    mlApi.getAccuracyMetrics.mockRejectedValue(
      new Error("Failed to fetch metrics"),
    );

    render(<MetricsTrendChart />);

    await waitFor(() => {
      expect(screen.getByText("Failed to fetch metrics")).toBeInTheDocument();
    });

    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("allows refreshing data", async () => {
    const user = userEvent.setup();
    render(<MetricsTrendChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledTimes(1);
    });

    const refreshButton = screen.getByLabelText("Refresh metrics");
    await user.click(refreshButton);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledTimes(2);
    });
  });

  it("applies dark mode styles", () => {
    const { container } = render(<MetricsTrendChart isDark={true} />);

    // Check for dark mode classes
    const mainDiv = container.firstChild;
    expect(mainDiv).toHaveClass("bg-white/10");
  });

  it("applies light mode styles by default", () => {
    const { container } = render(<MetricsTrendChart isDark={false} />);

    // Check for light mode classes
    const mainDiv = container.firstChild;
    expect(mainDiv).toHaveClass("bg-white/20");
  });

  it("accepts parameter prop", async () => {
    render(<MetricsTrendChart parameter="rainfall" />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledWith("rainfall");
    });
  });
});
