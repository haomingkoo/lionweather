import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route(/\/api\//, (route) => route.fulfill({ status: 503, json: {} }));
});

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test.describe(`at ${viewport.width}px`, () => {
    test.use({ viewport });

    test("the tour opens from the keyboard, closes on Esc and returns focus", async ({ page }) => {
      await page.goto("/");
      const trigger = page.getByRole("button", { name: "▶ 30-second tour" });
      await trigger.focus();
      await page.keyboard.press("Enter");
      const dialog = page.getByRole("dialog", { name: "LionWeather in 30 seconds" });
      await expect(dialog).toBeVisible();
      await expect(dialog.locator("video")).toHaveAttribute("poster", "/media/haze-poster.jpg?v=1");
      await expect(dialog.getByText("Music: Sascha Ende, ende.app (CC BY 4.0)")).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
      await expect(trigger).toBeFocused();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test("?tour=1 opens the tour without autoplay", async ({ page }) => {
      await page.goto("/?tour=1");
      const dialog = page.getByRole("dialog", { name: "LionWeather in 30 seconds" });
      await expect(dialog).toBeVisible();
      expect(await dialog.locator("video").evaluate((v) => v.paused)).toBe(true);
      await page.getByRole("button", { name: "Close tour" }).click();
      await expect(dialog).toBeHidden();
    });
  });
}
