# Data Normalization — Requirements

Status: **Approved (v3).** Includes the design-review changes to R-TYPE-2, R-DUR-1 and R-DUR-5.
Scope: turning `data/songs_part1.json` and `data/songs_part2.json` into one clean, auditable song dataset that the backend and dashboard read from.
Out of scope here: storage technology, API shape, UI. Those belong to the design and later specs.

## 1. Guiding principles

- **P1. Never invent values.** The pipeline does not impute, average, interpolate, or clamp. A value in the output either came from a source file or is `null`.
- **P2. Bad values become `null` with a reason.** Any value that is rejected is replaced with `null` and gets a machine-readable reason code (see §4). Nothing is dropped silently.
- **P3. Corrections need evidence.** A source value is changed (not nulled) only when the data itself shows what the correct value is. Today that only applies to the unit fix for durations (R-DUR).
- **P4. Everything is traceable.** For every output field you can tell which file and row it came from, what the raw value was, and why it was changed or nulled.
- **P5. Deterministic.** The same inputs always give byte-identical output. Order of files and rows does not change the result.

## 2. Source facts (from profiling)

| | part1 | part2 |
|---|---|---|
| Rows | 16 | 13 |
| Columns | id, title, danceability, energy, mood, acousticness, tempo, duration_ms, num_sections, num_segments | same, plus `valence` |
| Layout | column-oriented: `{column: {row_index: value}}` | same |

- Row indexes start at `"0"` in both files, so they are not keys. `id` is the only identity.
- 29 source rows, 4 ids in both files (`2takcw…`, `4uLU6h…`, `6DCZcS…`, `7qiZfU…`), so **25 unique ids** expected.

## 3. Requirements

### Ingestion

- **R-ING-1.** The pipeline reads both files in their column-oriented layout and rebuilds rows by row index within each file.
- **R-ING-2.** A key missing from a column for a given row is treated as "absent" (e.g. part1 row 2 has no `energy`). This is a missing value, not an error in the file.
- **R-ING-3.** Each source row keeps its provenance: file name and row index.
- **R-ING-4.** If the files have a structure the pipeline does not expect (a row index in some columns but not in `id`, an unknown column, a non-object column), the pipeline fails loudly with a clear message instead of guessing.

### Identity and merging

- **R-ID-1.** `id` is the primary key. A row with a missing or empty `id` is not loaded and is listed in the report.
- **R-ID-2.** Rows with the same `id` in both files are merged into one record.
- **R-ID-3.** When both sources have a value for a field and the values agree after parsing, that value is used.
- **R-ID-4.** When only one source has a usable value for a field, that value is used.
- **R-ID-5.** When both sources have usable values that **disagree** (e.g. `4uLU6h…` "Never Gonna Give You Up" danceability 0.727 vs 0.74), the field is set to `null` with reason `source_conflict`, and both raw values plus their sources go in the issues log. Neither file is treated as more authoritative (decision D1).
- **R-ID-6.** Rows with different ids are never merged, even if they look alike.

### Near-duplicates

- **R-DUP-1.** Two records with different ids are flagged `possible_duplicate`, with links to each other, only when **all** of these hold (decision D2):
  1. their normalized titles are equal (R-TXT, compared case-insensitively),
  2. both tempos are non-null and within 1% of each other,
  3. both durations are non-null and within 2% of each other (after R-DUR).

  Both records are kept, and no values are changed. Sharing a title alone (e.g. a cover) is not enough.
  - Known case: "Perfect" `0tgVpD…` and `7dNsHh…` (both in part2; tempo 95.05 for both, duration 263400/264000, a 0.23% gap).
- **R-DUP-2.** The flag carries the per-field differences so a reviewer can judge it without opening the raw files.

### Missing values

- **R-MISS-1.** The following all mean "missing" and become `null`:
  - absent key → reason `missing_absent`
  - JSON `null` → reason `missing_null`
  - the string `"N/A"` (case-insensitive, trimmed) → reason `missing_na`
  - empty or whitespace-only string → reason `missing_empty`
