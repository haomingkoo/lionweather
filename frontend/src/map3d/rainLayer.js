import { MercatorCoordinate } from "maplibre-gl";
import { RAIN_BOUNDS, fieldPixels } from "./rainField";

// MapLibre custom layer: the gauge rain field as a translucent sheet above the city,
// and drawn rain falling under it where the field is wet, leaning with the wind.
// The drops are a visual effect driven by the field, not measurements.

const SHEET_M = 900;
const DROPS = 14000;
const FALL_MS = 8; // terminal speed of a raindrop, m/s

const SHEET_VS = `#version 300 es
uniform mat4 u_matrix;
uniform vec4 u_rect;
uniform float u_z;
in vec2 a_corner;
out vec2 v_uv;
void main() {
  v_uv = a_corner;
  gl_Position = u_matrix * vec4(mix(u_rect.xy, u_rect.zw, a_corner), u_z, 1.0);
}`;

const SHEET_FS = `#version 300 es
precision mediump float;
uniform sampler2D u_color;
uniform float u_alpha;
in vec2 v_uv;
out vec4 frag;
void main() {
  vec4 c = texture(u_color, v_uv);
  float a = c.a * u_alpha;
  frag = vec4(c.rgb * a, a);
}`;

const DROP_VS = `#version 300 es
precision highp float;
uniform mat4 u_matrix;
uniform vec4 u_rect;
uniform float u_m;
uniform float u_top;
uniform float u_time;
uniform vec2 u_lean;
uniform sampler2D u_rate;
in vec3 a_seed;
out float v_a;
void main() {
  int end = gl_VertexID & 1;
  float rate = textureLod(u_rate, a_seed.xy, 0.0).r;
  // More drops where it rains harder: a drop shows when its seed is under the rate.
  float on = step(fract(a_seed.z * 7.31), rate * 1.15);
  float speed = 0.09 + 0.04 * fract(a_seed.z * 3.7);
  float f = fract(u_time * speed + a_seed.z);
  float z = u_top * (1.0 - f);
  float len = 80.0 + 300.0 * rate;
  float zz = z + (end == 1 ? len : 0.0);
  vec2 xy = mix(u_rect.xy, u_rect.zw, a_seed.xy);
  // Lean with the wind: drift grows with the height fallen.
  vec2 drift = u_lean * (u_top - zz) * u_m;
  v_a = on * (end == 1 ? 0.0 : 0.75) * smoothstep(0.0, 0.08, f) * smoothstep(1.0, 0.9, f);
  gl_Position = u_matrix * vec4(xy + vec2(drift.x, -drift.y), zz * u_m, 1.0);
}`;

const DROP_FS = `#version 300 es
precision mediump float;
uniform vec3 u_ink;
in float v_a;
out vec4 frag;
void main() { frag = vec4(u_ink * v_a, v_a); }`;

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

const INK = { light: [0.25, 0.38, 0.55], dark: [0.72, 0.84, 0.98] };

export class RainLayer {
  constructor() {
    this.id = "gauge-rain";
    this.type = "custom";
    this.renderingMode = "3d";
    this.field = null;
    this.lean = [0, 0];
    this.theme = "light";
    this.animate = true;
    this.visible = true;
    this.t0 = performance.now();
  }

