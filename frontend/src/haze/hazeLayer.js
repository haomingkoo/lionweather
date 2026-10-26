import { MercatorCoordinate } from "maplibre-gl";
import { REGIONS, sampleField } from "./hazeData";

// MapLibre custom layer with two parts:
//  - haze: stacked translucent slices from the ground to 1.4 km, shaded from a blurred
//    per-region mask, so towers stand inside the haze and are veiled by what is in front;
//  - wind: short streaks advected through the NEA station field.

export const SG_BOUNDS = [103.58, 1.18, 104.1, 1.49];
const MASK_BOUNDS = [103.55, 1.13, 104.15, 1.5];
const MASK_W = 1024;
const MASK_H = 640;
const BLUR_PX = 9; // about 600 m: soft edges, regions still read as regions
const SLICES = 20;
const TOP_M = 1400;
const SCALE_M = 480; // haze thins with height over about half a kilometre

const SLICE_VS = `#version 300 es
uniform mat4 u_matrix;
uniform vec4 u_rect;      // mercator x0, y0, x1, y1
uniform float u_meter;
uniform float u_flat;
uniform float u_slices;
uniform float u_top;
uniform float u_scale;
uniform float u_wsum;
in vec2 a_corner;
out vec2 v_uv;
out float v_w;
out float v_slice;
void main() {
  float i = float(gl_InstanceID);
  float alt = u_top * (i + 0.5) / u_slices;
  v_w = exp(-alt / u_scale) / u_wsum;
  v_slice = i;
  v_uv = a_corner;
  vec2 xy = mix(u_rect.xy, u_rect.zw, a_corner);
  gl_Position = u_matrix * vec4(xy, alt * u_meter * (1.0 - u_flat), 1.0);
}`;

const SLICE_FS = `#version 300 es
precision highp float;
uniform sampler2D u_maskA;
uniform sampler2D u_maskB;
uniform vec4 u_densA;
uniform float u_densB;
uniform vec3 u_col[5];
uniform float u_time;
uniform vec2 u_drift;
uniform float u_strength;
in vec2 v_uv;
in float v_w;
in float v_slice;
out vec4 frag;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
void main() {
  vec4 a = texture(u_maskA, v_uv);
  float b = texture(u_maskB, v_uv).r;
  float d = dot(a, u_densA) + b * u_densB;
  if (d < 0.003) discard;
  vec3 col = (a.x * u_densA.x * u_col[0] + a.y * u_densA.y * u_col[1] + a.z * u_densA.z * u_col[2] +
              a.w * u_densA.w * u_col[3] + b * u_densB * u_col[4]) / max(d, 1e-4);
  // Texture only: soft billows drifting with the wind, plus or minus a quarter.
  vec2 q = v_uv * vec2(34.0, 21.0) + u_drift * u_time + v_slice * 1.37;
  float n = 0.55 * noise(q) + 0.3 * noise(q * 2.07 + 3.1) + 0.15 * noise(q * 4.31 - 1.7);
  float column = u_strength * (1.0 - exp(-2.2 * d * d)) * (0.75 + 0.5 * n);
  float alpha = 1.0 - pow(1.0 - clamp(column, 0.0, 0.95), v_w);
  frag = vec4(col * alpha, alpha);
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
  frag = v_color * exp(-r * 2.5);
}`;

