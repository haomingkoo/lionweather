import { Component, lazy, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { getHazeScene, getHazeWindField } from "../api/haze";
import { ThemeProvider, useTheme } from "../contexts/ThemeContext";
import {
  REGIONS,
  capitalise,
  compass,
  findEvents,
  fmtDayTime,
  lastIndexWithData,
  peak,
  regionAt,
  worstRegion,
} from "./hazeData";
import { DIRECTION_WORDS, explainHour, pathSummary } from "./explain";
import { fieldHour, outlookText, prepareField, simulateSmoke, smokeOutlook } from "./smoke";
import { placeCard } from "./placement";
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

const DEFAULT_LAYERS = { haze: true, wind: true, regions: true, relief: true, buildings: true, hotspots: true, path: true, smoke: true };
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

function AtCursor({ scene, index, region, onRegion, why }) {
  const at = regionAt(scene, region, index);
  const wind = scene.wind.mean[index];
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
          <dt>PSI <small>24-hour</small></dt>
          <dd className="hz-num">{at.psi ?? "n/a"}</dd>
          <dd><Band band={at.psiBand} /></dd>
        </div>
        <div>
          <dt>PM2.5 <small>µg/m³, 1-hour</small></dt>
          <dd className="hz-num">{at.pm25 ?? "n/a"}</dd>
          <dd><Band band={at.pm25Band} /></dd>
        </div>
      </dl>
      {at.psiBand || at.pm25Band ? (
        <div className="hz-advice">
          {at.psiBand && <p><strong>Today:</strong> {at.psiBand.plain}</p>}
          {at.pm25Band && <p><strong>This hour:</strong> {at.pm25Band.plain}</p>}
          <p className="hz-muted hz-small">
            Advice for healthy people, based on NEA. Older people, children, pregnant women and anyone with heart or lung
            conditions should take more care. <a href={scene.links.nea} target="_blank" rel="noopener noreferrer">Read NEA&apos;s advice</a>
          </p>
        </div>
      ) : (
        <p className="hz-muted">NEA has no reading for this region at this hour.</p>
      )}
      <p className="hz-wind-line">
        {wind
          ? `Wind ${wind.speed_kn.toFixed(1)} knots from the ${compass(wind.dir_deg)}, averaged over ${wind.stations} stations.`
          : "No wind readings for this hour."}
      </p>
      {why && (
        <div className="hz-why" aria-live="polite">
          <h3>Why this hour looks like this</h3>
          <p><strong>{why.headline}</strong> {why.body}</p>
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
  const wind850 = air?.status === "ok" ? air.sg_wind["850hPa"][index] : null;
  return (
    <section className="hz-card" aria-label="Air path and smoke">
      <header className="hz-card-head"><h2>Air path and smoke</h2></header>
      {path ? (
        <>
          <p className="hz-label-line">Approximate path of air arriving at 850 hPa, from Open-Meteo wind.</p>
          <p>
            {summary && `Over the last day the air came from the ${DIRECTION_WORDS[summary.from]}`}
            {summary?.lands.length ? `, over ${summary.lands.join(" and ")}` : ""}
            {summary ? `; 24 hours earlier it was about ${summary.reachKm} km away.` : ""}
            {wind850 && ` Wind at that height over Singapore: ${wind850[0].toFixed(1)} m/s from the ${DIRECTION_WORDS[compass(wind850[1])]}.`}
          </p>
          {!path.complete && <p className="hz-muted hz-small">The path stops where it leaves the area the wind data covers.</p>}
        </>
      ) : (
        <p className="hz-muted">The air path is not available right now.</p>
      )}
      {hs.status === "ok" ? (
        <>
          <p className="hz-outlook">{outlookText(outlook, { fires: fireCount })}</p>
          <p className="hz-muted hz-small">
            Simulated smoke drift from NASA-detected fires using Open-Meteo wind. Not a forecast of PSI. Each detection is
            drawn smoking for 12 hours, and its smoke is followed for 2 days.
          </p>
          <p className="hz-muted hz-small">
            NASA satellite fire detections: {firesInDay} in the 24 hours to this hour.
            {hs.last_pass && ` Last satellite pass ${fmtDayTime(hs.last_pass)}.`} Clouds and thick smoke can hide fires, so some may be missed.
          </p>
        </>
      ) : (
        <p className="hz-muted">{hs.status === "error" ? "NASA fire detections did not load. Try again later." : "NASA fire detections are not available right now."}</p>
      )}
      {view !== "region" && <p className="hz-muted hz-small">Switch to Region to see the path, fires and smoke.</p>}
    </section>
  );
}

function Overview({ scene, dataEnd, windowFires }) {
  const psiPeak = peak(scene, "psi");
  const pmPeak = peak(scene, "pm25");
  const hs = scene.hotspots;
  return (
    <section className="hz-card" aria-label="Overview">
      <header className="hz-card-head"><h2>Overview</h2></header>
      <dl className="hz-rows">
        <div><dt>Window</dt><dd>{fmtDayTime(scene.hours[0])} to {fmtDayTime(scene.hours[dataEnd])}</dd></div>
        <div><dt>Highest PSI</dt><dd>{psiPeak ? `${psiPeak.value}, ${psiPeak.region}, ${fmtDayTime(scene.hours[psiPeak.index])}` : "No data"}</dd></div>
        <div><dt>Highest PM2.5</dt><dd>{pmPeak ? `${pmPeak.value} µg/m³, ${pmPeak.region}, ${fmtDayTime(scene.hours[pmPeak.index])}` : "No data"}</dd></div>
        <div><dt>Hours with data</dt><dd>Air {scene.coverage.air_hours} of {scene.coverage.hours}, wind {scene.coverage.wind_hours} of {scene.coverage.hours}</dd></div>
        <div><dt>Fire detections</dt><dd>{hs.status === "ok" ? `${windowFires} in this window` : "Not available"}</dd></div>
      </dl>
    </section>
  );
}

function Sources({ scene }) {
  const s = scene.sources;
  return (
    <section className="hz-card hz-sources" aria-label="Sources">
      <header className="hz-card-head"><h2>Sources</h2></header>
      <ul>
        <li>
          <a href={s.air.url} target="_blank" rel="noopener noreferrer">{s.air.name}</a>: PSI and PM2.5.
          {" "}Latest reading {scene.latest.air ? fmtDayTime(scene.latest.air) : "not available"}.
        </li>
        <li>
          <a href={s.wind.url} target="_blank" rel="noopener noreferrer">{s.wind.name}</a>: hourly averages of minute readings.
          {" "}Latest {scene.latest.wind ? fmtDayTime(scene.latest.wind) : "not available"}.
        </li>
        <li>
          <a href={s.air_path.url} target="_blank" rel="noopener noreferrer">Weather data by Open-Meteo.com</a> (CC BY 4.0): wind at
          850 hPa, 925 hPa and 10 m for the air path and smoke drift.
        </li>
        <li>
          <a href={s.fires.url} target="_blank" rel="noopener noreferrer">{s.fires.name}</a>
          {scene.hotspots.status === "ok" ? ": VIIRS heat detections, low confidence removed." : ": not available right now."}
        </li>
        <li>Buildings: OpenStreetMap contributors, via OpenFreeMap.</li>
      </ul>
      <p className="hz-muted hz-small">Checked {fmtDayTime(scene.fetched_at)} SGT. The page refreshes its data every 10 minutes.</p>
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

function Legend({ view, scene, smokeOn }) {
  if (view === "region") {
    return (
      <div className="hz-legend" aria-label="Map key">
        <span className="hz-key"><i className="hz-key-path" aria-hidden="true" />Air path at 850 hPa, dots every 6 h</span>
        <span className="hz-key"><i className="hz-key-path2" aria-hidden="true" />925 hPa</span>
        {scene.hotspots.status === "ok" && <span className="hz-key"><i className="hz-key-fire" aria-hidden="true" />Fire detections, larger is more fire power</span>}
        {smokeOn && scene.hotspots.status === "ok" && <span className="hz-key"><i className="hz-key-smoke" aria-hidden="true" />Simulated smoke drift</span>}
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
      <span className="hz-legend-hint hz-muted">Thicker, browner haze means more PM2.5. Streaks show the wind.</span>
    </div>
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
                <Legend view={view} scene={scene} smokeOn={layers.smoke && !!smoke} />
              </div>
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
                <Toggle checked={layers.haze} onChange={setLayer("haze")} label="Haze" note="Thickness follows each region's PM2.5" disabled={!webgl} />
                <Toggle checked={layers.wind} onChange={setLayer("wind")} label="Wind" note={`${stationCount} NEA stations`} disabled={!webgl} />
                <Toggle checked={layers.regions} onChange={setLayer("regions")} label="Regions" note="NEA's five reporting areas" disabled={!webgl} />
                <Toggle checked={layers.buildings} onChange={setLayer("buildings")} label="Buildings" note={dim === "3d" ? "OpenStreetMap, real heights" : "3D view only"} disabled={!webgl || dim !== "3d"} />
                <Toggle checked={layers.relief} onChange={setLayer("relief")} label="Relief" note="Hill shading" disabled={!webgl} />
                <Toggle checked={layers.path} onChange={setLayer("path")} label="Air path" note={pathOk ? "Approximate, from Open-Meteo wind" : "Not available right now"} disabled={!webgl || !pathOk} />
                <Toggle
                  checked={layers.hotspots}
                  onChange={setLayer("hotspots")}
                  label="Fire detections"
                  note={hs.status === "ok" ? "NASA satellites, 24 hours to the cursor" : "Not available right now"}
                  disabled={!webgl || hs.status !== "ok"}
                />
                <Toggle
                  checked={layers.smoke}
                  onChange={setLayer("smoke")}
                  label="Smoke drift"
                  note={smoke ? "Simulated from fires and wind" : "Needs fire detections and wind"}
                  disabled={!webgl || !smoke}
                />
              </div>
            </section>

            <Overview scene={scene} dataEnd={dataEnd} windowFires={windowFires} />

            {events.length > 0 && (
              <section className="hz-card" aria-label="Moments">
                <header className="hz-card-head"><h2>Moments</h2></header>
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
