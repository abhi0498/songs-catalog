# Main build session (spec-driven)

Raw export of the Claude Code session that built the pipeline, API and dashboard. My prompts and my answers to its questions are verbatim; the assistant's replies are its text output (tool calls and file contents omitted). Timestamps are UTC.

---

## Prompt 1 (2026-11-21 02:17 UTC)

```
I'm doing a take-home: normalize two messy song JSON exports, build a FastAPI
backend and React dashboard over the result, review an AI-written API, and write
up decisions. I want to work spec-driven: requirements → design → tasks →
implement, and I approve each step before moving on.

I've already profiled the data. Problems I found:
- Both files index rows from "0", so id is the only real key
- 4 ids appear in both files; one disagrees (danceability 0.727 vs 0.74)
- Two "Perfect" rows with different ids and near-identical values
- Missing values three ways: absent key, null, "N/A"
- Numbers stored as strings ("0.521")
- Out of range: danceability 1.42, acousticness -0.05, tempo 0
- 3 duration_ms values are actually seconds (158, 270, 356)
- valence only exists in part2
- Title " 4 walls  " has stray whitespace

Rules I want: never invent values. Bad values become null with a reason flag,
no clamping. Durations get fixed only with evidence.

Start by drafting specs/data/requirements.md from this. Don't write code yet.
```

**Assistant:**

I've drafted the requirements in [specs/data/requirements.md](specs/data/requirements.md). I checked the files first and your findings hold: 29 source rows and 4 shared ids, so 25 unique songs.

**What's in it**
- **Principles:** never invent values, no clamping, a value is changed only with evidence, every change can be traced back to its source, and reruns give the same output.
- **Requirements:** each has a number (R-ING, R-ID, R-DUP, R-MISS, R-TYPE, R-RNG, R-DUR, R-TXT, R-OUT, R-VER), with a table of valid ranges per field and a fixed list of reason codes.
- **Expected result on the real data:** which fields get nulled and why, the 3 durations that get fixed, and the Perfect pair that gets flagged. Tests can check against this directly.

**Decisions I made that you should check**
- **Duration fix:** a value below 1000 is multiplied by 1000 only if the result fits the song's own `num_segments`. Clean rows run about 227–331 ms per segment; Sunflower, Uptown Funk and Sweet Child come out at about 282, 267 and 239. If the check fails or can't be run, the value becomes null and isn't fixed.
- **`valence` from part1:** it gets its own reason code, `not_in_source`, so the dashboard can tell "never exported" apart from "exported but blank".
- **Perfect pair:** both rows are kept and flagged as possible duplicates of each other. Rows with different ids are never merged.

**Open questions (§6)**
1. **Conflicts (danceability 0.727 vs 0.74):** I recommend setting it to null with a `source_conflict` reason and keeping both raw values in the issues log. The other option is to prefer one file, which only makes sense if one is known to be more reliable.
2. **Duplicate check:** title alone, or also require close numbers? Title alone could flag covers that are different songs.
3. **`mood`:** every value is 0 or 1, but I don't know what it means. Do you?
4. **Duration check:** run it only on values below 1000, or on every duration?

---

## Prompt 2 (2026-11-21 05:06 UTC)

```
Discuss questions
```

**Assistant asked:**

- "Never Gonna Give You Up" has danceability 0.727 in part1 and 0.74 in part2. When the two files disagree on a field, what should the merged record hold? Options: Null + flag (Recommended); Prefer part2, flag; Prefer part1, flag
- Two "Perfect" rows have different ids and nearly the same numbers. What should count as a possible duplicate? Options: Title + close features (Recommended); Title only
- Every mood value is 0 or 1, and there's nothing that says what it means. How should we handle it? Options: Binary, neutral label (Recommended); I know the meaning
- Which durations should get the plausibility check against num_segments? Options: Check every duration (Recommended); Only values under 1000

**My answers to the assistant's questions:**

```
Your questions have been answered: ""Never Gonna Give You Up" has danceability 0.727 in part1 and 0.74 in part2. When the two files disagree on a field, what should the merged record hold?"="Null + flag (Recommended)", "Two "Perfect" rows have different ids and nearly the same numbers. What should count as a possible duplicate?"="Title + close features (Recommended)", "Every mood value is 0 or 1, and there's nothing that says what it means. How should we handle it?"="Binary, neutral label (Recommended)", "Which durations should get the plausibility check against num_segments?"="Check every duration (Recommended)". You can now continue with these answers in mind.
```

