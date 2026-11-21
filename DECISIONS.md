# Decisions

The short version of the decisions behind this project. The full reasoning, with numbered requirements, is in the specs: specs/data, specs/api and specs/frontend.

## Data

The one rule everything else follows: never invent a value. If a value can't be trusted it becomes null, and the reason goes into the record's field_flags (and into data/normalized/issues.json with the raw value). A consumer can trust every non-null value, and see why any null is null.

Duplicates across the two files. Row indexes mean nothing (both files start at "0"), so records are matched on id. 4 ids appear in both files and are merged into one record each, so 29 source rows become 25 songs. Each record lists the file and row it came from.

Conflicts (D1). Only one field actually disagrees: danceability for Never Gonna Give You Up, 0.727 in part1 and 0.74 in part2. It becomes null with source_conflict, and both raw values are kept in the issues log. Neither file wins because nothing shows one export is more reliable than the other. Trade-off: the song loses a value that is probably close to right either way. I preferred a visible gap to picking a winner on a guess.

Same title, different id (D2). The two "Perfect" rows have different ids and nearly identical numbers. They are kept as two songs and flagged as possible duplicates of each other. A pair is only flagged if the title matches and tempo is within 1% and duration within 2%, so a cover that just shares a title isn't flagged. Nothing is ever merged on similarity, because there's no artist column to confirm it.

Missing values. They show up three ways in this data: absent key (11:11 energy), JSON null (Bohemian Rhapsody acousticness) and "N/A" (Yesterday energy); empty strings are handled the same way. All become null, each with its own reason code (missing_absent, missing_null, missing_na, missing_empty), so you can still tell them apart. No imputation: a mean-filled energy would be a made-up measurement.

Wrong types. Numbers stored as strings ("0.521", "108.73") are parsed, since only the type was wrong, and logged as coerced_from_string. A string has to be a plain decimal; things Python's float() would also accept like "nan", "inf" or "1_000" are rejected. Booleans are never numbers. Integer fields accept 8.0 but not 8.5.

Out of range. danceability 1.42, acousticness -0.05 and tempo 0 become null with out_of_range and the raw value logged. No clamping: turning 1.42 into 1.0 would be a value nobody measured.

Units (D4). Three part2 durations (Sunflower 158, Uptown Funk 270, Sweet Child O Mine 356) are in seconds, not ms. Instead of a "multiply small values by 1000" rule, every duration is checked against its num_segments: real songs run at roughly the same ms per segment (median about 273), and the allowed band is half to double that. The three values only fit the band when read as seconds, so they are multiplied by 1000 and flagged. A value that doesn't fit is nulled, not guessed, and a duration with no num_segments to check against is kept but flagged duration_unverified (or nulled if it's too small to be ms). Result on this data: 3 fixed, none nulled.

The extra attribute. valence only exists in part2. I kept it rather than dropping real data. For the 12 songs that only come from part1 it is null with not_in_source, which is different from "the source had it but it was blank". The 4 songs in both files take it from part2.

mood (D3). It's 0/1 with no documentation. I checked whether it was derived from valence, but it isn't consistent (some high-valence songs are mood 0 and the other way round), so it's kept as a plain 0/1 label and not used to fill anything.

Titles. Whitespace is trimmed and collapsed (" 4 walls  " becomes "4 walls") and logged, but casing is left alone, because automatic title-casing would mangle real titles. Possibly truncated titles like "Another Brick" are not corrected, since that needs an outside source.

Output. The pipeline writes songs.json, issues.json and report.json to data/normalized/ and they're committed. Same input always gives byte-identical output.

## API

Songs in memory, ratings in SQLite. The songs are 25 read-only rows owned by the pipeline, so the API loads songs.json at startup and keeps it as the only copy. Ratings need durable, concurrent-safe writes, and SQLite gives that with no server and no extra dependency. Trade-off: new pipeline output needs an API restart, and SQLite is a single file that won't scale past one server.

Ids, not titles. A single song is always addressed by id: GET /songs/{id} and PUT /songs/{id}/rating. Titles aren't unique, so anything keyed by title would hit the wrong song (or both Perfects).

GET /songs?page&size&sort&order. The whole dataset is sorted, then paged, so sorting isn't limited to one page. Nulls go last in both directions, and ties are broken by id so pages never overlap. sort is checked against the known columns; anything else is a 422. A page past the end returns an empty list instead of an error.

GET /songs/search?title. This is how the not-unique-title problem is handled: it always returns {query, match_type, items}, with items a list, so two Perfects is a normal answer rather than an edge case. It tries an exact match first, ignoring case, spacing, accents and punctuation; only if there's none does it fall back to a partial match. match_type tells the UI which happened. Exact-first matters because "21" should return "21", not "21 Guns" too. Apostrophes are dropped and other punctuation becomes a space, so "gods plan" finds God's Plan while "11:11" stays different from "1111". Trade-off: "4walls" doesn't find "4 walls".

PUT /songs/{id}/rating with {"stars": n}. One rating per song, last write wins, because there are no user accounts to attach ratings to. stars must be a whole JSON number from 1 to 5; "5", 4.5, 4.0, true, 0 and 6 all get a 422 and nothing is written. Unknown id is a 404. Ratings are keyed by id in their own database, so they survive restarts and re-running the pipeline.

## Dashboard

Sorting, paging and search all go through the API; the UI never re-sorts rows itself, so what you see always matches the whole dataset. The table defaults to title order because id order looks random to a user, and the id column isn't shown for the same reason (it's still used behind the scenes for ratings). Null cells show "—" with the reason on hover. Download CSV saves exactly the rows on screen. The chart plots duration against number of segments with the three corrected songs highlighted, because that line is the evidence for the duration fix.

## Left out, and what I'd do with more time

- User accounts and per-user ratings (needed before ratings mean much), and a way to clear a rating (DELETE /songs/{id}/rating).
- Typo-tolerant search. Right now it only forgives case, spacing, accents and punctuation.
- Asking the upstream team about the 0.727/0.74 conflict and the two Perfects instead of leaving them flagged.
- Running the pipeline on a schedule with checks that fail loudly on new kinds of bad data, and having the API pick up new data without a restart.
- Moving ratings to a real database before running more than one API instance.
