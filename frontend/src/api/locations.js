import { request } from "./client";

export async function listLocations() {
  return request("/locations");
}

export async function createLocation(payload) {
  return request("/locations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteLocation(locationId) {
  return request(`/locations/${locationId}`, {
    method: "DELETE",
  });
}

export async function refreshLocation(locationId) {
  return request(`/locations/${locationId}/refresh`, {
    method: "POST",
  });
}
