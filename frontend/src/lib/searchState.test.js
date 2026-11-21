import { describe, expect, it } from "vitest";
import { ApiError } from "./api.js";
import { describeSearch } from "./searchState.js";

const done = (query, match_type, n) => ({
  state: "done", query, result: { query, match_type, items: Array.from({ length: n }, (_, i) => ({ id: `x${i}` })) },
});

describe("describeSearch", () => {
  it("idle shows nothing", () => {
    expect(describeSearch({ state: "idle" })).toBeNull();
  });
  it("empty query", () => {
    expect(describeSearch({ state: "empty" })).toEqual({ tone: "muted", message: "Enter a title to search" });
  });
  it("loading", () => {
    expect(describeSearch({ state: "loading", query: "perf" }).message).toBe('Searching for "perf"…');
  });
  it("exact, one", () => {
    expect(describeSearch(done("God's Plan", "exact", 1)))
      .toEqual({ tone: "info", message: '1 song titled "God\'s Plan"' });
  });
  it("exact, many", () => {
    expect(describeSearch(done("Perfect", "exact", 2)))
      .toEqual({ tone: "info", message: '2 songs titled "Perfect" (titles aren\'t unique)' });
  });
  it("partial, many", () => {
    expect(describeSearch(done("perf", "partial", 2)))
      .toEqual({ tone: "warn", message: 'No exact match for "perf", showing 2 partial matches' });
  });
  it("partial, one", () => {
    expect(describeSearch(done("guns", "partial", 1)).message)
      .toBe('No exact match for "guns", showing 1 partial match');
  });
  it("none", () => {
    expect(describeSearch(done("zzz", "none", 0)))
      .toEqual({ tone: "muted", message: 'No songs match "zzz"' });
  });
  it("422 shows the API message", () => {
    expect(describeSearch({ state: "error", query: "!!!", error: new ApiError(422, "title must contain a letter") }))
      .toEqual({ tone: "error", message: "title must contain a letter" });
  });
  it.each([0, 500])("status %i is a generic failure", (status) => {
    expect(describeSearch({ state: "error", query: "x", error: new ApiError(status, "boom") }))
      .toEqual({ tone: "error", message: "Search failed: boom" });
  });
});
