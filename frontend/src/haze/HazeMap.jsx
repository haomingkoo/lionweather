import { useEffect, useRef } from "react";
import { Map as MapLibreMap, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import regionsGeo from "./sg-regions.json";
import { HazeLayer, SG_BOUNDS, opticalDepth } from "./hazeLayer";
import { REGIONS, capitalise, hazeColor, regionAt, windField } from "./hazeData";
import { FONT, FONT_BOLD, PALETTES, applyTheme, buildStyle, pixelRatioFor } from "../map3d/basemap";
import { addBuildings, showBuildings, themeBuildings } from "../map3d/buildings";
import { MAX_PITCH, addOrbitControls } from "../map3d/controls";
import { WindTowersLayer } from "../map3d/windTowersLayer";
import { buildObstacleMask, gridSizeFor, latticeSpeed, makeFrame, toGrid } from "../map3d/lbm";
import { DISTRICTS, DISTRICT_SIZE_M, footprintsFrom } from "../map3d/streets";
import { labelBox } from "./placement";
import { eachParticleAt, edgeFade } from "./smoke";
import { fireStretches } from "./explain";

setWorkerUrl(workerUrl);

// Colours drawn on the map, per theme. Fire colours step with fire power.
const MAP_INK = {
  light: {
    label: "#111827", halo: "rgba(244,246,249,0.94)", line: "#1f2937", path: "#0369a1", path2: "#0369a1",
    tick: "#ffffff", smoke: "120,100,78", smokeK: 1, peat: "#7a8a47", peatLine: "#5b6a2f", fireLow: "#e8a23a", fireMid: "#d9622b", fireHigh: "#a3261c", fireStroke: "#fff7ea",
  },
  dark: {
    label: "#e8eef6", halo: "rgba(11,18,32,0.92)", line: "#cbd5e1", path: "#7dd3fc", path2: "#7dd3fc",
    tick: "#0b1220", smoke: "190,165,130", smokeK: 0.55, peat: "#8fa05c", peatLine: "#a9bb72", fireLow: "#f6c35b", fireMid: "#f08a3c", fireHigh: "#e2483a", fireStroke: "#2a1608",
  },
};

export const VIEWS = {
  sg: { center: [103.84, 1.322], zoom: 10.85, pitch: 58, bearing: -16 },
  region: { center: [108.6, -0.3], zoom: 5.05, pitch: 36, bearing: 0 },
};

function cameraFor(view, dim, width, district = "cbd") {
  const narrow = width < 700;
  if (view === "streets") {
    const d = DISTRICTS[district] || DISTRICTS.cbd;
    return { center: [d.lng, d.lat], zoom: narrow ? 14.6 : 15.2, pitch: dim === "3d" ? 60 : 0, bearing: dim === "3d" ? d.bearing : 0 };
  }
  const base = VIEWS[view];
  const zoom = base.zoom - (narrow ? (view === "sg" ? 1.25 : 1.1) : width < 1000 ? 0.4 : 0);
  const center = narrow && view === "sg" ? [103.83, 1.345] : narrow ? [107.4, -0.6] : base.center;
  const pitch = dim === "3d" ? (narrow ? Math.min(base.pitch, 50) : base.pitch) : 0;
  const bearing = dim === "3d" && !narrow ? base.bearing : 0;
  return { center, zoom, pitch, bearing };
}

function labelPoints(scene, index) {
  return {
    type: "FeatureCollection",
    features: REGIONS.map((r) => {
      const at = regionAt(scene, r, index);
      const loc = scene.regions[r];
      return {
        type: "Feature",
        properties: { name: capitalise(r), value: at.pm25 != null ? `${at.pm25}` : "no data" },
        geometry: { type: "Point", coordinates: [loc.lng, loc.lat] },
      };
    }),
  };
}

function fireGeo(fires) {
  return {
    type: "FeatureCollection",
    features: (fires || []).map(([lat, lng, frp, seen, n, age], i) => ({
      type: "Feature",
      id: i,
      properties: { frp, seen, n, age },
      geometry: { type: "Point", coordinates: [lng, lat] },
    })),
  };
}

const EMPTY = { type: "FeatureCollection", features: [] };

// Simulated smoke at this hour as weighted points; older smoke weighs less.
function smokeGeo(sim, hour) {
  if (!sim || hour == null) return EMPTY;
  const features = [];
  eachParticleAt(sim, hour, (lat, lon, age) => {
    if (age < 0) return;
    const w = Math.exp(-age / 48) * edgeFade(lat, lon, sim.bounds);
    if (w > 0.01) features.push({ type: "Feature", properties: { w }, geometry: { type: "Point", coordinates: [lon, lat] } });
  });
  return { type: "FeatureCollection", features };
}

function smokeRamp(rgb, k = 1) {
  // Light smoke on the night map reads heavier, so night uses a lower ceiling.
  return ["interpolate", ["linear"], ["heatmap-density"], 0, `rgba(${rgb},0)`, 0.1, `rgba(${rgb},${0.16 * k})`, 0.4, `rgba(${rgb},${0.34 * k})`, 1, `rgba(${rgb},${0.52 * k})`];
}

// The path runs from where the air was to Singapore, so arrows point at Singapore.
function pathGeo(path) {
  if (!path || path.points.length < 2) return EMPTY;
  const coords = path.points.map(([lat, lng]) => [lng, lat]).reverse();
  return { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: coords } }] };
}

