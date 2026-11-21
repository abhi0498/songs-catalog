# Songs Dashboard — Design

Status: **Approved (batch).**
Implements: [requirements.md](requirements.md).

## 1. Stack

- **Vite + React 19, plain JavaScript (JSX), plain CSS.** No TypeScript, to keep it simple. The data shapes are small and documented in the API spec.
- **Tests:** Vitest + jsdom + @testing-library/react + @testing-library/user-event + @testing-library/jest-dom.
- **No runtime dependencies besides `react` and `react-dom`.** The chart is hand-written SVG: 25 points and two axes don't justify a chart library.
- **Versions** are pinned exactly in `package.json`, and the lockfile is committed.

## 2. Layout

```
frontend/
  index.html  package.json  vite.config.js  README.md
  src/
    main.jsx            # mounts <App/>
    App.jsx             # page state: table query, page data, search, all-songs for chart
    styles.css
    lib/                # pure logic, unit-tested
      api.js            # fetchSongs, fetchAllSongs, searchSongs, rateSong, ApiError
      columns.js        # COLUMNS (key, label, numeric)
      sort.js           # nextSort()
      csv.js            # toCsv(), csvFilename(), downloadCsv()
      reasons.js        # reasonText(codes)
      searchState.js    # describeSearch()
      chart.js          # chartPoints(), linearScale(), niceTicks()
    components/
      SongTable.jsx     # header buttons + rows; used for the page and search results
      Cell.jsx          # value, or "—" with reason tooltip
      StarRating.jsx    # 5 buttons, pending/error display
      Pagination.jsx
      SearchPanel.jsx   # input, Get Song, Clear, message, results table
      DurationChart.jsx # SVG scatter
    test/setup.js       # jest-dom matchers
```

## 3. State (`App.jsx`, plain `useState`)

| State | Shape | Notes |
|---|---|---|
| `query` | `{page, sort, order}` | Starts as `{1, "id", "asc"}`. Changing it triggers a fetch in `useEffect`. |
| `pageData` | `{items, page, total, total_pages}` or null | The last successful page. It stays visible while the next one loads (R-TBL-4). |
| `status` | `"loading" \| "ok" \| "error"`, plus `error` | |
| `search` | `{state: "idle"\|"loading"\|"done"\|"error", query, result, error}` | |
| `allSongs` | array | Fetched once for the chart. |

- **Stale responses:** each fetch effect uses an `ignore` flag in its cleanup, so a slow old page can't overwrite a newer one.
- **Rating updates (R-RATE-3):** `onRated(song)` replaces that song by `id` in `pageData.items`, `search.result.items` and `allSongs`. It doesn't re-sort (R-RATE-5).

## 4. Pure modules

```js
// sort.js
export const DEFAULT_SORT = { sort: "id", order: "asc" };
export function nextSort(current, column) {
  return current.sort === column
    ? { sort: column, order: current.order === "asc" ? "desc" : "asc" }
    : { sort: column, order: "asc" };
}

// csv.js
export function toCsv(rows, columns) -> string   // BOM + header + rows, CRLF
// cell(v): null/undefined → ""; number → String(v); string → guard(=,+,-,@,\t,\r) then quote if [",\r\n]
export function csvFilename({ page, sort, order }) -> `songs-page-${page}-${sort}-${order}.csv`
export function downloadCsv(text, filename)       // Blob + object URL + temporary <a download>

// reasons.js
export const REASON_TEXT = { out_of_range: "...", source_conflict: "...", ... };
export function reasonText(codes = []) -> string  // mapped, unknown → raw code, joined "; ", [] → "No value"

// searchState.js
export function describeSearch(search) -> { tone: "info"|"warn"|"error"|"muted", message }

// chart.js
export const CORRECTED = "unit_corrected_s_to_ms";
export function chartPoints(songs) -> { points: [{id,title,x,y,corrected,storedAs}], excluded }
export function linearScale([d0,d1],[r0,r1]) -> fn
export function niceTicks(min, max, count) -> number[]
```

`storedAs` for a corrected point is `duration_ms / 1000`. That's exact, because the pipeline's only correction is ×1000 (data D4). It's used only in the tooltip text.

## 5. API client (`api.js`)

- `BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"`.
- `request(path, init)`: `fetch`. On a non-2xx status it parses the JSON body if it can and throws `ApiError(status, message)`:
  - `detail` is a string → that string
  - `detail` is a list → `detail[0].msg`
  - otherwise → `HTTP <status>`

  A network failure throws `ApiError(0, "Network error: …")`.
- `fetchSongs({page, sort, order})` → `/songs?page&size=10&sort&order`
- `fetchAllSongs()` → `/songs?size=100&sort=id`
- `searchSongs(title)` → `/songs/search?title=` (URL-encoded)
- `rateSong(id, stars)` → `PUT /songs/{encodeURIComponent(id)}/rating` with a JSON body

## 6. Components

- **`SongTable({rows, sortState?, onSort?, onRated, busy})`:** when `onSort` is given, headers are buttons with ▲/▼ and `aria-sort`. Search results pass no `onSort`, so their headers are plain text: the API doesn't sort search results (U1).
- **`Cell({song, column})`:**
  - `null` → `<span class="null" tabindex="0" title={reason} aria-label={"No value: " + reason}>—</span>`
  - otherwise → the value as served
  - `rating` is handled by `StarRating`, not `Cell`
- **`StarRating({song, onRated})`:**
  - owns its `pending` and `error` state
  - calls `rateSong`, then `onRated(updatedSong)` on success
  - on failure it sets `error`: a status of 400–499 shows `err.message`, anything else shows "Couldn't save rating. Try again."
  - stars are `<button aria-label="Rate n of 5" aria-pressed={n <= rating}>`
- **`SearchPanel({onRated})`:** owns the search state. The form submit trims; an empty query sets the "Enter a title" state without fetching. It renders `describeSearch` and, when there are results, a `SongTable` without sorting.
- **`DurationChart({songs})`:**
  - SVG with a `viewBox` and `width:100%`
  - axes with nice ticks (y in seconds)
  - normal points are circles, corrected points are larger diamonds in the accent color
  - each point is a `<g tabindex=0>` with a `<title>`
  - legend and caption
- **`Pagination({page, totalPages, total, onPage, busy})`.**

## 7. Styling

One `styles.css` with CSS variables for colors. The table scrolls horizontally inside its own wrapper on narrow screens, and the page itself never scrolls sideways. Null cells are muted with a dotted underline to hint at the tooltip. The corrected-point color is chosen to have enough contrast with the normal points, and the shape tells them apart too.

## 8. Testing

- **Unit (`src/lib/*.test.js`):** every function in §4–5, with `fetch` stubbed via `vi.stubGlobal`.
- **Components (`src/components/*.test.jsx`, `src/App.test.jsx`):** `fetch` mocked with a small router that matches on URL and method.
  - App: header click → the URL has `sort=tempo&order=asc`, a second click → `order=desc`, and the page resets to 1.
  - SearchPanel: each of exact-one, exact-many, partial, none, empty and 422.
  - StarRating: success updates the row, a 500 keeps the old stars and shows the message, a 422 shows `detail`.
  - Chart: 3 corrected points rendered as diamonds, and the excluded count shown.
- **Dev server:** `npm run dev` (Vite on 5173), with the API on 8000.
