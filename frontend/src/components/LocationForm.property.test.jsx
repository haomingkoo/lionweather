import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import fc from "fast-check";
import { LocationForm } from "./LocationForm";
import { LocationsProvider } from "../hooks/useLocations";

/**
 * Property-Based Tests for LocationForm Component
 * Feature: apple-weather-ui-redesign
 */

describe("Property-Based Tests: LocationForm", () => {
  // Clean up after each test to avoid DOM pollution
  afterEach(() => {
    cleanup();
  });
  /**
   * Property 9: Form inputs have visible labels
   * **Validates: Requirements 11.5**
   *
   * For any input field in the LocationForm component, there should be a
   * corresponding label element that is visible (not display:none or sr-only)
   * and associated with the input.
   */
  describe("Feature: apple-weather-ui-redesign, Property 9: Form inputs have visible labels", () => {
    it("should have visible labels for all input fields regardless of theme", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find all input elements in the form
            const inputs = container.querySelectorAll('input[type="number"]');

            // Requirement 11.5: Form component shall include visible labels for all input fields
            expect(inputs.length).toBeGreaterThan(0);

            inputs.forEach((input) => {
              // Find the parent label element
              const labelElement = input.closest("label");

              // Verify label exists
              expect(labelElement).not.toBeNull();

              // Find the label text (span element within the label)
              const labelText = labelElement.querySelector("span");

              // Verify label text exists and is visible
              expect(labelText).not.toBeNull();
              expect(labelText.textContent).toBeTruthy();

              // Verify label is not hidden with sr-only or display:none
              const labelStyles = window.getComputedStyle(labelText);
              expect(labelStyles.display).not.toBe("none");
              expect(labelText.className).not.toContain("sr-only");

              // Verify label has meaningful text
              const labelContent = labelText.textContent.trim();
              expect(labelContent.length).toBeGreaterThan(0);
              expect(["Latitude", "Longitude"]).toContain(labelContent);
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should have exactly two input fields with visible labels (latitude and longitude)", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container, getAllByText } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Verify exactly two input fields exist
            const inputs = container.querySelectorAll('input[type="number"]');
            expect(inputs.length).toBe(2);

            // Verify both required labels are visible (use getAllByText to handle multiple renders)
            const latitudeLabels = getAllByText("Latitude");
            const longitudeLabels = getAllByText("Longitude");

            // Should have at least one of each label
            expect(latitudeLabels.length).toBeGreaterThan(0);
            expect(longitudeLabels.length).toBeGreaterThan(0);

            // Verify labels are visible
            latitudeLabels.forEach((label) => expect(label).toBeVisible());
            longitudeLabels.forEach((label) => expect(label).toBeVisible());

            // Verify labels are associated with inputs
            const latitudeInput = latitudeLabels[0]
              .closest("label")
              .querySelector('input[type="number"]');
            const longitudeInput = longitudeLabels[0]
              .closest("label")
              .querySelector('input[type="number"]');

            expect(latitudeInput).not.toBeNull();
            expect(longitudeInput).not.toBeNull();

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should maintain label visibility across different theme modes", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { getAllByText } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Verify labels are visible regardless of theme (use getAllByText to handle multiple renders)
            const latitudeLabels = getAllByText("Latitude");
            const longitudeLabels = getAllByText("Longitude");

            // Should have at least one of each label
            expect(latitudeLabels.length).toBeGreaterThan(0);
            expect(longitudeLabels.length).toBeGreaterThan(0);

            // Verify all labels are visible
            latitudeLabels.forEach((label) => {
              expect(label).toBeVisible();

              // Verify labels have appropriate styling based on theme
              const labelStyles = window.getComputedStyle(label);

              // Labels should not be hidden
              expect(labelStyles.display).not.toBe("none");
              expect(labelStyles.visibility).not.toBe("hidden");
            });

            longitudeLabels.forEach((label) => {
              expect(label).toBeVisible();

              const labelStyles = window.getComputedStyle(label);
              expect(labelStyles.display).not.toBe("none");
              expect(labelStyles.visibility).not.toBe("hidden");
            });

            cleanup();
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should have labels with semantic HTML structure", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find all label elements
            const labels = container.querySelectorAll("label");

            // Should have at least 2 labels (latitude and longitude)
            expect(labels.length).toBeGreaterThanOrEqual(2);

            labels.forEach((label) => {
              // Each label should contain an input element
              const input = label.querySelector('input[type="number"]');

              if (input) {
                // Label should contain a span with text
                const labelText = label.querySelector("span");
                expect(labelText).not.toBeNull();
                expect(labelText.textContent.trim().length).toBeGreaterThan(0);

                // Verify proper nesting: label > span (text) + input
                expect(label.contains(labelText)).toBe(true);
                expect(label.contains(input)).toBe(true);
              }
            });
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should have labels with appropriate text color based on theme", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find label text elements
            const labelTexts = Array.from(
              container.querySelectorAll("label span"),
            ).filter((span) =>
              ["Latitude", "Longitude"].includes(span.textContent.trim()),
            );

            expect(labelTexts.length).toBe(2);

            labelTexts.forEach((labelText) => {
              // Verify label has theme-appropriate text color classes
              const className = labelText.className;

              if (isDark) {
                // Dark theme should use light text colors
                expect(className).toContain("text-white");
              } else {
                // Light theme should use dark text colors
                expect(className).toContain("text-slate");
              }
            });
          },
        ),
        { numRuns: 100 },
      );
    });

    it("should maintain label-input association for accessibility", () => {
      fc.assert(
        fc.property(
          fc.boolean(), // isDark prop
          (isDark) => {
            const { container } = render(
              <LocationsProvider>
                <LocationForm isDark={isDark} />
              </LocationsProvider>,
            );

            // Find all inputs
            const inputs = container.querySelectorAll('input[type="number"]');

            inputs.forEach((input) => {
              // Each input should be within a label element
              const parentLabel = input.closest("label");
              expect(parentLabel).not.toBeNull();

              // The label should contain visible text
              const labelText = parentLabel.querySelector("span");
              expect(labelText).not.toBeNull();
              expect(labelText.textContent.trim().length).toBeGreaterThan(0);

              // Verify the label-input relationship is maintained
              expect(parentLabel.contains(input)).toBe(true);
              expect(parentLabel.contains(labelText)).toBe(true);
            });
          },
        ),
        { numRuns: 100 },
      );
    });
  });
});
