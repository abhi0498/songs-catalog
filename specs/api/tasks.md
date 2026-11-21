# Songs API — Tasks

Status: **Approved (batch).**
Implements: [design.md](design.md) and [requirements.md](requirements.md) v2. Each task is test-first and one commit. Everything runs from `backend/`.

### A1 — Scaffold, config, song loading
- Add `app/` with `config.py` and `songs.py`. Add dependencies to `pyproject.toml`. Add `ratings.db*` to `.gitignore`.
- **Tests:**
  - `Settings.from_env` defaults point at `<repo>/data/normalized/songs.json` and `<repo>/backend/ratings.db` whatever the cwd, and env vars override them.
  - `load_songs` on the real file → 25 songs.
  - Missing file, not a list, missing key and duplicate id → `SongsLoadError` naming the path and the reason.
  - `SongStore.get` / `all` return id order, and a stored song is never mutated.
- Traces: R-CFG-1..3, R-SONG-2.

### A2 — Search key & matching
- `search.py`: `search_key` and `search`.
- **Tests:**
  - every R-SEARCH-2 table row, plus `"GODS PLAN"`, the curly apostrophe `"God’s Plan"`, `"  naïve "` and `"NAIVE"`
  - `"11:11"` ≠ `"1111"`
  - `21` → exact ["21"] only, `guns` → partial ["21 Guns"], `perfect` → exact, both, id order
  - `zzz` → none, []
  - a null title never matches
- Traces: R-SEARCH-2..4, R-SEARCH-6, D-API-1, D-API-2.

### A3 — Sorting & pagination
- `query.py`: `SORTABLE`, `sort_songs` and `paginate`.
- **Tests:**
  - asc/desc on a numeric field with nulls → nulls last both ways
  - ties ordered by id in both directions
  - title sort uses the search key ("café" next to "Cafe", lowercase mixed in)
  - `rating` with unrated → last
  - paging: 25/10 → 3 pages, page 3 has 5 items, page 4 is empty with the correct totals, total 0 → 0 pages
  - the input list is not mutated
- Traces: R-LIST-3, R-LIST-5..8.

### A4 — Rating store
- `ratings.py`: `RatingStore` with the schema from design §7.
- **Tests:**
  - set/get, and overwriting replaces
  - `all()`
  - persists across new `RatingStore` instances on the same file
  - the `CHECK` rejects 0 and 6 at the database level (`sqlite3.IntegrityError`)
  - creates the parent dir
  - rows for unknown ids are kept
- Traces: R-RATE-4..6.

### A5 — App factory & read endpoints
- `models.py` (`Song`, `Page`, `SearchResult`), `main.py` (`create_app`, CORS, `GET /songs`, `GET /songs/search`, `GET /songs/{id}`).
- **Tests (TestClient):**
  - **Pagination:** defaults; page 2 of `sort=tempo&order=desc` matches a sort of the whole dataset; page past the end.
  - **422s:** `page=0`, `size=0`, `size=101`, `page=abc`, `sort=loudness` (error lists the allowed values), `order=up`.
  - **Search:** exact/partial/none shape, `title=perfect` gives both, a missing or `"!!!"` title → 422.
  - **Single song:** `GET /songs/search` isn't treated as an id; unknown id → 404 `{"detail": ...}`.
  - **Song shape:** every song has every field plus `rating: null`, and values match `songs.json` exactly.
  - **CORS:** a preflight from `http://localhost:5173` is allowed, and one from another origin is not.
  - **Startup:** a bad songs file makes `create_app` raise.
- Traces: R-SONG-1..2, R-LIST-1..4, R-SEARCH-1, R-SEARCH-5, R-SEARCH-7, R-GET-1, R-CFG-2, R-CFG-4, R-ERR-1.

### A6 — Rating endpoint & persistence
- `RatingIn` and `PUT /songs/{id}/rating`.
- **Tests:**
  - `{"stars": 4}` → 200 with the full song and `rating: 4`; PUT twice gives the same result
  - 422 for each of `"5"`, `4.5`, `4.0`, `true`, `false`, `0`, `6`, `null`, `{}`, `{"stars": 3, "x": 1}`, `[3]`, a non-JSON body, and `?stars=3` with no body
  - unknown id → 404 and nothing stored
  - the rating shows up right away in list, `sort=rating`, search and get
  - **Restart:** rebuilding the app on the same db keeps the rating.
  - **Pipeline rerun:** rating a real song, running `pipeline.__main__.main` into the songs path and rebuilding the app keeps the rating on the same id.
  - **Orphans:** a rating on an id missing from a dataset is hidden, then comes back when the id returns.
- Traces: R-RATE-1..7, D-API-3.

### A7 — README & full check
- `backend/README.md`: an "API" section with how to run (`uvicorn app.main:create_app --factory --reload`), the endpoint table, the env vars, and the note that you restart after a pipeline run.
- Run the full suite, and smoke-test a real `uvicorn` with `curl` on each endpoint.
- Traces: R-CFG-3, R-VER-1..2.
