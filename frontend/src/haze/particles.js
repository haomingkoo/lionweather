import { MercatorCoordinate } from "maplibre-gl";
import { sampleField } from "./hazeData";

// MapLibre custom layer: haze puffs per region, wind streaks and the drift path.
// Haze puffs animate on the GPU; wind and drift points are small CPU buffers.

const HAZE_VS = `#version 300 es
uniform mat4 u_matrix;
uniform vec2 u_viewport;
uniform float u_time;
uniform float u_flat;
uniform float u_density[5];
uniform vec3 u_color[5];
uniform vec2 u_drift[5];
in vec3 a_pos;
in vec4 a_seed; // x: region, y: visibility rank, z: size, w: phase
in float a_meter;
out vec4 v_color;
void main() {
  int r = int(a_seed.x + 0.5);
  float loop = fract(u_time * 0.035 + a_seed.w);
  vec3 p = a_pos;
  p.xy += u_drift[r] * (loop - 0.5);
  p.z *= (1.0 - u_flat);
  float on = step(a_seed.y, u_density[r]);
  float fade = sin(loop * 3.14159);
  float radius = (900.0 + 1600.0 * a_seed.z) * a_meter;
  vec4 c = u_matrix * vec4(p, 1.0);
  vec4 e = u_matrix * vec4(p + vec3(radius, 0.0, 0.0), 1.0);
  float px = length(e.xy / e.w - c.xy / c.w) * 0.5 * u_viewport.x;
  gl_Position = c;
  gl_PointSize = on > 0.5 ? clamp(px * 2.0, 2.0, 220.0) : 0.0;
  float a = on * fade * mix(0.06, 0.2, u_density[r]) * (1.25 - 0.6 * a_seed.z) * mix(1.0, 0.8, u_flat);
  v_color = vec4(u_color[r] * a, a);
}`;

const DYN_VS = `#version 300 es
uniform mat4 u_matrix;
in vec3 a_pos;
in vec4 a_color;
in float a_size;
out vec4 v_color;
void main() {
  gl_Position = u_matrix * vec4(a_pos, 1.0);
  gl_PointSize = a_size;
  v_color = a_color;
}`;

const SOFT_FS = `#version 300 es
precision mediump float;
in vec4 v_color;
out vec4 frag;
void main() {
  vec2 d = gl_PointCoord - 0.5;
  float r = dot(d, d) * 4.0;
  if (r > 1.0) discard;
  frag = v_color * exp(-r * 3.0);
}`;

const LINE_VS = `#version 300 es
uniform mat4 u_matrix;
in vec3 a_pos;
in float a_alpha;
out vec4 v_color;
void main() {
  gl_Position = u_matrix * vec4(a_pos, 1.0);
  v_color = vec4(0.17, 0.15, 0.13, 1.0) * a_alpha;
}`;

const FLAT_FS = `#version 300 es
precision mediump float;
in vec4 v_color;
out vec4 frag;
void main() { frag = v_color; }`;

function compile(gl, vs, fs) {
  const program = gl.createProgram();
  for (const [type, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, src);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
    gl.attachShader(program, shader);
  }
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
  return program;
}

function pointInRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function inFeature(lng, lat, geometry) {
  const polys = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  return polys.some((rings) => pointInRing(lng, lat, rings[0]) && !rings.slice(1).some((h) => pointInRing(lng, lat, h)));
}

function bbox(geometry) {
  const polys = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  let [w, s, e, n] = [Infinity, Infinity, -Infinity, -Infinity];
  polys.forEach((p) => p[0].forEach(([x, y]) => {
    w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y);
  }));
  return [w, s, e, n];
}

