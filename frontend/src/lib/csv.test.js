import { describe, expect, it } from "vitest";
import { COLUMNS } from "./columns.js";
import { csvFilename, toCsv } from "./csv.js";

const BOM = "﻿";
const cols = [{ key: "title" }, { key: "tempo" }, { key: "rating" }];

function lines(csv) {
  expect(csv.startsWith(BOM)).toBe(true);
  return csv.slice(1).split("\r\n");
}

describe("toCsv", () => {
  it("header is the column keys in order (defaults to COLUMNS)", () => {
    expect(lines(toCsv([]))[0]).toBe(COLUMNS.map((c) => c.key).join(","));
  });

  it("uses CRLF, BOM and ends with a line break", () => {
    const csv = toCsv([{ title: "A", tempo: 1, rating: 2 }], cols);
    expect(csv).toBe(`${BOM}title,tempo,rating\r\nA,1,2\r\n`);
  });

  it("nulls become empty cells, numbers as served", () => {
    const csv = toCsv([{ title: "A", tempo: null, rating: null }, { title: "B", tempo: 108.73, rating: 5 }], cols);
    expect(lines(csv).slice(1, 3)).toEqual(["A,,", "B,108.73,5"]);
  });

  it("quotes fields with comma, quote or newline and doubles quotes", () => {
    const rows = [{ title: 'Say "hi", ok', tempo: 1, rating: 1 }, { title: "two\nlines", tempo: 1, rating: 1 },
                  { title: "cr\rhere", tempo: 1, rating: 1 }];
    expect(lines(toCsv(rows, cols)).slice(1, 3)).toEqual(['"Say ""hi"", ok",1,1', '"two\nlines",1,1']);
  });

  it.each([["=SUM(1)", "'=SUM(1)"], ["+1", "'+1"], ["-x", "'-x"], ["@cmd", "'@cmd"], ["\tx", "'\tx"]])(
    "guards formula-like text %j", (title, out) => {
      expect(lines(toCsv([{ title, tempo: 1, rating: 1 }], cols))[1]).toBe(`${out},1,1`);
    });

  it("never touches numbers, even negative", () => {
    expect(lines(toCsv([{ title: "A", tempo: -0.05, rating: 1 }], cols))[1]).toBe("A,-0.05,1");
  });

  it("keeps non-ASCII text", () => {
    expect(lines(toCsv([{ title: "Naïve", tempo: 1, rating: 1 }], cols))[1]).toBe("Naïve,1,1");
  });

  it("God's Plan needs no quoting", () => {
    expect(lines(toCsv([{ title: "God's Plan", tempo: 1, rating: null }], cols))[1]).toBe("God's Plan,1,");
  });
});

describe("csvFilename", () => {
  it("names page and sort", () => {
    expect(csvFilename({ page: 2, sort: "tempo", order: "desc" })).toBe("songs-page-2-tempo-desc.csv");
  });
});
