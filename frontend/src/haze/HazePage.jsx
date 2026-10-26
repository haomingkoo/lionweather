import { Component, lazy, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { getHazeScene, getHazeWindField } from "../api/haze";
import { ThemeProvider, useTheme } from "../contexts/ThemeContext";
import {
  REGIONS,
  adviceFor,
  capitalise,
  compass,
  findEvents,
  fmtDayTime,
  fmtTime,
  lastIndexWithData,
  peak,
  regionAt,
  worstRegion,
} from "./hazeData";
import { DIRECTION_WORDS, explainHour, pathSummary } from "./explain";
import { fieldHour, outlookText, prepareField, simulateSmoke, smokeOutlook } from "./smoke";
import { placeCard } from "./placement";
import { ORBIT_TIP, ORBIT_TIP_TOUCH } from "../map3d/controls";
import { PsiChart, Pm25Chart, WindChart } from "./Charts";
import { Timeline } from "./Timeline";
import { Map2D } from "./Map2D";
import "./haze.css";

const HazeMap = lazy(() => import("./HazeMap").then((m) => ({ default: m.HazeMap })));

// If the 3D map fails to start, fall back to the flat map instead of a blank panel.
class MapBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function hasWebGL2() {
  try {
    return !!document.createElement("canvas").getContext("webgl2");
  } catch {
    return false;
  }
}

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

const DEFAULT_LAYERS = { haze: true, wind: true, regions: true, relief: true, buildings: true, hotspots: true, path: true, path925: false, smoke: true };
const DAY_S = 24 * 3600;

// Points are [lat, lng, MW, seen, detections]: one point can merge several detections.
function countDetections(points) {
  return points.reduce((s, p) => s + (p[4] ?? 1), 0);
}

function Band({ band }) {
  if (!band) return <span className="hz-band hz-band-none">No data</span>;
  return (
    <span className="hz-band" style={{ "--c": `var(--band-${band.key})` }}>
      <i aria-hidden="true" />
      {band.label}
    </span>
  );
}

function Toggle({ checked, onChange, label, note, disabled }) {
  return (
    <label className={`hz-toggle${disabled ? " is-disabled" : ""}`}>
      <input type="checkbox" checked={checked && !disabled} onChange={(e) => onChange(e.target.checked)} disabled={disabled} />
      <span className="hz-toggle-text">
        <span>{label}</span>
        {note && <small>{note}</small>}
      </span>
    </label>
  );
}

function Segmented({ value, options, onChange, label, disabledValues = [] }) {
  return (
    <div className="hz-seg" role="group" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={v} type="button" aria-pressed={value === v} disabled={disabledValues.includes(v)} onClick={() => onChange(v)}>
          {text}
        </button>
      ))}
    </div>
  );
}

const KNOTS_PER_MS = 1.94384;
const NF = new Intl.NumberFormat("en-SG");

function InfoIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 7v4.5M8 4.6v.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

// A small "i" that opens a short note in place.
function Info({ label, children }) {
  return (
    <details className="hz-info">
      <summary aria-label={label} title={label}><InfoIcon /></summary>
      <div className="hz-info-body">{children}</div>
    </details>
  );
}

