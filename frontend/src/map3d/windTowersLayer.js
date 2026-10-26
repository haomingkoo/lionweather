import { MercatorCoordinate } from "maplibre-gl";
import { E, OPP, TAU, W, equilibrium } from "./lbm";

// MapLibre custom layer: a D2Q9 lattice-Boltzmann wind simulation on the GPU over a
// grid of real building footprints, drawn as tracers at street level. The shaders
// follow lbm.js (stepCPU), which is the tested reference.

const LBM_FS = `#version 300 es
precision highp float;
uniform highp sampler2D u_f0;
uniform highp sampler2D u_f1;
uniform highp sampler2D u_f2;
uniform highp sampler2D u_mask;
uniform int u_n;
uniform float u_u0;
uniform float u_tau;
layout(location = 0) out vec4 o0;
layout(location = 1) out vec4 o1;
layout(location = 2) out vec4 o2;
const ivec2 E[9] = ivec2[9](${E.map(([x, y]) => `ivec2(${x}, ${y})`).join(", ")});
const int OPP[9] = int[9](${OPP.join(", ")});
const float W[9] = float[9](${W.map((w) => w.toFixed(9)).join(", ")});
float fAt(ivec2 c, int i) {
  if (i < 4) return texelFetch(u_f0, c, 0)[i];
  if (i < 8) return texelFetch(u_f1, c, 0)[i - 4];
  return texelFetch(u_f2, c, 0).x;
}
float feq(int i, float rho, vec2 u) {
  float eu = dot(vec2(E[i]), u);
  return W[i] * rho * (1.0 + 3.0 * eu + 4.5 * eu * eu - 1.5 * dot(u, u));
}
void main() {
  ivec2 c = ivec2(gl_FragCoord.xy);
  // Outflow: the last column takes the new values of its neighbour (stepCPU copies them).
  if (c.x == u_n - 1) c.x = u_n - 2;
  float f[9];
  if (texelFetch(u_mask, c, 0).r > 0.5) {
    for (int i = 0; i < 9; i++) f[i] = W[i];
  } else if (c.x == 0) {
    for (int i = 0; i < 9; i++) f[i] = feq(i, 1.0, vec2(u_u0, 0.0));
  } else {
    float rho = 0.0;
    vec2 u = vec2(0.0);
    for (int i = 0; i < 9; i++) {
      ivec2 s = ivec2(min(u_n - 1, c.x - E[i].x), (c.y - E[i].y + u_n) % u_n);
      float v = texelFetch(u_mask, s, 0).r > 0.5 ? fAt(c, OPP[i]) : fAt(s, i);
      f[i] = v;
      rho += v;
      u += v * vec2(E[i]);
    }
    u /= rho;
    for (int i = 0; i < 9; i++) f[i] -= (f[i] - feq(i, rho, u)) / u_tau;
  }
  o0 = vec4(f[0], f[1], f[2], f[3]);
  o1 = vec4(f[4], f[5], f[6], f[7]);
  o2 = vec4(f[8], 0.0, 0.0, 0.0);
}`;

// Velocity, density and solid flag per cell; the outflow column copies its neighbour.
const VEL_FS = `#version 300 es
precision highp float;
uniform highp sampler2D u_f0;
uniform highp sampler2D u_f1;
uniform highp sampler2D u_f2;
uniform highp sampler2D u_mask;
uniform int u_n;
out vec4 o;
const vec2 E[9] = vec2[9](${E.map(([x, y]) => `vec2(${x}.0, ${y}.0)`).join(", ")});
void main() {
  ivec2 c = ivec2(gl_FragCoord.xy);
  if (c.x == u_n - 1) c.x -= 1;
  if (texelFetch(u_mask, c, 0).r > 0.5) { o = vec4(0.0, 0.0, 1.0, 1.0); return; }
  vec4 a = texelFetch(u_f0, c, 0);
  vec4 b = texelFetch(u_f1, c, 0);
  float f8 = texelFetch(u_f2, c, 0).x;
  float f[9] = float[9](a.x, a.y, a.z, a.w, b.x, b.y, b.z, b.w, f8);
  float rho = 0.0;
  vec2 u = vec2(0.0);
  for (int i = 0; i < 9; i++) { rho += f[i]; u += f[i] * E[i]; }
  o = vec4(u / rho, rho, 0.0);
}`;