**Assistant:**

I've added your four decisions to [specs/data/requirements.md](specs/data/requirements.md). The open-questions section is now a "Decisions" table (D1–D4) that gives the reason for each one.

1. **Conflicts:** when the two files disagree, the field becomes null with a `source_conflict` reason, and both raw values go in the issues log. Neither file is treated as more reliable.
2. **Duplicates:** two songs are flagged only if the title matches, tempo is within 1% and duration is within 2%. Perfect passes: same tempo, durations 0.23% apart. Covers that only share a title won't be flagged. Nothing is ever merged.
3. **Mood:** treated as a plain 0 or 1 with no meaning attached. The UI shows it as "mood 0" / "mood 1", and the write-up will say what it means is unknown.
4. **Durations:** every duration is now checked, not only values under 1000. The check compares milliseconds per segment against a range taken from the data: half to double the median. Values under 1000 that fit when read as seconds get multiplied by 1000. Anything else that doesn't fit becomes null.

I ran the duration check on the real files before writing it down:
- **Clean rows:** 208–342 ms per segment, median about 276, so the allowed range is about 138–553. Every clean row passes.
- **Fixed as seconds:** Sunflower, Uptown Funk and Sweet Child come out at about 282, 267 and 239 once multiplied by 1000.
- **Nulled:** no duration becomes null.

Checking every duration meant adding one case: a song with no `num_segments` can't be checked. Its duration is kept if it's 1000 or more and flagged `duration_unverified`. Below 1000 it becomes null.

I also fixed a mistake from the first draft, which gave the clean-row range as 227–331.

---

## Prompt 3 (2026-11-21 05:14 UTC)

```
Approve, draft design
```

**Assistant:**

I've drafted the design in [specs/data/design.md](specs/data/design.md). It's a small Python package in `backend/pipeline/`, using only the standard library, that reads both raw files and writes three outputs to `data/normalized/`: the clean songs, the issues log, and a summary report.

**How it works**
- **Six stages:** load, clean, durations, merge, duplicates, write. Each file is cleaned row by row before merging. That way every issue keeps its exact file and row, and a duration in seconds in one file and ms in the other won't show up as a false conflict.
- **Field rules in one place:** each field's type and valid range sit in one table in `schema.py`. The API imports field names and reason codes from there instead of copying them.
- **Absent vs null:** a missing key and a JSON `null` stay separate cases all the way through.
- **Same output every run:** there's no timestamp, the sort order is fixed, and files are written to a temp folder then moved in. Changing the order of the input files doesn't change the output, and a failed run leaves the previous output alone.
- **Song records:** each one carries its source rows, the reasons behind each field's final value (so the UI can mark individual cells), a combined flag list for filtering, and links to possible duplicates.

**Changes to the requirements (§9)**
1. **Duration range:** while writing the design I found the median double-counted the 4 songs that appear in both files. Counting each one once gives a median of 272.8 and an allowed range of about 136–546, instead of 276 and 138–553. The result is the same: 3 durations fixed and none nulled.
2. **Expected numbers:** the acceptance snapshot needs those new figures.
3. **NaN:** the requirements should say that `NaN` / `Infinity`, and the strings `"nan"` / `"inf"`, count as unparseable. Python's `float()` would otherwise accept them.

**Choices you might question**
- **No pandas:** it blurs absent, null and NaN, and turns int columns with a null into floats.
- **No Pydantic for cleaning:** it suits rejecting bad input at the API, not "null this field, record why, keep going".
- **Serving is left out:** in-memory vs SQLite, and where ratings live, belong in the backend spec. The design does say the API should sort nulls last and skip them in averages.

---

## Prompt 4 (2026-11-21 05:20 UTC)

```
Approve the changes. Two pushbacks: drop the temp-folder/atomic write,
plain file writes are enough for this. And confirm how conflicts are decided
if input order doesn't matter, part1 should still win per the requirements.
Then go to tasks.md.
```

**Assistant:**

