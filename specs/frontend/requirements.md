# Songs Dashboard — Requirements

Status: **Approved (batch).**
Scope: a single-page React dashboard over the [Songs API](../api/requirements.md). It reads songs, searches by title, writes ratings and shows one chart.
Out of scope: routing, auth, editing song data, deleting ratings (not in the API), mobile-first design (it must still work at phone width).

## 1. Principles

- **U1. The API is the source of truth.** Sorting, paging and search matching happen on the server. The UI never re-sorts or filters API results.
- **U2. Show unknowns honestly.** `null` is shown as "—" with the reason. It's never shown as 0 or a blank, and the UI never fills it in.
- **U3. Values as served.** Numbers are shown exactly as the API returns them, with no rounding or unit conversion in the table or CSV.
- **U4. Keep it simple.** React + Vite, plain CSS, no state library, no UI kit, and no chart library (the one chart is hand-drawn SVG).

## 2. Requirements

### Songs table

- **R-TBL-1.** On load, the app fetches `GET /songs?page=1&size=10&sort=title&order=asc` and shows the songs in a table. Title A→Z is the default because id order looks random to a user. The API keeps `id` as its own default, and the UI just asks for `title`.
- **R-TBL-2. Columns, left to right:**
  - `title`, `danceability`, `energy`, `acousticness`, `valence`, `tempo`, `duration_ms`, `num_sections`, `num_segments`, `mood`, `rating`, `id`
  - These are every sortable column the API offers (API R-LIST-4).
- **R-TBL-3. Pagination.** 10 rows per page. There are Prev/Next controls and a "Page X of Y · N songs" label. Prev is disabled on page 1, and Next on the last page.
- **R-TBL-4. States.** While a page is loading the previous rows stay visible, marked as loading. A failed fetch shows an error with a Retry button. An empty result shows "No songs".

### Sorting

- **R-SORT-1.** Every column header is a button. Clicking a **new** column sorts it `asc`. Clicking the **current** column toggles `asc` ↔ `desc`.
- **R-SORT-2.** Every sort change resets to page 1 and fetches from the API with `sort` and `order`. The UI never re-sorts rows itself (U1).
- **R-SORT-3.** The current column shows ▲ or ▼, and its header has `aria-sort="ascending" | "descending"`.

### Null cells

- **R-NULL-1.** A `null` value is shown as "—". Hovering or focusing it shows the reason, taken from the song's `field_flags[column]`.
- **R-NULL-2. Reason text.** Each reason code maps to a short plain-English text:
  - `out_of_range` → "Value out of valid range in the source; rejected"
  - `source_conflict` → "The two source files disagree; neither was chosen"
  - `missing_absent` / `missing_null` / `missing_na` / `missing_empty` → "Missing in the source"
  - `not_in_source` → "This source file has no such field"
  - `unparseable`, `not_integer` and `implausible_duration` get texts of their own too
  - an unknown code is shown as the raw code
  - several codes are joined with "; "
- **R-NULL-3.** An unrated song isn't a null cell. Its rating column shows empty stars (R-RATE-1).

### CSV download

- **R-CSV-1.** A "Download CSV" button saves the rows **currently shown in the table**: the current page in its current sort order.
- **R-CSV-2. Format:**
  - The header row uses the column keys from R-TBL-2, in that order.
  - Null values become empty cells. The "—" is display-only.
  - Fields containing a comma, quote, CR or LF are quoted, with quotes doubled (RFC 4180).
  - Line endings are CRLF, and the file starts with a UTF-8 BOM so Excel shows "Naïve" correctly.
- **R-CSV-3. Formula injection guard.** A **text** cell that starts with `=`, `+`, `-`, `@`, tab or CR gets a leading `'`. Numbers are never changed.
- **R-CSV-4.** The file is named `songs-page-<page>-<sort>-<order>.csv`. The button is disabled when no rows are shown.

### Title search ("Get Song")

