# Decisions

A running log of the decisions behind this project. Full reasoning is in the specs:
[data](specs/data/requirements.md) · [API](specs/api/requirements.md).

## Data normalization

| # | Decision | Why |
|---|---|---|
| — | Never invent values. Bad values become `null` with a reason code, with no clamping or imputing. | A visible gap is better than a believable wrong number. |
| D1 | When the two files disagree on a field, it becomes `null` with `source_conflict`. Neither file wins, and both raw values are kept in the issues log. | Nothing shows that either export is more trustworthy. |
| D2 | A possible duplicate needs the same title **and** tempo within 1% **and** duration within 2%. These are flags only, never merges. | Title alone would flag covers. Different ids are different records. |
| D3 | `mood` is an opaque 0/1 label. | Its meaning isn't documented. |
| D4 | Every duration is checked against ms-per-segment from the data. The only fix is seconds → ms, and only when the result fits. | The 3 bad values (158, 270, 356) match their segment counts as seconds. Nothing else is rescaled. |

## API

| # | Decision | Why |
|---|---|---|
| — | Songs are served from memory (loaded from `songs.json`). Ratings are stored in SQLite, keyed by song id. | Songs are 25 read-only rows owned by the pipeline. Ratings need durable writes and must survive pipeline reruns. |
| — | Ratings and single-song lookups use `id`. Title search always returns a list. | Titles aren't unique (two "Perfect"s). |
| D-API-1 | Search tries an exact match first, then falls back to partial, and returns `match_type`. | "21" shouldn't return "21 Guns", but a partial query should still find something. |
| D-API-2 | The search key drops apostrophes and turns other punctuation into spaces. | "gods plan" finds "God's Plan". "11:11" stays different from "1111". |
| D-API-3 | Ratings must be a strict JSON integer 1–5. `"5"`, `4.5`, `4.0`, `true`, `0` and `6` → 422. | No silent coercion. |
| D-API-4 | **No DELETE for ratings.** | Not in scope. A rating can be changed with PUT but not cleared. It's easy to add later (`DELETE /songs/{id}/rating` → 204). |
