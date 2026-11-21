# Songs API — Design

Status: **Approved (batch).**
Implements: [requirements.md](requirements.md) v2.

## 1. Overview

```
data/normalized/songs.json ──load once at startup──► SongStore (in memory, read-only)
                                                          │
 HTTP ─► FastAPI routes (main.py) ─► query logic (pure) ──┤
                                                          │
backend/ratings.db ◄──────── RatingStore (sqlite3) ◄──────┘  ratings merged into each response
```

Pure functions do the sorting, paging and searching on plain dicts, so they can be tested without HTTP. The routes stay thin: validate parameters, call the logic, attach ratings, return.

## 2. Code layout

```
backend/
  app/
    __init__.py
    config.py     # Settings from env vars; defaults resolved from __file__
    songs.py      # load_songs() + validation; SongStore
    search.py     # search_key(); search() → (match_type, items)
    query.py      # sort_songs(); paginate()
    ratings.py    # RatingStore over sqlite3
    models.py     # pydantic: RatingIn, Song, Page, SearchResult
    main.py       # create_app(settings) factory, lifespan, routes, CORS
  tests/api/
    conftest.py   # tmp songs.json + tmp ratings.db + TestClient fixture
    test_config.py test_search.py test_query.py test_ratings.py
    test_read_endpoints.py test_rating_endpoint.py
```

Run it with `uvicorn app.main:create_app --factory --reload` from `backend/`. With no arguments, `create_app()` reads the settings from the environment. There's deliberately **no module-level `app`**: importing `app.main` (for example in tests) would otherwise load the real songs and create `backend/ratings.db` as a side effect. Tests call `create_app(Settings(...))` directly with temporary paths.

## 3. Config (`config.py`)

```python
@dataclass(frozen=True)
class Settings:
    songs_path: Path      # env SONGS_PATH,    default <repo>/data/normalized/songs.json
    ratings_db: Path      # env RATINGS_DB,    default <repo>/backend/ratings.db
    cors_origins: tuple[str, ...]  # env CORS_ORIGINS (comma-separated), default ("http://localhost:5173",)

    @classmethod
    def from_env(cls) -> "Settings": ...
```

`ratings.db` (and `-wal`/`-journal` files) are added to `.gitignore`.

## 4. Songs (`songs.py`)

- `load_songs(path) -> list[dict]` reads the JSON and checks R-CFG-2:
  - the top level is a list
  - every item is an object with every key of the songs.json contract (the record keys from `pipeline.schema.FIELDS` plus `id`, `sources`, `field_flags`, `flags`, `possible_duplicates`)
  - ids are unique, non-empty strings

  Any failure raises `SongsLoadError` with the path and the reason. The field list is imported from `pipeline.schema`, so the contract is defined in one place (data design §7).
- `SongStore`:
  - holds the list sorted by id and a `by_id` dict
  - precomputes each song's search key, once, at load
  - `get(id)`, `all()` and `__len__`

Songs are never mutated. The rating is attached to a **copy** when building a response (`{**song, "rating": r}`).

## 5. Search (`search.py`)

```python
APOSTROPHES = "'’‘ʼ"

def search_key(text: str) -> str:
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = "".join(c for c in s if c not in APOSTROPHES)
    s = "".join(" " if unicodedata.category(c).startswith("P") else c for c in s)
    return " ".join(s.split())

def search(songs, query) -> tuple[Literal["exact","partial","none"], list[dict]]:
    q = search_key(query)            # caller has already rejected an empty q (422)
    exact   = [s for s in songs if key(s) == q]
    if exact:   return "exact", exact
    partial = [s for s in songs if q in key(s)]
    return ("partial", partial) if partial else ("none", [])
```

- Songs with a `null` title have no key and never match (R-SEARCH-6).
- `songs` comes in id order, so results are id-ordered (R-SEARCH-4).
- NFKD runs before casefold, so `"Ｎａïｖｅ"` (full-width letters) also folds to `naive`. That's fine and expected.

## 6. Sorting & paging (`query.py`)

```python
SORTABLE = ("id", "title", "danceability", "energy", "acousticness", "valence", "tempo",
            "duration_ms", "num_sections", "num_segments", "mood", "rating")

def sort_songs(songs: list[dict], field: str, order: str) -> list[dict]:
    keyf = search_key if field == "title" else identity
    present = sorted((s for s in songs if s[field] is not None), key=lambda s: s["id"])
    present.sort(key=lambda s: keyf(s[field]), reverse=(order == "desc"))   # stable
    missing = sorted((s for s in songs if s[field] is None), key=lambda s: s["id"])
    return present + missing
```

- Sorting by id first, then a **stable** sort on the value, gives ties in id order for both directions. Python's `sort(reverse=True)` keeps equal items in their original order (R-LIST-7). Nulls are always appended last (R-LIST-6).
- `paginate(items, page, size) -> (slice, total, total_pages)`. `total_pages = ceil(total / size)` (0 when empty). A page past the end gives an empty slice (R-LIST-3).
- The route merges ratings into the songs **before** sorting, so `sort=rating` works like any other column (R-RATE-7).

