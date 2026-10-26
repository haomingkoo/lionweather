import { request } from "./client";

export function getHazeScene(hours = 72) {
  return request(`/haze/scene?hours=${hours}`);
}

export function getHazeWindField(hours = 72) {
  return request(`/haze/wind-field?hours=${hours}`);
}