- **R-MISS-2.** `valence` exists only in part2. For records that only come from part1 it is `null` with reason `not_in_source`. That is kept separate from "source had it but it was blank" so the dashboard can tell the two apart.
- **R-MISS-3.** Records that are in both files take `valence` from part2 (R-ID-4).

### Types

- **R-TYPE-1.** Numbers stored as strings (e.g. `"0.521"`, `"108.73"`) are parsed into numbers. That counts as a type fix, not a value change, and is logged as `coerced_from_string` (info level).
- **R-TYPE-2.** A string that is not a valid number (and not a missing-value marker) becomes `null` with reason `unparseable`. That includes `"nan"`, `"inf"`, `"infinity"` (any case, with or without a sign) and the non-standard JSON literals `NaN` / `Infinity`, even though Python's `float()` would accept them.
- **R-TYPE-3.** Integer fields (`duration_ms`, `num_sections`, `num_segments`, `mood`) accept integral floats (e.g. `8.0`). Non-integral values become `null` with reason `not_integer`.
- **R-TYPE-4.** Booleans are never treated as numbers (`true` is not 1).

### Ranges and validity

No clamping. A value outside its valid domain becomes `null` with reason `out_of_range`, and the raw value is logged.

| Field | Type | Valid domain | Known violations |
|---|---|---|---|
| danceability | float | 0 ≤ x ≤ 1 | 1.42 (`64yrDB…` "21 Guns") |
| energy | float | 0 ≤ x ≤ 1 | — |
| acousticness | float | 0 ≤ x ≤ 1 | -0.05 (`3JvKfv…` "Another Brick") |
| valence | float | 0 ≤ x ≤ 1 | — |
| tempo | float (BPM) | x > 0 | 0 (`0VjIjW…` "Blinding Lights") |
| duration_ms | int | x > 0, after R-DUR | see R-DUR |
| num_sections | int | x ≥ 1 | — |
| num_segments | int | x ≥ 1 | — |
| mood | int | {0, 1} | — (meaning unknown, see R-MOOD-1) |

- **R-RNG-1.** Range checks run after type parsing and after the duration unit fix.
- **R-RNG-2.** `tempo = 0` is invalid (reason `out_of_range`). It is not read as "unknown" or "silence".
- **R-MOOD-1.** `mood` is treated as an opaque binary category (decision D3). The pipeline checks it is 0 or 1 and gives it no meaning. Downstream it is shown as "mood 0" / "mood 1", and the write-up says the meaning is unknown.

### Durations

Every duration is checked for plausibility, not only suspicious ones (decision D4).

- **R-DUR-1. Reference band.** Compute `ms_per_segment = duration_ms / num_segments` over unique `(id, duration_ms, num_segments)` observations with `duration_ms ≥ 1000` and a valid `num_segments`, so rows that are identical in both files are counted once. The reference is the **median** of those values, and the plausible band is **[median ÷ 2, median × 2]**. The band comes from the data, not a hard-coded number. Using a median with a wide factor means a few bad rows can't move the band much.
- **R-DUR-2. Check every row.** For each duration with a valid `num_segments`:
  1. If `duration_ms / num_segments` is inside the band, keep it.
  2. Else, if the raw value is below 1000 and `(value × 1000) / num_segments` is inside the band, treat it as seconds: multiply by 1000 and flag `unit_corrected_s_to_ms`. The log records the raw value, the computed ms/segment and the band.
  3. Else set it to `null` with reason `implausible_duration`, and log the computed ratio and band.
- **R-DUR-3. No evidence, no fix.** If `num_segments` is null or invalid, the duration can't be checked. A raw value ≥ 1000 is kept but flagged `duration_unverified` (info). A raw value < 1000 becomes `null` with `implausible_duration`, because it can't be a song length in ms and we have no evidence to correct it.
- **R-DUR-4. Only seconds get corrected.** Seconds → ms is the only unit fix. Any other mismatch (e.g. minutes) becomes null and is never rescaled.
- **R-DUR-5. Expected outcome on current data.** Clean rows: 22 unique observations, 208–342 ms/segment, median ≈ 272.8, band ≈ 136–546. All of them pass. `3KkXRk…` Sunflower 158 → 158000 (≈282), `4VqPOr…` Uptown Funk 270 → 270000 (≈267), `2QjOHC…` Sweet Child O Mine 356 → 356000 (≈239). No row becomes `implausible_duration`.

