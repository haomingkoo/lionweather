import { useEffect, useState } from "react";
import { request } from "../api/client";
import { get4DayForecast } from "../api/forecasts";
import { get7DayForecast, getHourlyForecast } from "../api/backend";

// WMO weather codes to the condition words NEA uses.
export function wmoToCondition(code) {
  if (code === 0) return "Clear";
  if (code <= 3) return "Partly Cloudy";
  if (code <= 48) return "Cloudy";
  if (code <= 67) return "Rain";
  if (code <= 82) return "Showers";
  if (code <= 99) return "Thunderstorm";
  return "Cloudy";
}

const sgtDate = (date = new Date()) => date.toLocaleDateString("en-CA", { timeZone: "Asia/Singapore" });

// NEA's 4-day outlook first, Open-Meteo for today and for days 5 to 7.
export function mergeDaily(neaForecasts = [], openMeteo = [], today = sgtDate()) {
  const toRow = (day, source) => ({
    date: day.date,
    high: day.temperature?.high ?? null,
    low: day.temperature?.low ?? null,
    condition: day.forecast || day.condition || "",
    source,
  });
  const daily = [];
  const nea = neaForecasts.slice(0, 4).map((d) => toRow(d, "NEA"));
  if (!nea.some((d) => d.date === today)) {
    const todayOm = openMeteo.find((d) => d.date === today);
    if (todayOm) daily.push(toRow(todayOm, "Open-Meteo"));
  }
  daily.push(...nea);
  const covered = new Set(daily.map((d) => d.date));
  for (const day of openMeteo) {
    if (daily.length >= 7) break;
    if (!covered.has(day.date) && day.date >= today) daily.push(toRow(day, "Open-Meteo"));
  }
  return daily.sort((a, b) => a.date.localeCompare(b.date)).slice(0, 7);
}

export function useForecasts(location) {
  const [state, setState] = useState({ hourly: [], daily: [], extra: null, status: "loading" });
  const lat = location?.latitude;
  const lng = location?.longitude;

  useEffect(() => {
    if (lat == null || lng == null) return undefined;
    let cancelled = false;
    setState((s) => ({ ...s, status: "loading" }));
    (async () => {
      const [hourlyRes, neaRes, omRes, extraRes] = await Promise.allSettled([
        getHourlyForecast(lat, lng),
        get4DayForecast(),
        get7DayForecast(lat, lng),
        request(`/weather/comprehensive/${location.id}?lat=${lat}&lng=${lng}`),
      ]);
      if (cancelled) return;
      const now = Date.now();
      const hourly = (hourlyRes.status === "fulfilled" ? hourlyRes.value : [])
        .filter((slot) => slot.time instanceof Date && slot.time.getTime() > now - 30 * 60 * 1000)
        .slice(0, 12)
        .map((slot) => ({
          time: slot.time,
          temperature: slot.temperature ?? null,
          condition: wmoToCondition(slot.weather_code),
          rainChance: slot.precip_prob ?? null,
        }));
      const daily = mergeDaily(
        neaRes.status === "fulfilled" ? neaRes.value?.forecasts || [] : [],
        omRes.status === "fulfilled" ? omRes.value : [],
      );
      const failed = hourly.length === 0 && daily.length === 0;
      setState({
        hourly,
        daily,
        extra: extraRes.status === "fulfilled" ? extraRes.value : null,
        status: failed ? "error" : "ready",
      });
    })();
    return () => { cancelled = true; };
  }, [lat, lng, location?.id]);

  return state;
}
