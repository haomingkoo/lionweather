import { request } from "./client";

export function getRainGauges() {
  return request("/rain/gauges");
}