function tickGeo(path) {
  if (!path) return EMPTY;
  return {
    type: "FeatureCollection",
    features: path.points
      .filter(([, , h]) => h > 0 && h % 6 === 0)
      .map(([lat, lng, h]) => ({
        type: "Feature",
        properties: { major: h % 24 === 0, label: h % 24 === 0 ? `${h / 24} day${h === 24 ? "" : "s"} ago` : "" },
        geometry: { type: "Point", coordinates: [lng, lat] },
      })),
  };
}

// The Singapore end of the path, where the "arriving now" label sits.
function headGeo(path) {
  if (!path || path.points.length < 2) return EMPTY;
  const [lat, lng] = path.points[0];
  return { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [lng, lat] } }] };
}

// Stretches of the path that pass over fire detections, and a label on the longest.
function fireStretchGeo(path, fires) {
  if (!path || !fires?.length) return [EMPTY, EMPTY];
  const runs = fireStretches(path.points, fires);
  if (!runs.length) return [EMPTY, EMPTY];
  const line = (a, b) => path.points.slice(a, b + 1).map(([lat, lng]) => [lng, lat]);
  const lines = { type: "FeatureCollection", features: runs.map(([a, b]) => ({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: line(a, b) } })) };
  const [a, b] = runs.reduce((best, r) => (r[1] - r[0] > best[1] - best[0] ? r : best));
  const [lat, lng] = path.points[Math.round((a + b) / 2)];
  const label = { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [lng, lat] } }] };
  return [lines, label];
}

// A point a fraction of the way along a path, from where the air was to Singapore.
function alongPath(path, f) {
  const pts = path.points.slice().reverse();
  const seg = [];
  let total = 0;
  for (let i = 1; i < pts.length; i += 1) {
    const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    seg.push(d);
    total += d;
  }
  let target = f * total;
  let i = 0;
  while (i < seg.length - 1 && target > seg[i]) {
    target -= seg[i];
    i += 1;
  }
  const k = seg[i] ? target / seg[i] : 0;
  return [pts[i][1] + (pts[i + 1][1] - pts[i][1]) * k, pts[i][0] + (pts[i + 1][0] - pts[i][0]) * k];
}

function arrowImage() {
  const size = 32;
  const c = document.createElement("canvas");
  c.width = size;
  c.height = size;
  const ctx = c.getContext("2d");
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 4;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(11, 8);
  ctx.lineTo(21, 16);
  ctx.lineTo(11, 24);
  ctx.stroke();
  return ctx.getImageData(0, 0, size, size);
}

// Clusters big enough to name on the map; the rest are still clickable dots.
const CLUSTER_LABEL_MIN = 25;
export const PEAT_URL = "/map3d/peat-sea.json";

function clusterGeo(clusters, selected) {
  return {
    type: "FeatureCollection",
    features: (clusters || []).map((c) => ({
      type: "Feature",
      id: c.id,
      properties: {
        id: c.id,
        frp: c.frp_mw,
        big: c.detections >= CLUSTER_LABEL_MIN,
        selected: c.id === selected,
        label: `${c.province || "Offshore"}\n${c.detections.toLocaleString("en-SG")} fires`,
      },
      geometry: { type: "Point", coordinates: [c.lng, c.lat] },
    })),
  };
}

