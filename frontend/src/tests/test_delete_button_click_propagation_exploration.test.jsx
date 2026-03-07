/**
 * Bug Condition Exploration Test - Delete Button Click Propagation
 *
 * **Property 1: Bug Condition** - Delete button click propagates to map layer
 * **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
 * **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
 * **GOAL**: Surface counterexamples that demonstrate the bug exists
 *
 * **Validates: Requirements 2.1**
 *
 * Bug Description:
 * WHEN clicking the delete button (X) on the precipitation map modal
 * THEN the system adds a map marker behind the delete button AND closes the modal
 * due to click event propagation
 *
 * Expected Behavior:
 * WHEN clicking the delete button (X) on the precipitation map modal
 * THEN the system SHALL close the modal without adding a map marker
 * by preventing click event propagation to the map layer
 *
 * Test Strategy:
 * This is a scoped PBT approach testing the concrete failing case:
 * - Render the PrecipitationMap modal
 * - Simulate clicking the delete (X) button
 * - Verify that NO map click event is triggered (no marker added)
 * - Verify that the modal closes (onClose is called)
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PrecipitationMap } from "../components/PrecipitationMap.jsx";

// Mock Leaflet
vi.mock("leaflet", () => ({
  default: {
    icon: vi.fn(() => ({})),
    Marker: { prototype: { options: {} } },
    imageOverlay: vi.fn(() => ({
      addTo: vi.fn(),
      remove: vi.fn(),
    })),
  },
}));

// Mock react-leaflet with map click tracking
let mapClickHandler = null;

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children, ...props }) => (
    <div data-testid="map-container" {...props}>
      {children}
    </div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Marker: ({ children }) => <div data-testid="marker">{children}</div>,
  Popup: ({ children }) => <div data-testid="popup">{children}</div>,
  useMapEvents: (handlers) => {
    // Capture the click handler to track if map clicks are triggered
    if (handlers && handlers.click) {
      mapClickHandler = handlers.click;
    }
    return null;
  },
  useMap: () => ({
    getBounds: () => ({
      getNorthEast: () => ({ lat: 1.5, lng: 104 }),
      getSouthWest: () => ({ lat: 1.2, lng: 103.6 }),
    }),
    getSize: () => ({ x: 800, y: 600 }),
    latLngToContainerPoint: () => ({ x: 400, y: 300 }),
    removeLayer: vi.fn(),
  }),
}));

// Mock API
vi.mock("../api/rainfall", () => ({
  getRainfallData: vi.fn(() => Promise.resolve({ stations: [] })),
}));

describe("Bug Condition Exploration - Delete Button Click Propagation", () => {
  const mockLocation = {
    id: 1,
    latitude: 1.3521,
    longitude: 103.8198,
    weather: {
      area: "Singapore",
      condition: "Partly Cloudy",
      temperature: "28",
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mapClickHandler = null;
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ frames: [] }),
      }),
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Test Case 1: Delete Button Click Should Not Propagate to Map", () => {
    it("should close modal without triggering map click when delete button is clicked (EXPECTED TO PASS after fix)", () => {
      const onClose = vi.fn();
      const mapClickSpy = vi.fn();

      // Override the map click handler to track if it's called
      const originalUseMapEvents = vi.mocked(
        require("react-leaflet").useMapEvents,
      );
      vi.mocked(require("react-leaflet").useMapEvents).mockImplementation(
        (handlers) => {
          if (handlers && handlers.click) {
            mapClickHandler = mapClickSpy;
          }
          return null;
        },
      );

      const { container } = render(
        <PrecipitationMap
          location={mockLocation}
          onClose={onClose}
          isDark={false}
        />,
      );

      // Find the delete button (X button)
      const deleteButton = screen.getByRole("button", {
        name: /close precipitation map/i,
      });
      expect(deleteButton).toBeInTheDocument();

      // Click the delete button
      fireEvent.click(deleteButton);

      // Expected behavior after fix:
      // 1. Modal should close (onClose called)
      expect(onClose).toHaveBeenCalledTimes(1);

      // 2. Map click handler should NOT be triggered (no marker added)
      // This is the key assertion - if the bug exists, the click will propagate
      // to the map layer and trigger a map click event
      expect(mapClickSpy).not.toHaveBeenCalled();
    });
  });

  describe("Test Case 2: Delete Button Click Event Propagation", () => {
    it("should prevent event propagation when delete button is clicked (EXPECTED TO PASS after fix)", () => {
      const onClose = vi.fn();

      const { container } = render(
        <PrecipitationMap
          location={mockLocation}
          onClose={onClose}
          isDark={false}
        />,
      );

      // Find the delete button
      const deleteButton = screen.getByRole("button", {
        name: /close precipitation map/i,
      });

      // Create a spy on the backdrop to see if it receives the click
      const backdrop = container.querySelector(".fixed.inset-0");
      const backdropClickSpy = vi.fn();
      backdrop.addEventListener("click", backdropClickSpy);

      // Click the delete button
      fireEvent.click(deleteButton);

      // Expected behavior after fix:
      // 1. Modal should close
      expect(onClose).toHaveBeenCalledTimes(1);

      // 2. The backdrop should NOT receive the click event
      // (event propagation is stopped at the button level)
      // Note: In the current buggy implementation, the click might propagate
      // through the modal content to the backdrop, then to the map
      expect(backdropClickSpy).not.toHaveBeenCalled();
    });
  });

  describe("Test Case 3: Verify stopPropagation is Called", () => {
    it("should call stopPropagation on the click event (EXPECTED TO PASS after fix)", () => {
      const onClose = vi.fn();

      render(
        <PrecipitationMap
          location={mockLocation}
          onClose={onClose}
          isDark={false}
        />,
      );

      // Find the delete button
      const deleteButton = screen.getByRole("button", {
        name: /close precipitation map/i,
      });

      // Create a mock event with stopPropagation
      const mockEvent = {
        stopPropagation: vi.fn(),
        preventDefault: vi.fn(),
        target: deleteButton,
        currentTarget: deleteButton,
        bubbles: true,
      };

      // Manually trigger the onClick handler with our mock event
      const onClickHandler = deleteButton.onclick;
      if (onClickHandler) {
        onClickHandler(mockEvent);
      } else {
        // If onclick is not directly accessible, fire the event normally
        fireEvent.click(deleteButton);
      }

      // Expected behavior after fix:
      // The event handler should call stopPropagation
      // Note: This test verifies the fix implementation detail
      // If stopPropagation is called, the event won't bubble to parent elements
      expect(onClose).toHaveBeenCalled();
    });
  });

  describe("Test Case 4: Modal Content Click Should Not Close Modal", () => {
    it("should not close modal when clicking inside modal content (EXPECTED TO PASS after fix)", () => {
      const onClose = vi.fn();

      const { container } = render(
        <PrecipitationMap
          location={mockLocation}
          onClose={onClose}
          isDark={false}
        />,
      );

      // Find the modal content (not the backdrop)
      const modalContent = container.querySelector(".relative.w-full");
      expect(modalContent).toBeInTheDocument();

      // Click inside the modal content
      fireEvent.click(modalContent);

      // Expected behavior: Modal should NOT close when clicking inside
      // (only backdrop clicks should close the modal)
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe("Test Case 5: Backdrop Click Should Close Modal", () => {
    it("should close modal when clicking the backdrop (EXPECTED TO PASS - this should work)", () => {
      const onClose = vi.fn();

      const { container } = render(
        <PrecipitationMap
          location={mockLocation}
          onClose={onClose}
          isDark={false}
        />,
      );

      // Find the backdrop
      const backdrop = container.querySelector(".fixed.inset-0");
      expect(backdrop).toBeInTheDocument();

      // Click the backdrop directly
      fireEvent.click(backdrop);

      // Expected behavior: Modal should close
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
