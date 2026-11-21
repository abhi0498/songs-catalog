import { describe, expect, it } from "vitest";
import { DEFAULT_SORT, nextSort } from "./sort.js";

describe("nextSort", () => {
  it("defaults to title ascending", () => {
    expect(DEFAULT_SORT).toEqual({ sort: "title", order: "asc" });
  });
  it("a new column starts ascending", () => {
    expect(nextSort({ sort: "id", order: "desc" }, "tempo")).toEqual({ sort: "tempo", order: "asc" });
  });
  it("the same column toggles asc -> desc -> asc", () => {
    const once = nextSort({ sort: "tempo", order: "asc" }, "tempo");
    expect(once).toEqual({ sort: "tempo", order: "desc" });
    expect(nextSort(once, "tempo")).toEqual({ sort: "tempo", order: "asc" });
  });
});
