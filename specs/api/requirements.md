# Songs API — Requirements

Status: **Approved (v2).** Open questions resolved in §5.
Scope: a FastAPI backend over the normalized dataset (`data/normalized/songs.json`, see [data spec](../data/requirements.md)) that serves songs and stores star ratings.
Out of scope: auth, multiple users, writing songs, deleting ratings (see §5 Q4), aggregates/stats endpoints.

## 1. Guiding principles

- **A1. The pipeline output is the source of truth for songs.** The API reads songs and never changes them. Ratings are the only thing it writes, and they live somewhere else.
- **A2. `id` is the identity.** Titles aren't unique (two "Perfect"s), so anything that addresses one song (rating, lookup) uses `id`. Title search returns a list.
- **A3. Null means unknown.** Null values from the pipeline are returned as `null`, never as 0 or "". They sort last and keep their flags.
- **A4. Strict input, clear errors.** Bad input gets a 4xx with a reason. Nothing is guessed or coerced (`"5"` is not 5).
- **A5. Deterministic responses.** The same request on the same data returns the same order, every time. Ties are always broken by `id`.

## 2. Storage decision

**Songs in memory, ratings in SQLite.**

| | Songs | Ratings |
|---|---|---|
| Size / access | 25 rows, read-only | small, written by users |
| Storage | loaded from `songs.json` into memory at startup | SQLite file (`ratings.db`), standard-library `sqlite3` |
| Why | Sorting and paging 25 rows in Python is trivial and keeps one copy of the data: the pipeline's file. Putting songs in a database would mean a load step that can drift out of sync. | Writes must persist across restarts and pipeline reruns, and survive concurrent requests. SQLite gives durable, transactional writes with no server and no extra dependency. A JSON file would need hand-written locking and atomic writes. In-memory would lose ratings on restart. |

Ratings are keyed by song `id` in their own file, which the pipeline never touches. That's what makes them survive a pipeline rerun (R-RATE-6). If the dataset grows to the point where in-memory sorting matters, songs can move into the same SQLite database without changing the API.

## 3. Requirements

### Song representation

- **R-SONG-1.** A song in any response has every field from `songs.json` (`id`, `title`, the audio features, `duration_ms`, `num_sections`, `num_segments`, `mood`, `sources`, `field_flags`, `flags`, `possible_duplicates`) plus `rating`: an integer 1–5, or `null` if unrated.
- **R-SONG-2.** Values are returned exactly as the pipeline wrote them. The API does no rounding, filling in or renaming.

### List songs — `GET /songs`

- **R-LIST-1.** Returns `{"items": [...], "page", "size", "total", "total_pages"}`. `total` is the number of songs in the whole dataset.
- **R-LIST-2. Pagination.** `page` is 1-based (default 1). `size` defaults to 10, and allowed sizes are 1–100. `page` < 1, `size` outside 1–100, or non-integer values → 422.
- **R-LIST-3.** A `page` past the end returns 200 with `items: []` and the correct `total` / `total_pages`. With 25 songs and size 10, `total_pages` is 3 and page 4 is empty.
- **R-LIST-4. Sorting.** `sort` (default `id`) can be any scalar column: `id`, `title`, `danceability`, `energy`, `acousticness`, `valence`, `tempo`, `duration_ms`, `num_sections`, `num_segments`, `mood`, `rating`. `order` is `asc` (default) or `desc`. Any other value → 422, and the error lists the allowed values.
- **R-LIST-5. Sort the whole dataset, then page.** Sorting happens before slicing, so page 2 of `sort=tempo&order=desc` holds the 11th–20th fastest songs overall.
- **R-LIST-6. Nulls last in both directions.** `null` values come after every non-null value, for `asc` and for `desc`.
- **R-LIST-7. Stable ties.** Songs with equal values, including all the nulls, are ordered by `id` ascending in both directions. That way pages never overlap or skip a song.
- **R-LIST-8.** `title` sorts by its search key (R-SEARCH-2), so "café" and "Cafe" sort together and lowercase titles don't land after all the uppercase ones.

### Title search — `GET /songs/search?title=…`

- **R-SEARCH-1. Response shape.** Returns `{"query": <as sent>, "match_type": "exact" | "partial" | "none", "items": [...]}`.
  - `items` is **always a list**, with 0, 1 or many songs. It's never a single object, and no match is 200 with `[]`, not 404.
  - `match_type` tells the UI which kind of match it is showing (D-API-1).
- **R-SEARCH-2. Search key.** The query and each title are compared on the same key, built in this order:
  1. Unicode NFKD, then remove combining marks (accents).
  2. Casefold.
  3. **Remove** apostrophes (`'`, `’`, `‘`, `ʼ`).
  4. **Replace** every other Unicode punctuation character with a space.
  5. Collapse runs of whitespace to one space and trim.

  | Input | Key |
  |---|---|
  | "God's Plan" | `gods plan` |
  | "11:11" | `11 11` (not `1111`) |
  | "Mr. Brightside" | `mr brightside` |
  | "Naïve" | `naive` |
  | " 4 walls  " | `4 walls` |

  Spacing is ignored in the sense of leading, trailing and repeated spaces. Spaces between words still count, so `"11 11"` and `"1111"` stay different (D-API-2).
