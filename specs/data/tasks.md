# Data Normalization — Tasks

Status: **Draft, awaiting approval**
Implements: [design.md](design.md) (approved) and [requirements.md](requirements.md) v3.

How to work: do the tasks in order. Each one is test-first: write the listed tests, see them fail, implement, see them pass. A task is done when its checks pass and `pytest` is green. Each task becomes one commit. Environment: Python ≥ 3.11 (local is 3.12; `StrEnum` needs 3.11), pytest is the only dev dependency, and everything runs from `backend/`.

---

### T1 — Scaffold
- Create `backend/pipeline/` (empty modules from design §2), `backend/tests/pipeline/`, and `backend/pyproject.toml` (project metadata, `requires-python = ">=3.11"`, pytest config with `testpaths`), plus a `.gitignore` entry for `__pycache__/` and `.pytest_cache/`.
- **Done when:** `cd backend && python -m pytest` runs and collects 0 tests without errors.
- Traces: design §2.

### T2 — Schema
- `schema.py`: `FieldSpec`, the `FIELDS` table (design §3), the `Reason` StrEnum with all 16 codes, the `SEVERITY` map, the constants (`DUP_TEMPO_TOL`, `DUP_DURATION_TOL`, `BAND_FACTOR`, `SECONDS_THRESHOLD`), the `ABSENT` sentinel, and the core dataclasses (`Source`, `Issue`, `Cleaned`, `SourceRow`).
- **Tests:** every `Reason` has a severity. The field list and order match the requirements. `valence` is part2-only. Domain checks accept the edges (0, 1) and reject just outside them. `mood` accepts only {0, 1}.
- Traces: requirements §3 range table, §4, R-MOOD-1.

### T3 — Value cleaning
- `clean.py`: `classify_missing`, `normalize_text`, `to_number`, `to_int`, `check_range`, and a `clean_field(spec, raw, source, id) -> Cleaned` that chains them (design §5.2). `duration_ms` skips `check_range`.
- **Tests (tables):**
  - missing: `ABSENT`→`missing_absent`, `None`→`missing_null`, `"N/A"` / `" n/a "`→`missing_na`, `""` / `"  "`→`missing_empty`
  - numbers: `"0.521"`→0.521 + `coerced_from_string`; `"abc"`→`unparseable`; `"nan"`, `"-Infinity"`, `float("nan")`→`unparseable`; `True`→`unparseable`
  - ints: `8.0`→8; `8.5`→`not_integer`
  - ranges: `1.42`, `-0.05`, tempo `0`→`out_of_range` with the raw value kept and **no clamping**
  - text: `" 4 walls  "`→`"4 walls"` + `whitespace_normalized`; `"Naïve"` keeps its diacritic, and NFD input comes out NFC; `"   "`→`missing_empty`
- Traces: R-MISS-1, R-TYPE-1..4, R-RNG-1..2, R-TXT-1..3, P1, P2.

### T4 — Loading
- `load.py`: `load_file(path) -> list[SourceRow]` with `parse_constant` rejection, structure checks that raise `PipelineError`, `ABSENT` for missing keys, skipping missing or blank ids with a `missing_id` issue, and per-field cleaning through T3.
- **Tests** (using `tmp_path` fixture files): an unknown column, a row index not in `id`, a non-object column, and a non-object top level each raise `PipelineError` naming the file and column. A missing key → `missing_absent`. A blank id → skipped + `missing_id`. Real part1 → 16 rows, real part2 → 13 rows, and part1 row 2 `energy` is `ABSENT`.
- Traces: R-ING-1..4, R-ID-1.

### T5 — Duration band & check
- `duration.py`: `compute_band(rows) -> Band` (unique `(id, duration_ms, num_segments)` observations, median, ÷2 / ×2) and `check_duration(dur, segs, band) -> Cleaned`.
- **Tests:**
  - band on the real rows: n = 22, median ≈ 272.8, band ≈ 136.4–545.6. Identical rows in both files are counted once. No observations → `PipelineError`.
  - in band → kept, no issue.
  - value < 1000 that fits as seconds → ×1000 + `unit_corrected_s_to_ms`, with detail holding the ratio, band and median.
  - value < 1000 that doesn't fit as seconds → `implausible_duration`.
  - value ≥ 1000 outside the band (e.g. minutes-like `4` or a huge value) → `implausible_duration`, never rescaled.
  - `num_segments` null and value ≥ 1000 → kept + `duration_unverified`. `num_segments` null and value < 1000 → `implausible_duration`.
  - real data: Sunflower 158→158000, Uptown Funk 270→270000, Sweet Child 356→356000. No other row changes.
