// Shared 3D Singapore basemap: keyless OpenFreeMap vector tiles, AWS terrain, and
// muted day and night palettes that follow DESIGN.md. Used by /haze; built so the
// rain map can reuse it.

export const OMT_ATTRIBUTION =
  '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> · ' +
  '<a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> · ' +
  '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>';
export const DEM_ATTRIBUTION =
  'Elevation: <a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener">Terrain Tiles on AWS</a> (Mapzen, NASA SRTM, USGS)';
const DEM_TILES = ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"];
export const FONT = ["Noto Sans Regular"];
export const FONT_BOLD = ["Noto Sans Bold"];

export const PALETTES = {
  light: {
    land: "#eef1f5",
    landcover: "#e2e8e3",
    park: "#dbe5da",
    water: "#c7d6e3",
    road: "#ffffff",
    street: "#f6f8fa",
    border: "#8593a5",
    label: "#4b5563",
    labelStrong: "#111827",
    halo: "#eef1f5",
    shadow: "#5b6b80",
    highlight: "#ffffff",
    accentShade: "#7d8b9c",
    buildingLow: "#c3cedc",
    buildingHigh: "#8fa3bd",
    light: { color: "#fff7ec", intensity: 0.6 },
    sky: "#dde6ef",
  },
  dark: {
    land: "#131c2b",
    landcover: "#152232",
    park: "#15242c",
    water: "#0a1322",
    road: "#24314a",
    street: "#1d283c",
    border: "#55657e",
    label: "#9fb0c4",
    labelStrong: "#e8eef6",
    halo: "#0b1220",
    shadow: "#02060d",
    highlight: "#3a4a63",
    accentShade: "#22314a",
    buildingLow: "#33415c",
    buildingHigh: "#5d7398",
    light: { color: "#d6e2f2", intensity: 0.5 },
    sky: "#0b1220",
  },
};

// [layer id, paint property, palette key]
const THEMED = [
  ["land", "background-color", "land"],
  ["landcover", "fill-color", "landcover"],
  ["park", "fill-color", "park"],
  ["water", "fill-color", "water"],
  ["roads", "line-color", "road"],
  ["streets", "line-color", "street"],
  ["borders", "line-color", "border"],
  ["relief", "hillshade-shadow-color", "shadow"],
  ["relief", "hillshade-highlight-color", "highlight"],
  ["relief", "hillshade-accent-color", "accentShade"],
  ["places", "text-color", "label"],
  ["places", "text-halo-color", "halo"],
  ["place-singapore", "text-color", "labelStrong"],
  ["place-singapore", "text-halo-color", "halo"],
];

export function buildStyle(theme = "light") {
  const p = PALETTES[theme] || PALETTES.light;
  return {
    version: 8,
    glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
    sources: {
      omt: { type: "vector", url: "https://tiles.openfreemap.org/planet", attribution: OMT_ATTRIBUTION },
      terrain: { type: "raster-dem", tiles: DEM_TILES, encoding: "terrarium", tileSize: 256, maxzoom: 12, attribution: DEM_ATTRIBUTION },
      relief: { type: "raster-dem", tiles: DEM_TILES, encoding: "terrarium", tileSize: 256, maxzoom: 12 },
    },
    layers: [
      { id: "land", type: "background", paint: { "background-color": p.land } },
      {
        id: "landcover",
        type: "fill",
        source: "omt",
        "source-layer": "landcover",
        filter: ["in", ["get", "class"], ["literal", ["wood", "grass", "farmland"]]],
        paint: { "fill-color": p.landcover, "fill-opacity": 0.7 },
      },
      { id: "park", type: "fill", source: "omt", "source-layer": "park", paint: { "fill-color": p.park, "fill-opacity": 0.7 } },
      {
        id: "relief",
        type: "hillshade",
        source: "relief",
        paint: {
          "hillshade-shadow-color": p.shadow,
          "hillshade-highlight-color": p.highlight,
          "hillshade-accent-color": p.accentShade,
          "hillshade-exaggeration": 0.35,
        },
      },
      { id: "water", type: "fill", source: "omt", "source-layer": "water", paint: { "fill-color": p.water } },
      {
        id: "roads",
        type: "line",
        source: "omt",
        "source-layer": "transportation",
        minzoom: 7,
        filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary"]]],
        paint: {
          "line-color": p.road,
          "line-width": ["interpolate", ["linear"], ["zoom"], 7, 0.4, 12, 1.3, 15, 4],
          "line-opacity": 0.85,
        },
      },
      {
        id: "streets",
        type: "line",
        source: "omt",
        "source-layer": "transportation",
        minzoom: 12.5,
        filter: ["in", ["get", "class"], ["literal", ["secondary", "tertiary", "minor"]]],
        paint: { "line-color": p.street, "line-width": ["interpolate", ["linear"], ["zoom"], 12.5, 0.3, 16, 2.5] },
      },
      {
        id: "borders",
        type: "line",
        source: "omt",
        "source-layer": "boundary",
        filter: ["==", ["get", "admin_level"], 2],
        paint: { "line-color": p.border, "line-width": 0.8, "line-dasharray": [3, 2] },
      },
      {
        id: "places",
        type: "symbol",
        source: "omt",
        "source-layer": "place",
        // Singapore's own label gives way to the region labels once zoomed in.
        filter: [
          "any",
          ["==", ["get", "class"], "country"],
          ["all", ["==", ["get", "class"], "city"], ["!=", ["get", "name"], "Singapore"]],
        ],
        layout: {
          "text-field": ["coalesce", ["get", "name:en"], ["get", "name"]],
          "text-font": FONT,
          "text-size": ["match", ["get", "class"], "country", 13, 11],
          "text-max-width": 8,
        },
        paint: { "text-color": p.label, "text-halo-color": p.halo, "text-halo-width": 1.2 },
      },
      {
        id: "place-singapore",
        type: "symbol",
        source: "omt",
        "source-layer": "place",
        maxzoom: 8,
        filter: ["all", ["==", ["get", "class"], "city"], ["==", ["get", "name"], "Singapore"]],
        layout: { "text-field": "Singapore", "text-font": FONT_BOLD, "text-size": 12 },
        paint: { "text-color": p.labelStrong, "text-halo-color": p.halo, "text-halo-width": 1.4 },
      },
    ],
  };
}

export function applyTheme(map, theme) {
  const p = PALETTES[theme] || PALETTES.light;
  THEMED.forEach(([id, prop, key]) => {
    if (map.getLayer(id)) map.setPaintProperty(id, prop, p[key]);
  });
  // Light fixed to the map from the south-west and fairly low, so the two visible
  // faces of a tower read as lit and shaded.
  map.setLight({ anchor: "map", position: [1.4, 225, 55], ...p.light });
}

// Desktop draws at the screen's full sharpness up to 2x; phones stay at 1.75x to save battery.
export function pixelRatioFor(win = typeof window !== "undefined" ? window : undefined) {
  const dpr = win?.devicePixelRatio || 1;
  const phone = (win?.innerWidth ?? 1024) < 700 || !!win?.matchMedia?.("(pointer: coarse)").matches;
  return Math.min(dpr, phone ? 1.75 : 2);
}