I've applied the three §9 changes and removed the atomic write. On your second pushback: part1 doesn't win under the current requirements. Conflicts become null. I haven't changed that, because it would reverse your earlier decision.

**Conflicts.** When I asked about conflicts you chose **D1: null + `source_conflict`, no file wins**, and requirements R-ID-5 says the same. That's why input order can't change the result: neither file is preferred, so a disagreement always becomes null. The design now says this outright in §5.4.

"Part1 wins" also works, but it's a different rule. "Never Gonna Give You Up" would keep danceability 0.727 with a flag, instead of null. Order still wouldn't matter, because the winner would be picked by file name, not by which file is read first. If you want this, it changes D1, R-ID-5, the acceptance snapshot in §5, and T6/T9 in tasks.

**Other changes**
- **[requirements.md](specs/data/requirements.md), now v3:**
  - Durations are counted once per song, so the median is about 272.8 and the allowed range about 136–546. The result is still 3 durations fixed and none nulled.
  - `NaN`, `Infinity`, `"nan"` and `"inf"` now count as unparseable.
- **[design.md](specs/data/design.md):** files are written directly. Bad input is caught before anything is written. If a write fails partway, rerunning the command fixes it.

**[tasks.md](specs/data/tasks.md)**
- **10 tasks, one commit each:** each lists its tests and which requirements it covers. They're written test-first, and the repo has Python 3.12 and pytest 8.4.
- **T1–T8** build the pipeline in the design's order: scaffold, schema, cleaning, loading, durations, merge, duplicates, output files and the command.
- **T9** checks every line of the expected result on the real data, and that two runs give identical output.
- **T10** commits the generated outputs so the backend and reviewers can use them without running the pipeline. If you'd rather keep generated files out of git, drop it.

---

## Prompt 5 (2026-11-21 05:24 UTC)

```
You're right, keep D1 (null + source_conflict), I misremembered.
Keep T10. Tasks approved, start T1.
```

**Assistant:**

T1 is done and the scaffold works.

**What's there**
- **`backend/pipeline/`:** all nine modules from design §2, each with only a docstring pointing to its section of the design.
- **`backend/tests/pipeline/`:** empty for now. Tests start in T2.
- **[backend/pyproject.toml](backend/pyproject.toml):** requires Python 3.11 or newer, with pytest as the only dev dependency. pytest is set to run from `backend/`, so tests can import `pipeline` without installing anything.
- **[.gitignore](.gitignore)** at the repo root: ignores `__pycache__`, `.pytest_cache` and `.venv`.

**Checks**
- **pytest:** it finds the config and collects 0 tests with no errors. It exits with code 5, which is pytest's code for "no tests collected", not a failure.
- **Imports:** every module imports cleanly.
- **Command:** `python -m pipeline` exits 0, though it does nothing yet.

Nothing is committed yet: the three spec files and T1 are both untracked. You're on `master`, while the repo's main branch is `main`. Committing straight to `master` is fine for a take-home; tell me if you'd rather work on a branch.

---

## Prompt 6 (2026-11-21 05:27 UTC)

```
You're right, keep D1 (null + source_conflict), I misremembered.
Keep T10. Tasks approved, start T1.
```

**Assistant:**

This looks like your previous message sent again. Everything in it is already done:

- **D1 kept:** conflicts become null with a `source_conflict` flag, and no file wins. Requirements and design both say so.
- **T10 kept:** it's still in [tasks.md](specs/data/tasks.md).
- **T1 done:** the `backend/pipeline/` stubs, `backend/tests/`, [backend/pyproject.toml](backend/pyproject.toml) and the root [.gitignore](.gitignore) are all in place. pytest runs and collects 0 tests with no errors.

Nothing is committed yet. Do you want me to commit the specs and T1 first, or go straight to T2 (schema)?

---

## Prompt 7 (2026-11-21 05:41 UTC)

```
Yes, T1
```

**Assistant:**

I read "Yes, T1" as "commit," so I made two commits on `master`:

- `d0e62b5`: the three spec files (requirements, design, tasks).
- `abc2ee0`: T1, which is the pipeline package stubs, the test folders, `pyproject.toml` and `.gitignore`.

