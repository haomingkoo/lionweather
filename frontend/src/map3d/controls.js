import { NavigationControl } from "maplibre-gl";

// Natural orbiting for the 3D maps, shared by /haze and the rain map.
//   mouse     right-drag, ctrl-drag or shift-drag orbits (rotate and tilt)
//   trackpad  pinch zooms; Safari's two-finger rotate turns the map
//   touch     two-finger twist rotates, two-finger vertical drag tilts
//   keyboard  Q and E rotate, W and S tilt, while the map has focus
//   on map    a draggable compass and tilt buttons
// MapLibre's own inertia and easing carry every move, so nothing snaps.

export const MAX_PITCH = 75;
const KEY_ROTATE = 15;
const KEY_TILT = 8;
const ORBIT_DEG_PER_PX = 0.4;
const TILT_DEG_PER_PX = 0.3;
const IDLE_MS = 20000;
const IDLE_DEG_PER_S = 1.5;

class TiltControl {
  onAdd(map) {
    this.map = map;
    const el = document.createElement("div");
    el.className = "maplibregl-ctrl maplibregl-ctrl-group map3d-tilt";
    const button = (label, delta, path) => {
      const b = document.createElement("button");
      b.type = "button";
      b.title = label;
      b.setAttribute("aria-label", label);
      b.innerHTML = `<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="${path}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      b.addEventListener("click", () => map.easeTo({ pitch: Math.max(0, Math.min(MAX_PITCH, map.getPitch() + delta)), duration: 400 }));
      el.appendChild(b);
    };
    button("Tilt up", 10, "M4 13 L10 7 L16 13");
    button("Tilt down", -10, "M4 7 L10 13 L16 7");
    this.el = el;
    return el;
  }

  onRemove() {
    this.el.remove();
  }
}

// Shift-drag orbits too (MapLibre uses shift for box zoom, which these maps skip).
function shiftOrbit(map) {
  const canvas = map.getCanvasContainer();
  let last = null;
  const down = (e) => {
    if (!e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    last = [e.clientX, e.clientY];
    map.stop();
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up, { once: true });
  };
  const move = (e) => {
    const dx = e.clientX - last[0];
    const dy = e.clientY - last[1];
    last = [e.clientX, e.clientY];
    map.jumpTo({
      bearing: map.getBearing() + dx * ORBIT_DEG_PER_PX,
      pitch: Math.max(0, Math.min(MAX_PITCH, map.getPitch() - dy * TILT_DEG_PER_PX)),
    });
  };
  const up = () => window.removeEventListener("mousemove", move);
  canvas.addEventListener("mousedown", down, true);
  return () => {
    canvas.removeEventListener("mousedown", down, true);
    window.removeEventListener("mousemove", move);
  };
}

// Safari reports trackpad rotation as gesture events; other browsers have no API for it.
function trackpadRotate(map) {
  const el = map.getCanvasContainer();
  let start = 0;
  const begin = (e) => {
    e.preventDefault();
    start = map.getBearing() + (e.rotation || 0);
  };
  const change = (e) => {
    e.preventDefault();
    map.jumpTo({ bearing: start - (e.rotation || 0) });
  };
  el.addEventListener("gesturestart", begin);
  el.addEventListener("gesturechange", change);
  return () => {
    el.removeEventListener("gesturestart", begin);
    el.removeEventListener("gesturechange", change);
  };
}

function keys(map) {
  const el = map.getCanvas();
  const onKey = (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    const k = e.key.toLowerCase();
    const bearing = { q: -KEY_ROTATE, e: KEY_ROTATE }[k];
    const tilt = { w: KEY_TILT, s: -KEY_TILT }[k];
    if (bearing == null && tilt == null) return;
    e.preventDefault();
    map.easeTo({
      bearing: map.getBearing() + (bearing || 0),
      pitch: Math.max(0, Math.min(MAX_PITCH, map.getPitch() + (tilt || 0))),
      duration: 300,
    });
  };
  el.addEventListener("keydown", onKey);
  return () => el.removeEventListener("keydown", onKey);
}

// A slow orbit after a quiet spell, on desktop only; any touch of the map stops it.
function idleOrbit(map, enabled) {
  if (!enabled()) return () => {};
  let timer = 0;
  let raf = 0;
  let lastT = 0;
  const stop = () => {
    cancelAnimationFrame(raf);
    raf = 0;
    clearTimeout(timer);
    timer = setTimeout(start, IDLE_MS);
  };
  const spin = (t) => {
    if (lastT && enabled()) map.setBearing(map.getBearing() + ((t - lastT) / 1000) * IDLE_DEG_PER_S);
    lastT = t;
    raf = requestAnimationFrame(spin);
  };
  function start() {
    if (!enabled() || document.hidden) return stop();
    lastT = 0;
    raf = requestAnimationFrame(spin);
  }
  const events = ["mousedown", "touchstart", "wheel", "keydown"];
  const el = map.getCanvasContainer();
  events.forEach((ev) => el.addEventListener(ev, stop, { passive: true }));
  timer = setTimeout(start, IDLE_MS);
  return () => {
    cancelAnimationFrame(raf);
    clearTimeout(timer);
    events.forEach((ev) => el.removeEventListener(ev, stop));
  };
}

/**
 * Wire the orbit controls onto a MapLibre map. Returns a cleanup function.
 * opts.reducedMotion: no idle orbit. opts.idle(): whether the idle orbit may run now.
 */
export function addOrbitControls(map, { reducedMotion = false, idle = () => true } = {}) {
  map.setMaxPitch(MAX_PITCH);
  map.boxZoom.disable();
  map.dragRotate.enable();
  map.touchZoomRotate.enable();
  map.touchZoomRotate.enableRotation();
  map.touchPitch.enable();
  map.keyboard.enable();
  map.addControl(new NavigationControl({ showCompass: true, showZoom: true, visualizePitch: true }), "bottom-right");
  map.addControl(new TiltControl(), "bottom-right");
  const desktop = typeof window !== "undefined" && window.matchMedia?.("(pointer: fine)").matches;
  const cleanups = [shiftOrbit(map), trackpadRotate(map), keys(map), idleOrbit(map, () => !reducedMotion && desktop && idle())];
  return () => cleanups.forEach((fn) => fn());
}

export const ORBIT_TIP = "Right-drag or shift-drag to orbit. Q and E rotate, W and S tilt.";
export const ORBIT_TIP_TOUCH = "Twist with two fingers to rotate. Drag two fingers up or down to tilt.";