const LINE_VS = `#version 300 es
uniform mat4 u_matrix;
uniform vec3 u_ink;
in vec3 a_pos;
in float a_alpha;
out vec4 v_color;
void main() {
  gl_Position = u_matrix * vec4(a_pos, 1.0);
  v_color = vec4(u_ink, 1.0) * a_alpha;
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

function rng(seed) {
  let t = seed >>> 0;
  return () => {
    t = (t + 0x6d2b79f5) >>> 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

// Three box blurs approximate a Gaussian. In place on a Float32 plane.
function blur(src, w, h, r) {
  const tmp = new Float32Array(src.length);
  const pass = (from, to, horizontal) => {
    const len = horizontal ? w : h;
    const lines = horizontal ? h : w;
    for (let l = 0; l < lines; l += 1) {
      let acc = 0;
      const idx = (k) => (horizontal ? l * w + k : k * w + l);
      for (let k = -r; k <= r; k += 1) acc += from[idx(Math.min(len - 1, Math.max(0, k)))];
      for (let k = 0; k < len; k += 1) {
        to[idx(k)] = acc / (2 * r + 1);
        acc += from[idx(Math.min(len - 1, k + r + 1))] - from[idx(Math.max(0, k - r))];
      }
    }
  };
  for (let i = 0; i < 3; i += 1) {
    pass(src, tmp, true);
    pass(tmp, src, false);
  }
  return src;
}

const mercX = (lng) => (lng + 180) / 360;
const mercY = (lat) => (180 - (180 / Math.PI) * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))) / 360;

// One soft mask per region, in Web Mercator over MASK_BOUNDS.
export function buildMasks(features, w = MASK_W, h = MASK_H, doc = document) {
  const [west, south, east, north] = MASK_BOUNDS;
  const x0 = mercX(west);
  const x1 = mercX(east);
  const y0 = mercY(north);
  const y1 = mercY(south);
  const canvas = doc.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  return REGIONS.map((region) => {
    const feature = features.find((f) => f.properties.region === region);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#fff";
    if (feature) {
      const polys = feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates;
      ctx.beginPath();
      polys.forEach((rings) => rings.forEach((ring) => {
        ring.forEach(([lng, lat], k) => {
          const px = ((mercX(lng) - x0) / (x1 - x0)) * w;
          const py = ((mercY(lat) - y0) / (y1 - y0)) * h;
          if (k === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.closePath();
      }));
      ctx.fill("evenodd");
    }
    const img = ctx.getImageData(0, 0, w, h).data;
    const plane = new Float32Array(w * h);
    for (let i = 0; i < plane.length; i += 1) plane[i] = img[i * 4 + 3] / 255;
    return blur(plane, w, h, BLUR_PX);
  });
}

const PALETTE = {
  light: { ink: [0.07, 0.09, 0.15], streak: 0.32, strength: 0.9 },
  dark: { ink: [0.86, 0.9, 0.96], streak: 0.22, strength: 0.85 },
};

const WIND_PARTICLES = 650;
const TRAIL = 12;
const TRAIL_STEP = 0.09; // seconds between trail points
const DEG_PER_KNOT_SECOND = 0.005;
const WIND_ALTITUDE = 300;

export class HazeLayer {
  constructor({ regions, onFrame }) {
    this.id = "haze-volume";
    this.type = "custom";
    this.renderingMode = "3d";
    this.regions = regions;
    this.onFrame = onFrame;
    this.density = new Float32Array(5);
    this.targetDensity = new Float32Array(5);
    this.color = new Float32Array(15);
    this.drift = [0, 0];
    this.flat = 0;
    this.targetFlat = 0;
    this.showHaze = true;
    this.showWind = true;
    this.field = null;
    this.animate = true;
    this.visible = true;
    this.theme = "light";
    this.time = 0;
    this.last = 0;
  }

  onAdd(map, gl) {
    this.map = map;
    this.gl = gl;
    this.sliceProgram = compile(gl, SLICE_VS, SLICE_FS);
    this.dynProgram = compile(gl, DYN_VS, SOFT_FS);
    this.lineProgram = compile(gl, LINE_VS, FLAT_FS);
    this.vao = gl.createVertexArray();
    this.quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);
    this.dynBuffer = gl.createBuffer();
    this.lineBuffer = gl.createBuffer();
    this.buildMaskTextures(gl);
    const [w, s, e, n] = MASK_BOUNDS;
    this.rect = [mercX(w), mercY(n), mercX(e), mercY(s)];
    this.meter = MercatorCoordinate.fromLngLat([103.82, 1.35]).meterInMercatorCoordinateUnits();
    let wsum = 0;
    for (let i = 0; i < SLICES; i += 1) wsum += Math.exp(-(TOP_M * (i + 0.5)) / SLICES / SCALE_M);
    this.wsum = wsum;
    this.windRand = rng(42);
    this.wind = Array.from({ length: WIND_PARTICLES }, () => this.spawn({}));
  }

  buildMaskTextures(gl) {
    const masks = buildMasks(this.regions);
    const pack = (planes) => {
      const out = new Uint8Array(MASK_W * MASK_H * 4);
      for (let i = 0; i < MASK_W * MASK_H; i += 1) {
        for (let c = 0; c < 4; c += 1) out[i * 4 + c] = planes[c] ? Math.round(planes[c][i] * 255) : 0;
      }
      return out;
    };
    const upload = (data) => {
      const tex = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, MASK_W, MASK_H, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return tex;
    };
    this.maskA = upload(pack(masks.slice(0, 4)));
    this.maskB = upload(pack([masks[4]]));
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

  setTheme(theme) {
    this.theme = PALETTE[theme] ? theme : "light";
    this.kick();
  }

  setRegionState(index, { density, color }) {
    this.targetDensity[index] = density;
    this.color.set(color.map((c) => c / 255), index * 3);
    this.kick();
  }

  // Mean wind in knots, towards: drives the slow drift of the haze texture.
  setDrift([u, v]) {
    this.drift = [u * 0.012, -v * 0.012];
  }

  setField(field) {
    this.field = field;
    if (!this.animate) this.settleStreamlines();
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

  // Reduced motion: still streamlines traced through the field instead of moving streaks.
  settleStreamlines() {
    if (!this.field || !this.wind) return;
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
    gl.bindVertexArray(this.vao);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.depthMask(false);

    if (this.showHaze) this.drawHaze(gl, matrix);
    if (this.showWind && this.field) this.drawWind(gl, matrix);
    gl.bindVertexArray(null);

    this.onFrame?.(now);
    if (this.visible && this.animate) this.map.triggerRepaint();
  }

  drawHaze(gl, matrix) {
    const p = this.sliceProgram;
    const u = (name) => gl.getUniformLocation(p, name);
    gl.useProgram(p);
    gl.uniformMatrix4fv(u("u_matrix"), false, matrix);
    gl.uniform4fv(u("u_rect"), this.rect);
    gl.uniform1f(u("u_meter"), this.meter);
    gl.uniform1f(u("u_flat"), this.flat);
    gl.uniform1f(u("u_slices"), SLICES);
    gl.uniform1f(u("u_top"), TOP_M);
    gl.uniform1f(u("u_scale"), SCALE_M);
    gl.uniform1f(u("u_wsum"), this.wsum);
    gl.uniform4f(u("u_densA"), this.density[0], this.density[1], this.density[2], this.density[3]);
    gl.uniform1f(u("u_densB"), this.density[4]);
    gl.uniform3fv(u("u_col"), this.color);
    gl.uniform1f(u("u_time"), this.time);
    gl.uniform2fv(u("u_drift"), this.drift);
    gl.uniform1f(u("u_strength"), PALETTE[this.theme].strength);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.maskA);
    gl.uniform1i(u("u_maskA"), 0);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, this.maskB);
    gl.uniform1i(u("u_maskB"), 1);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    const loc = gl.getAttribLocation(p, "a_corner");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, SLICES);
    gl.disableVertexAttribArray(loc);
    gl.activeTexture(gl.TEXTURE0);
  }

  drawWind(gl, matrix) {
    const z = WIND_ALTITUDE * (1 - this.flat) * this.meter;
    const verts = new Float32Array(this.wind.length * (TRAIL - 1) * 2 * 4);
    const strength = PALETTE[this.theme].streak;
    let k = 0;
    for (const p of this.wind) {
      const lifeFade = Math.min(1, p.age / 0.4, (p.life - p.age) / 0.4);
      for (let i = 0; i < TRAIL - 1; i += 1) {
        for (const j of [i, i + 1]) {
          const [lng, lat] = p.trail[j];
          verts[k++] = mercX(lng);
          verts[k++] = mercY(lat);
          verts[k++] = z;
          verts[k++] = Math.max(0, lifeFade) * strength * (1 - j / TRAIL);
        }
      }
    }
    const p = this.lineProgram;
    gl.useProgram(p);
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "u_matrix"), false, matrix);
    gl.uniform3fv(gl.getUniformLocation(p, "u_ink"), PALETTE[this.theme].ink);
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

  onRemove(map, gl) {
    [this.quad, this.dynBuffer, this.lineBuffer].forEach((b) => gl.deleteBuffer(b));
    [this.sliceProgram, this.dynProgram, this.lineProgram].forEach((p) => gl.deleteProgram(p));
    [this.maskA, this.maskB].forEach((t) => gl.deleteTexture(t));
    gl.deleteVertexArray(this.vao);
  }
}
