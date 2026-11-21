# Reflection

## 1. What is the single weakest part of your submission, and why did you leave it that way?

The tests. There are over 500 of them (415 backend, 87 frontend) and they all pass, but the same AI wrote both the code and the tests, so they can share the same blind spots. Green tests mostly prove the code does what the AI thought the spec meant. I tried to cover that in a few ways: the specs had concrete acceptance numbers I wrote down before any code existed, the end-to-end tests were deliberately broken once to check they actually fail, and the dashboard was checked in a real browser. That browser check found a bug the unit tests missed (clicking a column header sometimes didn't register because the button only covered the text). Still, I didn't write the tests myself line by line, and with a 3 hour budget I chose to spend my time on the data decisions and the review instead.

## 2. Where did AI save you the most time, and where did it cost you time or nearly lead you wrong?

It saved the most time on implementation. Once the requirements and design were agreed, it built the pipeline, the API and the dashboard task by task, test-first, and I mostly reviewed summaries and diffs. The leverage was in getting the spec right, not in typing prompts.

Where it cost time or nearly went wrong:

- It over-builds by default. 415 backend tests for 25 rows, rejecting Arabic digits in number strings, writing output to a temp folder and swapping it in. I had it drop the atomic write and let the rest go because it was already done.
- Its search recommendations were wrong for the actual use case. Pure partial matching would make "21" also return "21 Guns", and not ignoring punctuation would mean "gods plan" doesn't find "God's Plan". I overruled both: exact match first with a partial fallback, and punctuation ignored.
- It read buggy_api.py before I had reviewed it and mentioned the sort-within-a-page bug. I told it to stop and did my review separately.
- Once I was the one who was wrong. I pushed back with "part1 should win conflicts", and it pointed out that contradicted my own earlier decision (conflicts become null, no file wins). It was right and I kept my original rule.

## 3. What in the data surprised you? What did you decide not to fix, and why?

The duration bug was the most interesting. Three part2 songs had duration_ms of 158, 270 and 356, which are obviously seconds. I didn't want a blind "multiply small values by 1000" rule, so the check compares duration against num_segments. Every normal song runs at roughly the same milliseconds per segment, and those three only fit that pattern when read as seconds. So the fix is based on evidence in the data, and a value that doesn't fit gets nulled instead of guessed.

I was also surprised that the same song id disagreed between the two files (danceability 0.727 vs 0.74) and that missing values showed up three different ways (missing key, null, "N/A").

Things I decided not to fix:

- The 0.727 vs 0.74 conflict. I can't tell which file is right, so the value is null with both originals in the flag. Someone upstream should answer it.
- The two "Perfect" rows. They have different ids and nearly identical values, but there's no artist column, so they could be a single and a re-release. I flagged them as possible duplicates instead of merging them.
- Titles like "Another Brick" (probably truncated) and "Sweet Child O Mine" (missing apostrophe). Correcting titles needs an outside source, and search already handles the apostrophe.
- mood vs valence. I checked whether mood was derived from valence, but it isn't consistent (some high-valence songs have mood 0 and the other way round), so I didn't use one to fill in the other.

## 4. If this went to production Monday and real users hit it, what breaks first?

Probably the deployment itself: the dashboard defaults to calling the API on localhost and the API only allows the localhost:5173 origin, so both need config before it works anywhere else.

After that, ratings. There are no user accounts, so a rating is one value per song and anyone can overwrite anyone else's. Ratings are in a single SQLite file, which is fine for one server but won't work once there's more than one instance. And songs are loaded into memory at startup, so new data from the pipeline doesn't show up until the API is restarted.