Nothing else is changed and nothing is pushed. T2 is next: field rules, reason codes and core types in `schema.py`, written test-first.

---

## Prompt 8 (2026-11-21 05:41 UTC)

```
Start T2
```

**Assistant:**

T2 is done. I wrote the tests first and confirmed they failed, then wrote [schema.py](backend/pipeline/schema.py). All 72 tests pass, and it's committed on `master` as `29aeed4`.

**What `schema.py` holds**
- **Field table:** the 10 data fields in the order the output will use. Each has its type, its valid range and which files have it, so `valence` is marked part2-only. `columns_for(file)` gives the allowed columns per file, which loading will use to reject unknown columns.
- **Reason codes:** all 16 from requirements §4, each with its severity. They serialize as plain strings.
- **Constants:** 1% tempo and 2% duration for duplicates, half-to-double for the duration range, and 1000 as the seconds threshold.
- **`ABSENT`:** a marker for a missing key, kept separate from JSON `null`.
- **Core types:** `Source`, `Issue` (its severity comes from its reason), `Cleaned` and `SourceRow`.

**Small additions to the design**
- **Null needs a reason:** `Cleaned` raises an error if a value is null without a reason, so "every null has a reason" is checked in code, not just tested for.
- **`PipelineError`:** it lives in `schema.py` so every stage can raise it.
- **`id` on `SourceRow`:** later stages need it constantly, so it's a field of its own.

---

## Prompt 9 (2026-11-21 05:43 UTC)

```
Start T3
```

**Assistant:**

The real data gives exactly the issues the requirements expect. Committing T3 now.

T3 is done: [clean.py](backend/pipeline/clean.py) cleans each raw value. I wrote the tests first and confirmed they failed. All 166 tests now pass, and it's committed as `2018cec`.

**How a value gets cleaned**
1. **Missing values:** an absent key, `null`, `"N/A"` (any case, with spaces around it) and empty or whitespace-only strings each get their own reason.
2. **Numbers:** a string must be a plain decimal like `"0.521"` or `"1e3"` to count as a number. That's stricter than Python's `float()`, which would also accept `"nan"`, `"inf"`, `"1_000"` and non-ASCII digits like `"١٢"`. Real `NaN`/`Infinity` values and booleans are rejected too.
3. **Integers:** `8.0` becomes `8`, while `8.5` becomes null with `not_integer`. Float fields always come out as floats, so tempo `104` becomes `104.0`.
4. **Ranges:** a value outside its range becomes null with the raw value logged, and is never clamped. Durations skip this step because T5 handles them.
5. **Titles:** whitespace is trimmed and collapsed, which gets logged. Converting to standard Unicode form (NFC) is done silently, since it doesn't change what the text says.

If a string fails as a number and also fails the range check, both reasons are logged. For example, `"1.42"` gets `coerced_from_string` and `out_of_range`, and both entries show the final value as null.

**Run on the real files**, cleaning gives exactly the 9 issues the requirements expect:
- "3AM": danceability `"0.521"` and tempo `"108.73"` parsed from strings.
- `" 4 walls  "` becomes `"4 walls"`.
- 11:11 has no energy key, and Yesterday's energy is `"N/A"`.
- Bohemian Rhapsody's acousticness is `null`.
- Out of range: 21 Guns danceability 1.42, Blinding Lights tempo 0, Another Brick acousticness -0.05.

The conflict, the duplicates, the durations and missing valence don't show up yet. They come from later stages (T5–T7).

---

## Prompt 10 (2026-11-21 05:45 UTC)

```
Do T4 through T8, test-first, one commit each. Only stop and ask me if
something doesn't match the spec. Then show me a summary.
```

**Assistant:**

I'll go through T4–T8 in order, writing each task's tests first and committing each one.

T4 and T5 are committed. Next is T6, merging rows by id.

T4–T7 are committed and all 237 tests pass. Last is T8: the output files and the command.

All 250 tests pass. Before committing, I'll run the command on the real data into a scratch folder and check the result against the requirements' expected snapshot.

The real run matches requirements §5 line for line. Committing T8.

T4 through T8 are done, one commit each, with each task's tests written and seen failing before the code. Nothing differed from the spec, so I didn't need to stop. All 250 tests pass.

