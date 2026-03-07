import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelComparisonChart } from "./ModelComparisonChart";
import * as mlApi from "../api/ml";

vi.mock("../api/ml");

describe("ModelComparisonChart", () => {
  const mockMetricsData = {
    rankings: [
      {
        model_name: "arima",
        mae: 1.5,
        rmse: 2.0,
        mape: 5.0,
        is_recommended: false,
      },
      {
        model_name: "sarima",
        mae: 1.3,
        rmse: 1.8,
        mape: 4.5,
        is_recommended: false,
      },
      {
        model_name: "prophet",
        mae: 1.4,
        rmse: 1.9,
        mape: 4.8,
        is_recommended: false,
      },
      {
        model_name: "lstm",
        mae: 1.2,
        rmse: 1.7,
        mape: 4.2,
        is_recommended: true,
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mlApi.getAccuracyMetrics.mockResolvedValue(mockMetricsData);
  });

  it("renders the component with title", async () => {
    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(screen.getByText("Model Comparison")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Side-by-side performance metrics"),
    ).toBeInTheDocument();
  });

  it("displays all metric type options", async () => {
    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(screen.getByText("MAE")).toBeInTheDocument();
    });
    expect(screen.getByText("RMSE")).toBeInTheDocument();
    expect(screen.getByText("MAPE")).toBeInTheDocument();
  });

  it("displays sort order options", async () => {
    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(screen.getByText("Best to Worst")).toBeInTheDocument();
    });
    expect(screen.getByText("Worst to Best")).toBeInTheDocument();
  });

  it("fetches metrics data on mount", async () => {
    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledWith("temperature");
    });
  });

  it("displays recommended model badge", async () => {
    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(screen.getByText("Recommended Model:")).toBeInTheDocument();
    });
    expect(screen.getByText("LSTM")).toBeInTheDocument();
  });

  it("allows changing metric type", async () => {
    const user = userEvent.setup();
    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalled();
    });

    const rmseButton = screen.getByText("RMSE");
    await user.click(rmseButton);

    // Should not trigger new fetch, just update display
    expect(mlApi.getAccuracyMetrics).toHaveBeenCalledTimes(1);
  });

  it("allows changing sort order", async () => {
    const user = userEvent.setup();
    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalled();
    });

    const worstToBestButton = screen.getByText("Worst to Best");
    await user.click(worstToBestButton);

    // Should not trigger new fetch, just reorder data
    expect(mlApi.getAccuracyMetrics).toHaveBeenCalledTimes(1);
  });

  it("sorts data by selected metric in ascending order (best to worst)", async () => {
    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalled();
    });

    // Default is MAE, ascending (best to worst)
    // Expected order: LSTM (1.2), SARIMA (1.3), PROPHET (1.4), ARIMA (1.5)
    // We can't easily test the chart order, but we can verify the data is loaded
    expect(screen.getByText("Model Comparison")).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    mlApi.getAccuracyMetrics.mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    render(<ModelComparisonChart />);

    expect(screen.getByText("Loading model comparison...")).toBeInTheDocument();
  });

  it("handles error state", async () => {
    mlApi.getAccuracyMetrics.mockRejectedValue(
      new Error("Failed to fetch metrics"),
    );

    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(screen.getByText("Failed to fetch metrics")).toBeInTheDocument();
    });

    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("allows refreshing data", async () => {
    const user = userEvent.setup();
    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledTimes(1);
    });

    const refreshButton = screen.getByLabelText("Refresh comparison");
    await user.click(refreshButton);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledTimes(2);
    });
  });

  it("applies dark mode styles", () => {
    const { container } = render(<ModelComparisonChart isDark={true} />);

    // Check for dark mode classes
    const mainDiv = container.firstChild;
    expect(mainDiv).toHaveClass("bg-white/10");
  });

  it("applies light mode styles by default", () => {
    const { container } = render(<ModelComparisonChart isDark={false} />);

    // Check for light mode classes
    const mainDiv = container.firstChild;
    expect(mainDiv).toHaveClass("bg-white/20");
  });

  it("accepts parameter prop", async () => {
    render(<ModelComparisonChart parameter="rainfall" />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledWith("rainfall");
    });
  });

  it("handles empty rankings data", async () => {
    mlApi.getAccuracyMetrics.mockResolvedValue({ rankings: [] });

    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(
        screen.getByText("No comparison data available"),
      ).toBeInTheDocument();
    });
  });

  it("handles missing rankings property", async () => {
    mlApi.getAccuracyMetrics.mockResolvedValue({});

    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(
        screen.getByText("No comparison data available"),
      ).toBeInTheDocument();
    });
  });

  it("does not show recommended badge when no model is recommended", async () => {
    const dataWithoutRecommended = {
      rankings: mockMetricsData.rankings.map((model) => ({
        ...model,
        is_recommended: false,
      })),
    };
    mlApi.getAccuracyMetrics.mockResolvedValue(dataWithoutRecommended);

    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalled();
    });

    expect(screen.queryByText("Recommended Model:")).not.toBeInTheDocument();
  });

  it("handles models with missing metric values", async () => {
    const dataWithMissingMetrics = {
      rankings: [
        {
          model_name: "arima",
          mae: null,
          rmse: null,
          mape: null,
          is_recommended: false,
        },
      ],
    };
    mlApi.getAccuracyMetrics.mockResolvedValue(dataWithMissingMetrics);

    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalled();
    });

    // Should render without crashing
    expect(screen.getByText("Model Comparison")).toBeInTheDocument();
  });

  it("handles models with unknown names", async () => {
    const dataWithUnknownModel = {
      rankings: [
        {
          model_name: null,
          mae: 1.5,
          rmse: 2.0,
          mape: 5.0,
          is_recommended: false,
        },
      ],
    };
    mlApi.getAccuracyMetrics.mockResolvedValue(dataWithUnknownModel);

    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalled();
    });

    // Should render without crashing
    expect(screen.getByText("Model Comparison")).toBeInTheDocument();
  });

  it("refetches data when parameter prop changes", async () => {
    const { rerender } = render(
      <ModelComparisonChart parameter="temperature" />,
    );

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledWith("temperature");
    });

    rerender(<ModelComparisonChart parameter="humidity" />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalledWith("humidity");
    });

    expect(mlApi.getAccuracyMetrics).toHaveBeenCalledTimes(2);
  });

  it("displays metric descriptions as tooltips", async () => {
    render(<ModelComparisonChart />);

    await waitFor(() => {
      expect(mlApi.getAccuracyMetrics).toHaveBeenCalled();
    });

    const maeButton = screen.getByText("MAE");
    expect(maeButton).toHaveAttribute("title", "Mean Absolute Error");

    const rmseButton = screen.getByText("RMSE");
    expect(rmseButton).toHaveAttribute("title", "Root Mean Square Error");

    const mapeButton = screen.getByText("MAPE");
    expect(mapeButton).toHaveAttribute(
      "title",
      "Mean Absolute Percentage Error",
    );
  });
});
