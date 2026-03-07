import { request } from "./client";

export async function get24HourForecast() {
  return request("/forecasts/twenty-four-hour");
}

export async function get4DayForecast() {
  return request("/forecasts/four-day");
}

export async function get2HourForecast() {
  return request("/forecasts/two-hour");
}
