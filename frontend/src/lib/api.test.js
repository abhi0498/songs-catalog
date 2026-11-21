import { describe, expect, it, vi } from "vitest";
import { ApiError, BASE, fetchAllSongs, fetchSongs, rateSong, searchSongs } from "./api.js";
import { COLUMNS } from "./columns.js";

function respond(status, body, { json = true } = {}) {
  return vi.fn().mockResolvedValue(
    new Response(json ? JSON.stringify(body) : body, {
      status,
      headers: { "Content-Type": json ? "application/json" : "text/plain" },
    }),
  );
}

describe("api client", () => {
  it("defaults to localhost:8000", () => {
    expect(BASE).toBe("http://localhost:8000");
  });

  it("fetchSongs sends page, size 10, sort and order", async () => {
    const f = respond(200, { items: [] });
    vi.stubGlobal("fetch", f);
    await fetchSongs({ page: 2, sort: "tempo", order: "desc" });
    const url = new URL(f.mock.calls[0][0]);
    expect(url.origin + url.pathname).toBe("http://localhost:8000/songs");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      page: "2", size: "10", sort: "tempo", order: "desc",
    });
  });

  it("fetchAllSongs asks for up to 100 songs", async () => {
    const f = respond(200, { items: [] });
    vi.stubGlobal("fetch", f);
    await fetchAllSongs();
    expect(new URL(f.mock.calls[0][0]).searchParams.get("size")).toBe("100");
  });

  it("searchSongs URL-encodes the title", async () => {
    const f = respond(200, { items: [] });
    vi.stubGlobal("fetch", f);
    await searchSongs("God's Plan & co");
    const url = new URL(f.mock.calls[0][0]);
    expect(url.pathname).toBe("/songs/search");
    expect(url.searchParams.get("title")).toBe("God's Plan & co");
  });

  it("rateSong PUTs a JSON body to an encoded id", async () => {
    const f = respond(200, { id: "a/b", rating: 4 });
    vi.stubGlobal("fetch", f);
    const song = await rateSong("a/b", 4);
    const [url, init] = f.mock.calls[0];
    expect(url).toBe("http://localhost:8000/songs/a%2Fb/rating");
    expect(init.method).toBe("PUT");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ stars: 4 });
    expect(song.rating).toBe(4);
  });

  it("string detail becomes the message", async () => {
    vi.stubGlobal("fetch", respond(404, { detail: "song 'x' not found" }));
    const err = await fetchSongs({ page: 1, sort: "id", order: "asc" }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect([err.status, err.message]).toEqual([404, "song 'x' not found"]);
  });

  it("422 list detail uses the first message", async () => {
    vi.stubGlobal("fetch", respond(422, { detail: [{ msg: "title must contain a letter" }] }));
    const err = await searchSongs("!!!").catch((e) => e);
    expect([err.status, err.message]).toEqual([422, "title must contain a letter"]);
  });

  it("non-JSON error body falls back to HTTP status", async () => {
    vi.stubGlobal("fetch", respond(500, "Internal Server Error", { json: false }));
    const err = await rateSong("a", 3).catch((e) => e);
    expect([err.status, err.message]).toEqual([500, "HTTP 500"]);
  });

  it("network failure is status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const err = await rateSong("a", 3).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(err.message).toMatch(/^Network error/);
  });
});

describe("columns", () => {
  it("lists the user-facing columns, title first, without the internal id", () => {
    expect(COLUMNS.map((c) => c.key)).toEqual([
      "title", "danceability", "energy", "acousticness", "valence", "tempo",
      "duration_ms", "num_sections", "num_segments", "mood", "rating",
    ]);
  });
});