- Traces: R-DUR-1..5, D4, P3.

### T6 — Merge by id
- `merge.py`: `merge_by_id(rows) -> list[Record]`. Sources sorted by `(file, int(row))`. Field resolution follows the design §5.4 table. `not_in_source` is kept only when the final value is null.
- **Tests:** one case per table row: equal, one-sided, both null, conflict. The conflict detail lists both values and sources, and **no file wins**. `"0.521"` vs `0.521` → equal. A title conflict → null. Running the merge with the inputs reversed gives the same result. Real data: 25 records, 4 merged, "Never Gonna Give You Up" danceability null + `source_conflict` (0.727 / 0.74), merged records take valence from part2 with no `not_in_source`, and the 12 part1-only records have valence null + `not_in_source`.
- Traces: R-ID-2..6, R-MISS-2..3, D1, P5.

### T7 — Possible duplicates
- `duplicates.py`: `find_possible_duplicates(records)` groups by casefolded title, compares pairs on relative tempo/duration difference, and links both records, adding one issue per record with `field_diffs`.
- **Tests:** the real Perfect pair (`0tgVpD…` and `7dNsHh…`) is flagged both ways, with a duration diff of about 0.23%. Same title with tempo 2% apart → not flagged. Same title with a null tempo → not flagged. Titles that differ only in case → compared. Three records with one title → each matching pair is linked.
- Traces: R-DUP-1..2, D2, R-ID-6.

### T8 — Output files & CLI
- `output.py`: build records (field order from the schema, `field_flags`, `flags`, `possible_duplicates`, `sources`), sort issues, and build the report (input sha256, row counts, band, all the counts in R-OUT-4). Plain writes with `indent=2`, `ensure_ascii=False` and a trailing newline. No timestamps.
- `__main__.py`: `--data-dir` (default `../data`) and `--out-dir` (default `../data/normalized`), creating the out dir if needed. Exit 0 with a short summary, or exit 1 with the `PipelineError` message on stderr.
- **Tests:** record keys are in schema order. `field_flags` only lists reasons for the final state (a one-sided missing value that got filled in doesn't appear). `flags` is the sorted union. The report counts match the issues. The CLI exits 1 on a broken fixture and leaves the out dir empty.
- Traces: R-OUT-1..5, design §5.6, §6.

### T9 — End-to-end acceptance & determinism
- `test_end_to_end.py`: run the CLI on the real files into `tmp_path` and check every line of requirements §5:
  - 25 records, 4 merged
  - nulls: danceability (21 Guns `out_of_range`, Never Gonna Give You Up `source_conflict`), energy (11:11 `missing_absent`, Yesterday `missing_na`), acousticness (Bohemian Rhapsody `missing_null`, Another Brick `out_of_range`), tempo (Blinding Lights `out_of_range`), valence ×12 `not_in_source`
  - 3 duration corrections, 0 `implausible_duration`
  - "3AM" danceability 0.521 and tempo 108.73 coerced. Title "4 walls".
  - 1 Perfect duplicate pair
  - the raw files are unchanged (sha256 before and after)
- Determinism: two runs give byte-identical output, and passing the input files in the other order changes nothing.
- Traces: R-VER-1..3, P5, requirements §5.

### T10 — Generate & check in outputs
- Run `python -m pipeline` and commit `data/normalized/{songs,issues,report}.json`, so the backend and reviewers can use them without running the pipeline. Add a short "how to run" section to `backend/README.md`.
- **Done when:** the committed outputs match what a fresh run produces (T9 already proves runs are byte-identical).
- Traces: R-OUT-5, design §7.

---

## Not in these tasks
- How the API serves the data, ratings, and the dashboard: separate backend and frontend specs.
- The write-up: it will use `report.json` and the decisions D1–D4, but it's its own deliverable.
- The `buggy_api.py` review: its own deliverable.
