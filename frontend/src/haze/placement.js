// Place a hover card near the pointer without covering map labels or leaving the map.

function overlap(a, b) {
  const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return w > 0 && h > 0 ? w * h : 0;
}

// Candidates in order of preference; the first that fits and covers nothing wins,
// otherwise the one covering the least.
export function placeCard({ x, y, w, h, width, height, obstacles = [], gap = 14, margin = 8 }) {
  const candidates = [
    [x + gap, y + gap],
    [x + gap, y - gap - h],
    [x - gap - w, y + gap],
    [x - gap - w, y - gap - h],
    [x - w / 2, y + gap * 2],
    [x - w / 2, y - gap * 2 - h],
    [x + gap * 3, y - h / 2],
    [x - gap * 3 - w, y - h / 2],
  ];
  let best = null;
  for (const [cx, cy] of candidates) {
    const left = Math.max(margin, Math.min(width - w - margin, cx));
    const top = Math.max(margin, Math.min(height - h - margin, cy));
    const box = { x: left, y: top, w, h };
    // Never cover the pointer itself.
    const pointer = { x: x - 4, y: y - 4, w: 8, h: 8 };
    const cost = obstacles.reduce((s, o) => s + overlap(box, o), 0) + overlap(box, pointer) * 10;
    if (cost === 0) return { left, top };
    if (!best || cost < best.cost) best = { left, top, cost };
  }
  return { left: best.left, top: best.top };
}

// Region labels are two centred lines (name, value) around their anchor.
export function labelBox({ x, y }, { w = 58, h = 40 } = {}) {
  return { x: x - w / 2, y: y - h / 2, w, h };
}