- **R-SRCH-1.** A text box and a **Get Song** button, which Enter also triggers, call `GET /songs/search?title=…`. Results appear in their own panel above the table, and the table stays as it is.
- **R-SRCH-2. Each outcome is shown clearly:**

  | Response | Message |
  |---|---|
  | `exact`, 1 song | "1 song titled "God's Plan"" |
  | `exact`, many songs | "2 songs titled "Perfect" (titles aren't unique)" |
  | `partial` | "No exact match for "perf", showing 2 partial matches" (or "…1 partial match") |
  | `none` | "No songs match "zzz"" |

  The message uses the query as the user typed it.
- **R-SRCH-3.** Matches are listed with the same cells as the table (null "—" with reasons, star rating), in the order the API returns them.
- **R-SRCH-4.** An empty or whitespace-only query shows "Enter a title to search" without calling the API. A 422 from the API (e.g. `"!!!"`) shows the API's message. A network or server error shows an error message. A "Clear" button hides the panel.
- **R-SRCH-5.** While a search is in flight, the button shows "Searching…" and is disabled.

### Star rating

- **R-RATE-1.** The rating cell shows 5 star buttons. The current rating is filled, and unrated means all 5 are empty. Each button has an accessible label ("Rate 3 of 5").
- **R-RATE-2.** Clicking star *n* sends `PUT /songs/{id}/rating` with `{"stars": n}`. While it's pending, that row's stars are disabled.
- **R-RATE-3.** On success, the row shows the rating the API returned. That same song is updated wherever it's shown (table and search results).
- **R-RATE-4. Errors.** On failure the previous rating stays, and an inline error appears next to the stars: the API's `detail` for 4xx, or "Couldn't save rating. Try again." for a network or 5xx error. The error clears on the next successful rating of that song.
- **R-RATE-5.** When the table is sorted by `rating`, a new rating doesn't re-sort the current page by itself (U1). The order changes on the next fetch.

### Chart: duration vs num_segments

- **R-CHART-1.** One scatter plot of every song (fetched once as `GET /songs?size=100`): x = `num_segments`, y = duration (`duration_ms`, labelled in seconds).
- **R-CHART-2.** Songs whose `field_flags.duration_ms` contains `unit_corrected_s_to_ms` are highlighted with a different color **and** shape, and appear in a legend ("Corrected from seconds (3)").
  - **This is the evidence for the fix.** The corrected points sit on the same duration/segments trend as every other song. Their original values (corrected ÷ 1000, e.g. 158 s) would sit near zero.
  - A caption says this in one sentence.
- **R-CHART-3.** Hovering or focusing a point shows its title, duration and segments. Corrected points also show "stored as 158, read as seconds".
- **R-CHART-4.** Songs with a null `duration_ms` or `num_segments` are left out, with "N songs not plotted (missing values)" under the chart if N > 0.
- **R-CHART-5.** The chart is readable without color: shape plus legend. The SVG has a title and a description.

### Configuration & errors

- **R-CFG-1.** The API base URL comes from `VITE_API_URL` (default `http://localhost:8000`). The API's CORS already allows `http://localhost:5173`.
- **R-ERR-1.** Every API call goes through one client. Any non-2xx status becomes an error carrying the status and a readable message: the API's `detail` string, or the first validation message for a 422.

### Verification

- **R-VER-1.** Vitest unit tests for the pure logic:
  - CSV (escaping, nulls, BOM, CRLF, injection guard, column order)
  - the sort toggle
  - the search-state messages (every row of R-SRCH-2, plus the empty and error states)
  - null-reason text
  - chart point preparation (corrected flags, excluded songs, original values)
  - the API client's error handling
- **R-VER-2.** Component tests (Vitest + Testing Library, with `fetch` mocked) for:
  - a header click sending the right sort params and toggling
  - the search panel's messages
  - a rating success updating the row, and a rating failure keeping the old value and showing the error
- **R-VER-3.** A manual check against the real API: load, sort, page, search ("perfect", "perf", "21", "zzz"), rate and reload, CSV opened, chart highlights 3 points.