| Task | Commit | What it does |
|---|---|---|
| T4 loading | `1342725` | Rebuilds rows from the column layout. Unknown columns or files, a row index missing from `id`, non-object columns, bad JSON or a missing file stop the run with a clear error. Rows with a missing id are skipped and logged. `NaN` in the JSON is treated as unparseable. |
| T5 durations | `6385c1e` | Builds the allowed range from 22 unique observations (median 272.8 ms/segment, range 136.4–545.7) and checks every duration against it. The only fix is seconds → ms, and only when the result fits the range. |
| T6 merge | `a3650cd` | One record per id. When the files disagree, the field becomes null with `source_conflict` and neither file wins. Input order doesn't change the result (tested with reversed inputs). |
| T7 duplicates | `dd529a0` | Two records are flagged only if the title matches (ignoring case), tempo is within 1% and duration within 2%. They're linked both ways and their values are never changed. |
| T8 output and command | `69261d5` | `python -m pipeline` writes `songs.json`, `issues.json` and `report.json`. A run that fails on bad input exits 1 and writes nothing. |

**Real-data run:** I wrote the outputs to a scratch folder, since `data/normalized/` waits for T10. It matches every line of the expected result in requirements §5:
- **Records:** 29 source rows become 25 records, 4 of them merged from both files.
- **Nulls:** danceability ×2 (21 Guns out of range, Never Gonna Give You Up conflict), energy ×2 (11:11 missing key, Yesterday `"N/A"`), acousticness ×2 (Bohemian Rhapsody `null`, Another Brick out of range), tempo ×1 (Blinding Lights 0), valence ×12 (part1-only songs).
- **Duration fixes:** Sunflower, Uptown Funk and Sweet Child O Mine are converted from seconds. No duration is nulled.
- **Other:** "3AM" has two numbers parsed from strings, `" 4 walls  "` becomes "4 walls", and the two "Perfect" rows are flagged as a pair.

**Small decisions the spec didn't cover:**
- **`run.py`:** I added this file to chain the stages, so the output code doesn't also run the pipeline.
- **Duplicate issues:** their `field` is `"record"`, since a duplicate is about the whole song rather than one field.
- **Non-string ids:** an id like `123` is treated as missing and the row is skipped. I chose this over turning it into the string `"123"`.
- **Missing keys in the output:** they show up as `null` in `raw_value`. The reason code (`missing_absent` or `not_in_source`) tells them apart from a real `null`.
- **Report extra:** it has a count by severity, which the design didn't list.

Nothing is pushed.

---

## Prompt 11 (2026-11-21 06:39 UTC)

```
Do T9 and T10, commit each.
Then start the API spec cycle: draft specs/api/requirements.md.
What I need:
- GET all songs with pagination (page + size)
- Sorting by any column, asc/desc, across the whole dataset, nulls last
- Title search that ignores case/spacing/accents and always returns a list
  (titles aren't unique: two "Perfect"s)
- PUT a 1–5 star rating that persists. Reject "5", 4.5, true, 0, 6 with 422
- Ratings must survive re-running the pipeline
Keep it simple: FastAPI, SQLite or in-memory, your call with justification.
Requirements only, don't write code yet.
```

**Assistant:**

These tests passed on the first run because the code already exists. To make sure they can actually fail, I'll break one rule on purpose and run them again.

The tests caught the break, and the file is restored. Committing T9, then generating the real outputs for T10.

T9 and T10 are committed. Before drafting the API requirements, I'll read the rest of the AI-written API so the spec avoids the same mistakes.

T9 and T10 are committed, and the API requirements are drafted in [specs/api/requirements.md](specs/api/requirements.md). I haven't committed the API requirements yet, since they're still waiting for your approval.

**T9 (`a162d78`): end-to-end tests**
- **What they check:** every line of the expected result in data requirements §5, that the raw files don't change, that two runs give byte-identical output, and that swapping the input file order changes nothing. All 270 tests pass.
- **They can fail:** they passed on the first run because the code already existed. So I made the duration range narrower on purpose, and 3 of them failed. Then I put it back.

**T10 (`6d36224`)**: `data/normalized/` now has `songs.json`, `issues.json` and `report.json`, and [backend/README.md](backend/README.md) explains how to run the pipeline and the tests.

