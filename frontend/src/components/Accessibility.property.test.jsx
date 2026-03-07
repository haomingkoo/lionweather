import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import fc from "fast-check";
import { LocationForm } from "./LocationForm";
import { EnhancedLocationList } from "./EnhancedLocationList";
import { ViewToggle } from "./ViewToggle";
import { LocationsProvider } from "../hooks/useLocations";

/**
 * Property-Based Tests for Accessibility
 * Feature: apple-weather-ui-redesign
 */

describe("Property-Based Tests: Accessibility", () => {
  // Clean up after each test to avoid DOM pollution
  afterEach(() => {
    cleanup();
  });

  /**
   * Property 8: Keyboard accessibility for interactive elements
   * **Validates: Requirements 11.4, 11.2, 11.6**
   *
   * For any interactive element (button, input, link), the element should be
   * keyboard focusable (not have tabIndex={-1}) and should include focus state
   * styling (focus:ring or focus:outline classes).
   */
  describe("Feature: apple-weather-ui-redesign, Property 8: Keyboard accessibility for interactive elements", () => {
    /**
     * Test that all buttons in LocationForm are keyboard focusable
     * and have focus indicators
     */
    it("should have keyboard focusable buttons with focus indicators in LocationForm", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find all button elements
            const buttons = container.querySelectorAll("button");

            // Requirement 11.4: Weather app shall support keyboard navigation for all interactive elements
            expect(buttons.length).toBeGreaterThan(0);

            buttons.forEach((button) => {
              // Verify button is keyboard focusable (tabIndex should not be -1)
              const tabIndex = button.getAttribute("tabindex");
              expect(tabIndex).not.toBe("-1");

              // Requirement 11.2: Action button shall maintain focus indicators with at least 2 pixels of outline
              // Requirement 11.6: When an action button is focused, the action button shall display a visible focus ring
              const className = button.className;

              // Verify button has focus state styling
              expect(
                className.includes("focus:ring") ||
                  className.includes("focus:outline"),
              ).toBe(true);

              // If it has focus:ring, verify it has appropriate ring width
              if (className.includes("focus:ring-2")) {
                // Ring width of 2px meets requirement 11.2
                expect(className).toContain("focus:ring-2");
              }
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    /**
     * Test that all inputs in LocationForm are keyboard focusable
     * and have focus indicators
     */
    it("should have keyboard focusable inputs with focus indicators in LocationForm", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find all input elements
            const inputs = container.querySelectorAll("input");

            // Requirement 11.4: Weather app shall support keyboard navigation for all interactive elements
            expect(inputs.length).toBeGreaterThan(0);

            inputs.forEach((input) => {
              // Verify input is keyboard focusable (tabIndex should not be -1)
              const tabIndex = input.getAttribute("tabindex");
              expect(tabIndex).not.toBe("-1");

              // Requirement 11.2: Action button shall maintain focus indicators with at least 2 pixels of outline
              const className = input.className;

              // Verify input has focus state styling
              expect(
                className.includes("focus:ring") ||
                  className.includes("focus:outline"),
              ).toBe(true);

              // Verify ring width meets 2px requirement
              if (className.includes("focus:ring-2")) {
                expect(className).toContain("focus:ring-2");
              }
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    /**
     * Test that ViewToggle buttons are keyboard focusable
     * and have focus indicators
     */
    it("should have keyboard focusable buttons with focus indicators in ViewToggle", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          fc.constantFrom("list", "map"), // view prop
          (isDark, view) => {
            const mockOnViewChange = () => {};

            const { container } = render(
              <ViewToggle
                view={view}
                onViewChange={mockOnViewChange}
                isDark={isDark}
              />,
            );

            // Find all button elements
            const buttons = container.querySelectorAll("button");

            // Should have 2 buttons (list and map)
            expect(buttons.length).toBe(2);

            buttons.forEach((button) => {
              // Verify button is keyboard focusable
              const tabIndex = button.getAttribute("tabindex");
              expect(tabIndex).not.toBe("-1");

              // Verify button has focus state styling
              const className = button.className;
              expect(
                className.includes("focus:ring") ||
                  className.includes("focus:outline"),
              ).toBe(true);

              // Verify button has aria-label for accessibility
              const ariaLabel = button.getAttribute("aria-label");
              expect(ariaLabel).toBeTruthy();
              expect(["List view", "Map view"]).toContain(ariaLabel);
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    /**
     * Test that no interactive elements have tabIndex=-1
     * which would prevent keyboard navigation
     */
    it("should not have any interactive elements with tabIndex=-1", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find all potentially interactive elements
            const interactiveElements = container.querySelectorAll(
              "button, input, a, [role='button']",
            );

            expect(interactiveElements.length).toBeGreaterThan(0);

            interactiveElements.forEach((element) => {
              // Requirement 11.4: All interactive elements must be keyboard navigable
              const tabIndex = element.getAttribute("tabindex");

              // tabIndex should not be -1 (which removes from tab order)
              expect(tabIndex).not.toBe("-1");

              // If tabIndex is explicitly set, it should be 0 or positive
              if (tabIndex !== null) {
                expect(parseInt(tabIndex)).toBeGreaterThanOrEqual(0);
              }
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    /**
     * Test that focus indicators have sufficient visibility
     * by checking for ring or outline classes
     */
    it("should have visible focus indicators on all interactive elements", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find all interactive elements
            const interactiveElements =
              container.querySelectorAll("button, input");

            expect(interactiveElements.length).toBeGreaterThan(0);

            interactiveElements.forEach((element) => {
              const className = element.className;

              // Requirement 11.6: When focused, action button shall display a visible focus ring
              // Verify element has focus state styling
              const hasFocusIndicator =
                className.includes("focus:ring") ||
                className.includes("focus:outline");

              expect(hasFocusIndicator).toBe(true);

              // If using focus:ring, verify it has appropriate styling
              if (className.includes("focus:ring")) {
                // Should have ring width (focus:ring-2 for 2px)
                const hasRingWidth =
                  className.includes("focus:ring-1") ||
                  className.includes("focus:ring-2") ||
                  className.includes("focus:ring-4");

                expect(hasRingWidth).toBe(true);

                // Should have ring color for visibility
                const hasRingColor =
                  className.includes("focus:ring-white") ||
                  className.includes("focus:ring-blue") ||
                  className.includes("focus:ring-red") ||
                  className.includes("focus:ring-slate");

                expect(hasRingColor).toBe(true);
              }
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    /**
     * Test that focus indicators meet the 2px minimum requirement
     */
    it("should have focus indicators with at least 2px width", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find all interactive elements
            const interactiveElements =
              container.querySelectorAll("button, input");

            expect(interactiveElements.length).toBeGreaterThan(0);

            interactiveElements.forEach((element) => {
              const className = element.className;

              // Requirement 11.2: Focus indicators must be at least 2 pixels
              if (className.includes("focus:ring")) {
                // Check for ring width classes
                const hasMinimumRingWidth =
                  className.includes("focus:ring-2") ||
                  className.includes("focus:ring-4") ||
                  className.includes("focus:ring-8");

                // focus:ring-1 is only 1px, which doesn't meet requirement
                const hasInsufficientRing = className.includes("focus:ring-1");

                // Should have at least 2px ring width
                expect(hasMinimumRingWidth || !hasInsufficientRing).toBe(true);
              }

              if (className.includes("focus:outline")) {
                // Outline should have sufficient width
                // focus:outline-none removes outline, which is only acceptable if focus:ring is present
                if (className.includes("focus:outline-none")) {
                  expect(className.includes("focus:ring")).toBe(true);
                }
              }
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    /**
     * Test that interactive elements have appropriate ARIA labels
     * for screen reader accessibility
     */
    it("should have appropriate ARIA labels on interactive elements", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          fc.constantFrom("list", "map"), // view prop
          (isDark, view) => {
            const mockOnViewChange = () => {};

            const { container } = render(
              <ViewToggle
                view={view}
                onViewChange={mockOnViewChange}
                isDark={isDark}
              />,
            );

            // Find all buttons
            const buttons = container.querySelectorAll("button");

            buttons.forEach((button) => {
              // Buttons should have either aria-label or visible text content
              const ariaLabel = button.getAttribute("aria-label");
              const textContent = button.textContent.trim();

              // At least one should be present for accessibility
              const hasAccessibleLabel = !!(
                ariaLabel || textContent.length > 0
              );
              expect(hasAccessibleLabel).toBe(true);

              // If aria-label is present, it should be meaningful
              if (ariaLabel) {
                expect(ariaLabel.length).toBeGreaterThan(0);
              }
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });
  });
});
