import regionsGeo from "./sg-regions.json";
import { capitalise, regionAt } from "./hazeData";

// Flat SVG map for browsers without WebGL 2.
const [W, S, E, N] = [103.59, 1.15, 104.1, 1.48];
const WIDTH = 1000;
const HEIGHT = Math.round((WIDTH * (N - S)) / ((E - W) * Math.cos((1.35 * Math.PI) / 180)));

const px = (lng) => ((lng - W) / (E - W)) * WIDTH;
const py = (lat) => ((N - lat) / (N - S)) * HEIGHT;

function pathFor(geometry) {
  const polys = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  return polys
    .map((rings) => rings.map((ring) => `M${ring.map(([x, y]) => `${px(x).toFixed(1)},${py(y).toFixed(1)}`).join("L")}Z`).join(""))
    .join("");
}

export function Map2D({ scene, index, region, onSelect, onHover, metric = "psi" }) {
  return (
    <div className="hz-map2d">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`Flat map of ${metric === "psi" ? "PSI" : "PM2.5"} by region`}>
        <rect width={WIDTH} height={HEIGHT} className="hz-map2d-sea" />
        {regionsGeo.features.map((f) => {
          const r = f.properties.region;
          const at = regionAt(scene, r, index);
          return (
            <path
              key={r}
              d={pathFor(f.geometry)}
              className="hz-map2d-region"
              fill={at[`${metric}Band`]?.color || "#9aa5b4"}
              fillOpacity={r === region ? 0.6 : 0.42}
              strokeOpacity={r === region ? 0.9 : 0.4}
              strokeWidth={r === region ? 2.5 : 1}
              onClick={() => onSelect(r)}
              onMouseMove={(e) => onHover({ kind: "region", region: r, x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY })}
              onMouseLeave={() => onHover(null)}
            />
          );
        })}
        {scene.wind.stations.map((s) => {
          const w = scene.wind.station_hourly[s.name]?.[index];
          if (!w) return null;
          const len = 10 + w[0] * 3;
          return (
            <g key={s.name} className="hz-map2d-arrow" transform={`translate(${px(s.lng)},${py(s.lat)}) rotate(${w[1] + 180})`}>
              <line x1="0" y1={len / 2} x2="0" y2={-len / 2} strokeWidth="2.5" />
              <path d={`M0,${-len / 2 - 6} L5,${-len / 2 + 2} L-5,${-len / 2 + 2} Z`} stroke="none" />
            </g>
          );
        })}
        {Object.entries(scene.regions).map(([r, loc]) => {
          const at = regionAt(scene, r, index);
          return (
            <text key={r} x={px(loc.lng)} y={py(loc.lat)} textAnchor="middle" className="hz-map2d-label">
              <tspan x={px(loc.lng)}>{capitalise(r)}</tspan>
              <tspan x={px(loc.lng)} dy="1.2em" className="hz-map2d-value">{at[metric] ?? "no data"}</tspan>
            </text>
          );
        })}
      </svg>
    </div>
  );
}
