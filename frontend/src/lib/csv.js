/** CSV of the rows currently shown (R-CSV-1..4). RFC 4180 quoting, CRLF, UTF-8 BOM. */
import { COLUMNS } from "./columns.js";

const BOM = "﻿";
const FORMULA_START = /^[=+\-@\t\r]/;
const NEEDS_QUOTES = /[",\r\n]/;

function cell(value) {
  if (value === null || value === undefined) return "";
  if (typeof value !== "string") return String(value); // numbers are never altered
  let s = FORMULA_START.test(value) ? `'${value}` : value; // spreadsheet formula guard
  if (NEEDS_QUOTES.test(s)) s = `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function toCsv(rows, columns = COLUMNS) {
  const header = columns.map((c) => c.key).join(",");
  const body = rows.map((row) => columns.map((c) => cell(row[c.key])).join(","));
  return BOM + [header, ...body].join("\r\n") + "\r\n";
}

export function csvFilename({ page, sort, order }) {
  return `songs-page-${page}-${sort}-${order}.csv`;
}

export function downloadCsv(text, filename) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
