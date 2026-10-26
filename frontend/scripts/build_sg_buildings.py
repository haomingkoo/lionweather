"""Bake Singapore's taller OSM buildings into a small asset for the 3D maps.

OpenFreeMap only carries separate buildings at zoom 14, so the island-wide view needs its
own copy. Run once with `pip install mapbox-vector-tile shapely`, then
`python scripts/build_sg_buildings.py [cache_dir]` from frontend/.
Data: OpenStreetMap contributors (ODbL) via OpenFreeMap / OpenMapTiles.
"""
import json
import math
import os
import sys
import urllib.request

import mapbox_vector_tile
from shapely.geometry import shape
from shapely.ops import unary_union

ZOOM = 14
BOUNDS = (103.59, 1.20, 104.06, 1.48)  # west, south, east, north
MIN_HEIGHT = 40  # metres; about 13 storeys, so HDB towns and the city show
SIMPLIFY = 0.00008  # degrees, about 9 m: finer than a pixel at island zoom
SCALE = 1e5  # coordinates stored as integer steps of 0.00001 degrees, about 1 m
OUT = "public/map3d/sg-buildings.json"
CACHE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/sg-building-tiles"


def tile_range(z):
    def xy(lng, lat):
        n = 2 ** z
        x = int((lng + 180) / 360 * n)
        y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
        return x, y
    x0, y1 = xy(BOUNDS[0], BOUNDS[1])
    x1, y0 = xy(BOUNDS[2], BOUNDS[3])
    return range(x0, x1 + 1), range(y0, y1 + 1)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lionweather-build"})
    with urllib.request.urlopen(req) as r:
        return r.read()


def tile_url():
    return json.loads(get("https://tiles.openfreemap.org/planet"))["tiles"][0]


def fetch(url, path):
    if not os.path.exists(path):
        data = get(url)
        with open(path, "wb") as f:
            f.write(data)
    with open(path, "rb") as f:
        return f.read()


def to_lnglat(x, y, z, tx, ty, extent):
    n = 2 ** z
    lng = (tx + x / extent) / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + 1 - y / extent) / n))))
    return lng, lat


def main():
    os.makedirs(CACHE, exist_ok=True)
    template = tile_url()
    xs, ys = tile_range(ZOOM)
    by_height = {}
    for tx in xs:
        for ty in ys:
            data = fetch(template.format(z=ZOOM, x=tx, y=ty), f"{CACHE}/{ZOOM}-{tx}-{ty}.pbf")
            layer = mapbox_vector_tile.decode(data, default_options={"y_coord_down": False}).get("building")
            if not layer:
                continue
            extent = layer.get("extent", 4096)
            for f in layer["features"]:
                h = f["properties"].get("render_height") or 0
                if h < MIN_HEIGHT:
                    continue
                g = f["geometry"]
                polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []
                for rings in polys:
                    ring = [to_lnglat(x, y, ZOOM, tx, ty, extent) for x, y in rings[0]]
                    if len(ring) < 4:
                        continue
                    poly = shape({"type": "Polygon", "coordinates": [ring]})
                    if not poly.is_valid or poly.area <= 0:
                        continue
                    key = (round(h), round(f["properties"].get("render_min_height") or 0))
                    by_height.setdefault(key, []).append(poly)
    out = []
    for (h, base), polys in by_height.items():
        # Buildings split across tile edges are merged back into one footprint.
        merged = unary_union(polys).simplify(SIMPLIFY)
        for p in getattr(merged, "geoms", [merged]):
            if p.geom_type != "Polygon" or p.area <= 0:
                continue
            # First point absolute from the west/south corner, then deltas; the
            # closing point is implied.
            pts = [(round((x - BOUNDS[0]) * SCALE), round((y - BOUNDS[1]) * SCALE)) for x, y in p.exterior.coords[:-1]]
            flat = list(pts[0])
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                flat += [x1 - x0, y1 - y0]
            out.append([h, base, flat])
    out.sort(key=lambda b: -b[0])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"attribution": "OpenStreetMap contributors (ODbL), via OpenFreeMap", "min_height": MIN_HEIGHT, "origin": BOUNDS[:2], "scale": SCALE, "buildings": out}, f, separators=(",", ":"))
    print(len(out), "buildings,", os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