// Tracers: (x, y, tail x, tail y) and (age, life, seed, -) in grid cells.
const PART_FS = `#version 300 es
precision highp float;
uniform highp sampler2D u_p;
uniform highp sampler2D u_q;
uniform highp sampler2D u_vel;
uniform float u_n;
uniform float u_steps;
uniform float u_time;
layout(location = 0) out vec4 oP;
layout(location = 1) out vec4 oQ;
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void main() {
  ivec2 c = ivec2(gl_FragCoord.xy);
  vec4 p = texelFetch(u_p, c, 0);
  vec4 q = texelFetch(u_q, c, 0);
  vec4 v = texture(u_vel, p.xy / u_n);
  vec2 pos = p.xy + v.xy * u_steps;
  vec2 tail = mix(p.zw, pos, 0.08);
  q.x += 1.0;
  bool dead = q.x > q.y || pos.x < 0.0 || pos.x >= u_n || pos.y < 0.0 || pos.y >= u_n || v.w > 0.5;
  if (dead) {
    float r1 = hash(vec2(q.z, u_time));
    float r2 = hash(vec2(u_time, q.z * 1.37));
    // Most respawn anywhere; a share enters with the wind on the left edge.
    pos = r1 < 0.3 ? vec2(r2 * 3.0, hash(vec2(r1, q.z)) * u_n) : vec2(r1, r2) * u_n;
    tail = pos;
    q.x = 0.0;
    q.y = 60.0 + hash(vec2(q.z, r1)) * 140.0;
  }
  oP = vec4(pos, tail);
  oQ = q;
}`;

const QUAD_VS = `#version 300 es
void main() {
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

// Grid cell -> mercator, through the frame turned to the wind.
const GRID_TO_MERC = `
uniform mat4 u_matrix;
uniform vec2 u_origin;
uniform float u_m;
uniform float u_size;
uniform float u_n;
uniform vec2 u_d;
uniform vec2 u_pp;
uniform float u_z;
vec4 place(vec2 g) {
  vec2 xy = (g / u_n - 0.5) * u_size;
  vec2 en = xy.x * u_d + xy.y * u_pp;
  return u_matrix * vec4(u_origin.x + en.x * u_m, u_origin.y - en.y * u_m, u_z * u_m, 1.0);
}`;

const TRACER_VS = `#version 300 es
precision highp float;
uniform highp sampler2D u_p;
uniform highp sampler2D u_q;
uniform highp sampler2D u_vel;
uniform int u_pw;
uniform float u_u0;
${GRID_TO_MERC}
out float v_a;
void main() {
  int id = gl_VertexID >> 1;
  ivec2 c = ivec2(id % u_pw, id / u_pw);
  vec4 p = texelFetch(u_p, c, 0);
  vec4 q = texelFetch(u_q, c, 0);
  vec2 g = (gl_VertexID & 1) == 0 ? p.zw : p.xy;
  float speed = length(texture(u_vel, p.xy / u_n).xy) / max(u_u0, 1e-4);
  float fade = min(1.0, min(q.x / 8.0, (q.y - q.x) / 8.0));
  v_a = fade * clamp(0.45 + 0.6 * speed, 0.0, 1.0) * ((gl_VertexID & 1) == 0 ? 0.0 : 1.0);
  gl_Position = place(g);
}`;

// Reduced motion: a still field of short strokes along the flow.
const FIELD_VS = `#version 300 es
precision highp float;
uniform highp sampler2D u_vel;
uniform int u_seeds;
uniform float u_u0;
${GRID_TO_MERC}
out float v_a;
void main() {
  int id = gl_VertexID >> 1;
  vec2 g = (vec2(id % u_seeds, id / u_seeds) + 0.5) * (u_n / float(u_seeds));
  vec4 v = texture(u_vel, g / u_n);
  float speed = length(v.xy) / max(u_u0, 1e-4);
  vec2 dir = length(v.xy) > 1e-6 ? normalize(v.xy) : vec2(1.0, 0.0);
  float len = (u_n / float(u_seeds)) * 0.8 * clamp(speed, 0.0, 1.6);
  bool head = (gl_VertexID & 1) == 1;
  v_a = v.w > 0.5 ? 0.0 : (head ? 0.9 : 0.15);
  gl_Position = place(g + (head ? dir * len : vec2(0.0)));
}`;

const LINE_FS = `#version 300 es
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

