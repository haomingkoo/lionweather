import { fmtDay, fmtDayTime, fmtTime } from "./hazeData";

function Icon({ d }) {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <path d={d} fill="currentColor" />
    </svg>
  );
}

const PLAY = "M4 2.5v11l9-5.5z";
const PAUSE = "M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z";
const BACK = "M3 2.5h2v11H3zM13 2.5v11L6 8z";
const FWD = "M11 2.5h2v11h-2zM3 2.5v11L10 8z";

export function Timeline({ hours, index, onIndex, playing, onPlay, speed, onSpeed, windowHours, onWindow, events, latestIndex }) {
  const n = hours.length;
  const pct = (i) => (n > 1 ? (i / (n - 1)) * 100 : 0);
  const ticks = hours.map((h, i) => ({ h, i })).filter(({ h }) => Number(fmtTime(h).slice(0, 2)) % 6 === 0);
  return (
    <section className="hz-timeline" aria-label="Timeline">
      <div className="hz-tl-head">
        <h2>Timeline</h2>
        <output className="hz-tl-now" aria-live="polite">
          {fmtDayTime(hours[index])}
          {index === latestIndex && <span className="hz-tl-latest">latest</span>}
        </output>
        <label className="hz-select">
          <span className="hz-sr">Time window</span>
          <select value={windowHours} onChange={(e) => onWindow(Number(e.target.value))}>
            <option value={24}>Last 24 hours</option>
            <option value={48}>Last 48 hours</option>
            <option value={72}>Last 72 hours</option>
          </select>
        </label>
      </div>
      <div className="hz-tl-body">
        <div className="hz-tl-controls">
          <button type="button" className="hz-icon-btn" onClick={() => onIndex(Math.max(0, index - 1))} aria-label="Previous hour">
            <Icon d={BACK} />
          </button>
          <button type="button" className="hz-icon-btn hz-play" onClick={onPlay} aria-label={playing ? "Pause" : "Play"} aria-pressed={playing}>
            <Icon d={playing ? PAUSE : PLAY} />
          </button>
          <button type="button" className="hz-icon-btn" onClick={() => onIndex(Math.min(n - 1, index + 1))} aria-label="Next hour">
            <Icon d={FWD} />
          </button>
          <label className="hz-select hz-speed">
            <span className="hz-sr">Playback speed</span>
            <select value={speed} onChange={(e) => onSpeed(Number(e.target.value))}>
              <option value={1}>1×</option>
              <option value={2}>2×</option>
              <option value={4}>4×</option>
            </select>
          </label>
        </div>
        <div className="hz-tl-track">
          <div className="hz-tl-events">
            {events.map((e) => (
              <button
                key={`${e.kind}-${e.index}`}
                type="button"
                className={`hz-tl-event hz-tl-event-${e.kind}`}
                style={{ left: `${pct(e.index)}%`, "--c": e.color }}
                onClick={() => onIndex(e.index)}
                title={`${e.label}, ${fmtDayTime(hours[e.index])}`}
                aria-label={`${e.label}, ${fmtDayTime(hours[e.index])}`}
              />
            ))}
          </div>
          <input
            type="range"
            min={0}
            max={n - 1}
            step={1}
            value={index}
            onChange={(e) => onIndex(Number(e.target.value))}
            aria-label="Hour"
            aria-valuetext={fmtDayTime(hours[index])}
            style={{ "--p": `${pct(index)}%` }}
          />
          <div className="hz-tl-ticks" aria-hidden="true">
            {ticks.map(({ h, i }) => (
              <span key={h} style={{ left: `${pct(i)}%` }} className={fmtTime(h) === "00:00" ? "hz-tl-day" : ""}>
                {fmtTime(h) === "00:00" ? fmtDay(h) : fmtTime(h)}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