// Deterministic so the cloud looks the same on every visit.
function rng(seed) {
  let t = seed >>> 0;
  return () => {
    t = (t + 0x6d2b79f5) >>> 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

export const SG_BOUNDS = [103.58, 1.18, 104.1, 1.49];
const PUFFS_PER_REGION = 1400;
const WIND_PARTICLES = 900;
const TRAIL = 12;
const TRAIL_STEP = 0.09; // seconds between trail points
const DEG_PER_KNOT_SECOND = 0.005;
const WIND_ALTITUDE = 260;
const DRIFT_DOTS = 28;

export class HazeLayer {
  constructor({ regions, onFrame }) {
    this.id = "haze-particles";
    this.type = "custom";
    this.renderingMode = "3d";
    this.regions = regions; // GeoJSON features with properties.region
    this.onFrame = onFrame;
    this.density = new Float32Array(5);
    this.targetDensity = new Float32Array(5);
    this.color = new Float32Array(15);
    this.drift = new Float32Array(10);
    this.flat = 0;
    this.targetFlat = 0;
    this.showHaze = true;
    this.showWind = true;
    this.field = null;
    this.path = null;
    this.animate = true;
    this.visible = true;
    this.time = 0;
    this.last = 0;
  }

  onAdd(map, gl) {
    this.map = map;
    this.gl = gl;
    this.hazeProgram = compile(gl, HAZE_VS, SOFT_FS);
    this.dynProgram = compile(gl, DYN_VS, SOFT_FS);
    this.lineProgram = compile(gl, LINE_VS, FLAT_FS);
    this.buildHaze();
    this.buildWind();
    this.vao = gl.createVertexArray();
    this.dynBuffer = gl.createBuffer();
    this.lineBuffer = gl.createBuffer();
  }

  buildHaze() {
    const gl = this.gl;
    const rand = rng(1965);
    const n = this.regions.length * PUFFS_PER_REGION;
    const data = new Float32Array(n * 8);
    let k = 0;
    this.regions.forEach((feature) => {
      const r = ["north", "south", "east", "west", "central"].indexOf(feature.properties.region);
      const [w, s, e, nb] = bbox(feature.geometry);
      let placed = 0;
      while (placed < PUFFS_PER_REGION) {
        const lng = w + (e - w) * rand();
        const lat = s + (nb - s) * rand();
        if (!inFeature(lng, lat, feature.geometry)) continue;
        const alt = 60 + 2600 * rand() ** 1.6;
        const mc = MercatorCoordinate.fromLngLat([lng, lat], alt);
        data.set([mc.x, mc.y, mc.z, r, rand(), rand(), rand(), mc.meterInMercatorCoordinateUnits()], k * 8);
        k += 1;
        placed += 1;
      }
    });
    this.hazeCount = k;
    this.hazeBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.hazeBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    this.meter = MercatorCoordinate.fromLngLat([103.82, 1.35]).meterInMercatorCoordinateUnits();
  }

  buildWind() {
    const rand = rng(42);
    this.windRand = rand;
    this.wind = Array.from({ length: WIND_PARTICLES }, () => this.spawn({}));
  }

  spawn(p) {
    const [w, s, e, n] = SG_BOUNDS;
    p.lng = w + (e - w) * this.windRand();
    p.lat = s + (n - s) * this.windRand();
    p.age = 0;
    p.acc = 0;
    p.life = 2.5 + this.windRand() * 3.5;
    p.trail = Array.from({ length: TRAIL }, () => [p.lng, p.lat]);
    return p;
  }

  setRegionState(index, { density, color, drift }) {
    this.targetDensity[index] = density;
    this.color.set(color.map((c) => c / 255), index * 3);
    // Drift loop length follows wind: about 6 km at 10 knots.
    const [u, v] = drift;
    this.drift[index * 2] = u * 600 * this.meter;
    this.drift[index * 2 + 1] = -v * 600 * this.meter;
    this.kick();
  }

  setField(field) {
    this.field = field;
    if (!this.animate) this.settleStreamlines();
    this.kick();
  }

  setPath(points) {
    this.path = points && points.length > 1 ? points.map(([lat, lng]) => [lng, lat]).reverse() : null;
    this.kick();
  }

  setFlat(flat) {
    this.targetFlat = flat ? 1 : 0;
    this.kick();
  }

  setAnimate(animate) {
    this.animate = animate;
    if (!animate) this.settleStreamlines();
    this.kick();
  }

  setVisible(visible) {
    const was = this.visible;
    this.visible = visible;
    if (visible && !was) {
      this.last = 0;
      this.kick();
    }
  }

  kick() {
    this.map?.triggerRepaint();
  }

  // Reduced motion: draw still streamlines traced through the field instead of moving streaks.
  settleStreamlines() {
    if (!this.field) return;
    this.wind.forEach((p) => {
      this.spawn(p);
      for (let i = 0; i < TRAIL; i += 1) this.step(p, TRAIL_STEP, true);
      p.age = 1;
      p.life = 2;
    });
  }

  step(p, dt, keepAlive = false) {
    const [u, v] = sampleField(this.field, p.lng, p.lat);
    p.lng += u * DEG_PER_KNOT_SECOND * dt;
    p.lat += v * DEG_PER_KNOT_SECOND * dt;
    p.age += dt;
    p.acc += dt;
    p.trail[0] = [p.lng, p.lat];
    if (p.acc >= TRAIL_STEP) {
      p.acc = 0;
      p.trail.pop();
      p.trail.unshift([p.lng, p.lat]);
    }
    const [w, s, e, n] = SG_BOUNDS;
    const out = p.lng < w || p.lng > e || p.lat < s || p.lat > n;
    if (!keepAlive && (out || p.age > p.life)) this.spawn(p);
  }

  advance(now) {
    const dt = this.last ? Math.min(0.05, (now - this.last) / 1000) : 0;
    this.last = now;
    if (!this.animate) {
      this.density.set(this.targetDensity);
      this.flat = this.targetFlat;
      return;
    }
    this.time += dt;
    const ease = 1 - Math.exp(-dt * 4);
    for (let i = 0; i < 5; i += 1) this.density[i] += (this.targetDensity[i] - this.density[i]) * ease;
    this.flat += (this.targetFlat - this.flat) * ease;
    if (this.field && this.showWind) this.wind.forEach((p) => this.step(p, dt));
  }

  render(gl, options) {
    const now = performance.now();
    this.advance(now);
    const matrix = new Float32Array(options.defaultProjectionData.mainMatrix);
    // Own vertex array, so MapLibre's bound one is never modified.
    gl.bindVertexArray(this.vao);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.enable(gl.DEPTH_TEST);
    gl.depthMask(false);

    if (this.showHaze) this.drawHaze(gl, matrix);
    if (this.showWind && this.field) this.drawWind(gl, matrix);
    if (this.path) this.drawPath(gl, matrix);
    gl.bindVertexArray(null);

    this.onFrame?.(now);
    if (this.visible && this.animate) this.map.triggerRepaint();
  }

  drawHaze(gl, matrix) {
    const p = this.hazeProgram;
    gl.useProgram(p);
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "u_matrix"), false, matrix);
    gl.uniform2f(gl.getUniformLocation(p, "u_viewport"), gl.drawingBufferWidth, gl.drawingBufferHeight);
    gl.uniform1f(gl.getUniformLocation(p, "u_time"), this.time);
    gl.uniform1f(gl.getUniformLocation(p, "u_flat"), this.flat);
    gl.uniform1fv(gl.getUniformLocation(p, "u_density"), this.density);
    gl.uniform3fv(gl.getUniformLocation(p, "u_color"), this.color);
    gl.uniform2fv(gl.getUniformLocation(p, "u_drift"), this.drift);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.hazeBuffer);
    const stride = 32;
    const attr = (name, size, offset) => {
      const loc = gl.getAttribLocation(p, name);
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, size, gl.FLOAT, false, stride, offset);
      return loc;
    };
    const locs = [attr("a_pos", 3, 0), attr("a_seed", 4, 12), attr("a_meter", 1, 28)];
    gl.drawArrays(gl.POINTS, 0, this.hazeCount);
    locs.forEach((l) => gl.disableVertexAttribArray(l));
  }

  drawWind(gl, matrix) {
    const z = WIND_ALTITUDE * (1 - this.flat) * this.meter;
    const verts = new Float32Array(this.wind.length * (TRAIL - 1) * 2 * 4);
    let k = 0;
    for (const p of this.wind) {
      const lifeFade = Math.min(1, p.age / 0.4, (p.life - p.age) / 0.4);
      for (let i = 0; i < TRAIL - 1; i += 1) {
        for (const j of [i, i + 1]) {
          const [lng, lat] = p.trail[j];
          verts[k++] = (lng + 180) / 360;
          verts[k++] = (180 - (180 / Math.PI) * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))) / 360;
          verts[k++] = z;
          verts[k++] = Math.max(0, lifeFade) * 0.7 * (1 - j / TRAIL);
        }
      }
    }
    const p = this.lineProgram;
    gl.useProgram(p);
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "u_matrix"), false, matrix);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.lineBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, verts, gl.DYNAMIC_DRAW);
    const pos = gl.getAttribLocation(p, "a_pos");
    const alpha = gl.getAttribLocation(p, "a_alpha");
    gl.enableVertexAttribArray(pos);
    gl.enableVertexAttribArray(alpha);
    gl.vertexAttribPointer(pos, 3, gl.FLOAT, false, 16, 0);
    gl.vertexAttribPointer(alpha, 1, gl.FLOAT, false, 16, 12);
    gl.drawArrays(gl.LINES, 0, k / 4);
    gl.disableVertexAttribArray(pos);
    gl.disableVertexAttribArray(alpha);
  }

  drawPath(gl, matrix) {
    const path = this.path;
    const seg = [];
    let total = 0;
    for (let i = 1; i < path.length; i += 1) {
      const d = Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]);
      seg.push(d);
      total += d;
    }
    if (!total) return;
    const ratio = this.map.getPixelRatio?.() || 1;
    const verts = new Float32Array(DRIFT_DOTS * 8);
    for (let k = 0; k < DRIFT_DOTS; k += 1) {
      const s = ((this.animate ? this.time * 0.06 : 0) + k / DRIFT_DOTS) % 1;
      let target = s * total;
      let i = 0;
      while (i < seg.length - 1 && target > seg[i]) {
        target -= seg[i];
        i += 1;
      }
      const f = seg[i] ? target / seg[i] : 0;
      const lng = path[i][0] + (path[i + 1][0] - path[i][0]) * f;
      const lat = path[i][1] + (path[i + 1][1] - path[i][1]) * f;
      const mc = MercatorCoordinate.fromLngLat([lng, lat], 0);
      const a = Math.sin(Math.PI * s) ** 0.5;
      verts.set([mc.x, mc.y, mc.z, 0.72 * a, 0.32 * a, 0.1 * a, a, 11 * ratio], k * 8);
    }
    const p = this.dynProgram;
    gl.useProgram(p);
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "u_matrix"), false, matrix);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.dynBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, verts, gl.DYNAMIC_DRAW);
    const locs = [["a_pos", 3, 0], ["a_color", 4, 12], ["a_size", 1, 28]].map(([name, size, off]) => {
      const loc = gl.getAttribLocation(p, name);
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 32, off);
      return loc;
    });
    gl.disable(gl.DEPTH_TEST);
    gl.drawArrays(gl.POINTS, 0, DRIFT_DOTS);
    locs.forEach((l) => gl.disableVertexAttribArray(l));
  }

  onRemove(map, gl) {
    [this.hazeBuffer, this.dynBuffer, this.lineBuffer].forEach((b) => gl.deleteBuffer(b));
    [this.hazeProgram, this.dynProgram, this.lineProgram].forEach((p) => gl.deleteProgram(p));
    gl.deleteVertexArray(this.vao);
  }
}
