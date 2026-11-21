# Songs Dashboard — Tasks

Status: **Approved (batch).**
Implements: [design.md](design.md). Each task is test-first and one commit, run from `frontend/`.

### F1 — Scaffold & API client
- Vite + React project (`package.json` with exact versions, `vite.config.js` with the Vitest jsdom config, `index.html`, `main.jsx`, a bare `App.jsx`, `styles.css`, `test/setup.js`). Ignore `node_modules/` and `dist/`.
- `lib/api.js`, `lib/columns.js`.
- **Tests:**
  - URLs and params for each call
  - a 404 with a string `detail` → `ApiError(404, detail)`
  - a 422 with a list `detail` → the first `msg`
  - a non-JSON 500 → "HTTP 500"
  - a network failure → status 0
  - the PUT body and header
  - ids are URL-encoded
- Traces: R-CFG-1, R-ERR-1.

### F2 — Sorting & the table
- `lib/sort.js`, `components/SongTable.jsx`, `Pagination.jsx`, `Cell.jsx` (values only for now). App fetches on load and on query change, ignoring stale responses.
- **Tests:**
  - `nextSort`: new column → asc, same column toggles, default
  - App on load requests `page=1&size=10&sort=title&order=asc` and renders 10 rows
  - clicking the Tempo header → `sort=tempo&order=asc`, clicking again → `desc`, `aria-sort` updates
  - from page 2, a sort click → page 1
  - Next/Prev disabled at the ends
  - fetch error → Retry refetches
- Traces: R-TBL-1..4, R-SORT-1..3.

### F3 — Null cells & CSV
- `lib/reasons.js`, `lib/csv.js`, null rendering in `Cell`, and the Download CSV button.
- **Tests:**
  - `reasonText`: each code, multiple codes, unknown code, empty list
  - `toCsv`: header order, null → empty, comma/quote/newline quoting, BOM + CRLF, `=SUM(1)` and `-x` guarded, `-0.05` as a number not guarded, "Naïve" kept
  - `csvFilename`
  - `Cell` renders "—" with the reason in `title`
  - the button is disabled with no rows
- Traces: R-NULL-1..3, R-CSV-1..4.

### F4 — Title search
- `lib/searchState.js`, `components/SearchPanel.jsx`.
- **Tests:**
  - `describeSearch` for exact-1, exact-many, partial-1, partial-many, none, empty, error, loading
  - panel: Enter and button both search, an empty query doesn't fetch, a 422 shows the API message, Clear hides the panel, results show "—" cells and the button reads "Searching…" while pending
- Traces: R-SRCH-1..5.

### F5 — Star rating
- `components/StarRating.jsx`, with `onRated` wired through App to the table and search results.
- **Tests:**
  - shows the current rating
  - a click sends a PUT with `{"stars": n}` and disables the stars while pending
  - success updates the row (and the search panel row for the same id)
  - a 500 keeps the old rating and shows "Couldn't save rating. Try again."
  - a 422 shows `detail`
  - the error clears after a later success
- Traces: R-RATE-1..5.

### F6 — Duration chart
- `lib/chart.js`, `components/DurationChart.jsx`, plus the App fetch of all songs.
- **Tests:**
  - `chartPoints`: corrected flag from `field_flags`, `storedAs` = ms/1000, nulls excluded and counted
  - `linearScale`
  - `niceTicks`
  - the component renders N circles + 3 diamonds for the real-shaped data, the legend count, and "not plotted" only when needed
- Traces: R-CHART-1..5.

### F7 — README & manual check
- `frontend/README.md` (install, dev, test, `VITE_API_URL`), and a root README link section.
- Run the whole Vitest suite, then the manual check from R-VER-3 against the real API in the browser.
- Traces: R-VER-3.
