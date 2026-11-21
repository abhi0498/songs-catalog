# Backend

## Data pipeline

Normalizes `data/songs_part1.json` and `data/songs_part2.json` into a clean
dataset. Spec: [`specs/data/`](../specs/data/) (requirements, design, tasks).

Requires Python ≥ 3.11, standard library only. Run it from this folder with the venv active (setup is in the [root README](../README.md#quick-start)):

```bash
python -m pipeline
```

Options: `--data-dir` (default `../data`), `--out-dir` (default `../data/normalized`).

It writes three files to `data/normalized/`:

| File | Contents |
|---|---|
| `songs.json` | One record per unique id, sorted by id. Rejected values are `null`. `field_flags` says why each field ended up as it did, `flags` is the union, `sources` lists the file and row each record came from. |
| `issues.json` | Every finding: id, field, source, raw value, final value, reason code, severity, detail. |
| `report.json` | Input hashes, the duration band, and counts by field, reason and severity. |

Rules in short: values are never invented or clamped, bad values become `null`
with a reason code, conflicts between files become `null` (neither file wins),
and a duration is only fixed (seconds → ms) when its `num_segments` backs it up.
The same input always gives byte-identical output, and the generated files are
committed. Rerun the command after changing the inputs or the rules.

Exit code 0 on success, 1 on a structural problem with the inputs (the message
names the file and column). Nothing is written in that case.

## API

FastAPI over `data/normalized/songs.json`, with star ratings in SQLite.
Spec: [`specs/api/`](../specs/api/). Run it from this folder:

Install with `pip install -e ".[dev]"` inside a venv (see the [root README](../README.md#quick-start)), then:

```bash
uvicorn app.main:create_app --factory --reload
```

Interactive docs are at http://127.0.0.1:8000/docs.

| Method | Path | Notes |
|---|---|---|
| GET | `/songs?page=1&size=10&sort=id&order=asc` | `page` ≥ 1, `size` 1–100. `sort` is any column, including `rating`. The whole dataset is sorted before paging, nulls go last in both directions, and ties are ordered by id. |
| GET | `/songs/search?title=…` | `{query, match_type, items}`. Exact match first (ignoring case, accents, spacing and punctuation), else partial. `items` is always a list. |
| GET | `/songs/{id}` | 404 if unknown |
| PUT | `/songs/{id}/rating` | Body `{"stars": 1..5}`, a strict JSON integer. `"5"`, `4.5`, `4.0`, `true`, `0` and `6` → 422. |

Environment variables:

| Variable | Default |
|---|---|
| `SONGS_PATH` | `../data/normalized/songs.json` |
| `RATINGS_DB` | `backend/ratings.db` (gitignored) |
| `CORS_ORIGINS` | `http://localhost:5173` (comma-separated) |

Songs are loaded once at startup, and the API won't start if `songs.json` is
missing or invalid. **After re-running the pipeline, restart the API.**
Ratings live in their own database, keyed by song id, so they survive both.
There's no endpoint to delete a rating (see [DECISIONS.md](../DECISIONS.md)).

## Tests

```bash
python -m pytest
```

Test dependencies come with `pip install -e ".[dev]"`.