function AtCursor({ scene, index, region, onRegion, why }) {
  const at = regionAt(scene, region, index);
  const wind = scene.wind.mean[index];
  const advice = adviceFor(at.psiBand, at.pm25Band);
  return (
    <section className="hz-card hz-cursor-card" aria-label="At cursor">
      <header className="hz-card-head">
        <h2>At cursor</h2>
        <span className="hz-muted">{fmtDayTime(scene.hours[index])}</span>
      </header>
      <label className="hz-select hz-region-select">
        <span>Region</span>
        <select value={region} onChange={(e) => onRegion(e.target.value)}>
          {Object.keys(scene.regions).map((r) => (
            <option key={r} value={r}>{capitalise(r)}</option>
          ))}
        </select>
      </label>
      <dl className="hz-stats">
        <div>
          <dt>PSI <small>24 h</small></dt>
          <dd className="hz-num">{at.psi ?? "n/a"}</dd>
          <dd><Band band={at.psiBand} /></dd>
        </div>
        <div>
          <dt>PM2.5 <small>µg/m³, 1 h</small></dt>
          <dd className="hz-num">{at.pm25 ?? "n/a"}</dd>
          <dd><Band band={at.pm25Band} /></dd>
        </div>
      </dl>
      {advice ? (
        <div className="hz-advice">
          <p className="hz-advice-main">{advice}</p>
          <p className="hz-muted hz-small">
            Sensitive groups: take care. <a href={scene.links.nea} target="_blank" rel="noopener noreferrer">NEA advice ↗</a>
          </p>
        </div>
      ) : (
        <p className="hz-muted">No NEA reading here this hour.</p>
      )}
      <p className="hz-wind-line" title={wind ? `Average of ${wind.stations} NEA stations` : undefined}>
        {wind ? `Wind ${wind.speed_kn.toFixed(1)} kn from ${compass(wind.dir_deg)}` : "No wind reading this hour."}
      </p>
      {why && (
        <div className="hz-why" aria-live="polite">
          <h3>Why</h3>
          <p><strong>{why.headline}</strong></p>
          {why.body && <p>{why.body}</p>}
          {why.context && <p className="hz-muted hz-small">{why.context}</p>}
        </div>
      )}
    </section>
  );
}

function AirPathCard({ scene, index, view, outlook, fireCount, firesInDay }) {
  const air = scene.air_path;
  const hs = scene.hotspots;
  const path = air?.status === "ok" ? air.paths["850hPa"][index] : null;
  const summary = path ? pathSummary(path.points, { hours: 24 }) : null;
  return (
    <section className="hz-card" aria-label="Where today's air came from">
      <header className="hz-card-head">
        <h2>Where today&apos;s air came from</h2>
        <Info label="How this is worked out">
          <p>We trace the wind backwards from Singapore, hour by hour, to show where the air you&apos;re breathing was 1 to 3 days ago.</p>
          <p className="hz-muted">
            Open-Meteo wind at 850 hPa (about 1.5 km up). The smoke drift carries particles from each NASA fire detection on the
            same wind: 12 hours of smoke per detection, followed for 2 days. Not a PSI forecast. Clouds can hide fires.
          </p>
        </Info>
      </header>
      {summary ? (
        <p title="850 hPa">
          Air arriving ~1.5 km up came from the {DIRECTION_WORDS[summary.from]}
          {summary.lands.length ? `, over ${summary.lands.join(" and ")}` : ""} ({NF.format(summary.reachKm)} km away 24 h ago).
        </p>
      ) : (
        <p className="hz-muted">Air path not available right now.</p>
      )}
      {hs.status === "ok" ? (
        <>
          <p className="hz-outlook">{outlookText(outlook, { fires: fireCount })}</p>
          <p className="hz-muted hz-small">
            Fires seen, last 24 h: {NF.format(firesInDay)}
            {hs.last_pass && ` · last pass ${fmtTime(hs.last_pass)}`}
          </p>
        </>
      ) : (
        <p className="hz-muted">Fire detections not available right now.</p>
      )}
      {view !== "region" && <p className="hz-muted hz-small">Region view shows the path, fires and smoke.</p>}
    </section>
  );
}

function Overview({ scene, dataEnd, windowFires }) {
  const psiPeak = peak(scene, "psi");
  const pmPeak = peak(scene, "pm25");
  const hs = scene.hotspots;
  const missingAir = scene.coverage.hours - scene.coverage.air_hours;
  const missingWind = scene.coverage.hours - scene.coverage.wind_hours;
  const gaps = [missingAir && `${missingAir} h of air readings`, missingWind && `${missingWind} h of wind`].filter(Boolean);
  return (
    <section className="hz-card" aria-label="Overview">
      <header className="hz-card-head"><h2>Overview</h2></header>
      <dl className="hz-rows">
        <div><dt>Showing</dt><dd>{fmtDayTime(scene.hours[0])} to {fmtDayTime(scene.hours[dataEnd])}</dd></div>
        <div><dt>Highest PSI</dt><dd>{psiPeak ? `${psiPeak.value}, ${psiPeak.region}, ${fmtDayTime(scene.hours[psiPeak.index])}` : "No data"}</dd></div>
        <div><dt>Highest PM2.5</dt><dd>{pmPeak ? `${pmPeak.value} µg/m³, ${pmPeak.region}, ${fmtDayTime(scene.hours[pmPeak.index])}` : "No data"}</dd></div>
        {gaps.length > 0 && <div><dt>Missing</dt><dd>{gaps.join(", ")}</dd></div>}
        <div><dt>Fires seen</dt><dd>{hs.status === "ok" ? NF.format(windowFires) : "Not available"}</dd></div>
      </dl>
    </section>
  );
}