  onAdd(map, gl) {
    this.map = map;
    this.gl = gl;
    this.sheet = compile(gl, SHEET_VS, SHEET_FS);
    this.drops = compile(gl, DROP_VS, DROP_FS);
    this.vao = gl.createVertexArray();
    this.quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);
    const seeds = new Float32Array(DROPS * 2 * 3);
    for (let i = 0; i < DROPS; i += 1) {
      const s = [Math.random(), Math.random(), Math.random()];
      seeds.set(s, i * 6);
      seeds.set(s, i * 6 + 3);
    }
    this.seedBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.seedBuf);
    gl.bufferData(gl.ARRAY_BUFFER, seeds, gl.STATIC_DRAW);
    const tex = () => {
      const t = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return t;
    };
    this.colorTex = tex();
    this.rateTex = tex();
    const [w, s, e, n] = RAIN_BOUNDS;
    const sw = MercatorCoordinate.fromLngLat([w, s]);
    const ne = MercatorCoordinate.fromLngLat([e, n]);
    // Textures run north to south; the rectangle goes from the north-west corner.
    this.rect = [sw.x, ne.y, ne.x, sw.y];
    this.m = MercatorCoordinate.fromLngLat([(w + e) / 2, (s + n) / 2]).meterInMercatorCoordinateUnits();
    if (this.field) this.upload();
  }

  setField(field) {
    this.field = field;
    if (this.gl) this.upload();
  }

  // Wind in knots and the direction it blows from.
  setWind(wind) {
    if (!wind) {
      this.lean = [0, 0];
      return;
    }
    const ms = wind.speed_kn * 0.5144;
    const to = ((wind.dir_deg + 180) * Math.PI) / 180;
    this.lean = [(Math.sin(to) * ms) / FALL_MS, (Math.cos(to) * ms) / FALL_MS];
  }

  setTheme(t) {
    this.theme = INK[t] ? t : "light";
    this.map?.triggerRepaint();
  }

  setAnimate(a) {
    this.animate = a;
    this.map?.triggerRepaint();
  }

  setVisible(v) {
    this.visible = v;
    if (v) this.map?.triggerRepaint();
  }

  upload() {
    const gl = this.gl;
    const f = this.field;
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    gl.bindTexture(gl.TEXTURE_2D, this.colorTex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, f.cols, f.rows, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(fieldPixels(f, { alpha: 1 }).buffer));
    // Rate on a log scale: 1 at about 100 mm/h.
    const rate = new Uint8Array(f.cols * f.rows);
    for (let i = 0; i < rate.length; i += 1) rate[i] = Math.round(Math.min(1, Math.log10(1 + Math.max(0, f.data[i])) / 2) * 255);
    gl.bindTexture(gl.TEXTURE_2D, this.rateTex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, f.cols, f.rows, 0, gl.RED, gl.UNSIGNED_BYTE, rate);
    this.map.triggerRepaint();
  }

  render(gl, options) {
    if (!this.field || this.field.max <= 0) return;
    const matrix = new Float32Array(options.defaultProjectionData.mainMatrix);
    gl.bindVertexArray(this.vao);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.enable(gl.DEPTH_TEST);
    gl.depthMask(false);

    if (this.animate) {
      const p = this.drops;
      gl.useProgram(p);
      gl.uniformMatrix4fv(gl.getUniformLocation(p, "u_matrix"), false, matrix);
      gl.uniform4fv(gl.getUniformLocation(p, "u_rect"), this.rect);
      gl.uniform1f(gl.getUniformLocation(p, "u_m"), this.m);
      gl.uniform1f(gl.getUniformLocation(p, "u_top"), SHEET_M);
      gl.uniform1f(gl.getUniformLocation(p, "u_time"), (performance.now() - this.t0) / 1000);
      gl.uniform2fv(gl.getUniformLocation(p, "u_lean"), this.lean);
      gl.uniform3fv(gl.getUniformLocation(p, "u_ink"), INK[this.theme]);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.rateTex);
      gl.uniform1i(gl.getUniformLocation(p, "u_rate"), 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.seedBuf);
      const loc = gl.getAttribLocation(p, "a_seed");
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 3, gl.FLOAT, false, 0, 0);
      gl.drawArrays(gl.LINES, 0, DROPS * 2);
      gl.disableVertexAttribArray(loc);
    }

    const p = this.sheet;
    gl.useProgram(p);
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "u_matrix"), false, matrix);
    gl.uniform4fv(gl.getUniformLocation(p, "u_rect"), this.rect);
    gl.uniform1f(gl.getUniformLocation(p, "u_z"), SHEET_M * this.m);
    gl.uniform1f(gl.getUniformLocation(p, "u_alpha"), 0.55);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.colorTex);
    gl.uniform1i(gl.getUniformLocation(p, "u_color"), 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    const loc = gl.getAttribLocation(p, "a_corner");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.disableVertexAttribArray(loc);
    gl.bindVertexArray(null);
    if (this.animate && this.visible) this.map.triggerRepaint();
  }

  onRemove(map, gl) {
    [this.quad, this.seedBuf].forEach((b) => gl.deleteBuffer(b));
    [this.colorTex, this.rateTex].forEach((t) => gl.deleteTexture(t));
    [this.sheet, this.drops].forEach((p) => gl.deleteProgram(p));
    gl.deleteVertexArray(this.vao);
  }
}
