// Text for the climate section of the Forecast model tab.
// Rainfall figures are island averages (see climate_trends.rainfall_basis).

const MIN_BASELINE_SHARE = 0.25;

// Percentage change, or null when the baseline is too small for a percentage to mean anything.
export function pctChange(value, baseline) {
  if (!Number.isFinite(value) || !Number.isFinite(baseline) || baseline <= 0) return null;
  if (baseline < MIN_BASELINE_SHARE * Math.abs(value)) return null;
  return Math.round((value / baseline - 1) * 100);
}

const mm = (v) => Math.round(v).toLocaleString("en-SG");

export function climateBullets(ct) {
  const years = ct?.years_covered || [];
  const annual = ct?.annual || {};
  const trends = ct?.long_term_trends || {};
  const rec = ct?.all_time_records || {};
  const full = years.filter((y) => annual[y]?.rainfall?.total_mm != null);
  if (full.length < 2) return [];

  const bullets = [];

  const byRain = full
    .map((y) => ({ year: y, total: annual[y].rainfall.total_mm }))
    .sort((a, b) => b.total - a.total);
  const wettest = byRain[0];
  const driest = byRain[byRain.length - 1];
  const pct = pctChange(wettest.total, driest.total);
  bullets.push(
    `${wettest.year} was the wettest full year, with ${mm(wettest.total)} mm averaged across rain gauges. ` +
      `${driest.year} was the driest, with ${mm(driest.total)} mm` +
      (pct != null ? `, so ${wettest.year} had ${pct}% more rain.` : "."),
  );

  const tTrend = trends.temperature_mean;
  if (tTrend?.significant) {
    bullets.push(`Average temperature rose by ${tTrend.slope_per_year.toFixed(3)}°C a year (p=${tTrend.p_value}).`);
  } else if (tTrend) {
    bullets.push(`Average temperature shows no clear trend over these years (p=${tTrend.p_value}).`);
  }

  const hottestYear = full
    .map((y) => ({ year: y, mean: annual[y]?.temperature?.mean_c }))
    .filter((t) => Number.isFinite(t.mean))
    .sort((a, b) => b.mean - a.mean)[0];
  if (hottestYear) {
    bullets.push(`${hottestYear.year} was the warmest year, averaging ${hottestYear.mean.toFixed(1)}°C.`);
  }

  const first = full[0];
  const last = full[full.length - 1];
  const t0 = annual[first]?.rainfall?.thundery_station_hours;
  const t1 = annual[last]?.rainfall?.thundery_station_hours;
  if (Number.isFinite(t0) && Number.isFinite(t1)) {
    bullets.push(
      `A gauge recorded 30 mm or more in an hour ${t0.toLocaleString("en-SG")} times in ${first} and ${t1.toLocaleString("en-SG")} times in ${last}.`,
    );
  }

  const rTrend = trends.rainfall_total;
  if (rTrend?.significant) {
    const dir = rTrend.slope_per_year > 0 ? "rose" : "fell";
    bullets.push(`Yearly rainfall ${dir} by about ${mm(Math.abs(rTrend.slope_per_year))} mm a year (p=${rTrend.p_value}).`);
  }

  if (rec.wettest_station_hour) {
    let s = `The wettest hour at a single gauge was ${rec.wettest_station_hour.value_mm} mm on ${rec.wettest_station_hour.date}.`;
    if (rec.wettest_island_hour) {
      s += ` Averaged across all gauges, the wettest hour was ${rec.wettest_island_hour.value_mm} mm on ${rec.wettest_island_hour.date}.`;
    }
    bullets.push(s);
  }

  return bullets;
}
