import { request } from "./client";

export function getHazeScene(hours = 72) {
  return request(`/haze/scene?hours=${hours}`);
}