**API requirements: main choices**
- **Storage:** songs are kept in memory, loaded from `songs.json` at startup. Ratings go in SQLite.
  - **Songs in memory:** there are 25 read-only rows, and this keeps the pipeline's file as the only copy.
  - **Ratings in SQLite:** they need writes that last through restarts and are safe under concurrent requests. SQLite is in the standard library, so there's no new dependency.
  - **Why ratings survive a pipeline rerun:** they're keyed by `id` in their own file, which the pipeline never touches. If a rated song disappears from a new dataset, its rating is kept but not shown.
- **Ids, not titles:** a single song is always addressed by `id`. That means `GET /songs/{id}` and `PUT /songs/{id}/rating`. Title search always returns a list, so both Perfects come back.
- **Sorting:** the whole dataset is sorted first, then split into pages. Nulls go last in both directions, and ties are ordered by `id` so pages never overlap. This avoids the AI-written API's bug of sorting within a page. A page past the end returns an empty list, not an error.
- **Ratings are strict:** the body must be `{"stars": n}` with a whole number from 1 to 5. Your five cases get a 422, and so do `null`, a missing field and extra fields.

**Open questions (§5), with my recommendations**
1. **Search:** match part of a title, so `perf` finds both Perfects.
2. **Punctuation:** don't ignore it, so `"gods plan"` won't match "God's Plan". Ignoring it would also make "11:11" match "1111".
3. **`4.0` as a rating:** reject it, by the same strict rule that rejects `"5"`.
4. **Clearing a rating:** you didn't ask for one. I can add `DELETE /songs/{id}/rating` or leave it out.

---

## Prompt 12 (2026-11-21 06:42 UTC)

```
Don't discuss buggy_api.py any further. I'm reviewing it myself later.


Don't discuss buggy_api.py any further. I'm reviewing it myself later.

Open questions:
1. Exact match first (case/space/accent-insensitive). Only if none, fall
   back to partial. Return match_type so the UI can show which. Pure
   partial makes "21" also return "21 Guns".
2. Ignore punctuation: drop apostrophes, replace other punctuation with a
   space. "gods plan" should find God's Plan; "11:11" becomes "11 11"
   so it won't collide with "1111".
3. Agree, reject 4.0.
4. Leave DELETE out, note it in DECISIONS.

Update requirements, then draft design + tasks. Batch-approve is fine
after that: implement all tasks, test-first, one commit each.
```

**Assistant:**

Strict validation rejects exactly the cases you listed. Now I'll update the requirements.

Requirements are committed. Now the API design and tasks.

Design and tasks are committed (`35a361e`). Starting A1: the app scaffold, config and song loading.

A1 is committed (`df25019`). Next is A2: the search key and matching.

A2 is committed (`766d692`). Next is A3: sorting and pagination.

A3 is committed (`ce5e832`). Next is A4: the SQLite rating store.

A5 is committed (`cd75aec`). Next is A6: the rating endpoint and persistence.

All 415 tests pass. Committing A6, then the README and a live smoke test (A7).

Every endpoint works on a real server, and the rating survived a restart. Committing A7.

The API is finished. All 415 tests pass (pipeline and API), and I checked every endpoint against a running server.

**Spec**
- **Requirements (`bacefea`):** updated with your four answers. [DECISIONS.md](DECISIONS.md) is new: it logs the data decisions D1–D4 and the API decisions, including that there's no DELETE for ratings.
- **Design and tasks (`35a361e`):** [specs/api/](specs/api/).

**Two changes I made to apply your answers**
- **Spaces between words still count.** My earlier draft removed all whitespace, but then "11:11" (key `11 11`) would collide with "1111" again. Now spacing is trimmed and collapsed, not removed. As a result `"4walls"` no longer finds "4 walls". `"4 WALLS"` and `" 4  walls "` still do.
- **Search returns an object.** It's `{query, match_type, items}` instead of a bare list, so it can carry `match_type`. `items` is always a list, even for 0 or 1 matches.

**Implementation, one commit each**

