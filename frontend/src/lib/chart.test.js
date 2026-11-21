import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { CORRECTED, chartPoints, linearScale, niceTicks } from "./chart.js";

const REAL = JSON.parse(readFileSync(resolve(process.cwd(), "../data/normalized/songs.json"), "utf-8"));

describe("chartPoints", () => {
  it("plots every real song and flags the 3 corrected durations", () => {
    const { points, excluded } = chartPoints(REAL);
    expect(points).toHaveLength(25);
    expect(excluded).toBe(0);
    const corrected = points.filter((p) => p.corrected);
    expect(corrected.map((p) => p.title).sort()).toEqual(["Sunflower", "Sweet Child O Mine", "Uptown Funk"]);
    expect(corrected.map((p) => p.storedAs).sort((a, b) => a - b)).toEqual([158, 270, 356]);
  });

  it("x is num_segments, y is duration_ms", () => {
    const [p] = chartPoints([{ id: "a", title: "A", duration_ms: 158000, num_segments: 560,
                               field_flags: { duration_ms: [CORRECTED] } }]).points;
    expect(p).toEqual({ id: "a", title: "A", x: 560, y: 158000, corrected: true, storedAs: 158 });
  });

  it("uncorrected points have no storedAs", () => {
    const [p] = chartPoints([{ id: "a", title: "A", duration_ms: 1, num_segments: 1, field_flags: {} }]).points;
    expect(p.corrected).toBe(false);
    expect(p.storedAs).toBeNull();
  });

  it("songs with a null duration or segment count are excluded and counted", () => {
    const songs = [
      { id: "a", duration_ms: null, num_segments: 5, field_flags: {} },
      { id: "b", duration_ms: 5, num_segments: null, field_flags: {} },
      { id: "c", duration_ms: 5, num_segments: 5, field_flags: {} },
    ];
    const { points, excluded } = chartPoints(songs);
    expect(points.map((p) => p.id)).toEqual(["c"]);
    expect(excluded).toBe(2);
  });
});

describe("linearScale", () => {
  it("maps domain to range, including inverted ranges", () => {
    const y = linearScale([0, 100], [300, 0]);
    expect([y(0), y(50), y(100)]).toEqual([300, 150, 0]);
  });
  it("degenerate domain maps to the middle", () => {
    expect(linearScale([5, 5], [0, 10])(5)).toBe(5);
  });
});

describe("niceTicks", () => {
  it.each([
    [0, 1560, 5, [0, 500, 1000, 1500]],
    [0, 401.2, 5, [0, 100, 200, 300, 400]],
    [0, 1, 5, [0, 0.2, 0.4, 0.6, 0.8, 1]],
    [0, 0, 5, [0]],
  ])("niceTicks(%d, %d, %d)", (min, max, n, expected) => {
    expect(niceTicks(min, max, n)).toEqual(expected);
  });
});