function Sources({ scene }) {
  const s = scene.sources;
  const w = scene.wind.stations.length;
  return (
    <section className="hz-card hz-sources" aria-label="Sources">
      <header className="hz-card-head"><h2>Sources</h2></header>
      <ul>
        <li>
          <a href={s.air.url} target="_blank" rel="noopener noreferrer">NEA (data.gov.sg)</a>: PSI, PM2.5,{" "}
          <a href={s.wind.url} target="_blank" rel="noopener noreferrer">wind</a> from {w} stations
          {scene.latest.air ? ` · updated ${fmtTime(scene.latest.air)}` : ""}
        </li>
        <li><a href={s.air_path.url} target="_blank" rel="noopener noreferrer">Open-Meteo</a>: regional wind (CC BY 4.0)</li>
        <li><a href={s.fires.url} target="_blank" rel="noopener noreferrer">NASA FIRMS</a>: fire detections</li>
        <li>OpenStreetMap, via OpenFreeMap: buildings</li>
      </ul>
      <p className="hz-muted hz-small">Checked {fmtTime(scene.fetched_at)}. Refreshes every 10 min.</p>
    </section>
  );
}

function Tooltip({ hover, scene, index, bounds }) {
  const ref = useRef(null);
  const [pos, setPos] = useState(null);
  useLayoutEffect(() => {
    if (!hover || !ref.current) return;
    const { offsetWidth: w, offsetHeight: h } = ref.current;
    setPos(placeCard({ x: hover.x, y: hover.y, w, h, width: bounds.width, height: bounds.height, obstacles: hover.obstacles || [] }));
  }, [hover, bounds.width, bounds.height]);
  if (!hover) return null;
  let body;
  if (hover.kind === "fire") {
    body = (
      <>
        <strong>{hover.n > 1 ? `${hover.n} NASA satellite fire detections` : "NASA satellite fire detection"}</strong>
        <span>Seen {fmtDayTime(new Date(hover.seen * 1000).toISOString())}</span>
        <span>Fire power {hover.frp} MW{hover.n > 1 ? " in total" : ""}</span>
      </>
    );
  } else {
    const at = regionAt(scene, hover.region, index);
    body = (
      <>
        <strong>{capitalise(hover.region)}</strong>
        <span>PSI {at.psi ?? "no data"}{at.psiBand ? `, ${at.psiBand.label.toLowerCase()}` : ""}</span>
        <span>PM2.5 {at.pm25 ?? "no data"}{at.pm25Band ? `, ${at.pm25Band.label.toLowerCase()}` : ""}</span>
      </>
    );
  }
  const style = pos ? { left: pos.left, top: pos.top } : { left: hover.x + 14, top: hover.y + 14, visibility: "hidden" };
  return (
    <div ref={ref} className="hz-tooltip" style={style} role="status">
      {body}
    </div>
  );
}

function Legend({ view, scene, smokeOn, path925 }) {
  if (view === "region") {
    return (
      <div className="hz-legend" aria-label="Map key">
        <span className="hz-key" title="850 hPa, dot every 6 h"><i className="hz-key-path" aria-hidden="true" />Where today&apos;s air came from</span>
        {path925 && <span className="hz-key" title="925 hPa"><i className="hz-key-path2" aria-hidden="true" />Closer to the ground</span>}
        {scene.hotspots.status === "ok" && <span className="hz-key"><i className="hz-key-fire" aria-hidden="true" />Fires, larger is hotter</span>}
        {smokeOn && scene.hotspots.status === "ok" && <span className="hz-key"><i className="hz-key-smoke" aria-hidden="true" />Smoke drift, simulated</span>}
      </div>
    );
  }
  return (
    <div className="hz-legend" aria-label="Map key">
      <span className="hz-legend-title">PM2.5 µg/m³</span>
      {scene.bands.pm25.map((b, i) => {
        const lo = i === 0 ? 0 : scene.bands.pm25[i - 1].max + 1;
        return (
          <span key={b.key} className="hz-key" style={{ "--c": `var(--band-${b.key})` }}>
            <i aria-hidden="true" />
            {b.label} <span className="hz-muted hz-num">{b.max ? `${lo}–${b.max}` : `${lo - 1}+`}</span>
          </span>
        );
      })}
      <span className="hz-legend-hint hz-muted">Browner haze, more PM2.5. Streaks show wind.</span>
    </div>
  );
}

