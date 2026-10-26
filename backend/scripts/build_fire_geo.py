"""Bake the province and peatland shapes the fire map uses. Run once by hand.

    pip install pyshp shapely
    python scripts/build_fire_geo.py <dir with geoBoundaries ADM1 GeoJSON and PEATMAP SEA_Peatland.shp>

Provinces: geoBoundaries gbOpen ADM1 for Indonesia and Malaysia (OpenStreetMap,
ODbL) and Brunei (public domain). Peatland: PEATMAP, Xu et al. 2018, University of
Leeds, CC BY 4.0 (https://doi.org/10.5518/252), clipped and simplified here.
"""
import json
import math
import os
import sys

import shapefile
from shapely.geometry import box, mapping, shape
from shapely.ops import transform, unary_union

SRC = sys.argv[1] if len(sys.argv) > 1 else "."
BBOX = box(94.5, -6.5, 120.0, 8.0)
R = 6378137.0
ADM_OUT = "app/data/adm1_sea.json"
PEAT_OUT = "../frontend/public/map3d/peat-sea.json"
PEAT_BACKEND = "app/data/peat_sea.json"


def rounded(geom, nd):
    return json.loads(json.dumps(mapping(geom)), parse_float=lambda v: round(float(v), nd))


def provinces():
    feats = []
    for code, country in (("IDN", "Indonesia"), ("MYS", "Malaysia"), ("BRN", "Brunei")):
        with open(os.path.join(SRC, f"{code}-adm1.geojson")) as f:
            data = json.load(f)
        for feat in data["features"]:
            geom = shape(feat["geometry"]).buffer(0)
            if not geom.intersects(BBOX):
                continue
            geom = geom.intersection(BBOX).simplify(0.01, preserve_topology=True)
            if geom.is_empty:
                continue
            feats.append({
                "type": "Feature",
                "properties": {"name": feat["properties"]["shapeName"], "country": country},
                "geometry": rounded(geom, 3),
            })
    return {
        "type": "FeatureCollection",
        "attribution": "geoBoundaries ADM1 (OpenStreetMap contributors, ODbL; Brunei public domain)",
        "features": feats,
    }


def peat():
    def to_lnglat(x, y, z=None):
        return math.degrees(x / R), math.degrees(math.asin(max(-1.0, min(1.0, y / R))))

    reader = shapefile.Reader(os.path.join(SRC, "SEA_Peatland.shp"))
    parts = []
    for shp in reader.shapes():
        geom = transform(to_lnglat, shape(shp.__geo_interface__)).buffer(0)
        parts.append(geom.intersection(BBOX))
    merged = unary_union(parts).simplify(0.015, preserve_topology=True)
    # Drop specks under about 4 km² so the asset stays small.
    polys = [p for p in getattr(merged, "geoms", [merged]) if p.area > 0.0003]
    geom = unary_union(polys)
    return {
        "type": "FeatureCollection",
        "attribution": "PEATMAP, Xu et al. 2018, University of Leeds (CC BY 4.0), simplified",
        "features": [{"type": "Feature", "properties": {}, "geometry": rounded(geom, 3)}],
    }


def main():
    for path, data in ((ADM_OUT, provinces()), (PEAT_OUT, peat())):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        print(path, os.path.getsize(path), "bytes", len(data["features"]), "features")
    # The backend checks clusters against the same peat outline.
    with open(PEAT_OUT) as src, open(PEAT_BACKEND, "w") as dst:
        dst.write(src.read())


if __name__ == "__main__":
    main()
