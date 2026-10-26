import { PALETTES } from "./basemap";

// Real-height OSM buildings. OpenFreeMap carries separate buildings only from zoom 14,
// so the island-wide view uses a baked copy of the ones 40 m and taller
// (scripts/build_sg_buildings.py). The count drawn is capped by zoom:
//   below 10.5   landmark towers, 100 m and up
//   10.5 to 14   every baked building, 40 m and up
//   14 and up    every building from the live tiles
export const BUILDINGS_URL = "/map3d/sg-buildings.json";
export const BUILDING_LAYERS = ["bld-landmark", "bld-city", "bld-street"];
const LANDMARK_HEIGHT = 100;
const CITY_MAX_ZOOM = 14;

// Baked rows are [height, base, [x0, y0, dx1, dy1, ...]] in integer steps from the origin.
export function decodeBuildings(asset) {
  const [ox, oy] = asset.origin;
  const scale = asset.scale;
  const features = asset.buildings.map(([height, base, flat], i) => {
    let x = flat[0];
    let y = flat[1];
    const ring = [[ox + x / scale, oy + y / scale]];
    for (let k = 2; k < flat.length; k += 2) {
      x += flat[k];
      y += flat[k + 1];
      ring.push([ox + x / scale, oy + y / scale]);
    }
    ring.push(ring[0]);
    return { type: "Feature", id: i, properties: { h: height, b: base }, geometry: { type: "Polygon", coordinates: [ring] } };
  });
  return { type: "FeatureCollection", features };
}

function colorRamp(p, heightExpr) {
  return ["interpolate", ["linear"], heightExpr, 0, p.buildingLow, 60, p.buildingLow, 280, p.buildingHigh];
}

function paint(p, heightExpr, baseExpr) {
  return {
    "fill-extrusion-color": colorRamp(p, heightExpr),
    "fill-extrusion-height": heightExpr,
    "fill-extrusion-base": baseExpr,
    "fill-extrusion-opacity": 0.95,
    "fill-extrusion-vertical-gradient": true,
  };
}

// Adds the three building layers below `before`. The baked set loads in the background.
export function addBuildings(map, { theme = "light", before, fetchImpl = fetch } = {}) {
  const p = PALETTES[theme] || PALETTES.light;
  map.addSource("sg-buildings", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  const baked = paint(p, ["get", "h"], ["get", "b"]);
  map.addLayer({
    id: "bld-landmark",
    type: "fill-extrusion",
    source: "sg-buildings",
    maxzoom: 10.5,
    filter: [">=", ["get", "h"], LANDMARK_HEIGHT],
    paint: baked,
  }, before);
  map.addLayer({ id: "bld-city", type: "fill-extrusion", source: "sg-buildings", minzoom: 10.5, maxzoom: CITY_MAX_ZOOM, paint: baked }, before);
  map.addLayer({
    id: "bld-street",
    type: "fill-extrusion",
    source: "omt",
    "source-layer": "building",
    minzoom: CITY_MAX_ZOOM,
    paint: paint(p, ["coalesce", ["get", "render_height"], 6], ["coalesce", ["get", "render_min_height"], 0]),
  }, before);
  return fetchImpl(BUILDINGS_URL)
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`buildings ${r.status}`))))
    .then((asset) => {
      map.getSource("sg-buildings")?.setData(decodeBuildings(asset));
      return asset.buildings.length;
    });
}

export function themeBuildings(map, theme) {
  const p = PALETTES[theme] || PALETTES.light;
  BUILDING_LAYERS.forEach((id) => {
    if (!map.getLayer(id)) return;
    const h = id === "bld-street" ? ["coalesce", ["get", "render_height"], 6] : ["get", "h"];
    map.setPaintProperty(id, "fill-extrusion-color", colorRamp(p, h));
  });
}

export function showBuildings(map, on) {
  BUILDING_LAYERS.forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
}