| Task | Commit | What it does |
|---|---|---|
| A1 | `df25019` | Settings from environment variables, with defaults based on the code's location. Loading checks `songs.json` against the pipeline's field list, so the API won't start on a bad file. |
| A2 | `766d692` | Search key and matching. `21` finds only "21", `guns` finds "21 Guns" as a partial match, and `gods plan` finds "God's Plan". |
| A3 | `ce5e832` | The whole dataset is sorted, then split into pages. Nulls go last in both directions, and ties are ordered by id. |
| A4 | `23076f7` | SQLite rating store with a database rule that stars must be 1–5. Ratings for ids missing from the current dataset are kept. |
| A5 | `cd75aec` | `GET /songs`, `/songs/search` and `/songs/{id}`, plus CORS for the Vite dev server. |
| A6 | `ad66a7d` | `PUT /songs/{id}/rating`. 17 bad bodies are tested to get a 422, including `"5"`, `4.5`, `4.0`, `true`, `0`, `6`, `null` and a non-JSON body. |
| A7 | `6ba2d61` | README: how to run it, the endpoints and the environment variables. |

**Ratings persist**
- **Restart:** a rating survives an API restart, both in tests and on the live server.
- **Pipeline rerun:** it survives re-running the pipeline into the same path.
- **Missing song:** if a rated song drops out of the dataset, its rating is hidden. It comes back when the song returns.

**One change from the design:** start the API with:
```bash
uvicorn app.main:create_app --factory --reload
```
There's no module-level `app`. Otherwise just importing `app.main` in a test would load the real songs and create `backend/ratings.db`. The design doc and README are updated to match.

Nothing is pushed.

---

## Prompt 13 (2026-11-21 09:19 UTC)

```
Backend approved. Now the frontend, same spec cycle: requirements →
design → tasks, then batch-implement test-first, one commit each.
Only stop if something contradicts the spec.

Requirements:
- React + Vite, plain CSS, no state library
- On load, fetch and show songs in a table, 10 per page
- Every column sortable, click toggles asc/desc, sorting done by the API
- Download the currently shown rows as CSV
- Title search box + "Get Song" button: show 0 / 1 / many matches clearly,
  use match_type to say "no exact match, showing partial matches"
- Star rating column (1–5) that writes to the API, handles errors
- Null cells shown as "—" with the reason on hover, from the song's
  field reasons
- One chart: scatter of duration vs num_segments, with the 3
  unit-corrected songs highlighted. It shows the evidence for the fix.
- Vitest tests for the non-trivial logic (CSV, sort toggle, search states)

Keep it simple
```

**Assistant:**

Node 22 and npm are available, and `frontend/` is empty. I'll write the three spec docs first.

Specs are committed (`d15b8d5`). Starting F1: the Vite scaffold and API client. I'm pinning exact versions of React, Vite and Vitest that are already well established.

Dependencies are installed. Now the config files, the API client tests, then the client itself.

F1 is committed (`25d9fda`). Next is F2: sorting, the table and pagination. I'll start with a shared fake API for the component tests.

F2 is committed (`b6ee1ed`). Next is F3: null cells with reasons, and the CSV download.

jsdom doesn't provide `URL.createObjectURL`, so the test has to define it rather than spy on it. That's a test-only fix.

The rating column also shows "—" until star ratings land in F5, so the test should look the dash up by its reason text instead.

F4 is committed (`1ba954d`). Next is F5: the star rating.

F5 is committed (`aa2b2e0`). Last feature is F6: the duration vs segments scatter, drawn as plain SVG.

In jsdom, `import.meta.url` isn't a `file:` URL, so the tests will find the data file from the working directory instead.

F6 is committed (`55bf9af`). For F7 I still need real styles, since `styles.css` is still a placeholder, plus the READMEs and a check in a real browser.

The dashboard loads real data from the API. Now I'll go through sorting, searching and rating in the browser.

The table shows ascending after two clicks, so I'll check whether the second click actually reached the button.

Descending sort works. The table scrolls sideways inside its own box at this width, as intended. Next I'll check search.

The rating saved. Next I'll reload the page to check it persists, then look at the chart.

The rating survived the reload, the chart highlights the 3 corrected songs, and the page doesn't scroll sideways. One last check at phone width.

Phone width works: the table scrolls inside its box and the page itself doesn't scroll sideways. Now the READMEs, then a full test run and a production build.

