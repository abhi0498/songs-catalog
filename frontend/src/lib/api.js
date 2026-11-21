/** The single API client (R-ERR-1). Any non-2xx response becomes an ApiError. */

export const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const PAGE_SIZE = 10;

export class ApiError extends Error {
  /** status 0 means the request never got a response (network error). */
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function messageFrom(status, body) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return `HTTP ${status}`;
}

async function request(path, init) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch (e) {
    throw new ApiError(0, `Network error: ${e.message}`);
  }
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null; // non-JSON body (e.g. a plain-text 500)
  }
  if (!res.ok) throw new ApiError(res.status, messageFrom(res.status, body));
  return body;
}

export function fetchSongs({ page, sort, order }) {
  const params = new URLSearchParams({ page, size: PAGE_SIZE, sort, order });
  return request(`/songs?${params}`);
}

export function fetchAllSongs() {
  return request(`/songs?${new URLSearchParams({ size: 100, sort: "id" })}`);
}

export function searchSongs(title) {
  return request(`/songs/search?${new URLSearchParams({ title })}`);
}

export function rateSong(id, stars) {
  return request(`/songs/${encodeURIComponent(id)}/rating`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stars }),
  });
}
