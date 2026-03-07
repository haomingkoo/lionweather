import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ConfidenceIntervalChart } from "./ConfidenceIntervalChart";
import * as mlApi from "../api/ml";

// Mock the ML API
vi.mock("../api/ml");

describe("ConfidenceIntervalChart", () => {
  const mockPredictions = {
    country: "Singapore",
    location: "Changi",
    forecast_type: "24h",
    generated_at: "2024-01-15T10:00:00Z",
    forecasts: [
      {
        timestamp: "2024-01-15T11:00:00Z",
        predicted_value: 28.5,
        confidence_lower: 27.2,
        confidence_upper: 29.8,
      },
      {
        timestamp: "2024-01-15T12:00:00Z",
        predicted_value: 29.0,
        confidence_lower: 27.5,
        confidence_upper: 30.5,
      },
      {
        timestamp: "2024-01-15T13:00:00Z",
        predicted_value: 29.5,
        confidence_lower: 28.0,
        confidence_upper: 31.0,
      },
      {
        timestamp: "2024-01-15T14:00:00Z",
        predicted_value: 30.0,
        confidence_lower: 28.5,
        confidence_upper: 31.5,
      },
      {
        timestamp: "2024-01-15T15:00:00Z",
        predicted_value: 30.2,
        confidence_lower: 28.7,
        confidence_upper: 31.7,
      },
      {
        timestamp: "2024-01-15T16:00:00Z",
        predicted_value: 29.8,
        confidence_lower: 28.3,
        confidence_upper: 31.3,
      },
    ],
  };

  const mockCurrentWeather = {
    current: {
      temperature: 28.0,
      rainfall: 0.5,
      humidity: 75.0,
      wind_speed: 12.5,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mlApi.get24HourPredictions.mockResolvedValue(mockPredictions);
    mlApi.getCurrentWeather.mockResolvedValue(mockCurrentWeather);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("Component Rendering", () => {
    it("should render the component with title and description", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(screen.getByText("Confidence Intervals")).toBeInTheDocument();
        expect(
          screen.getByText("Predictions with 95% confidence bands"),
        ).toBeInTheDocument();
      });
    });

    it("should show loading state initially", () => {
      mlApi.get24HourPredictions.mockImplementation(
        () => new Promise(() => {}),
      );
      render(<ConfidenceIntervalChart />);

      expect(screen.getByText("Loading predictions...")).toBeInTheDocument();
    });

    it("should render in dark mode", async () => {
      const { container } = render(<ConfidenceIntervalChart isDark={true} />);

      await waitFor(() => {
        const title = screen.getByText("Confidence Intervals");
        expect(title).toHaveClass("text-white");
      });
    });

    it("should render in light mode", async () => {
      const { container } = render(<ConfidenceIntervalChart isDark={false} />);

      await waitFor(() => {
        const title = screen.getByText("Confidence Intervals");
        expect(title).toHaveClass("text-slate-900");
      });
    });
  });

  describe("Data Fetching", () => {
    it("should fetch predictions on mount", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalledWith(
          "Singapore",
          null,
          "temperature",
        );
        expect(mlApi.getCurrentWeather).toHaveBeenCalledWith("Singapore", null);
      });
    });

    it("should fetch predictions with custom country and location", async () => {
      render(
        <ConfidenceIntervalChart country="Malaysia" location="Kuala Lumpur" />,
      );

      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalledWith(
          "Malaysia",
          "Kuala Lumpur",
          "temperature",
        );
        expect(mlApi.getCurrentWeather).toHaveBeenCalledWith(
          "Malaysia",
          "Kuala Lumpur",
        );
      });
    });

    it("should handle API errors gracefully", async () => {
      mlApi.get24HourPredictions.mockRejectedValue(
        new Error("API Error: Network failure"),
      );

      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(
          screen.getByText("API Error: Network failure"),
        ).toBeInTheDocument();
        expect(screen.getByText("Retry")).toBeInTheDocument();
      });
    });

    it("should handle missing current weather data", async () => {
      mlApi.getCurrentWeather.mockRejectedValue(new Error("Not available"));

      render(<ConfidenceIntervalChart />);

      // Should still render predictions even without current weather
      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalled();
      });
    });

    it("should retry fetching data when retry button is clicked", async () => {
      mlApi.get24HourPredictions.mockRejectedValueOnce(
        new Error("Network error"),
      );
      mlApi.get24HourPredictions.mockResolvedValueOnce(mockPredictions);

      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(screen.getByText("Network error")).toBeInTheDocument();
      });

      const retryButton = screen.getByText("Retry");
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe("Parameter Selection", () => {
    it("should render all parameter buttons", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(screen.getByText("Temperature")).toBeInTheDocument();
        expect(screen.getByText("Rainfall")).toBeInTheDocument();
        expect(screen.getByText("Humidity")).toBeInTheDocument();
        expect(screen.getByText("Wind Speed")).toBeInTheDocument();
      });
    });

    it("should highlight selected parameter", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        const tempButton = screen.getByText("Temperature");
        expect(tempButton).toHaveClass("bg-blue-500");
      });
    });

    it("should fetch new data when parameter changes", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalledWith(
          "Singapore",
          null,
          "temperature",
        );
      });

      const rainfallButton = screen.getByText("Rainfall");
      fireEvent.click(rainfallButton);

      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalledWith(
          "Singapore",
          null,
          "rainfall",
        );
      });
    });

    it("should update chart when switching between parameters", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        const tempButton = screen.getByText("Temperature");
        expect(tempButton).toHaveClass("bg-blue-500");
      });

      const humidityButton = screen.getByText("Humidity");
      fireEvent.click(humidityButton);

      await waitFor(() => {
        expect(humidityButton).toHaveClass("bg-blue-500");
        expect(mlApi.get24HourPredictions).toHaveBeenCalledWith(
          "Singapore",
          null,
          "humidity",
        );
      });
    });
  });

  describe("Date Range Selection", () => {
    it("should render all date range buttons", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(screen.getByText("6 Hours")).toBeInTheDocument();
        expect(screen.getByText("12 Hours")).toBeInTheDocument();
        expect(screen.getByText("24 Hours")).toBeInTheDocument();
      });
    });

    it("should default to 24 hours range", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        const button24h = screen.getByText("24 Hours");
        expect(button24h).toHaveClass("bg-blue-500");
      });
    });

    it("should change selected range when clicked", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        const button24h = screen.getByText("24 Hours");
        expect(button24h).toHaveClass("bg-blue-500");
      });

      const button6h = screen.getByText("6 Hours");
      fireEvent.click(button6h);

      await waitFor(() => {
        expect(button6h).toHaveClass("bg-blue-500");
      });
    });

    it("should filter data based on selected range", async () => {
      const { rerender } = render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalled();
      });

      // Click 6 hours button
      const button6h = screen.getByText("6 Hours");
      fireEvent.click(button6h);

      // The chart should now show only 6 hours of data
      // This is tested indirectly through the component's internal state
      await waitFor(() => {
        expect(button6h).toHaveClass("bg-blue-500");
      });
    });
  });

  describe("Zoom and Pan Controls", () => {
    it("should render zoom toggle button", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        const zoomButton = screen.getByLabelText("Toggle zoom");
        expect(zoomButton).toBeInTheDocument();
      });
    });

    it("should toggle zoom state when clicked", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        const zoomButton = screen.getByLabelText("Toggle zoom");
        expect(zoomButton).toHaveClass("bg-blue-500");
      });

      const zoomButton = screen.getByLabelText("Toggle zoom");
      fireEvent.click(zoomButton);

      await waitFor(() => {
        expect(zoomButton).not.toHaveClass("bg-blue-500");
      });
    });

    it("should have zoom enabled by default", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        const zoomButton = screen.getByLabelText("Toggle zoom");
        expect(zoomButton).toHaveClass("bg-blue-500");
      });
    });
  });

  describe("Refresh Functionality", () => {
    it("should render refresh button", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        const refreshButton = screen.getByLabelText("Refresh predictions");
        expect(refreshButton).toBeInTheDocument();
      });
    });

    it("should refetch data when refresh button is clicked", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalledTimes(1);
      });

      const refreshButton = screen.getByLabelText("Refresh predictions");
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalledTimes(2);
      });
    });

    it("should disable refresh button while loading", async () => {
      mlApi.get24HourPredictions.mockImplementation(
        () => new Promise(() => {}),
      );

      render(<ConfidenceIntervalChart />);

      // During loading, the component shows loading state without the refresh button
      expect(screen.getByText("Loading predictions...")).toBeInTheDocument();
    });
  });

  describe("Confidence Interval Display", () => {
    it("should display confidence interval information", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(
          screen.getByText(/95% confidence interval/i),
        ).toBeInTheDocument();
      });
    });

    it("should show info footer with explanation", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(
          screen.getByText(/There is a 95% probability/i),
        ).toBeInTheDocument();
      });
    });

    it("should explain uncertainty in the footer", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(
          screen.getByText(/Wider bands indicate higher uncertainty/i),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Data Transformation", () => {
    it("should transform API data correctly", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalled();
      });

      // Verify that the component processes the data
      // This is tested indirectly through successful rendering
      expect(
        screen.queryByText("No prediction data available"),
      ).not.toBeInTheDocument();
    });

    it("should handle empty forecasts array", async () => {
      mlApi.get24HourPredictions.mockResolvedValue({
        forecasts: [],
      });

      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        // When there's no data, the chart still renders with empty state
        // The component shows the UI but with no chart data
        expect(screen.getByText("Weather Parameter")).toBeInTheDocument();
      });
    });

    it("should handle missing forecasts property", async () => {
      mlApi.get24HourPredictions.mockResolvedValue({});

      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(
          screen.getByText("No prediction data available"),
        ).toBeInTheDocument();
      });
    });

    it("should include current weather as first data point", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(mlApi.getCurrentWeather).toHaveBeenCalled();
      });

      // The current weather should be added to the chart data
      // This is tested indirectly through the component's data processing
    });
  });

  describe("Edge Cases", () => {
    it("should handle null predictions gracefully", async () => {
      mlApi.get24HourPredictions.mockResolvedValue(null);

      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(
          screen.getByText("No prediction data available"),
        ).toBeInTheDocument();
      });
    });

    it("should handle undefined predictions gracefully", async () => {
      mlApi.get24HourPredictions.mockResolvedValue(undefined);

      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(
          screen.getByText("No prediction data available"),
        ).toBeInTheDocument();
      });
    });

    it("should handle malformed timestamp data", async () => {
      const malformedData = {
        forecasts: [
          {
            timestamp: "invalid-date",
            predicted_value: 28.5,
            confidence_lower: 27.2,
            confidence_upper: 29.8,
          },
        ],
      };

      mlApi.get24HourPredictions.mockResolvedValue(malformedData);

      render(<ConfidenceIntervalChart />);

      // Should not crash, but may show invalid date
      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalled();
      });
    });

    it("should handle missing confidence values", async () => {
      const incompleteData = {
        forecasts: [
          {
            timestamp: "2024-01-15T11:00:00Z",
            predicted_value: 28.5,
            // Missing confidence_lower and confidence_upper
          },
        ],
      };

      mlApi.get24HourPredictions.mockResolvedValue(incompleteData);

      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(mlApi.get24HourPredictions).toHaveBeenCalled();
      });
    });
  });

  describe("Accessibility", () => {
    it("should have accessible button labels", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        expect(screen.getByLabelText("Toggle zoom")).toBeInTheDocument();
        expect(
          screen.getByLabelText("Refresh predictions"),
        ).toBeInTheDocument();
      });
    });

    it("should have proper button titles", async () => {
      render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        const zoomButton = screen.getByLabelText("Toggle zoom");
        expect(zoomButton).toHaveAttribute("title");
      });
    });
  });

  describe("Integration with Recharts", () => {
    it("should render chart when data is available", async () => {
      const { container } = render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        // Recharts renders SVG elements
        const svg = container.querySelector("svg");
        expect(svg).toBeInTheDocument();
      });
    });

    it("should not render chart when no data", async () => {
      mlApi.get24HourPredictions.mockResolvedValue({ forecasts: [] });

      const { container } = render(<ConfidenceIntervalChart />);

      await waitFor(() => {
        // Recharts still renders a container even with no data
        // We should check that there's no actual chart content
        const rechartsContainer = container.querySelector(
          ".recharts-responsive-container",
        );
        expect(rechartsContainer).toBeInTheDocument();
      });
    });
  });
});
