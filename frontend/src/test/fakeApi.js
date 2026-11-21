/** A tiny in-memory stand-in for the Songs API, installed as global fetch in component tests. */
import { vi } from "vitest";

export function makeSong(i, overrides = {}) {
  const id = `s${String(i).padStart(2, "0")}`;
  return {
    id,
    title: `Song ${i}`,
    danceability: 0.5, energy: 0.5, acousticness: 0.1, valence: 0.5,
    tempo: 100 + i, duration_ms: 200000 + i * 1000, num_sections: 8, num_segments: 800 + i * 4,
    mood: i % 2,
    sources: [{ file: "songs_part1.json", row: String(i) }],
    field_flags: {}, flags: [], possible_duplicates: [],
    rating: null,
    ...overrides,
  };
}

export function makeSongs(n = 25) {
  return Array.from({ length: n }, (_, i) => makeSong(i + 1));
}

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json" },
  });
}

/**
 * Install a fake fetch. `songs` is mutable server state. `overrides(url, init)` may return
 * a Response (or a Promise of one) to take over a request, e.g. to simulate errors.
 */
export function installFakeApi(songs = makeSongs(), overrides = () => undefined) {
  const calls = [];
  const fetchMock = vi.fn(async (input, init = {}) => {
    const url = new URL(input);
    const method = init.method ?? "GET";
    calls.push({ url, method, body: init.body ? JSON.parse(init.body) : undefined });
    const custom = await overrides(url, init);
    if (custom) return custom;

    if (method === "GET" && url.pathname === "/songs") {
      const page = Number(url.searchParams.get("page") ?? 1);
      const size = Number(url.searchParams.get("size") ?? 10);
      const sort = url.searchParams.get("sort") ?? "id";
      const order = url.searchParams.get("order") ?? "asc";
      const present = songs.filter((s) => s[sort] !== null);
      const missing = songs.filter((s) => s[sort] === null);
      present.sort((a, b) => (a[sort] < b[sort] ? -1 : a[sort] > b[sort] ? 1 : 0));
      if (order === "desc") present.reverse();
      const all = [...present, ...missing];
      return json(200, {
        items: all.slice((page - 1) * size, page * size),
        page, size, total: all.length, total_pages: Math.ceil(all.length / size),
      });
    }
    if (method === "GET" && url.pathname === "/songs/search") {
      const q = (url.searchParams.get("title") ?? "").trim().toLowerCase();
      const exact = songs.filter((s) => s.title?.toLowerCase() === q);
      const partial = songs.filter((s) => s.title?.toLowerCase().includes(q));
      const [match_type, items] = exact.length ? ["exact", exact]
        : partial.length ? ["partial", partial] : ["none", []];
      return json(200, { query: url.searchParams.get("title"), match_type, items });
    }
    const rate = url.pathname.match(/^\/songs\/([^/]+)\/rating$/);
    if (method === "PUT" && rate) {
      const song = songs.find((s) => s.id === decodeURIComponent(rate[1]));
      if (!song) return json(404, { detail: "not found" });
      song.rating = JSON.parse(init.body).stars;
      return json(200, { ...song });
    }
    return json(404, { detail: `no fake route for ${method} ${url.pathname}` });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock, songs };
}

export { json };