export function HazeMap({ scene, index, region, view, dim, layers, motion, theme, smoke, smokeHour, fires, cluster, onCluster, onHover, onSelect, district = "cbd", inflow, onWindStatus }) {
  const container = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const readyRef = useRef(false);
  const propsRef = useRef({});
  propsRef.current = { onHover, onSelect, onCluster, onWindStatus, scene, view, dim };
  const windRef = useRef(null);
  const buildToken = useRef(0);

  useEffect(() => {
    const el = container.current;
    const map = new MapLibreMap({
      container: el,
      style: buildStyle(theme),
      ...cameraFor(view, dim, el.clientWidth, district),
      maxPitch: MAX_PITCH,
      maxBounds: [[84, -16], [132, 16]],
      pixelRatio: pixelRatioFor(),
      attributionControl: { compact: true },
      canvasContextAttributes: { antialias: true },
    });
    mapRef.current = map;

    let frames = 0;
    let since = performance.now();
    const layer = new HazeLayer({
      regions: regionsGeo.features,
      onFrame: (now) => {
        frames += 1;
        window.__hazeFrames = (window.__hazeFrames || 0) + 1;
        if (now - since >= 1000) {
          window.__hazeFps = Math.round((frames * 1000) / (now - since));
          frames = 0;
          since = now;
        }
      },
    });
    layer.setTheme(theme);
    layerRef.current = layer;
    const phone = el.clientWidth < 700 || !!window.matchMedia?.("(pointer: coarse)").matches;
    const wind = new WindTowersLayer({
      n: gridSizeFor({ phone }),
      particles: phone ? 8192 : 16384,
      onStatus: (status) => propsRef.current.onWindStatus?.(status),
    });
    wind.setTheme(theme);
    wind.setAnimate(motion);
    windRef.current = wind;
    window.__windLayer = wind;

    map.on("load", () => {
      const ink = MAP_INK[theme] || MAP_INK.light;
      applyTheme(map, theme);
      map.addSource("regions", { type: "geojson", data: regionsGeo, promoteId: "region" });
      map.addSource("labels", { type: "geojson", data: EMPTY });
      map.addSource("fires", { type: "geojson", data: EMPTY });
      map.addSource("path850", { type: "geojson", data: EMPTY });
      map.addSource("path925", { type: "geojson", data: EMPTY });
      map.addSource("ticks", { type: "geojson", data: EMPTY });
      map.addSource("pathhead", { type: "geojson", data: EMPTY });
      map.addSource("pathfire", { type: "geojson", data: EMPTY });
      map.addSource("pathfire-label", { type: "geojson", data: EMPTY });
      map.addSource("pathdot", { type: "geojson", data: EMPTY });
      map.addSource("peat", { type: "geojson", data: EMPTY });
      map.addSource("clusters", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "peat-fill", type: "fill", source: "peat", paint: { "fill-color": ink.peat, "fill-opacity": ["interpolate", ["linear"], ["zoom"], 4, 0.5, 8, 0.3] } }, "places");
      map.addLayer({ id: "peat-line", type: "line", source: "peat", paint: { "line-color": ink.peatLine, "line-width": 0.6, "line-opacity": 0.6 } }, "places");
      map.addSource("smoke", { type: "geojson", data: EMPTY });
      map.addImage("path-arrow", arrowImage(), { pixelRatio: 2, sdf: true });

      map.addLayer({
        id: "region-fill",
        type: "fill",
        source: "regions",
        paint: {
          "fill-color": ["coalesce", ["feature-state", "color"], PALETTES[theme].land],
          "fill-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.16, 0.06],
        },
      }, "places");
      map.addLayer({
        id: "region-line",
        type: "line",
        source: "regions",
        paint: {
          "line-color": ink.line,
          "line-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.85, 0.3],
          "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 1.8, 0.8],
        },
      }, "places");
      addBuildings(map, { theme, before: "places" }).catch(() => {});

      map.addLayer({
        id: "smoke",
        type: "heatmap",
        source: "smoke",
        maxzoom: 10,
        paint: {
          "heatmap-weight": ["get", "w"],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 4, 1.1, 9, 2],
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 4, 16, 6, 30, 9, 64],
          "heatmap-color": smokeRamp(ink.smoke, ink.smokeK),
          "heatmap-opacity": 0.9,
        },
      });
      map.addLayer({
        id: "path925",
        type: "line",
        source: "path925",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ink.path2, "line-width": 1.4, "line-opacity": 0.55, "line-dasharray": [2, 2] },
      });
      map.addLayer({
        id: "path850",
        type: "line",
        source: "path850",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ink.path, "line-width": 3, "line-opacity": 0.95 },
      });
      map.addLayer({
        id: "path-arrows",
        type: "symbol",
        source: "path850",
        layout: { "symbol-placement": "line", "symbol-spacing": 70, "icon-image": "path-arrow", "icon-size": 1.1, "icon-allow-overlap": true },
        paint: { "icon-color": ink.tick },
      });
      map.addLayer({
        id: "path-ticks",
        type: "circle",
        source: "ticks",
        paint: {
          "circle-radius": ["case", ["get", "major"], 5, 3],
          "circle-color": ink.tick,
          "circle-stroke-color": ink.path,
          "circle-stroke-width": 2,
        },
      });
      map.addLayer({
        id: "path-tick-labels",
        type: "symbol",
        source: "ticks",
        filter: ["get", "major"],
        layout: { "text-field": ["get", "label"], "text-font": FONT, "text-size": 12, "text-offset": [0, 1.1], "text-anchor": "top" },
        paint: { "text-color": ink.label, "text-halo-color": ink.halo, "text-halo-width": 1.6 },
      });
      const fireColor = ["interpolate", ["linear"], ["get", "frp"], 0, ink.fireLow, 20, ink.fireMid, 100, ink.fireHigh];
      const fireFade = ["interpolate", ["linear"], ["get", "age"], 0, 1, 24, 0.3];
      map.addLayer({
        id: "fires-glow",
        type: "circle",
        source: "fires",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, ["interpolate", ["linear"], ["get", "frp"], 0, 4, 100, 11], 9, ["interpolate", ["linear"], ["get", "frp"], 0, 10, 100, 24]],
          "circle-color": fireColor,
          "circle-blur": 1,
          "circle-opacity": ["*", 0.45, fireFade],
        },
      });
      map.addLayer({
        id: "fires-core",
        type: "circle",
        source: "fires",
        paint: {
          // Sized by fire power when zoomed out; from zoom 10 each point is drawn at the
          // true size of a VIIRS pixel, 375 m across (radius in pixels doubles per zoom).
          "circle-radius": ["interpolate", ["exponential", 2], ["zoom"], 4, ["interpolate", ["linear"], ["get", "frp"], 0, 1.4, 100, 3.6], 9, ["interpolate", ["linear"], ["get", "frp"], 0, 2.4, 100, 4], 10, 2.45, 16, 157],
          "circle-color": fireColor,
          "circle-opacity": fireFade,
          "circle-stroke-color": ink.fireStroke,
          "circle-stroke-width": 0.6,
          "circle-stroke-opacity": fireFade,
        },
      });
      // The air path draws over the fires so the stretch that crossed them reads.
      map.addLayer({
        id: "path-fire-glow",
        type: "line",
        source: "pathfire",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ink.fireMid, "line-width": 12, "line-blur": 6, "line-opacity": 0.55 },
      });
      ["path925", "path850"].forEach((id) => map.moveLayer(id));
      map.addLayer({
        id: "path-fire",
        type: "line",
        source: "pathfire",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ink.fireMid, "line-width": 3.5 },
      });
      ["path-arrows", "path-ticks", "path-tick-labels"].forEach((id) => map.moveLayer(id));
      map.addLayer({
        id: "cluster-ring",
        type: "circle",
        source: "clusters",
        paint: {
          "circle-radius": ["case", ["get", "selected"], 22, ["get", "big"], 14, 8],
          "circle-color": "rgba(0,0,0,0)",
          "circle-stroke-color": ink.label,
          "circle-stroke-width": ["case", ["get", "selected"], 2.5, 0],
          "circle-stroke-opacity": 0.9,
        },
      });
      map.addLayer({
        id: "cluster-labels",
        type: "symbol",
        source: "clusters",
        filter: ["get", "big"],
        layout: {
          "text-field": ["get", "label"],
          "text-font": FONT_BOLD,
          "text-size": 12,
          "text-anchor": "top",
          "text-offset": [0, 1.2],
          "symbol-sort-key": ["-", 0, ["get", "frp"]],
        },
        paint: { "text-color": ink.label, "text-halo-color": ink.halo, "text-halo-width": 1.8 },
      });
      map.addLayer({
        id: "path-dot-glow",
        type: "circle",
        source: "pathdot",
        paint: { "circle-radius": 14, "circle-color": ink.path, "circle-blur": 1, "circle-opacity": ["get", "a"] },
      });
      map.addLayer({
        id: "path-dot",
        type: "circle",
        source: "pathdot",
        paint: { "circle-radius": 5, "circle-color": ink.tick, "circle-stroke-color": ink.path, "circle-stroke-width": 2.5, "circle-opacity": ["get", "a"], "circle-stroke-opacity": ["get", "a"] },
      });
      map.addLayer({
        id: "path-fire-label",
        type: "symbol",
        source: "pathfire-label",
        layout: { "text-field": "passed over fires here", "text-font": FONT, "text-size": 12, "text-anchor": "left", "text-offset": [1.2, 0] },
        paint: { "text-color": ink.label, "text-halo-color": ink.halo, "text-halo-width": 1.8 },
      });
      map.addLayer({
        id: "path-head",
        type: "symbol",
        source: "pathhead",
        layout: { "text-field": "Air arriving now came this way", "text-font": FONT_BOLD, "text-size": 12, "text-anchor": "left", "text-offset": [1.1, 0.6], "text-max-width": 12 },
        paint: { "text-color": ink.label, "text-halo-color": ink.halo, "text-halo-width": 1.8 },
      });
      map.addLayer(layer);
      map.addLayer(wind);
      map.addLayer({
        id: "region-labels",
        type: "symbol",
        source: "labels",
        minzoom: 8,
        layout: {
          "text-field": ["format", ["get", "name"], { "font-scale": 0.85 }, "\n", {}, ["get", "value"], { "text-font": ["literal", FONT_BOLD], "font-scale": 1.2 }],
          "text-font": FONT,
          "text-size": 13,
          "text-line-height": 1.15,
          "text-allow-overlap": true,
        },
        paint: { "text-color": ink.label, "text-halo-color": ink.halo, "text-halo-width": 1.8 },
      });

      const labelBoxes = () => {
        const s = propsRef.current.scene;
        if (!s || map.getZoom() < 8) return [];
        return REGIONS.map((r) => labelBox(map.project([s.regions[r].lng, s.regions[r].lat])));
      };
      const hover = (e) => {
        const f = e.features?.[0];
        if (!f) return;
        map.getCanvas().style.cursor = "pointer";
        const fire = f.layer.id === "fires-core";
        propsRef.current.onHover?.({
          kind: fire ? "fire" : "region",
          x: e.point.x,
          y: e.point.y,
          region: f.properties.region,
          frp: f.properties.frp,
          seen: f.properties.seen,
          n: f.properties.n,
          obstacles: labelBoxes(),
        });
      };
      map.on("mousemove", "region-fill", hover);
      map.on("mousemove", "fires-core", hover);
      const leave = () => {
        map.getCanvas().style.cursor = "";
        propsRef.current.onHover?.(null);
      };
      map.on("mouseleave", "region-fill", leave);
      const pickCluster = (e) => {
        const id = e.features?.[0]?.properties.id;
        if (id != null) propsRef.current.onCluster?.(Number(id));
      };
      ["cluster-ring", "cluster-labels"].forEach((id) => {
        map.on("click", id, pickCluster);
        map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
      });
      map.on("mouseleave", "fires-core", leave);
      map.on("click", "region-fill", (e) => {
        const r = e.features?.[0]?.properties.region;
        if (r) propsRef.current.onSelect?.(r);
      });

      // Start with the credits folded behind the (i) button; they open on tap.
      el.querySelector(".maplibregl-ctrl-attrib")?.classList.remove("maplibregl-compact-show");
      readyRef.current = true;
      window.__hazeMap = map;
      map.fire("haze:sync");
    });

    // Stop drawing when the map is off screen or the tab is hidden.
    const removeOrbit = addOrbitControls(map, {
      reducedMotion: !motion,
      idle: () => propsRef.current.view === "sg" && propsRef.current.dim === "3d",
    });
    const io = new IntersectionObserver(([entry]) => {
      layer.setVisible(entry.isIntersecting && !document.hidden);
      wind.setVisible(entry.isIntersecting && !document.hidden);
    });
    io.observe(el);
    const onVis = () => {
      layer.setVisible(!document.hidden);
      wind.setVisible(!document.hidden);
    };
    document.addEventListener("visibilitychange", onVis);

    return () => {
      removeOrbit();
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      map.remove();
      mapRef.current = null;
      readyRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Run fn now if the map is ready, and again when it becomes ready.
  const useMapSync = (fn, deps) => {
    useEffect(() => {
      const map = mapRef.current;
      if (!map) return undefined;
      const run = () => readyRef.current && fn(map, layerRef.current);
      run();
      map.on("haze:sync", run);
      return () => map.off("haze:sync", run);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);
  };

  // The hour under the cursor.
  useMapSync((map, layer) => {
    if (!scene) return;
    const mean = scene.wind.mean[index];
    REGIONS.forEach((r, i) => {
      const at = regionAt(scene, r, index);
      map.setFeatureState({ source: "regions", id: r }, { color: at.pm25Band?.color || PALETTES[theme].land, selected: r === region });
      layer.setRegionState(i, { density: opticalDepth(at.pm25), color: hazeColor(at.pm25, theme) });
    });
    if (mean) {
      const rad = (mean.dir_deg * Math.PI) / 180;
      layer.setDrift([-mean.speed_kn * Math.sin(rad), -mean.speed_kn * Math.cos(rad)]);
    }
    map.getSource("labels")?.setData(labelPoints(scene, index));
    layer.setField(windField(scene.wind.stations, scene.wind.station_hourly, index, SG_BOUNDS));
    const air = scene.air_path?.status === "ok" ? scene.air_path.paths : null;
    map.getSource("path850")?.setData(pathGeo(air?.["850hPa"]?.[index]));
    map.getSource("path925")?.setData(pathGeo(air?.["925hPa"]?.[index]));
    map.getSource("ticks")?.setData(tickGeo(air?.["850hPa"]?.[index]));
    map.getSource("pathhead")?.setData(headGeo(air?.["850hPa"]?.[index]));
  }, [scene, index, region, theme]);

  useMapSync((map) => {
    map.getSource("fires")?.setData(fireGeo(fires));
    const air = scene?.air_path?.status === "ok" ? scene.air_path.paths["850hPa"][index] : null;
    const [lines, label] = fireStretchGeo(air, fires);
    map.getSource("pathfire")?.setData(lines);
    map.getSource("pathfire-label")?.setData(label);
  }, [fires, scene, index]);

  // Fire clusters, and the camera flying in when one is picked.
  useMapSync((map) => map.getSource("clusters")?.setData(clusterGeo(scene?.hotspots?.clusters, cluster)), [scene, cluster]);
  const lastCluster = useRef(null);
  useMapSync((map) => {
    const was = lastCluster.current;
    lastCluster.current = cluster;
    if (cluster == null) {
      // Back to region: return to the region camera.
      if (was != null && view === "region") {
        const cam = cameraFor(view, dim, container.current.clientWidth, district);
        if (motion) map.flyTo({ ...cam, duration: 1800 });
        else map.jumpTo(cam);
      }
      return;
    }
    const c = scene?.hotspots?.clusters?.find((x) => x.id === cluster);
    if (!c) return;
    const [w, s, e, n] = c.bbox;
    const pad = 0.15;
    const opts = { padding: 60, maxZoom: 9.5, pitch: dim === "3d" ? 55 : 0, bearing: 0 };
    if (motion) map.fitBounds([[w - pad, s - pad], [e + pad, n + pad]], { ...opts, duration: 2200 });
    else map.fitBounds([[w - pad, s - pad], [e + pad, n + pad]], { ...opts, animate: false });
  }, [cluster]);

  // Peatland loads the first time the Region view opens.
  const peatLoaded = useRef(false);
  useMapSync((map) => {
    if (view !== "region" || !layers.peat || peatLoaded.current) return;
    peatLoaded.current = true;
    fetch(PEAT_URL)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`peat ${r.status}`))))
      .then((data) => map.getSource("peat")?.setData(data))
      .catch(() => {
        peatLoaded.current = false;
      });
  }, [view, layers.peat]);

  // A dot travels along the path into Singapore every 4 seconds: air flowing in.
  useEffect(() => {
    const map = mapRef.current;
    const path = scene?.air_path?.status === "ok" ? scene.air_path.paths["850hPa"][index] : null;
    if (!map || !path || path.points.length < 2 || !motion || view !== "region" || !layers.path) {
      map?.getSource("pathdot")?.setData(EMPTY);
      return undefined;
    }
    let raf = 0;
    const tick = (now) => {
      const f = (now % 4000) / 4000;
      const a = Math.min(1, f / 0.1, (1 - f) / 0.1);
      const [lng, lat] = alongPath(path, f);
      map.getSource("pathdot")?.setData({ type: "Feature", properties: { a }, geometry: { type: "Point", coordinates: [lng, lat] } });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [scene, index, motion, view, layers.path]);
  useMapSync((map) => map.getSource("smoke")?.setData(smokeGeo(smoke, smokeHour)), [smoke, smokeHour]);

  // Theme: day and night palettes.
  useMapSync((map, layer) => {
    const ink = MAP_INK[theme] || MAP_INK.light;
    applyTheme(map, theme);
    themeBuildings(map, theme);
    layer.setTheme(theme);
    const set = (id, prop, value) => map.getLayer(id) && map.setPaintProperty(id, prop, value);
    set("region-line", "line-color", ink.line);
    set("region-labels", "text-color", ink.label);
    set("region-labels", "text-halo-color", ink.halo);
    set("path850", "line-color", ink.path);
    set("path925", "line-color", ink.path2);
    set("path-arrows", "icon-color", ink.tick);
    set("path-ticks", "circle-color", ink.tick);
    set("path-ticks", "circle-stroke-color", ink.path);
    set("path-tick-labels", "text-color", ink.label);
    set("path-tick-labels", "text-halo-color", ink.halo);
    ["path-fire-label", "path-head"].forEach((id) => {
      set(id, "text-color", ink.label);
      set(id, "text-halo-color", ink.halo);
    });
    set("path-fire", "line-color", ink.fireMid);
    set("path-fire-glow", "line-color", ink.fireMid);
    set("path-dot-glow", "circle-color", ink.path);
    set("path-dot", "circle-color", ink.tick);
    set("path-dot", "circle-stroke-color", ink.path);
    const fireColor = ["interpolate", ["linear"], ["get", "frp"], 0, ink.fireLow, 20, ink.fireMid, 100, ink.fireHigh];
    set("fires-glow", "circle-color", fireColor);
    set("fires-core", "circle-color", fireColor);
    set("fires-core", "circle-stroke-color", ink.fireStroke);
    set("smoke", "heatmap-color", smokeRamp(ink.smoke, ink.smokeK));
    set("peat-fill", "fill-color", ink.peat);
    set("peat-line", "line-color", ink.peatLine);
    set("cluster-labels", "text-color", ink.label);
    set("cluster-labels", "text-halo-color", ink.halo);
    set("cluster-ring", "circle-stroke-color", ink.label);
  }, [theme]);

  // Layer toggles.
  useMapSync((map, layer) => {
    const vis = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    showBuildings(map, layers.buildings && dim === "3d");
    vis("relief", layers.relief);
    vis("region-fill", layers.regions);
    vis("region-line", layers.regions);
    vis("region-labels", layers.regions);
    // The air path and fires belong to the Region view; over the city they only clutter.
    const region = view === "region";
    ["fires-glow", "fires-core"].forEach((id) => vis(id, layers.hotspots && region));
    ["path850", "path-arrows", "path-ticks", "path-tick-labels", "path-fire", "path-fire-glow", "path-fire-label", "path-head", "path-dot", "path-dot-glow"].forEach((id) => vis(id, layers.path && region));
    vis("path925", layers.path925 && region);
    ["peat-fill", "peat-line"].forEach((id) => vis(id, layers.peat && region));
    ["cluster-ring", "cluster-labels"].forEach((id) => vis(id, layers.hotspots && region));
    layer.showHaze = layers.haze;
    // In the street view the simulated flow replaces the island-wide streaks.
    layer.showWind = layers.wind && view !== "streets";
    vis("smoke", layers.smoke && region);
    layer.kick();
  }, [layers, dim, view]);

  // 2D/3D and camera. Terrain only in the Region view: Singapore is flat, and
  // buildings there stand at their real height on the ground.
  useMapSync((map, layer) => {
    if (dim === "3d" && view === "region") map.setTerrain({ source: "terrain", exaggeration: 1.5 });
    else map.setTerrain(null);
    layer.setFlat(dim === "2d");
    const [on, off] = dim === "2d" ? [0.5, 0.36] : [0.16, 0.06];
    map.setPaintProperty("region-fill", "fill-opacity", ["case", ["boolean", ["feature-state", "selected"], false], on, off]);
    layer.setAnimate(motion);
    const cam = cameraFor(view, dim, container.current.clientWidth, district);
    if (motion) map.flyTo({ ...cam, duration: 2400, curve: 1.3, essential: false });
    else map.jumpTo(cam);
  }, [view, dim, motion, district]);

  // Wind among the towers: build the obstacle grid from the footprints loaded for
  // the district, turned to this hour's measured wind, and restart the simulation.
  // Tiles arrive after the camera does, and the animated layers keep the map from
  // ever going idle, so each finished move and each loaded tile batch (debounced)
  // checks whether more buildings have loaded since the last build.
  const windBuild = useRef(null);
  useMapSync((map) => {
    const wind = windRef.current;
    if (windBuild.current) {
      map.off("moveend", windBuild.current.later);
      map.off("sourcedata", windBuild.current.onData);
      clearTimeout(windBuild.current.timer);
    }
    windBuild.current = null;
    const on = view === "streets" && !!inflow;
    wind.setActive(on);
    wind.setTheme(theme);
    if (!on) return;
    const d = DISTRICTS[district] || DISTRICTS.cbd;
    const state = { count: -1 };
    const build = () => {
      if (map.isMoving()) return;
      const frame = makeFrame({ lat: d.lat, lng: d.lng, sizeM: DISTRICT_SIZE_M, n: wind.n, fromDeg: inflow.fromDeg });
      const inside = (f) => {
        const ring = f.geometry?.type === "Polygon" ? f.geometry.coordinates[0] : f.geometry?.coordinates?.[0]?.[0];
        if (!ring?.length) return false;
        const [gx, gy] = toGrid(frame, ring[0][0], ring[0][1]);
        return gx > -40 && gx < frame.n + 40 && gy > -40 && gy < frame.n + 40;
      };
      const live = map.querySourceFeatures("omt", { sourceLayer: "building" }).filter(inside);
      const baked = map.getSource("sg-buildings") ? map.querySourceFeatures("sg-buildings").filter(inside) : [];
      const count = live.length + baked.length;
      if (count <= state.count * 1.1 + 5) return;
      state.count = count;
      const mask = buildObstacleMask(footprintsFrom([...live, ...baked]), frame);
      wind.setScene({ frame, mask, u0: latticeSpeed(inflow.speedKn) });
      window.__windSolid = mask.reduce((a, v) => a + v, 0) / mask.length;
    };
    const handle = { build, timer: 0 };
    handle.later = () => {
      clearTimeout(handle.timer);
      handle.timer = setTimeout(build, 400);
    };
    handle.onData = (e) => e.sourceId === "omt" && handle.later();
    windBuild.current = handle;
    map.on("moveend", handle.later);
    map.on("sourcedata", handle.onData);
    handle.later();
    map.triggerRepaint();
  }, [view, district, inflow?.fromDeg, inflow?.speedKn, theme]);

  useMapSync(() => windRef.current?.setAnimate(motion), [motion]);

  return <div ref={container} className="hz-map-canvas" aria-label="Map of haze over Singapore" role="region" />;
}