- **R-SEARCH-3. Exact first, then partial.**
  - **Exact:** if any title's key equals the query key, return only those songs with `match_type: "exact"`.
  - **Partial:** otherwise, return songs whose key contains the query key as a substring, with `match_type: "partial"`.
  - **None:** otherwise, `match_type: "none"` and `items: []`.

  So `title=21` returns only "21" (exact), not "21 Guns". `title=guns` returns "21 Guns" (partial).
- **R-SEARCH-4.** Both "Perfect" songs come back for `title=perfect` (exact), ordered by `id`. Within any match type, items are ordered by `id`.
- **R-SEARCH-5.** A missing `title` parameter, or one whose key is empty (e.g. `"  "`, `"!!!"`), → 422.
- **R-SEARCH-6.** Songs with a `null` title never match.
- **R-SEARCH-7.** Results include `rating` and all flags, the same as in the list.

### Single song — `GET /songs/{id}`

- **R-GET-1.** Returns one song by `id`, or 404 if there's none. This is the only way to address a single song. Title lookups go through search (A2).

### Rating — `PUT /songs/{id}/rating`

- **R-RATE-1.** The body is JSON `{"stars": <int>}`. `stars` must be a JSON integer from 1 to 5. It doesn't come from the query string.
- **R-RATE-2. Strict validation → 422** for:
  - `"5"` (string)
  - `4.5` and `4.0` (floats, D-API-3)
  - `true` / `false` (boolean)
  - `0` and `6` (out of range)
  - `null`
  - a missing `stars`
  - extra fields
  - a non-object or non-JSON body
- **R-RATE-3.** An unknown `id` → 404. Nothing is stored for songs that aren't in the dataset.
- **R-RATE-4.** `PUT` sets or replaces the song's single rating, and doing it twice gives the same result. The response is 200 with the full song, including the new `rating`.
- **R-RATE-5. Persists.** A stored rating survives an API restart. A failed write returns 5xx and is never reported as success.
- **R-RATE-6. Survives pipeline reruns.** Ratings are keyed by `id` in their own database, so re-running `python -m pipeline` and restarting the API keeps every rating on the same song.
  - If a rated id is missing from a new dataset, its rating is kept in the database but not served.
  - If the id comes back, its rating comes back with it. Nothing is silently deleted.
- **R-RATE-7.** Ratings show up right away in `GET /songs` (including `sort=rating`), search and `GET /songs/{id}`, with no restart needed.

### Startup & configuration

- **R-CFG-1.** The songs path (default `data/normalized/songs.json` in the repo) and ratings database path (default `backend/ratings.db`, gitignored) can be changed with environment variables. Defaults are resolved from the code's location, not the current directory.
- **R-CFG-2.** If `songs.json` is missing or invalid (not a list, a record missing a field, duplicate ids), the API refuses to start with a clear error, rather than serving an empty list.
- **R-CFG-3.** Songs are loaded once at startup. To pick up a new pipeline run, restart the API. (That's a known limit, and it's fine for this scope.)
- **R-CFG-4.** CORS allows the dashboard's local dev origin (Vite, `http://localhost:5173`), configurable. No other origins by default.

### Errors

- **R-ERR-1.** Errors use FastAPI's standard shape: `{"detail": ...}` for 404, and its validation error list for 422. Errors always come back with the right status code, never a 200 that has an `error` field in it.

### Verification

- **R-VER-1.** Every requirement has an automated test against FastAPI's `TestClient`, with a temporary songs file and ratings database.
- **R-VER-2.** Specific cases:
  - sorting with nulls in both directions (`tempo` has a null)
  - page 2 of a sort across the whole dataset
  - a page past the end
  - every row of the R-SEARCH-2 table
  - `21` returning exact "21" only, and `guns` returning partial
  - both "Perfect"s returned
  - each rejected rating value in R-RATE-2
  - a rating that survives a pipeline rerun followed by a restart

## 4. Endpoint summary

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | `/songs?page&size&sort&order` | 200 page object | 422 |
| GET | `/songs/search?title=` | 200 `{query, match_type, items}` | 422 |
| GET | `/songs/{id}` | 200 song | 404 |
| PUT | `/songs/{id}/rating` body `{"stars": n}` | 200 song | 404, 422 |

## 5. Decisions

| # | Topic | Decision | Why |
|---|---|---|---|
| D-API-1 | Search matching | Exact key match first. Only if there's none, fall back to substring. Return `match_type`. | Pure substring would return "21 Guns" for "21". Falling back still helps a user who typed part of a title. |
| D-API-2 | Punctuation | Drop apostrophes, and replace other punctuation with a space | "gods plan" finds "God's Plan", while "11:11" becomes `11 11` and doesn't collide with "1111". That's also why spaces between words are kept rather than removed. |
| D-API-3 | `4.0` as rating | Rejected (strict integer) | It's a float in JSON, and the same rule rejects `"5"` and `true`. |
| D-API-4 | Deleting a rating | Not provided | Not asked for. Recorded in DECISIONS.md. Can be added later as `DELETE /songs/{id}/rating` → 204. |
