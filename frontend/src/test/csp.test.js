import { readFileSync, readdirSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = join(__dirname, "..", "..");
const serve = JSON.parse(readFileSync(join(root, "public", "serve.json"), "utf8"));
const csp = serve.headers[0].headers.find((h) => h.key === "Content-Security-Policy").value;
const directive = (name) => (csp.split(";").map((d) => d.trim().split(/\s+/)).find(([n]) => n === name) || []).slice(1);

function files(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? files(p) : /\.(jsx?|mjs)$/.test(f) && !/\.test\./.test(f) ? [p] : [];
  });
}

describe("site-wide Content-Security-Policy", () => {
  it("applies to every path and keeps the frame and object locks", () => {
    expect(serve.headers[0].source).toBe("**");
    expect(directive("frame-ancestors")).toEqual(["'none'"]);
    expect(directive("object-src")).toEqual(["'none'"]);
    expect(directive("script-src")).not.toContain("'unsafe-inline'");
  });

  it("allows the API, map tiles, terrain and search hosts the app calls", () => {
    const connect = directive("connect-src");
    const img = directive("img-src");
    ["https://lionweather-backend-production.up.railway.app", "https://tiles.openfreemap.org", "https://s3.amazonaws.com"].forEach((h) => {
      expect(connect).toContain(h);
      expect(img).toContain(h);
    });
    expect(connect).toContain("https://nominatim.openstreetmap.org");
    expect(connect).toContain("https://www.onemap.gov.sg");
    expect(img).toContain("https://tile.openstreetmap.org");
    // Cloudflare injects its Web Analytics beacon at the edge.
    expect(directive("script-src")).toContain("https://static.cloudflareinsights.com");
    expect(connect).toContain("https://cloudflareinsights.com");
    expect(directive("worker-src")).toEqual(expect.arrayContaining(["'self'", "blob:"]));
    expect(directive("media-src")).toEqual(["'self'"]);
  });

  it("covers every host the source code fetches or draws from", () => {
    const allowed = new Set([...directive("connect-src"), ...directive("img-src")]);
    // Hosts in fetch(...) calls, tile templates and terrain URLs.
    const used = new Set();
    files(join(root, "src")).forEach((f) => {
      const text = readFileSync(f, "utf8");
      for (const m of text.matchAll(/(?:fetch\(\s*`|url[:=]\s*["`]|tiles:\s*\[\s*"|DEM_TILES = \[")(https:\/\/[a-z0-9.-]+)/gi)) used.add(m[1]);
      for (const m of text.matchAll(/["`](https:\/\/[a-z0-9.-]+)\/[^"`]*\{z\}/gi)) used.add(m[1]);
    });
    expect(used.size).toBeGreaterThan(2);
    used.forEach((h) => expect(allowed, h).toContain(h));
  });

  it("hashes the inline theme script of the static pages", () => {
    ["privacy.html", "terms.html"].forEach((page) => {
      const html = readFileSync(join(root, "public", page), "utf8");
      const body = html.match(/<script>([\s\S]*?)<\/script>/)[1];
      const hash = `'sha256-${createHash("sha256").update(body).digest("base64")}'`;
      expect(directive("script-src")).toContain(hash);
    });
  });
});
