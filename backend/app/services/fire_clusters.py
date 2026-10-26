"""Group NASA fire detections into clusters, named by province, with a peatland share.

Provinces come from geoBoundaries ADM1 (OpenStreetMap, ODbL; Brunei public domain)
and peatland from PEATMAP (Xu et al. 2018, University of Leeds, CC BY 4.0), both
baked into app/data by scripts/build_fire_geo.py.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"
CELL_DEG = 0.15  # detections in touching cells of about 17 km join one cluster


def _polygons(geometry: dict) -> list[list[np.ndarray]]:
    polys = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    return [[np.asarray(ring, dtype=float) for ring in poly] for poly in polys]


def _bbox(rings: list[np.ndarray]) -> tuple[float, float, float, float]:
    outer = rings[0]
    return outer[:, 0].min(), outer[:, 1].min(), outer[:, 0].max(), outer[:, 1].max()


def _in_ring(lon: np.ndarray, lat: np.ndarray, ring: np.ndarray, chunk: int = 400) -> np.ndarray:
    """Vectorised ray casting: which points fall inside one ring (in chunks, to bound memory)."""
    if len(lon) > chunk:
        return np.concatenate([_in_ring(lon[i:i + chunk], lat[i:i + chunk], ring) for i in range(0, len(lon), chunk)])
    x0, y0 = ring[:-1, 0][:, None], ring[:-1, 1][:, None]
    x1, y1 = ring[1:, 0][:, None], ring[1:, 1][:, None]
    crosses = (y0 > lat) != (y1 > lat)
    with np.errstate(divide="ignore", invalid="ignore"):
        x_at = (x1 - x0) * (lat - y0) / (y1 - y0) + x0
    return (np.count_nonzero(crosses & (lon < x_at), axis=0) % 2) == 1


def _in_polygons(lon: np.ndarray, lat: np.ndarray, polys) -> np.ndarray:
    inside = np.zeros(lon.shape, bool)
    for rings, (w, s, e, n) in polys:
        cand = (~inside) & (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
        if not cand.any():
            continue
        idx = np.nonzero(cand)[0]
        hit = _in_ring(lon[idx], lat[idx], rings[0])
        for hole in rings[1:]:
            hit &= ~_in_ring(lon[idx], lat[idx], hole)
        inside[idx[hit]] = True
    return inside


@lru_cache(maxsize=1)
def provinces() -> list[dict]:
    data = json.loads((DATA / "adm1_sea.json").read_text())
    out = []
    for feat in data["features"]:
        polys = [(rings, _bbox(rings)) for rings in _polygons(feat["geometry"])]
        out.append({"name": feat["properties"]["name"], "country": feat["properties"]["country"], "polys": polys})
    return out


@lru_cache(maxsize=1)
def peatland() -> list:
    data = json.loads((DATA / "peat_sea.json").read_text())
    return [(rings, _bbox(rings)) for feat in data["features"] for rings in _polygons(feat["geometry"])]


def locate(lats, lons) -> tuple[list[int | None], np.ndarray]:
    """Province index (None offshore) and peatland flag for each point."""
    lat = np.asarray(lats, float)
    lon = np.asarray(lons, float)
    which: list[int | None] = [None] * len(lat)
    for i, prov in enumerate(provinces()):
        for k in np.nonzero(_in_polygons(lon, lat, prov["polys"]))[0]:
            if which[k] is None:
                which[k] = i
    return which, _in_polygons(lon, lat, peatland())


def cluster_points(points: list[list]) -> tuple[list[int], list[dict]]:
    """Points are [lat, lng, MW, seen, detections]. Returns each point's cluster id and the clusters.

    Detections in touching grid cells form one cluster; a cluster spanning a
    border is split by province, so every cluster has one name.
    """
    if not points:
        return [], []
    which, peat = locate([p[0] for p in points], [p[1] for p in points])
    cells = {}
    for i, p in enumerate(points):
        cells.setdefault((math.floor(p[0] / CELL_DEG), math.floor(p[1] / CELL_DEG)), []).append(i)

    parent = {c: c for c in cells}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    for (y, x) in cells:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                n = (y + dy, x + dx)
                if n in cells:
                    parent[find(n)] = find((y, x))

    groups: dict[tuple, list[int]] = {}
    for cell, idx in cells.items():
        root = find(cell)
        for i in idx:
            groups.setdefault((root, which[i]), []).append(i)

    provs = provinces()
    clusters = []
    ids = [0] * len(points)
    ordered = sorted(groups.values(), key=lambda idx: -sum(points[i][2] for i in idx))
    for cid, idx in enumerate(ordered):
        detections = sum(points[i][4] for i in idx)
        frp = sum(points[i][2] for i in idx)
        weight = [max(points[i][2], 0.1) for i in idx]
        lat = sum(points[i][0] * w for i, w in zip(idx, weight)) / sum(weight)
        lon = sum(points[i][1] * w for i, w in zip(idx, weight)) / sum(weight)
        prov = which[idx[0]]
        on_peat = sum(points[i][4] for i in idx if peat[i])
        for i in idx:
            ids[i] = cid
        clusters.append({
            "id": cid,
            "province": provs[prov]["name"] if prov is not None else None,
            "country": provs[prov]["country"] if prov is not None else None,
            "lat": round(lat, 3),
            "lng": round(lon, 3),
            "bbox": [
                round(min(points[i][1] for i in idx), 3), round(min(points[i][0] for i in idx), 3),
                round(max(points[i][1] for i in idx), 3), round(max(points[i][0] for i in idx), 3),
            ],
            "detections": detections,
            "frp_mw": round(frp, 1),
            "first": min(points[i][3] for i in idx),
            "last": max(points[i][3] for i in idx),
            "peat_share": round(on_peat / detections, 2) if detections else 0,
        })
    return ids, clusters