const INK = { light: [0.06, 0.1, 0.18], dark: [0.88, 0.93, 1.0] };
const SPINUP_STEPS = 600;
const STILL_STEPS = 2500;

export class WindTowersLayer {
  constructor({ n = 320, particles = 16384, onStatus } = {}) {
    this.id = "wind-towers";
    this.type = "custom";
    this.renderingMode = "3d";
    this.n = n;
    this.pw = 128;
    this.ph = Math.ceil(particles / this.pw);
    this.onStatus = onStatus;
    this.active = false;
    this.visible = true;
    this.animate = true;
    this.theme = "light";
    this.frame = null;
    this.u0 = 0.06;
    this.stepsPerFrame = 10;
    this.time = 0;
  }

  onAdd(map, gl) {
    this.map = map;
    this.gl = gl;
    this.supported = !!gl.getExtension("EXT_color_buffer_float");
    if (!this.supported) {
      this.onStatus?.("unsupported");
      return;
    }
    const n = this.n;
    this.lbmProgram = compile(gl, QUAD_VS, LBM_FS);
    this.velProgram = compile(gl, QUAD_VS, VEL_FS);
    this.partProgram = compile(gl, QUAD_VS, PART_FS);
    this.tracerProgram = compile(gl, TRACER_VS, LINE_FS);
    this.fieldProgram = compile(gl, FIELD_VS, LINE_FS);
    this.vao = gl.createVertexArray();
    const tex = (w, h, internal, format, type, filter, data = null) => {
      const t = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, internal, w, h, 0, format, type, data);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return t;
    };
    const f32 = (w, h) => tex(w, h, gl.RGBA32F, gl.RGBA, gl.FLOAT, gl.NEAREST);
    this.f = [[f32(n, n), f32(n, n), f32(n, n)], [f32(n, n), f32(n, n), f32(n, n)]];
    this.mask = tex(n, n, gl.R8, gl.RED, gl.UNSIGNED_BYTE, gl.NEAREST, new Uint8Array(n * n));
    this.vel = tex(n, n, gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT, gl.LINEAR);
    this.p = [[f32(this.pw, this.ph), f32(this.pw, this.ph)], [f32(this.pw, this.ph), f32(this.pw, this.ph)]];
    const fb = (textures) => {
      const b = gl.createFramebuffer();
      gl.bindFramebuffer(gl.FRAMEBUFFER, b);
      textures.forEach((t, i) => gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0 + i, gl.TEXTURE_2D, t, 0));
      const ok = gl.checkFramebufferStatus(gl.FRAMEBUFFER) === gl.FRAMEBUFFER_COMPLETE;
      return ok ? b : null;
    };
    this.fFB = [fb(this.f[0]), fb(this.f[1])];
    this.velFB = fb([this.vel]);
    this.pFB = [fb(this.p[0]), fb(this.p[1])];
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    if (this.fFB.includes(null) || !this.velFB || this.pFB.includes(null)) {
      this.supported = false;
      this.onStatus?.("unsupported");
      return;
    }
    this.cur = 0;
    this.pcur = 0;
    this.onStatus?.("ready");
    if (this.pending) this.setScene(this.pending);
  }

  // A new place, mask or inflow: reset the lattice and spin the flow up.
  setScene({ frame, mask, u0 }) {
    this.pending = { frame, mask, u0 };
    if (!this.gl || !this.supported) return;
    const gl = this.gl;
    const n = this.n;
    this.frame = frame;
    this.u0 = u0;
    this.origin = MercatorCoordinate.fromLngLat([frame.lng, frame.lat]);
    this.m = this.origin.meterInMercatorCoordinateUnits();
    gl.bindTexture(gl.TEXTURE_2D, this.mask);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    // R8 reads back normalised, so solid cells are stored as 255.
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, n, n, gl.RED, gl.UNSIGNED_BYTE, mask.map((v) => (v ? 255 : 0)));
    const eq = equilibrium(1, u0, 0);
    const planes = [new Float32Array(n * n * 4), new Float32Array(n * n * 4), new Float32Array(n * n * 4)];
    for (let c = 0; c < n * n; c += 1) {
      for (let i = 0; i < 9; i += 1) planes[i >> 2][c * 4 + (i & 3)] = mask[c] ? W[i] : eq[i];
    }
    this.f[this.cur].forEach((t, k) => {
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, n, n, gl.RGBA, gl.FLOAT, planes[k]);
    });
    const P = new Float32Array(this.pw * this.ph * 4);
    const Q = new Float32Array(this.pw * this.ph * 4);
    for (let i = 0; i < this.pw * this.ph; i += 1) {
      const x = Math.random() * n;
      const y = Math.random() * n;
      P.set([x, y, x, y], i * 4);
      Q.set([Math.random() * 100, 60 + Math.random() * 140, Math.random() * 1000, 0], i * 4);
    }
    gl.bindTexture(gl.TEXTURE_2D, this.p[this.pcur][0]);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, this.pw, this.ph, gl.RGBA, gl.FLOAT, P);
    gl.bindTexture(gl.TEXTURE_2D, this.p[this.pcur][1]);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, this.pw, this.ph, gl.RGBA, gl.FLOAT, Q);
    this.withState(() => {
      this.stepLattice(this.animate ? SPINUP_STEPS : STILL_STEPS);
      this.computeVelocity();
    });
    this.map.triggerRepaint();
  }

  setActive(on) {
    this.active = on;
    this.map?.triggerRepaint();
  }

  setVisible(v) {
    this.visible = v;
    if (v) this.map?.triggerRepaint();
  }

  setAnimate(a) {
    this.animate = a;
  }

  setTheme(t) {
    this.theme = INK[t] ? t : "light";
  }

  withState(fn) {
    const gl = this.gl;
    const fbo = gl.getParameter(gl.FRAMEBUFFER_BINDING);
    const vp = gl.getParameter(gl.VIEWPORT);
    // MapLibre may leave scissor, culling or a colour mask on; any of them would
    // leave parts of the lattice unwritten. Switch them off and put them back after.
    const caps = [gl.BLEND, gl.DEPTH_TEST, gl.STENCIL_TEST, gl.SCISSOR_TEST, gl.CULL_FACE];
    const was = caps.map((c) => gl.isEnabled(c));
    const mask = gl.getParameter(gl.COLOR_WRITEMASK);
    caps.forEach((c) => gl.disable(c));
    gl.colorMask(true, true, true, true);
    gl.bindVertexArray(this.vao);
    fn();
    gl.bindVertexArray(null);
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.viewport(vp[0], vp[1], vp[2], vp[3]);
    caps.forEach((c, i) => (was[i] ? gl.enable(c) : gl.disable(c)));
    gl.colorMask(mask[0], mask[1], mask[2], mask[3]);
  }

  bindTextures(program, entries) {
    const gl = this.gl;
    entries.forEach(([name, t], i) => {
      gl.activeTexture(gl.TEXTURE0 + i);
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.uniform1i(gl.getUniformLocation(program, name), i);
    });
  }

  stepLattice(steps) {
    const gl = this.gl;
    const p = this.lbmProgram;
    gl.useProgram(p);
    gl.viewport(0, 0, this.n, this.n);
    gl.uniform1i(gl.getUniformLocation(p, "u_n"), this.n);
    gl.uniform1f(gl.getUniformLocation(p, "u_u0"), this.u0);
    gl.uniform1f(gl.getUniformLocation(p, "u_tau"), TAU);
    for (let s = 0; s < steps; s += 1) {
      const src = this.f[this.cur];
      const dst = 1 - this.cur;
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.fFB[dst]);
      gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1, gl.COLOR_ATTACHMENT2]);
      this.bindTextures(p, [["u_f0", src[0]], ["u_f1", src[1]], ["u_f2", src[2]], ["u_mask", this.mask]]);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      this.cur = dst;
    }
  }

  computeVelocity() {
    const gl = this.gl;
    const p = this.velProgram;
    gl.useProgram(p);
    gl.viewport(0, 0, this.n, this.n);
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.velFB);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0]);
    gl.uniform1i(gl.getUniformLocation(p, "u_n"), this.n);
    const f = this.f[this.cur];
    this.bindTextures(p, [["u_f0", f[0]], ["u_f1", f[1]], ["u_f2", f[2]], ["u_mask", this.mask]]);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  stepParticles(steps) {
    const gl = this.gl;
    const p = this.partProgram;
    gl.useProgram(p);
    gl.viewport(0, 0, this.pw, this.ph);
    const dst = 1 - this.pcur;
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.pFB[dst]);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1]);
    gl.uniform1f(gl.getUniformLocation(p, "u_n"), this.n);
    gl.uniform1f(gl.getUniformLocation(p, "u_steps"), steps);
    gl.uniform1f(gl.getUniformLocation(p, "u_time"), (this.time += 0.0137) % 1000);
    this.bindTextures(p, [["u_p", this.p[this.pcur][0]], ["u_q", this.p[this.pcur][1]], ["u_vel", this.vel]]);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    this.pcur = dst;
  }

  prerender() {
    if (!this.supported || !this.frame || !this.active || !this.visible || !this.animate) return;
    this.withState(() => {
      this.stepLattice(this.stepsPerFrame);
      this.computeVelocity();
      this.stepParticles(this.stepsPerFrame);
    });
  }

  placeUniforms(p, matrix) {
    const gl = this.gl;
    const f = this.frame;
    gl.uniformMatrix4fv(gl.getUniformLocation(p, "u_matrix"), false, matrix);
    gl.uniform2f(gl.getUniformLocation(p, "u_origin"), this.origin.x, this.origin.y);
    gl.uniform1f(gl.getUniformLocation(p, "u_m"), this.m);
    gl.uniform1f(gl.getUniformLocation(p, "u_size"), f.sizeM);
    gl.uniform1f(gl.getUniformLocation(p, "u_n"), this.n);
    gl.uniform2f(gl.getUniformLocation(p, "u_d"), f.d[0], f.d[1]);
    gl.uniform2f(gl.getUniformLocation(p, "u_pp"), f.p[0], f.p[1]);
    gl.uniform1f(gl.getUniformLocation(p, "u_z"), 6);
    gl.uniform1f(gl.getUniformLocation(p, "u_u0"), this.u0);
    gl.uniform3fv(gl.getUniformLocation(p, "u_ink"), INK[this.theme]);
  }

  render(gl, options) {
    if (!this.supported || !this.frame || !this.active) return;
    const matrix = new Float32Array(options.defaultProjectionData.mainMatrix);
    gl.bindVertexArray(this.vao);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.depthMask(false);
    if (this.animate) {
      const p = this.tracerProgram;
      gl.useProgram(p);
      this.placeUniforms(p, matrix);
      gl.uniform1i(gl.getUniformLocation(p, "u_pw"), this.pw);
      this.bindTextures(p, [["u_p", this.p[this.pcur][0]], ["u_q", this.p[this.pcur][1]], ["u_vel", this.vel]]);
      gl.drawArrays(gl.LINES, 0, this.pw * this.ph * 2);
    } else {
      const p = this.fieldProgram;
      const seeds = 90;
      gl.useProgram(p);
      this.placeUniforms(p, matrix);
      gl.uniform1i(gl.getUniformLocation(p, "u_seeds"), seeds);
      this.bindTextures(p, [["u_vel", this.vel]]);
      gl.drawArrays(gl.LINES, 0, seeds * seeds * 2);
    }
    gl.bindVertexArray(null);
    gl.activeTexture(gl.TEXTURE0);
    if (this.animate && this.visible) this.map.triggerRepaint();
  }

  // For checks: read the velocity field back (lattice units, grid order).
  readVelocity() {
    if (!this.supported || !this.frame) return null;
    const gl = this.gl;
    const out = new Float32Array(this.n * this.n * 4);
    this.withState(() => {
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.velFB);
      gl.readPixels(0, 0, this.n, this.n, gl.RGBA, gl.FLOAT, out);
    });
    return out;
  }

  onRemove(map, gl) {
    if (!this.supported) return;
    [...this.f.flat(), ...this.p.flat(), this.mask, this.vel].forEach((t) => gl.deleteTexture(t));
    [...this.fFB, this.velFB, ...this.pFB].forEach((b) => gl.deleteFramebuffer(b));
    [this.lbmProgram, this.velProgram, this.partProgram, this.tracerProgram, this.fieldProgram].forEach((p) => gl.deleteProgram(p));
    gl.deleteVertexArray(this.vao);
  }
}