The dashboard is built and committed, one commit per task. Nothing contradicted the spec, so I didn't stop. All 87 frontend tests pass, the 415 backend tests still pass, and the production build works.

| Task | Commit | What it does |
|---|---|---|
| Specs | `d15b8d5` | [requirements, design, tasks](specs/frontend/) |
| F1 | `25d9fda` | Vite + React 19 project. One API client that turns any failed response into an error with a readable message. |
| F2 | `b6ee1ed` | Table, 10 per page. Clicking a header sorts through the API and toggles asc/desc, and a sort change goes back to page 1. Retry if loading fails. |
| F3 | `381872b` | Nulls shown as "—" with the reason on hover or focus. CSV of the rows on screen: BOM, CRLF, proper quoting, formula characters escaped, numbers untouched. |
| F4 | `1ba954d` | Search box and Get Song button with a message for each outcome: exact (one or many), partial ("No exact match for "perf", showing 2 partial matches"), none, empty and a 422. |
| F5 | `aa2b2e0` | Star rating saved to the API. Stars are disabled while saving. On failure the old rating stays and an error shows (the API's message for a 422, a retry message for network errors and 500s). The table and search results stay in sync. |
| F6 | `55bf9af` | Hand-drawn SVG scatter. The 3 corrected songs are orange diamonds, so color isn't needed to tell them apart. They sit on the same trend as the other 22, which is the evidence for the fix. |
| F7 | `02a392e` | Styles, plus the frontend and root READMEs. |

**Browser check against the real API**
- Load, sorting both ways, and partial search for "perf".
- Rating a song: it was still there after a reload.
- The chart shows 22 circles and 3 diamonds.
- At phone width (375px) the page doesn't scroll sideways.

One thing I didn't do in the browser was click Download CSV. It's covered by the unit tests and a component test.

The browser check caught one real problem: clicking a header could miss, because the sort button only covered its text and the columns shifted once data loaded. I made the button fill the whole header cell (in F7).

**Changes from the design**
- **Search state lives in `App`**, not inside the search panel. That's what lets a new rating update both the table and the search results.
- **Two tests had to work around jsdom.** It has no object URLs and no `Blob.text()`. The download code itself didn't change.

**Two untracked items in the repo**
- `.claude/launch.json` is mine: it starts the dev server for the browser preview. I left it out of the commits.
- `REVIEW.md` isn't mine. It looks like your review file, so I haven't touched or read it.

Nothing is pushed.

---

## Prompt 14 (2026-11-21 09:41 UTC)

```
One small thing I noticed: the main table’s default order is 11:11, One More Time, Blinding Lights… That’s sorted by id, which looks random to a user. Defaulting to sort by title would look more natural.
```

**Assistant:**

The tests fail as expected. Now the change itself, plus the spec text.

All 87 tests pass. To see what users will actually get on the first page, I'll ask the real API for the title order.

The order reads naturally: numbers first, then A→Z, with "Café" and "Naïve" in their alphabetical places. Committing.

The dashboard now loads sorted by title A→Z, with the Title header showing ▲. It's committed as `b177bd2`.

On the real data, page 1 now reads: 11:11, 21, 21 Guns, 3AM, 4 walls, Africa, Another Brick, Billie Jean, Blinding Lights, Bohemian Rhapsody. Because the API sorts titles ignoring accents and case, "Café del Mar" and "Naïve" land in their alphabetical places. The two "Perfect"s sit next to each other, ordered by id.

**What changed**
- **The change itself:** one line in [sort.js](frontend/src/lib/sort.js) sets the dashboard's default sort to `title` ascending.
- **Tests:** I updated them first and saw them fail. They now check that the first request uses `sort=title`, that the Title header is marked ascending, and that the CSV filename becomes `songs-page-2-title-asc.csv`. All 87 frontend tests pass.
- **Spec:** the frontend requirements, design and tasks now say `title` too. The requirement notes why: id order looks random to a user.
- **API left alone:** its default is still `id`, which is a stable order for any client that doesn't ask for one. The dashboard just asks for `title`.

You have uncommitted edits to the READMEs, `pyproject.toml` and `.gitignore`, plus `REVIEW.md`. I left all of them alone and out of the commit.
