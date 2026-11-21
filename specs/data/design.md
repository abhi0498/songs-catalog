# Data Normalization — Design

Status: **Approved.** Revised: plain file writes instead of atomic writes, and conflict handling spelled out.
Implements: [requirements.md](requirements.md) v2 (R-* and D1–D4 refer to it).

## 1. Overview

A small Python package, run as a command, that reads the two raw files and writes three JSON files: the clean records, the issues log, and a summary report. It uses only the standard library, keeps all decisions in one place, and is built from pure functions so each rule can be tested on its own.

```
data/songs_part1.json ─┐
data/songs_part2.json ─┤
                       ▼
 1 load        → SourceRow per (file, row)               R-ING
 2 clean       → each field: value + issues              R-MISS, R-TYPE, R-RNG, R-TXT, R-MOOD
 3 durations   → band from all rows, then check each     R-DUR   (needs a whole-dataset pass)
 4 merge       → one record per id                       R-ID, D1
 5 duplicates  → link look-alike records                 R-DUP, D2
 6 assemble    → records + issues + report               R-OUT
                       ▼
data/normalized/songs.json · issues.json · report.json
```

Stages 2–3 run on each source row **before** merging. That way a duration stored in seconds in one file and ms in the other agrees after the fix instead of counting as a conflict, and every issue carries the exact file and row it came from (P4).

## 2. Code layout

```
backend/
  pipeline/
    __init__.py
    schema.py       # field specs, reason codes + severity, constants (tolerances)
    load.py         # read column-oriented JSON → SourceRow; structural checks
    clean.py        # pure per-value functions
    duration.py     # compute_band(), check_duration()
    merge.py        # merge_by_id()
    duplicates.py   # find_possible_duplicates()
    output.py       # build records, issues, report; deterministic writing
    __main__.py     # CLI: python -m pipeline [--data-dir] [--out-dir]
  tests/pipeline/
    test_clean.py  test_duration.py  test_merge.py  test_duplicates.py
    test_load.py   test_end_to_end.py   # real files vs §5 acceptance snapshot
```

It lives under `backend/` so the API can import `schema.py` (field names, reason codes) instead of copying them. The command runs from `backend/`.

## 3. Schema (`schema.py`)

The rules for each field are data, not branches spread across the code:

```python
@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: Literal["str", "float", "int"]
    check: Callable[[float], bool] | None   # domain test, None = no check
    sources: frozenset[str]                 # files expected to have it
```

| name | kind | check | sources |
|---|---|---|---|
| title | str | — | both |
| danceability, energy, acousticness | float | `0 <= x <= 1` | both |
| valence | float | `0 <= x <= 1` | part2 |
| tempo | float | `x > 0` | both |
| duration_ms | int | `x > 0` (plus R-DUR) | both |
| num_sections, num_segments | int | `x >= 1` | both |
| mood | int | `x in {0, 1}` | both |

`Reason` is a `StrEnum` of the codes in requirements §4, with a `SEVERITY` lookup table. Tunable values are named constants: `DUP_TEMPO_TOL = 0.01`, `DUP_DURATION_TOL = 0.02`, `BAND_FACTOR = 2`, `SECONDS_THRESHOLD = 1000`.

## 4. Core types

```python
@dataclass(frozen=True)
class Source:      file: str; row: str            # e.g. ("songs_part1.json", "12")

@dataclass(frozen=True)
class Issue:       id: str; field: str; source: Source | None
                   raw_value: Any; final_value: Any; reason: Reason; detail: dict | None

@dataclass(frozen=True)
class Cleaned:     value: Any | None; issues: tuple[Issue, ...]   # value None ⇒ ≥1 nulling issue

@dataclass
class SourceRow:   source: Source; raw: dict[str, Any | ABSENT]; clean: dict[str, Cleaned]
```

`ABSENT` is a sentinel separate from `None`, so "key missing" and "JSON null" stay two different cases through the whole pipeline (R-MISS-1).