## 7. Ratings (`ratings.py`)

```sql
CREATE TABLE IF NOT EXISTS ratings (
  song_id    TEXT PRIMARY KEY,
  stars      INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
  updated_at TEXT NOT NULL
);
```

- `RatingStore(path)`: creates the parent dir and table on init, `all() -> dict[id, stars]`, `get(id)`, `set(id, stars)`.
- `set` is an upsert: `INSERT … ON CONFLICT(song_id) DO UPDATE`.
- Each call opens a short-lived connection (`with sqlite3.connect(path) as conn`), which commits on success and rolls back on error. FastAPI runs sync routes in a thread pool, and per-call connections avoid sharing a connection across threads.
- The `CHECK` constraint backs up the API validation, so a bad value can't land in the database even through a bug.
- Ratings are never deleted. Rows for ids that aren't in the current dataset just stay there and are ignored when building responses (R-RATE-6).
- SQLite errors aren't caught, so they surface as 500 (R-RATE-5).

## 8. Models (`models.py`)

```python
class RatingIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    stars: int = Field(ge=1, le=5)     # strict: rejects "5", 4.5, 4.0, true, null (checked)

class Song(BaseModel):  # response model; mirrors songs.json + rating
    id: str; title: str | None
    danceability: float | None; energy: float | None; acousticness: float | None
    valence: float | None; tempo: float | None
    duration_ms: int | None; num_sections: int | None; num_segments: int | None; mood: int | None
    sources: list[dict[str, str]]; field_flags: dict[str, list[str]]
    flags: list[str]; possible_duplicates: list[str]
    rating: int | None

class Page(BaseModel):         items: list[Song]; page: int; size: int; total: int; total_pages: int
class SearchResult(BaseModel): query: str; match_type: Literal["exact","partial","none"]; items: list[Song]
```

I checked strict mode with pydantic 2.11.7 locally: `"5"`, `4.5`, `4.0`, `true` and `null` give `int_type`, `0` gives `greater_than_equal`, and `6` gives `less_than_equal`.

## 9. Routes (`main.py`)

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    songs = SongStore(load_songs(settings.songs_path))   # fail fast: before the app exists (R-CFG-2)
    ratings = RatingStore(settings.ratings_db)
    app = FastAPI(title="Songs API")
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "PUT"], allow_headers=["Content-Type"])
    ...
```

| Route | Parameters (FastAPI validation → 422) |
|---|---|
| `GET /songs` | `page: int = Query(1, ge=1)`, `size: int = Query(10, ge=1, le=100)`, `sort: Literal[*SORTABLE] = "id"`, `order: Literal["asc","desc"] = "asc"` |
| `GET /songs/search` | `title: str = Query(...)`, plus 422 when `search_key(title) == ""` |
| `GET /songs/{song_id}` | 404 if unknown |
| `PUT /songs/{song_id}/rating` | body `RatingIn`, 404 if unknown, then `ratings.set`, then return the song |

- `/songs/search` is registered **before** `/songs/{song_id}`, so the word "search" isn't taken as an id.
- The 422 for an empty search key is raised as `RequestValidationError` with the standard error list shape (R-ERR-1).
- Loading happens inside `create_app`, not in a lifespan hook, so a bad `songs.json` fails as soon as the app is imported or created. Tests can assert on that directly.

## 10. Testing (R-VER)

- **Fixtures:**
  - `songs_file` writes a small hand-built dataset to `tmp_path`, with nulls in `tempo`, two same-title songs, "21" / "21 Guns", "God's Plan", "11:11", "Naïve", " 4 walls"-style titles and mixed-case titles.
  - `client` builds `create_app(Settings(songs_file, tmp_path/"ratings.db", ...))`.
  - A `real_client` runs over the committed `data/normalized/songs.json`.
- **Pure tests:** `search_key` table, exact/partial/none, sort asc/desc with nulls and ties, paging edges.
- **HTTP tests:** every route, every 422/404 case in R-RATE-2 / R-LIST-2 / R-LIST-4 / R-SEARCH-5.
- **Persistence:**
  - Restart: PUT, then build a new app on the same db, then GET → rating present.
  - Rerun: PUT, then run `python -m pipeline` into the songs path, then build a new app → same rating on the same id.
  - Orphans: rate an id, rebuild with a dataset that lacks it (rating hidden), then rebuild with the original (rating back).

## 11. Dependencies

`fastapi`, `uvicorn` as runtime dependencies. `pytest` and `httpx` (which `TestClient` needs) for dev. Locally: fastapi 0.115.13, pydantic 2.11.7, httpx 0.28.1, uvicorn 0.34.3. Lower bounds go in `pyproject.toml`.