### Text

- **R-TXT-1.** `title` is trimmed at both ends and internal runs of whitespace are collapsed to one space (`" 4 walls  "` → `"4 walls"`). Logged as `whitespace_normalized` (info).
- **R-TXT-2.** Case, punctuation and diacritics are kept as-is (`Naïve`, `Café del Mar`, `God's Plan`). Text is NFC-normalized so equal titles compare equal.
- **R-TXT-3.** A title that is empty after trimming becomes `null` with reason `missing_empty`.

### Outputs

- **R-OUT-1. Clean dataset**: one record per unique id with every canonical field (missing ones as `null`). Sorted by id.
- **R-OUT-2. Issues log**: one entry per finding with `id`, `field`, `source` (file + row), `raw_value`, `final_value`, `reason`, `severity` (`info` | `warning` | `error`), and optional `detail`.
- **R-OUT-3. Per-record flags**: each record exposes the list of reason codes on it, so the API and dashboard can filter and badge "has data issues" without joining the log.
- **R-OUT-4. Summary report**: counts of rows read, unique ids, merged ids, nulls by field and reason, corrections, conflicts, and possible duplicates. This feeds the write-up.
- **R-OUT-5.** Raw source files are never modified.

### Verification

- **R-VER-1.** Every known problem in §2 and §3 has an automated test that checks its exact expected outcome.
- **R-VER-2.** Tests cover the rules on synthetic edge cases as well as the real files (e.g. a duration < 1000 with null `num_segments` → null, not corrected).
- **R-VER-3.** A rerun gives identical output (P5).

## 4. Reason codes

| Code | Severity | Meaning |
|---|---|---|
| `missing_absent` | warning | Key not present in source |
| `missing_null` | warning | Source value was JSON null |
| `missing_na` | warning | Source value was "N/A" |
| `missing_empty` | warning | Empty/whitespace string |
| `not_in_source` | info | Field doesn't exist in that source file |
| `coerced_from_string` | info | Numeric string parsed to number |
| `whitespace_normalized` | info | Title whitespace cleaned |
| `unparseable` | warning | Non-numeric string in numeric field |
| `not_integer` | warning | Non-integral value in integer field |
| `out_of_range` | warning | Outside valid domain, nulled (not clamped) |
| `implausible_duration` | warning | Looks like a unit error but no evidence to fix it |
| `unit_corrected_s_to_ms` | warning | Duration converted with evidence |
| `duration_unverified` | info | Duration kept but couldn't be checked (no num_segments) |
| `source_conflict` | warning | Sources disagree, nulled |
| `possible_duplicate` | info | Same title as another id |
| `missing_id` | error | Row not loaded |

## 5. Expected result on current data (acceptance snapshot)

- 25 records. 4 merged from both files.
- Nulled: `danceability` ×2 (21 Guns out_of_range; Never Gonna Give You Up source_conflict), `energy` ×2 (11:11 absent, Yesterday N/A), `acousticness` ×2 (Bohemian Rhapsody null, Another Brick out_of_range), `tempo` ×1 (Blinding Lights out_of_range), `valence` ×12 (part1-only, not_in_source).
- Corrected: 3 durations (R-DUR-4). Coerced: "3AM" danceability and tempo strings. Trimmed: "4 walls".
- Flagged: 1 possible-duplicate pair (Perfect). 0 durations nulled.

## 6. Decisions

| # | Topic | Decision | Why |
|---|---|---|---|
| D1 | Cross-file conflicts | Null + `source_conflict`, keep both raw values in the log | Nothing shows either file is more trustworthy, and picking one would be inventing that. |
| D2 | Possible duplicates | Same title **and** tempo within 1% **and** duration within 2%. Flag only, never merge | Title alone would flag covers. The features show it's the same recording. |
| D3 | `mood` | Opaque binary {0, 1} with a neutral label | Its meaning isn't documented, so we don't make one up. |
| D4 | Duration checks | Check every duration against a ms/segment band from the data. Only seconds → ms gets corrected | Catches any unit error, while only fixing the one kind we have evidence for. |
