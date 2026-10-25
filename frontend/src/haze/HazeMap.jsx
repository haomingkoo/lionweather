import { useEffect, useRef } from "react";
import { Map as MapLibreMap, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import regionsGeo from "./sg-regions.json";
import { HazeLayer, SG_BOUNDS } from "./particles";
import {
  REGIONS,
  capitalise,
  hazeColor,
  hazeDensity,
  regionAt,
  windField,
} from "./hazeData";

setWorkerUrl(workerUrl);

const OMT_ATTRIBUTION =
  '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> · ' +
  '<a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> · ' +
  '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>';
const DEM_ATTRIBUTION =
  'Elevation: <a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener">Terrain Tiles on AWS</a> (Mapzen, NASA SRTM, USGS)';
const DEM_TILES = ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"];
const FONT = ["Noto Sans Regular"];
const FONT_BOLD = ["Noto Sans Bold"];

const INK = "#3a332c";
const LAND = "#ebe4d7";

const STYLE = {
  version: 8,
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  sources: {
    omt: { type: "vector", url: "https://tiles.openfreemap.org/planet", attribution: OMT_ATTRIBUTION },
    terrain: { type: "raster-dem", tiles: DEM_TILES, encoding: "terrarium", tileSize: 256, maxzoom: 13, attribution: DEM_ATTRIBUTION },
    relief: { type: "raster-dem", tiles: DEM_TILES, encoding: "terrarium", tileSize: 256, maxzoom: 12 },
  },
  layers: [
    { id: "land", type: "background", paint: { "background-color": LAND } },
    {
      id: "landcover",
      type: "fill",
      source: "omt",
      "source-layer": "landcover",
      filter: ["in", ["get", "class"], ["literal", ["wood", "grass", "farmland"]]],
      paint: { "fill-color": "#dcd9c2", "fill-opacity": 0.55 },
    },
    {
      id: "park",
      type: "fill",
      source: "omt",
      "source-layer": "park",
      paint: { "fill-color": "#d3d8bd", "fill-opacity": 0.6 },
    },
    {
      id: "relief",
      type: "hillshade",
      source: "relief",
      paint: {
        "hillshade-shadow-color": "#6b5a43",
        "hillshade-highlight-color": "#fff8ea",
        "hillshade-accent-color": "#8c7a5f",
        "hillshade-exaggeration": 0.45,
      },
    },
    {
      id: "water",
      type: "fill",
      source: "omt",
      "source-layer": "water",
      paint: { "fill-color": "#c3cfcb" },
    },
    {
      id: "roads",
      type: "line",
      source: "omt",
      "source-layer": "transportation",
      minzoom: 7,
      filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary"]]],
      paint: {
        "line-color": "#f8f3e9",
        "line-width": ["interpolate", ["linear"], ["zoom"], 7, 0.4, 12, 1.4, 15, 4],
        "line-opacity": 0.9,
      },
    },
    {
      id: "streets",
      type: "line",
      source: "omt",
      "source-layer": "transportation",
      minzoom: 12.5,
      filter: ["in", ["get", "class"], ["literal", ["secondary", "tertiary", "minor"]]],
      paint: { "line-color": "#f3ede2", "line-width": ["interpolate", ["linear"], ["zoom"], 12.5, 0.3, 16, 2.5] },
    },
    {
      id: "borders",
      type: "line",
      source: "omt",
      "source-layer": "boundary",
      filter: ["==", ["get", "admin_level"], 2],
      paint: { "line-color": "#9a8c77", "line-width": 0.8, "line-dasharray": [3, 2] },
    },
    {
      id: "buildings",
      type: "fill-extrusion",
      source: "omt",
      "source-layer": "building",
      minzoom: 13,
      paint: {
        "fill-extrusion-color": "#d9cfbf",
        "fill-extrusion-height": ["coalesce", ["get", "render_height"], 6],
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": 0.92,
      },
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
      paint: { "text-color": "#6a5f52", "text-halo-color": LAND, "text-halo-width": 1.2 },
    },
    {
      id: "place-singapore",
      type: "symbol",
      source: "omt",
      "source-layer": "place",
      maxzoom: 8,
      filter: ["all", ["==", ["get", "class"], "city"], ["==", ["get", "name"], "Singapore"]],
      layout: { "text-field": "Singapore", "text-font": FONT_BOLD, "text-size": 12 },
      paint: { "text-color": "#2b2622", "text-halo-color": LAND, "text-halo-width": 1.4 },
    },
  ],
};

export const VIEWS = {
  sg: { center: [103.835, 1.335], zoom: 10.25, pitch: 56, bearing: -14 },
  region: { center: [105.2, 0.35], zoom: 5.7, pitch: 40, bearing: 0 },
};

function cameraFor(view, dim, width) {
  const base = VIEWS[view];
  const narrow = width < 700;
  const phone = narrow && view === "sg";
  const zoom = base.zoom - (narrow ? (view === "sg" ? 1.3 : 0.9) : 0);
  const center = phone ? [103.83, 1.345] : base.center;
  const pitch = dim === "3d" ? (phone ? 48 : base.pitch) : 0;
  const bearing = dim === "3d" && !phone ? base.bearing : 0;
  return { ...base, center, zoom, pitch, bearing };
}

function labelPoints(scene, index) {
  return {
    type: "FeatureCollection",
    features: REGIONS.map((r) => {
      const at = regionAt(scene, r, index);
      const loc = scene.regions[r];
      return {
        type: "Feature",
        properties: {
          name: capitalise(r),
          value: at.pm25 != null ? `${at.pm25}` : "no data",
        },
        geometry: { type: "Point", coordinates: [loc.lng, loc.lat] },
      };
    }),
  };
}

function hotspotGeo(scene) {
  return {
    type: "FeatureCollection",
    features: (scene.hotspots?.points || []).map((p) => ({
      type: "Feature",
      properties: { frp: p.frp, at: p.at },
      geometry: { type: "Point", coordinates: [p.lng, p.lat] },
    })),
  };
}

function pathGeo(points) {
  return {
    type: "FeatureCollection",
    features: points && points.length > 1
      ? [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: points.map(([lat, lng]) => [lng, lat]) } }]
      : [],
  };
}