## 5. Stages

### 5.1 Load (`load.py`)
- Parse with `json.load(..., parse_constant=_reject)` so the non-standard `NaN` / `Infinity` literals go down the `unparseable` path instead of becoming floats.
- Check the structure (R-ING-4), stopping with `PipelineError` on the first problem: the top level must be an object, every column an object, every column name known for that file (`FieldSpec.sources`), and every row index in any column must also be in `id`.
- Rows come from the `id` column's indexes. Columns without that index give `ABSENT`.
- Missing or blank `id` → the row is skipped and a `missing_id` issue is logged (R-ID-1).

### 5.2 Clean (`clean.py`)
One pure function per concern, chained for each field kind:

```
classify_missing(raw)      → ABSENT / None / "N/A" / "" / whitespace  →  null + missing_*
    ↓ (if present)
str fields:   normalize_text  → NFC, strip, collapse \s+   (whitespace_normalized if changed)
              empty after     → missing_empty
num fields:   to_number       → bool → unparseable; int/float as-is;
                                str → float(s.strip()) else unparseable (coerced_from_string if ok);
                                reject nan/inf (float("nan") parses!) → unparseable
int fields:   to_int          → integral float → int; else not_integer
    ↓
check_range(spec)          → out_of_range (raw value logged, never clamped)
```

`duration_ms` skips `check_range` here. Stage 3 handles its domain.

### 5.3 Durations (`duration.py`)
- `compute_band(rows)`: collect `duration_ms / num_segments` over **unique `(id, duration_ms, num_segments)` observations** where both cleaned values are present and `duration_ms >= 1000`. Counting unique observations stops rows that are identical in both files from being counted twice. Return `Band(median, low=median/2, high=median*2, n)`. If there are no observations, raise `PipelineError`, since nothing can be checked without a reference.
- `check_duration(cleaned_dur, cleaned_segments, band)` follows R-DUR-2/3 exactly. The `detail` it logs is `{"ms_per_segment": …, "band": [low, high], "median": …}`.
- On current data: 22 observations, 208–342 ms/segment, median 272.8, band 136.4–545.6. The three seconds values come out at about 282, 267 and 239, and pass. These match requirements R-DUR-5.

### 5.4 Merge (`merge.py`)
Group cleaned rows by `id`. Within a group, sort sources by `(file, int(row))` so the order the inputs are given in can't change `sources` or conflict details (P5). For each field (D1):

| part1 | part2 | result |
|---|---|---|
| value a | value b, a == b | a |
| value | null / absent | that value. The other side's missing issue stays in the log, but is not on the record |
| null | null | null, with both sides' issues |
| a | b, a ≠ b | null + `source_conflict`, detail `{"values": [{source, value}, …]}` |

- **No file wins a conflict.** That's why input order can't change the result: there's no "first" or "preferred" source to pick, and a disagreement always becomes null.
- Equality is exact, after parsing: `"0.521" == 0.521` counts as equal, `0.727 != 0.74`. There's no tolerance, because "close enough" would be choosing one value.
- `not_in_source` is only logged when the final value is null. Part1's missing `valence` on a merged record is expected, not a finding.
- Conflicts on `title` follow the same rule.

### 5.5 Duplicates (`duplicates.py`)
Group records by `casefold(title)`, then check every pair in a group against D2 using the relative difference `|a−b| / max(a,b)`. Either value null → no flag. A match adds the other id to `possible_duplicates` on both records, plus one `possible_duplicate` issue per record with detail `{"other_id", "tempo_diff_pct", "duration_diff_pct", "field_diffs": {...}}` (R-DUP-2).

### 5.6 Assemble & write (`output.py`)
Writes three files to `data/normalized/`:

