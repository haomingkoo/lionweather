import { useEffect, useRef, useState } from "react";
import { Map as MapLibreMap, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import { FONT, applyTheme, buildStyle, pixelRatioFor } from "../map3d/basemap";
import { addBuildings, themeBuildings } from "../map3d/buildings";
import { MAX_PITCH, addOrbitControls } from "../map3d/controls";
import { RainLayer } from "../map3d/rainLayer";

setWorkerUrl(workerUrl);

const EMPTY = { type: "FeatureCollection", features: [] };
const INK = {
  light: { gauge: "#0369a1", halo: "#ffffff", place: "#111827", label: "#111827" },
  dark: { gauge: "#7dd3fc", halo: "#0b1220", place: "#e8eef6", label: "#e8eef6" },
};

function gaugeGeo(gauges) {
  return {
    type: "FeatureCollection",
    features: gauges.map((g) => ({
      type: "Feature",
      properties: { name: g.name, mm5: g.mm5 ?? -1, hour: g.hourMm ?? -1, wet: (g.mm5 ?? 0) > 0 },
      geometry: { type: "Point", coordinates: [g.lng, g.lat] },
    })),
  };
}

function placeGeo(locations) {
  return {
    type: "FeatureCollection",
    features: locations.map((l) => ({
      type: "Feature",
      properties: { id: l.id, name: l.weather?.area || `${l.latitude.toFixed(3)}, ${l.longitude.toFixed(3)}` },
      geometry: { type: "Point", coordinates: [l.longitude, l.latitude] },
    })),
  };
}

// The rain map in 3D: buildings, the gauge rain field as a sheet above the city,
// drawn rain under it, gauges you can hover, and the places you saved.
export function RainMap3D({ field, gauges, wind, theme, motion, locations, onMapClick, onPlace }) {
  const el = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const ready = useRef(false);
  const props = useRef({});
  props.current = { onMapClick, onPlace };
  const [hover, setHover] = useState(null);

  useEffect(() => {
    const map = new MapLibreMap({
      container: el.current,
      style: buildStyle(theme),
      center: [103.84, 1.33],
      zoom: el.current.clientWidth < 700 ? 9.9 : 10.9,
      pitch: 55,
      bearing: -12,
      maxPitch: MAX_PITCH,
      maxBounds: [[103.2, 1.0], [104.5, 1.7]],
      pixelRatio: pixelRatioFor(),
      attributionControl: { compact: true },
      canvasContextAttributes: { antialias: true },
    });
    mapRef.current = map;
    const layer = new RainLayer();
    layer.setTheme(theme);
    layer.setAnimate(motion);
    layerRef.current = layer;
    const removeOrbit = addOrbitControls(map, { reducedMotion: !motion, idle: () => false });

    map.on("load", () => {
      const ink = INK[theme] || INK.light;
      applyTheme(map, theme);
      addBuildings(map, { theme, before: "places" }).catch(() => {});
      map.addSource("gauges", { type: "geojson", data: EMPTY });
      map.addSource("saved", { type: "geojson", data: EMPTY });
      map.addLayer(layer);
      map.addLayer({
        id: "gauges",
        type: "circle",
        source: "gauges",
        paint: {
          "circle-radius": ["case", ["get", "wet"], 6, 4],
          "circle-color": ink.halo,
          "circle-stroke-color": ink.gauge,
          "circle-stroke-width": ["case", ["get", "wet"], 3, 1.5],
        },
      });
      map.addLayer({
        id: "saved",
        type: "circle",
        source: "saved",
        paint: { "circle-radius": 7, "circle-color": ink.place, "circle-stroke-color": ink.halo, "circle-stroke-width": 2 },
      });
      map.addLayer({
        id: "saved-labels",
        type: "symbol",
        source: "saved",
        layout: { "text-field": ["get", "name"], "text-font": FONT, "text-size": 12, "text-offset": [0, 1.2], "text-anchor": "top" },
        paint: { "text-color": ink.label, "text-halo-color": ink.halo, "text-halo-width": 1.6 },
      });
      map.on("mousemove", "gauges", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        map.getCanvas().style.cursor = "pointer";
        setHover({ x: e.point.x, y: e.point.y, ...f.properties });
      });
      map.on("mouseleave", "gauges", () => {
        map.getCanvas().style.cursor = "";
        setHover(null);
      });
      map.on("click", (e) => {
        const hit = map.queryRenderedFeatures(e.point, { layers: ["saved", "gauges"] });
        const saved = hit.find((f) => f.layer.id === "saved");
        if (saved) return props.current.onPlace?.(saved.properties.id);
        if (hit.length) return undefined;
        return props.current.onMapClick?.({ latlng: { lat: e.lngLat.lat, lng: e.lngLat.lng } });
      });
      el.current?.querySelector(".maplibregl-ctrl-attrib")?.classList.remove("maplibregl-compact-show");
      ready.current = true;
      window.__rainMap = map;
      map.fire("rain:sync");
    });

    const io = new IntersectionObserver(([entry]) => layer.setVisible(entry.isIntersecting && !document.hidden));
    io.observe(el.current);
    return () => {
      io.disconnect();
      removeOrbit();
      map.remove();
      ready.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const useSync = (fn, deps) => {
    useEffect(() => {
      const map = mapRef.current;
      if (!map) return undefined;
      const run = () => ready.current && fn(map, layerRef.current);
      run();
      map.on("rain:sync", run);
      return () => map.off("rain:sync", run);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);
  };

  useSync((map, layer) => layer.setField(field), [field]);
  useSync((map, layer) => layer.setWind(wind), [wind]);
  useSync((map) => map.getSource("gauges")?.setData(gaugeGeo(gauges)), [gauges]);
  useSync((map) => map.getSource("saved")?.setData(placeGeo(locations)), [locations]);
  useSync((map, layer) => layer.setAnimate(motion), [motion]);
  useSync((map, layer) => {
    const ink = INK[theme] || INK.light;
    applyTheme(map, theme);
    themeBuildings(map, theme);
    layer.setTheme(theme);
    const set = (id, prop, v) => map.getLayer(id) && map.setPaintProperty(id, prop, v);
    set("gauges", "circle-color", ink.halo);
    set("gauges", "circle-stroke-color", ink.gauge);
    set("saved", "circle-color", ink.place);
    set("saved", "circle-stroke-color", ink.halo);
    set("saved-labels", "text-color", ink.label);
    set("saved-labels", "text-halo-color", ink.halo);
  }, [theme]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div ref={el} style={{ width: "100%", height: "100%" }} role="region" aria-label="3D rain map of Singapore" />
      {hover && (
        <div
          className="pointer-events-none absolute z-10 rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink tabular-nums"
          style={{ left: Math.min(hover.x + 14, (el.current?.clientWidth || 400) - 220), top: hover.y + 14 }}
          role="status"
        >
          <p className="font-semibold">{hover.name}</p>
          <p>{hover.mm5 >= 0 ? `${hover.mm5.toFixed(1)} mm in 5 min` : "No reading"}</p>
          {hover.hour >= 0 && <p className="text-muted">{hover.hour.toFixed(1)} mm in the last hour</p>}
        </div>
      )}
    </div>
  );
}

export default RainMap3D;
