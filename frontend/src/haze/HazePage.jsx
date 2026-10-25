import { Component, lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { getHazeScene } from "../api/haze";
import {
  capitalise,
  compass,
  findEvents,
  fmtDayTime,
  lastIndexWithData,
  peak,
  regionAt,
  worstRegion,
} from "./hazeData";
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

const DEFAULT_LAYERS = { haze: true, wind: true, regions: true, relief: true, buildings: true, hotspots: true, path: true };

function Band({ band }) {
  if (!band) return <span className="hz-band hz-band-none">No data</span>;
  return (
    <span className="hz-band" style={{ "--c": band.color }}>
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
        <button
          key={v}
          type="button"
          aria-pressed={value === v}
          disabled={disabledValues.includes(v)}
          onClick={() => onChange(v)}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

function AtCursor({ scene, index, region, onRegion }) {
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
          <dd className="hz-num">{at.psi ?? "–"}</dd>
          <dd><Band band={at.psiBand} /></dd>
        </div>
        <div>
          <dt>PM2.5 <small>µg/m³, 1-hour</small></dt>
          <dd className="hz-num">{at.pm25 ?? "–"}</dd>
          <dd><Band band={at.pm25Band} /></dd>
        </div>
      </dl>
      {(at.psiBand || at.pm25Band) ? (
        <div className="hz-advice">
          {at.psiBand && <p><strong>Today:</strong> {at.psiBand.plain}</p>}
          {at.pm25Band && <p><strong>This hour:</strong> {at.pm25Band.plain}</p>}
          <p className="hz-muted">
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
    </section>
  );
}

function Overview({ scene, dataEnd }) {
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
        <div><dt>Fire hotspots</dt><dd>{hs.status === "ok" ? `${hs.points.length} in the last ${hs.days} days` : hs.status === "error" ? "NASA FIRMS did not answer" : "Off, see below"}</dd></div>
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
          <a href={s.fires.url} target="_blank" rel="noopener noreferrer">{s.fires.name}</a>
          {scene.hotspots.status === "ok" ? ": satellite fire detections, low confidence removed." : ": not connected."}
        </li>
      </ul>
      <p className="hz-muted">Checked {fmtDayTime(scene.fetched_at)} SGT. The page refreshes its data every 10 minutes.</p>
    </section>
  );
}

function Tooltip({ hover, scene, index }) {
  if (!hover) return null;
  let body;
  if (hover.kind === "fire") {
    body = (
      <>
        <strong>Fire hotspot</strong>
        <span>Seen {fmtDayTime(hover.at)}</span>
        <span>Fire power {hover.frp} MW</span>
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
  return (
    <div className="hz-tooltip" style={{ left: hover.x + 14, top: hover.y + 14 }} role="status">
      {body}
    </div>
  );
}

export function HazePage() {
  const [windowHours, setWindowHours] = useState(72);
  const [scene, setScene] = useState(null);
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
    }
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

  return (
    <div className="hz-app">
      <header className="hz-top">
        <a className="hz-back" href="/">LionWeather</a>
        <span className="hz-top-sep" aria-hidden="true" />
        <h1>Haze over Singapore</h1>
        <p className="hz-top-sub">PSI, PM2.5 and wind, hour by hour</p>
        {scene && (
          <p className="hz-top-updated">
            Latest NEA reading {scene.latest.air ? fmtDayTime(scene.latest.air) : "not available"}
          </p>
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
            <div className="hz-map">
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
                    onHover={setHover}
                    onSelect={setRegion}
                  />
                </Suspense>
                </MapBoundary>
              ) : (
                <Map2D scene={scene} index={index} region={region} onSelect={setRegion} onHover={setHover} />
              )}
              <Tooltip hover={hover} scene={scene} index={index} />

              <div className="hz-map-tools">
                <Segmented
                  label="Map area"
                  value={view}
                  onChange={setView}
                  options={[["sg", "Singapore"], ["region", "Region"]]}
                  disabledValues={webgl ? [] : ["region"]}
                />
                {webgl && (
                  <Segmented label="Map style" value={dim} onChange={setDim} options={[["2d", "2D"], ["3d", "3D"]]} />
                )}
              </div>
              {!webgl && <p className="hz-map-note">This browser cannot draw the 3D map, so you are seeing a flat view.</p>}
            </div>

              <div className="hz-legend">
                {view === "sg" ? (
                  <>
                    <p className="hz-legend-title">PM2.5 this hour, µg/m³</p>
                    <ul>
                      {scene.bands.pm25.map((b, i) => {
                        const lo = i === 0 ? 0 : scene.bands.pm25[i - 1].max + 1;
                        return (
                          <li key={b.key} style={{ "--c": `var(--band-${b.key})` }}>
                            <i aria-hidden="true" />
                            {b.label} <span>{b.max ? `${lo}–${b.max}` : `${lo - 1}+`}</span>
                          </li>
                        );
                      })}
                    </ul>
                    <p className="hz-legend-note hz-legend-hint">Thicker, browner cloud means more PM2.5. Streaks show the wind.</p>
                  </>
                ) : (
                  <>
                    <p className="hz-legend-title">Where the air came from</p>
                    <p className="hz-legend-note">
                      Approximate. The dashed line traces where the air reaching Singapore at {fmtDayTime(scene.hours[index])} was
                      over the {scene.trajectory_hours} hours before, using only wind measured in Singapore. Winds over Sumatra and
                      higher up differ, so read it as a direction, not a route.
                    </p>
                    {hs.status !== "ok" && <p className="hz-legend-note hz-legend-warn">Fire hotspots are not shown: {hs.status === "error" ? hs.message : "the server has no NASA FIRMS key yet."}</p>}
                  </>
                )}
              </div>
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
            <AtCursor scene={scene} index={index} region={region} onRegion={setRegion} />

            <section className="hz-card" aria-label="Layers">
              <header className="hz-card-head"><h2>Layers</h2></header>
              <div className="hz-toggles">
                <Toggle checked={layers.haze} onChange={setLayer("haze")} label="Haze" note="Cloud thickness follows PM2.5" disabled={!webgl} />
                <Toggle checked={layers.wind} onChange={setLayer("wind")} label="Wind" note={`${stationCount} NEA stations`} disabled={!webgl} />
                <Toggle checked={layers.regions} onChange={setLayer("regions")} label="Regions" note="NEA's five reporting areas" disabled={!webgl} />
                <Toggle checked={layers.relief} onChange={setLayer("relief")} label="Relief" note="Hill shading" disabled={!webgl} />
                <Toggle checked={layers.buildings} onChange={setLayer("buildings")} label="Buildings" note={dim === "3d" ? "Zoom in to see them" : "3D view only"} disabled={!webgl || dim !== "3d"} />
                <Toggle checked={layers.path} onChange={setLayer("path")} label="Air path" note="Approximate, Region view" disabled={!webgl} />
                <Toggle
                  checked={layers.hotspots}
                  onChange={setLayer("hotspots")}
                  label="Fire hotspots"
                  note={hs.status === "ok" ? "NASA satellites, last 3 days" : "Needs a NASA FIRMS key"}
                  disabled={!webgl || hs.status !== "ok"}
                />
              </div>
            </section>

            <Overview scene={scene} dataEnd={dataEnd} />

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
          </aside>
        </main>
      )}
    </div>
  );
}

export default HazePage;
