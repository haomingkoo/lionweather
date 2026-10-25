import { request } from "./client";

export function getAirQualityLatest() {
  return request("/air-quality/latest");
}

export function getAirQualityHistory(hours = 24) {
  return request(`/air-quality/history?hours=${hours}`);
}