export function HazeMap({ scene, index, region, view, dim, layers, motion, onHover, onSelect }) {
  const container = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const readyRef = useRef(false);
  const propsRef = useRef({});
  propsRef.current = { onHover, onSelect };

  // Create the map once.
  useEffect(() => {
    const el = container.current;
    const map = new MapLibreMap({
      container: el,
      style: STYLE,
      ...cameraFor(view, dim, el.clientWidth),
      maxPitch: 70,
      pixelRatio: Math.min(window.devicePixelRatio || 1, 1.75),
      attributionControl: { compact: true },
      canvasContextAttributes: { antialias: true },
      dragRotate: true,
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
          const fps = Math.round((frames * 1000) / (now - since));
          window.__hazeFps = fps;
          frames = 0;
          since = now;
        }
      },
    });
    layerRef.current = layer;

    map.on("load", () => {
      map.addSource("regions", { type: "geojson", data: regionsGeo, promoteId: "region" });
      map.addSource("labels", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("hotspots", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("path", { type: "geojson", data: pathGeo(null) });

      map.addLayer({
        id: "region-fill",
        type: "fill",
        source: "regions",
        paint: {
          "fill-color": ["coalesce", ["feature-state", "color"], "#cfc6b6"],
          "fill-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.16, 0.08],
        },
      }, "buildings");
      map.addLayer({
        id: "region-line",
        type: "line",
        source: "regions",
        paint: {
          "line-color": INK,
          "line-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.85, 0.35],
          "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 1.8, 0.8],
        },
      }, "buildings");
      map.addLayer({
        id: "path-line",
        type: "line",
        source: "path",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#b4581f", "line-width": 2, "line-opacity": 0.75, "line-dasharray": [1.5, 2] },
      });
      map.addLayer({
        id: "hotspots",
        type: "circle",
        source: "hotspots",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, ["interpolate", ["linear"], ["get", "frp"], 0, 1.6, 100, 4], 9, 6],
          "circle-color": ["interpolate", ["linear"], ["get", "frp"], 0, "#e3a33b", 30, "#d0571f", 150, "#8f2a1c"],
          "circle-opacity": 0.85,
          "circle-stroke-color": "#fff6e8",
          "circle-stroke-width": 0.5,
        },
      });
      map.addLayer(layer);
      map.addLayer({
        id: "region-labels",
        type: "symbol",
        source: "labels",
        minzoom: 8,
        layout: {
          "text-field": ["format", ["get", "name"], { "font-scale": 0.85 }, "\n", {}, ["get", "value"], { "text-font": ["literal", FONT_BOLD], "font-scale": 1.15 }],
          "text-font": FONT,
          "text-size": 13,
          "text-line-height": 1.15,
          "text-allow-overlap": true,
        },
        paint: { "text-color": "#2b2622", "text-halo-color": "rgba(246,241,232,0.92)", "text-halo-width": 1.6 },
      });

      const hover = (e) => {
        const f = e.features?.[0];
        if (!f) return;
        map.getCanvas().style.cursor = "pointer";
        propsRef.current.onHover?.({ kind: f.layer.id === "hotspots" ? "fire" : "region", x: e.point.x, y: e.point.y, region: f.properties.region, frp: f.properties.frp, at: f.properties.at });
      };
      map.on("mousemove", "region-fill", hover);
      map.on("mousemove", "hotspots", hover);
      const leave = () => {
        map.getCanvas().style.cursor = "";
        propsRef.current.onHover?.(null);
      };
      map.on("mouseleave", "region-fill", leave);
      map.on("mouseleave", "hotspots", leave);
      map.on("click", "region-fill", (e) => {
        const r = e.features?.[0]?.properties.region;
        if (r) propsRef.current.onSelect?.(r);
      });

      // Start with the credits folded behind the (i) button; they open on tap.
      el.querySelector(".maplibregl-ctrl-attrib")?.classList.remove("maplibregl-compact-show");
      readyRef.current = true;
      map.fire("haze:sync");
    });

    // Stop drawing when the map is off screen or the tab is hidden.
    const io = new IntersectionObserver(([entry]) => {
      layer.setVisible(entry.isIntersecting && !document.hidden);
    });
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

  // Push the hour under the cursor into the map.
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !scene) return;
    const sync = () => {
      if (!readyRef.current) return;
      const mean = scene.wind.mean[index];
      REGIONS.forEach((r, i) => {
        const at = regionAt(scene, r, index);
        map.setFeatureState({ source: "regions", id: r }, {
          color: at.pm25Band?.color || "#cfc6b6",
          selected: r === region,
        });
        let drift = [0, 0];
        if (mean) {
          const rad = (mean.dir_deg * Math.PI) / 180;
          drift = [-mean.speed_kn * Math.sin(rad), -mean.speed_kn * Math.cos(rad)];
        }
        layer.setRegionState(i, { density: hazeDensity(at.pm25), color: hazeColor(at.pm25), drift });
      });
      map.getSource("labels")?.setData(labelPoints(scene, index));
      layer.setField(windField(scene.wind.stations, scene.wind.station_hourly, index, SG_BOUNDS));
      const path = scene.trajectories?.[index];
      map.getSource("path")?.setData(pathGeo(path));
      layer.setPath(layers.path ? path : null);
    };
    sync();
    map.on("haze:sync", sync);
    return () => map.off("haze:sync", sync);
  }, [scene, index, region, layers.path]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !scene) return;
    const apply = () => {
      if (!readyRef.current) return;
      map.getSource("hotspots")?.setData(hotspotGeo(scene));
    };
    apply();
    map.on("haze:sync", apply);
    return () => map.off("haze:sync", apply);
  }, [scene]);

  // Layer toggles.
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map) return;
    const apply = () => {
      if (!readyRef.current) return;
      const vis = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
      vis("buildings", layers.buildings && dim === "3d");
      vis("relief", layers.relief);
      vis("region-fill", layers.regions);
      vis("region-line", layers.regions);
      vis("region-labels", layers.regions);
      vis("hotspots", layers.hotspots);
      vis("path-line", layers.path);
      layer.showHaze = layers.haze;
      layer.showWind = layers.wind;
      layer.kick();
    };
    apply();
    map.on("haze:sync", apply);
    return () => map.off("haze:sync", apply);
  }, [layers, dim]);

  // 2D/3D and camera.
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map) return;
    const apply = () => {
      if (!readyRef.current) return;
      if (dim === "3d") map.setTerrain({ source: "terrain", exaggeration: view === "sg" ? 2.2 : 1.4 });
      else map.setTerrain(null);
      layer.setFlat(dim === "2d");
      // Flat view leans on the fill colour; 3D leaves the colour to the haze itself.
      const [on, off] = dim === "2d" ? [0.5, 0.36] : [0.16, 0.08];
      map.setPaintProperty("region-fill", "fill-opacity", ["case", ["boolean", ["feature-state", "selected"], false], on, off]);
      layer.setAnimate(motion);
      const cam = cameraFor(view, dim, container.current.clientWidth);
      if (motion) map.flyTo({ ...cam, duration: 2600, curve: 1.3, essential: false });
      else map.jumpTo(cam);
    };
    apply();
    map.on("haze:sync", apply);
    return () => map.off("haze:sync", apply);
  }, [view, dim, motion]);

  return <div ref={container} className="hz-map-canvas" aria-label="Map of haze over Singapore" role="region" />;
}