// Shown once per browser, then remembered.
function OrbitTip() {
  const [show, setShow] = useState(() => {
    try {
      return !localStorage.getItem("hz-orbit-tip");
    } catch {
      return false;
    }
  });
  if (!show) return null;
  const touch = typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches;
  const close = () => {
    setShow(false);
    try {
      localStorage.setItem("hz-orbit-tip", "1");
    } catch {
      /* private mode: the tip just shows again next time */
    }
  };
  return (
    <p className="hz-tip" role="note">
      <span>{touch ? ORBIT_TIP_TOUCH : ORBIT_TIP}</span>
      <button type="button" onClick={close} aria-label="Dismiss tip">Got it</button>
    </p>
  );
}

function useSize(ref) {
  const [size, setSize] = useState({ width: 800, height: 500 });
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(([e]) => setSize({ width: e.contentRect.width, height: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

function HazeView() {
  const { theme } = useTheme();
  const [windowHours, setWindowHours] = useState(72);
  const [scene, setScene] = useState(null);
  const [field, setField] = useState(null);
  const [error, setError] = useState(null);
  const [index, setIndex] = useState(0);
  const [region, setRegion] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [view, setView] = useState("sg");
  const reduced = useMemo(prefersReducedMotion, []);
  const webgl = useMemo(hasWebGL2, []);
  const [dim, setDim] = useState(reduced ? "2d" : "3d");
  const [layers, setLayers] = useState(DEFAULT_LAYERS);
  const [hover, setHover] = useState(null);
  const mapBox = useRef(null);
  const mapSize = useSize(mapBox);

  const load = useCallback(async (hours) => {
    setError(null);
    try {
      const data = await getHazeScene(hours);
      setScene(data);
      const last = lastIndexWithData(data);
      setIndex(last);
      setRegion((r) => r || worstRegion(data, last));
    } catch (e) {
      setError(e.message || "Could not load haze data.");
      return;
    }
    // The smoke drift needs the wind field too; the page works without it.
    getHazeWindField(hours).then((f) => setField(prepareField(f))).catch(() => setField(null));
  }, []);

  useEffect(() => {
    load(windowHours);
    const id = setInterval(() => load(windowHours), 10 * 60 * 1000);
    return () => clearInterval(id);
  }, [load, windowHours]);

  const dataEnd = scene ? lastIndexWithData(scene) : 0;

  useEffect(() => {
    if (!playing || !scene) return undefined;
    const id = setInterval(() => {
      setIndex((i) => {
        if (i >= dataEnd) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, 900 / speed);
    return () => clearInterval(id);
  }, [playing, speed, scene, dataEnd]);

  const events = useMemo(() => (scene ? findEvents(scene) : []), [scene]);
  const points = useMemo(() => (scene?.hotspots?.status === "ok" ? scene.hotspots.points : []), [scene]);
  const smoke = useMemo(() => simulateSmoke(field, points), [field, points]);
  const cursorT = scene ? new Date(scene.hours[index]).getTime() / 1000 : 0;
  const windowStart = scene ? new Date(scene.hours[0]).getTime() / 1000 : 0;
  // Detections from the 24 hours up to the end of the cursor hour, with their age.
  const fires = useMemo(
    () => points.filter((p) => p[3] <= cursorT + 3600 && p[3] > cursorT + 3600 - DAY_S).map((p) => [...p.slice(0, 5), Math.max(0, (cursorT - p[3]) / 3600)]),
    [points, cursorT],
  );
  const windowFires = useMemo(() => countDetections(points.filter((p) => p[3] >= windowStart && p[3] <= windowStart + windowHours * 3600)), [points, windowStart, windowHours]);
  const smokeHour = smoke && scene ? fieldHour(smoke, scene.hours[index]) : null;
  const outlook = useMemo(() => smokeOutlook(smoke, smokeHour), [smoke, smokeHour]);

  const why = useMemo(() => {
    if (!scene) return null;
    const pm25 = Object.fromEntries(REGIONS.map((r) => [r, regionAt(scene, r, index).pm25]));
    const air = scene.air_path?.status === "ok" ? scene.air_path : null;
    const mean = scene.wind.mean[index];
    return explainHour({
      pm25,
      wind850: air?.sg_wind["850hPa"][index] ?? null,
      surface: mean ? [mean.speed_kn, mean.dir_deg] : null,
      path: air?.paths["850hPa"][index]?.points ?? null,
      fires,
      firesKnown: scene.hotspots.status === "ok",
    });
  }, [scene, index, fires]);

  const togglePlay = () => {
    if (!playing && index >= dataEnd) setIndex(0);
    setPlaying((p) => !p);
  };
  const setLayer = (key) => (on) => setLayers((l) => ({ ...l, [key]: on }));
  const scrub = (i) => {
    setPlaying(false);
    setIndex(i);
  };

  const hs = scene?.hotspots;
  const stationCount = scene?.wind.stations.length ?? 0;
  const pathOk = scene?.air_path?.status === "ok";

  return (
    <div className="hz-app">
      <header className="hz-top">
        <a className="hz-back" href="/">LionWeather</a>
        <span className="hz-top-sep" aria-hidden="true" />
        <h1>Haze over Singapore</h1>
        <p className="hz-top-sub">PSI, PM2.5, wind and where the air came from, hour by hour</p>
        {scene && (
          <p className="hz-top-updated">Latest NEA reading {scene.latest.air ? fmtDayTime(scene.latest.air) : "not available"}</p>
        )}
      </header>

      {!scene && !error && (
        <div className="hz-state" role="status">
          <span className="hz-spinner" aria-hidden="true" />
          Loading the last {windowHours} hours of NEA readings…
        </div>
      )}
      {!scene && error && (
        <div className="hz-state hz-state-error" role="alert">
          <p>Haze data could not load. {error}</p>
          <button type="button" className="hz-btn" onClick={() => load(windowHours)}>Try again</button>
        </div>
      )}

      {scene && region && (
        <main className="hz-main">
          <div className="hz-stage">
            <div className="hz-map-area">
              <div className="hz-toolbar">
                <Segmented
                  label="Map area"
                  value={view}
                  onChange={setView}
                  options={[["sg", "Singapore"], ["region", "Region"]]}
                  disabledValues={webgl ? [] : ["region"]}
                />
                {webgl && <Segmented label="Map style" value={dim} onChange={setDim} options={[["2d", "2D"], ["3d", "3D"]]} />}
                <Legend view={view} scene={scene} smokeOn={layers.smoke && !!smoke} path925={layers.path925} />
              </div>
              {webgl && dim === "3d" && <OrbitTip />}
              <div className="hz-map" ref={mapBox}>
                {webgl ? (
                  <MapBoundary fallback={<Map2D scene={scene} index={index} region={region} onSelect={setRegion} onHover={setHover} />}>
                    <Suspense fallback={<div className="hz-state" role="status">Loading the map…</div>}>
                      <HazeMap
                        scene={scene}
                        index={index}
                        region={region}
                        view={view}
                        dim={dim}
                        layers={layers}
                        motion={!reduced}
                        theme={theme}
                        smoke={smoke}
                        smokeHour={smokeHour}
                        fires={fires}
                        onHover={setHover}
                        onSelect={setRegion}
                      />
                    </Suspense>
                  </MapBoundary>
                ) : (
                  <Map2D scene={scene} index={index} region={region} onSelect={setRegion} onHover={setHover} />
                )}
                <Tooltip hover={hover} scene={scene} index={index} bounds={mapSize} />
              </div>
              {!webgl && <p className="hz-map-note">This browser cannot draw the 3D map, so you are seeing a flat view.</p>}
            </div>

            <Timeline
              hours={scene.hours}
              index={index}
              onIndex={scrub}
              playing={playing}
              onPlay={togglePlay}
              speed={speed}
              onSpeed={setSpeed}
              windowHours={windowHours}
              onWindow={(h) => {
                setPlaying(false);
                setWindowHours(h);
              }}
              events={events}
              latestIndex={dataEnd}
            />

            <div className="hz-charts">
              <PsiChart scene={scene} cursor={index} region={region} onScrub={scrub} />
              <Pm25Chart scene={scene} cursor={index} region={region} onScrub={scrub} />
              <WindChart scene={scene} cursor={index} onScrub={scrub} />
            </div>
          </div>

          <aside className="hz-side">
            <AtCursor scene={scene} index={index} region={region} onRegion={setRegion} why={why} />

            <AirPathCard scene={scene} index={index} view={view} outlook={outlook} fireCount={points.length} firesInDay={countDetections(fires)} />

            <section className="hz-card" aria-label="Layers">
              <header className="hz-card-head"><h2>Layers</h2></header>
              <div className="hz-toggles">
                <Toggle checked={layers.haze} onChange={setLayer("haze")} label="Haze" note="Thickness follows PM2.5" disabled={!webgl} />
                <Toggle checked={layers.wind} onChange={setLayer("wind")} label="Wind" note={`${stationCount} NEA stations`} disabled={!webgl} />
                <Toggle checked={layers.regions} onChange={setLayer("regions")} label="Regions" note="NEA's five areas" disabled={!webgl} />
                <Toggle checked={layers.buildings} onChange={setLayer("buildings")} label="Buildings" note={dim === "3d" ? "OpenStreetMap, real heights" : "3D view only"} disabled={!webgl || dim !== "3d"} />
                <Toggle checked={layers.relief} onChange={setLayer("relief")} label="Relief" note="Hill shading" disabled={!webgl} />
                <Toggle checked={layers.path} onChange={setLayer("path")} label="Where today's air came from" note={pathOk ? "About 1.5 km up, last 3 days" : "Not available right now"} disabled={!webgl || !pathOk} />
                <Toggle checked={layers.path925} onChange={setLayer("path925")} label="Same, closer to the ground" note="About 750 m up" disabled={!webgl || !pathOk} />
                <Toggle
                  checked={layers.hotspots}
                  onChange={setLayer("hotspots")}
                  label="Fire detections"
                  note={hs.status === "ok" ? "NASA satellites, last 24 h" : "Not available right now"}
                  disabled={!webgl || hs.status !== "ok"}
                />
                <Toggle
                  checked={layers.smoke}
                  onChange={setLayer("smoke")}
                  label="Smoke drift"
                  note={smoke ? "Simulated" : "Needs fires and wind"}
                  disabled={!webgl || !smoke}
                />
              </div>
            </section>

            <Overview scene={scene} dataEnd={dataEnd} windowFires={windowFires} />

            {events.length > 0 && (
              <section className="hz-card" aria-label="Key changes">
                <header className="hz-card-head"><h2>Key changes</h2></header>
                <p className="hz-muted hz-small hz-card-sub">Tap to jump the timeline.</p>
                <ol className="hz-moments">
                  {events.map((e) => (
                    <li key={`${e.kind}-${e.index}`}>
                      <button type="button" onClick={() => scrub(e.index)} aria-current={e.index === index ? "true" : undefined}>
                        <i style={{ "--c": e.color }} aria-hidden="true" />
                        <span>{e.label}</span>
                        <time>{fmtDayTime(scene.hours[e.index])}</time>
                      </button>
                    </li>
                  ))}
                </ol>
              </section>
            )}

            <Sources scene={scene} />

            <footer className="hz-footer">
              <nav aria-label="Site">
                <ul>
                  <li>© 2026 Haoming Koo</li>
                  <li aria-hidden="true">·</li>
                  <li><a href="/privacy.html">Privacy</a></li>
                  <li aria-hidden="true">·</li>
                  <li><a href="/terms.html">Terms</a></li>
                  <li aria-hidden="true">·</li>
                  <li>Contact (<a href="mailto:privacy@kooexperience.com">privacy@kooexperience.com</a>)</li>
                  <li aria-hidden="true">·</li>
                  <li>More projects → <a href="https://kooexperience.com/">kooexperience.com</a></li>
                </ul>
              </nav>
            </footer>
          </aside>
        </main>
      )}
    </div>
  );
}

export function HazePage() {
  return (
    <ThemeProvider>
      <HazeView />
    </ThemeProvider>
  );
}

export default HazePage;
