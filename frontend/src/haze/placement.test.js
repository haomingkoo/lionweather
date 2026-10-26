import { describe, expect, it } from "vitest";
import { labelBox, placeCard } from "./placement";

const card = { w: 150, h: 64, width: 1000, height: 600 };

function overlaps(a, b) {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

describe("placeCard", () => {
  it("sits below and right of the pointer when nothing is in the way", () => {
    expect(placeCard({ ...card, x: 300, y: 200 })).toEqual({ left: 314, top: 214 });
  });

  it("moves off a label it would cover, like South 66 under the West card", () => {
    const south = labelBox({ x: 400, y: 260 });
    const pos = placeCard({ ...card, x: 330, y: 220, obstacles: [south] });
    expect(overlaps({ x: pos.left, y: pos.top, w: card.w, h: card.h }, south)).toBe(false);
  });

  it("stays inside the map near the edges", () => {
    const pos = placeCard({ ...card, x: 990, y: 590 });
    expect(pos.left + card.w).toBeLessThanOrEqual(1000);
    expect(pos.top + card.h).toBeLessThanOrEqual(600);
    expect(pos.left).toBeGreaterThanOrEqual(0);
  });

  it("picks the least-covering spot when every spot covers something", () => {
    const walls = [{ x: 0, y: 0, w: 1000, h: 600 }];
    const pos = placeCard({ ...card, x: 500, y: 300, obstacles: walls });
    expect(Number.isFinite(pos.left) && Number.isFinite(pos.top)).toBe(true);
  });
});
