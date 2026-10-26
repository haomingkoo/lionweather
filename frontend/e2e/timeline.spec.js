import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const scene = JSON.parse(readFileSync(new URL("../src/haze/scene.fixture.json", import.meta.url)));
// A longer window, so a drag has room to miss: repeat the six fixture hours to 48.
const hours = Array.from({ length: 48 }, (_, i) => new Date(Date.parse(scene.hours[0]) + i * 3600e3).toISOString());
const stretch = (series) => Object.fromEntries(Object.entries(series).map(([k, v]) => [k, hours.map((_, i) => v[i % v.length])]));
const long = {
  ...scene,
  hours,
  psi: stretch(scene.psi),
  pm25: stretch(scene.pm25),
  wind: { ...scene.wind, mean: hours.map((_, i) => scene.wind.mean[i % scene.wind.mean.length]), station_hourly: {} },
  coverage: { hours: 48, air_hours: 48, wind_hours: 48 },
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/haze/scene*", (route) => route.fulfill({ json: long }));
  await page.route("**/api/haze/wind-field*", (route) => route.fulfill({ json: { status: "unavailable" } }));
  // The map is not under test, and software WebGL on CI runners is slow enough to
  // stall input. Report no WebGL 2 so the page uses its flat map.
  await page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
      return type === "webgl2" ? null : getContext.call(this, type, ...rest);
    };
  });
});

// Seasons had a slider whose drag did not land on the chosen date. A real mouse
// drag on this one must land within an hour of where it is let go.
test("dragging the timeline lands within one hour of the target", async ({ page }) => {
  await page.goto("/haze");
  const slider = page.getByRole("slider", { name: "Hour" });
  await expect(slider).toBeVisible();
  const box = await slider.boundingBox();
  const max = hours.length - 1;
  const thumb = 16;
  const xFor = (i) => box.x + thumb / 2 + ((box.width - thumb) * i) / max;
  const y = box.y + box.height / 2;
  const from = Number(await slider.inputValue());
  for (const target of [5, 30, 17, 44]) {
    const start = Number(await slider.inputValue());
    await page.mouse.move(xFor(start), y);
    await page.mouse.down();
    await page.mouse.move(xFor(target), y, { steps: 12 });
    await page.mouse.up();
    const landed = Number(await slider.inputValue());
    expect(Math.abs(landed - target), `target ${target}, landed ${landed}`).toBeLessThanOrEqual(1);
    await expect(page.locator(".hz-tl-now")).toContainText(
      new Intl.DateTimeFormat("en-SG", { timeZone: "Asia/Singapore", day: "numeric", month: "short" }).format(new Date(hours[landed])),
    );
  }
  expect(from).toBe(max);
});
