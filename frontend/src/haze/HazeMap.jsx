import { useEffect, useRef } from "react";
import { Map as MapLibreMap, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import regionsGeo from "./sg-regions.json";
import { HazeLayer, SG_BOUNDS, opticalDepth } from "./hazeLayer";
import { REGIONS, capitalise, hazeColor, regionAt, windField } from "./hazeData";
import { FONT, FONT_BOLD, PALETTES, applyTheme, buildStyle, pixelRatioFor } from "../map3d/basemap";
import { addBuildings, showBuildings, themeBuildings } from "../map3d/buildings";
import { labelBox } from "./placement";
import { eachParticleAt } from "./smoke";

setWorkerUrl(workerUrl);

// Colours drawn on the map, per theme. Fire colours step with fire power.
const MAP_INK = {
  light: {
    label: "#111827", halo: "rgba(244,246,249,0.94)", line: "#1f2937", path: "#0369a1", path2: "#0369a1",
    tick: "#ffffff", smoke: "120,100,78", smokeK: 1, fireLow: "#e8a23a", fireMid: "#d9622b", fireHigh: "#a3261c", fireStroke: "#fff7ea",
  },
  dark: {
    label: "#e8eef6", halo: "rgba(11,18,32,0.92)", line: "#cbd5e1", path: "#7dd3fc", path2: "#7dd3fc",
    tick: "#0b1220", smoke: "190,165,130", smokeK: 0.55, fireLow: "#f6c35b", fireMid: "#f08a3c", fireHigh: "#e2483a", fireStroke: "#2a1608",
  },
};

export const VIEWS = {
  sg: { center: [103.84, 1.322], zoom: 10.85, pitch: 58, bearing: -16 },
  region: { center: [108.6, -0.3], zoom: 5.05, pitch: 36, bearing: 0 },
};

function cameraFor(view, dim, width) {
  const base = VIEWS[view];
  const narrow = width < 700;
  const zoom = base.zoom - (narrow ? (view === "sg" ? 1.25 : 0.75) : width < 1000 ? 0.4 : 0);
  const center = narrow && view === "sg" ? [103.83, 1.345] : narrow ? [107.2, -0.6] : base.center;
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
    features.push({ type: "Feature", properties: { w: Math.exp(-age / 48) }, geometry: { type: "Point", coordinates: [lon, lat] } });
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
        properties: { major: h % 24 === 0, label: h % 24 === 0 ? `${h} h ago` : "" },
        geometry: { type: "Point", coordinates: [lng, lat] },
      })),
  };
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

export function HazeMap({ scene, index, region, view, dim, layers, motion, theme, smoke, smokeHour, fires, onHover, onSelect }) {
  const container = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const readyRef = useRef(false);
  const propsRef = useRef({});
  propsRef.current = { onHover, onSelect, scene };

  useEffect(() => {
    const el = container.current;
    const map = new MapLibreMap({
      container: el,
      style: buildStyle(theme),
      ...cameraFor(view, dim, el.clientWidth),
      maxPitch: 70,
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

    map.on("load", () => {
      const ink = MAP_INK[theme] || MAP_INK.light;
      applyTheme(map, theme);
      map.addSource("regions", { type: "geojson", data: regionsGeo, promoteId: "region" });
      map.addSource("labels", { type: "geojson", data: EMPTY });
      map.addSource("fires", { type: "geojson", data: EMPTY });
      map.addSource("path850", { type: "geojson", data: EMPTY });
      map.addSource("path925", { type: "geojson", data: EMPTY });
      map.addSource("ticks", { type: "geojson", data: EMPTY });
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
        layout: { "symbol-placement": "line", "symbol-spacing": 90, "icon-image": "path-arrow", "icon-size": 0.8, "icon-allow-overlap": true },
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
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, ["interpolate", ["linear"], ["get", "frp"], 0, 1.4, 100, 3.6], 9, ["interpolate", ["linear"], ["get", "frp"], 0, 3, 100, 7]],
          "circle-color": fireColor,
          "circle-opacity": fireFade,
          "circle-stroke-color": ink.fireStroke,
          "circle-stroke-width": 0.6,
          "circle-stroke-opacity": fireFade,
        },
      });
      map.addLayer(layer);
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
    const io = new IntersectionObserver(([entry]) => layer.setVisible(entry.isIntersecting && !document.hidden));
    io.observe(el);
    const onVis = () => layer.setVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVis);

    return () => {
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
  }, [scene, index, region, theme]);

  useMapSync((map) => map.getSource("fires")?.setData(fireGeo(fires)), [fires]);
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
    const fireColor = ["interpolate", ["linear"], ["get", "frp"], 0, ink.fireLow, 20, ink.fireMid, 100, ink.fireHigh];
    set("fires-glow", "circle-color", fireColor);
    set("fires-core", "circle-color", fireColor);
    set("fires-core", "circle-stroke-color", ink.fireStroke);
    set("smoke", "heatmap-color", smokeRamp(ink.smoke, ink.smokeK));
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
    ["path850", "path925", "path-arrows", "path-ticks", "path-tick-labels"].forEach((id) => vis(id, layers.path && region));
    layer.showHaze = layers.haze;
    layer.showWind = layers.wind;
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
    const cam = cameraFor(view, dim, container.current.clientWidth);
    if (motion) map.flyTo({ ...cam, duration: 2400, curve: 1.3, essential: false });
    else map.jumpTo(cam);
  }, [view, dim, motion]);

  return <div ref={container} className="hz-map-canvas" aria-label="Map of haze over Singapore" role="region" />;
}
