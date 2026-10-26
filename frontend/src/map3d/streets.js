// District presets and inputs for the wind-among-towers simulation.

export const DISTRICTS = {
  cbd: { label: "CBD and Marina Bay", lat: 1.2833, lng: 103.8545, bearing: -25 },
  orchard: { label: "Orchard", lat: 1.3035, lng: 103.8335, bearing: 10 },
  jurong: { label: "Jurong East", lat: 1.3333, lng: 103.7425, bearing: 0 },
};
export const DISTRICT_SIZE_M = 2000;

// Footprints of the buildings MapLibre has loaded, as polygon ring lists.
export function footprintsFrom(features) {
  const polys = [];
  for (const f of features) {
    const g = f.geometry;
    if (!g) continue;
    if (g.type === "Polygon") polys.push(g.coordinates);
    else if (g.type === "MultiPolygon") g.coordinates.forEach((p) => polys.push(p));
  }
  return polys;
}

// Measured wind for the district this hour: the nearest NEA station that reported,
// else the island average. Knots and the direction it blows from.
export function districtInflow(scene, index, { lat, lng }) {
  let best = null;
  for (const s of scene.wind.stations) {
    const r = scene.wind.station_hourly?.[s.name]?.[index];
    if (!r) continue;
    const d = Math.hypot((s.lng - lng) * Math.cos((lat * Math.PI) / 180), s.lat - lat) * 111.32;
    if (!best || d < best.km) best = { km: d, speedKn: r[0], fromDeg: r[1], station: s.name };
  }
  if (best) return best;
  const m = scene.wind.mean?.[index];
  return m ? { km: null, speedKn: m.speed_kn, fromDeg: m.dir_deg, station: null } : null;
}