**songs.json**: a list sorted by `id`:
```json
{
  "id": "4uLU6hMCjMI75M1A2tKUQC",
  "title": "Never Gonna Give You Up",
  "danceability": null, "energy": 0.91, "acousticness": 0.152, "valence": 0.44,
  "tempo": 113.319, "duration_ms": 213573, "num_sections": 8, "num_segments": 812, "mood": 1,
  "sources": [{"file": "songs_part1.json", "row": "13"}, {"file": "songs_part2.json", "row": "1"}],
  "field_flags": {"danceability": ["source_conflict"]},
  "flags": ["source_conflict"],
  "possible_duplicates": []
}
```
`field_flags` holds only the reasons that explain the field's **final** state, so the UI can badge cells. `flags` is their sorted union plus record-level reasons (`possible_duplicate`), for filtering (R-OUT-3).

**issues.json**: every `Issue`, info entries included, sorted by `(id, field, source.file, source.row, reason)` (R-OUT-2).

**report.json**: counts (R-OUT-4) plus provenance: `{"inputs": [{"file", "sha256", "rows"}], "band": {...}, "records": 25, "merged": 4, "nulls_by_field_and_reason": {...}, "corrections": 3, "conflicts": 1, "possible_duplicate_pairs": 1, "by_reason": {...}}`. There is **no timestamp**, so output is byte-identical on every run (P5).

How files are written: `json.dumps(..., indent=2, ensure_ascii=False, sort_keys=False)` with key order fixed by the schema and a trailing newline. Each file is written directly with a plain write; there's no temp-file step. Every `PipelineError` is raised before the write stage, so a run that fails on bad input writes nothing. If writing itself fails partway, rerunning the command fixes it.

## 6. CLI & errors
```
cd backend && python -m pipeline --data-dir ../data --out-dir ../data/normalized
```
- Exit 0 on success, and print a one-screen summary taken from the report.
- Exit 1 on `PipelineError` (bad structure, no band). The message names the file and column. These errors happen before anything is written.
- Data problems are **never** errors. They become issues (P2).

## 7. Interface to the backend
- The contract is `songs.json` as specified in §5.6, with field names and reason codes imported from `pipeline.schema`.
- The backend spec decides how it's served (in-memory vs SQLite) and where ratings live. The pipeline doesn't know about the API.
- The API should treat `null` as "unknown" everywhere: sorting puts nulls last, and aggregates skip them and report how many.

## 8. Testing strategy (R-VER)
- **Unit tests, per function**: each `clean.py` function gets a table of tests (all four missing forms, `"0.521"`, `"nan"`, `True`, `8.0`, `8.5`, the edges 0 and 1, `1.42`, `-0.05`). `check_duration` gets every branch, including null segments with values above and below 1000. Merge gets every row of the §5.4 table. Duplicates get a same-title-different-tempo case that must not be flagged.
- **Structure**: unknown column, row index not in `id`, non-object column → `PipelineError`.
- **End to end**: run on the real files and check the requirements §5 snapshot exactly (25 records, each named null and reason, 3 corrections with their values, 1 Perfect pair).
- **Determinism**: run twice, and with the input order swapped. Output bytes must be identical.

## 9. Changes this design asked of requirements (applied in requirements v3)
1. **R-DUR-1**: compute the band from *unique (id, duration_ms, num_segments) observations*, so rows that are the same in both files aren't double-counted.
2. **R-DUR-5**: update the expected numbers to 22 observations, median ≈ 272.8, band ≈ 136–546. The outcome doesn't change: 3 corrections and 0 nulls.
3. **R-ING-1 / NaN**: say explicitly that `NaN` / `Infinity` and the strings `"nan"` / `"inf"` are `unparseable`.

## 10. Alternatives considered
- **pandas**: it makes it easy to lose the difference between absent, null and NaN, and it converts types quietly (an int column with a null becomes float). Explicit per-value code is clearer for these rules, and with 29 rows performance doesn't matter.
- **Pydantic for cleaning**: good at validating and rejecting, but awkward for "keep going, null this field, record a reason". It's fine at the API boundary, not here.
- **Merge before cleaning**: simpler, but issues would lose their source row, and a seconds value in one file would show up as a false conflict.
