import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const scene = JSON.parse(readFileSync(new URL("../src/haze/scene.fixture.json", import.meta.url)));

test.beforeEach(async ({ page }) => {
  await page.route("**/api/haze/scene*", (route) => route.fulfill({ json: scene }));
  await page.route("**/api/haze/wind-field*", (route) => route.fulfill({ json: { status: "unavailable" } }));
  // Other API calls on the dashboard are not under test.
  await page.route(/\/api\/(?!haze|rain)/, (route) => route.fulfill({ status: 503, json: {} }));
  await page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
      return type === "webgl2" ? null : getContext.call(this, type, ...rest);
    };
  });
});

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test.describe(`at ${viewport.width}px`, () => {
    test.use({ viewport });

    test("/haze opened directly: the wordmark goes home", async ({ page }) => {
      await page.goto("/haze");
      await page.getByRole("link", { name: "LionWeather home" }).click();
      await expect(page).toHaveURL(/\/$/);
      await expect(page.getByRole("navigation", { name: "Sections" })).toBeVisible();
    });

    test("/haze has a visible back link and the portfolio link", async ({ page }) => {
      await page.goto("/haze");
      const back = page.getByRole("link", { name: "← Back to forecast" });
      await expect(back).toBeVisible();
      const portfolio = page.getByRole("link", { name: "kooexperience.com", exact: true });
      await portfolio.scrollIntoViewIfNeeded();
      await expect(portfolio).toBeVisible();
      await expect(portfolio).toHaveAttribute("href", "https://kooexperience.com/");
      await back.click();
      await expect(page).toHaveURL(/\/$/);
    });

    test("the dashboard links to /haze and back works", async ({ page }) => {
      await page.goto("/");
      await page.getByRole("link", { name: "Haze", exact: true }).click();
      await expect(page).toHaveURL(/\/haze$/);
      await page.goBack();
      await expect(page).toHaveURL(/\/$/);
    });

    for (const path of ["/privacy.html", "/terms.html", "/#map"]) {
      test(`${path} links home, to /haze and to the portfolio`, async ({ page }) => {
        await page.goto(path);
        await expect(page.getByRole("link", { name: "Haze", exact: true })).toBeVisible();
        const portfolio = page.getByRole("link", { name: "kooexperience.com", exact: true });
        await portfolio.scrollIntoViewIfNeeded();
        await expect(portfolio).toBeVisible();
      });
    }
  });
}

test("a dry island shows no rain, not an error", async ({ page }) => {
  const times = Array.from({ length: 25 }, (_, i) => new Date(Date.UTC(2026, 9, 26, 13, 40 + i * 5)).toISOString());
  const stations = Array.from({ length: 89 }, (_, i) => ({ id: `S${i}`, name: `G${i}`, lat: 1.3 + (i % 9) * 0.02, lng: 103.65 + Math.floor(i / 9) * 0.04 }));
  const dry = { times, stations, values: Object.fromEntries(stations.map((s) => [s.id, times.map(() => 0)])), wind: null };
  await page.route("**/api/rain/gauges", (route) => route.fulfill({ json: dry }));
  await page.goto("/#map");
  await expect(page.getByText(/No rain right now\. 89 NEA gauges, checked/)).toBeVisible();
  await expect(page.getByText(/could not load/)).toHaveCount(0);
});
