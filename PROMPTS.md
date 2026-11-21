# Prompts

I used Claude Code for everything. The raw export of the build session is in prompts/main-session.md (14 prompts): my prompts are verbatim, the assistant's replies are its text output without the tool calls.

The method was spec-driven. For each part (data pipeline, API, dashboard) the AI drafted requirements, then a design, then a task list, and I approved each before it moved on. Implementation was test-first, one commit per task. Most of my steering happened in the spec stages, which is why the implementation prompts are short.

## Phase 1: data pipeline (prompts 1-10)

Before writing any code I went through the data and listed its problems (with Claude's help on the profiling). Prompt 1 gave the session that list plus three rules that were my call: never invent a value, never clamp, only fix a duration when there's evidence for it. It asked for requirements only. It came back with numbered requirements, an expected result on the real data that tests could check against, and four open questions.

Prompt 2 ("Discuss questions"): it asked about conflicts, duplicate detection, mood and which durations to check. I took its recommendation on all four (conflicts become null with a source_conflict flag, duplicates need matching title plus close tempo and duration, mood stays a neutral 0/1, every duration gets checked). Honest note: I accepted these quickly, and it shows in prompt 4.

Prompt 3 approved the requirements. While writing the design, the AI caught its own mistake: the duration range was computed with the 4 overlap songs counted twice. It proposed corrected numbers and showed the result didn't change (same 3 durations fixed). Good catch on its part.

Prompt 4, two pushbacks:
- I told it to drop the temp-folder/atomic write. That's production safety for a script I'd run a few times, so it was over-engineering here. It removed it.
- I said "part1 should still win per the requirements". This one was me being wrong. It pointed out I had chosen null-on-conflict in prompt 2, that the requirements said so, and listed what would have to change if I really wanted part1 to win. It didn't quietly change the rule to match what I'd just said, which is what I want from it.

Prompt 5 confirmed I'd misremembered and kept the null rule. Prompt 6 is the same message sent twice by accident; it noticed and didn't redo anything.

Prompts 7-9 went one task at a time (T1-T3). "Yes, T1" was ambiguous and it read it as "commit", which was fine. At that pace it was too slow for a 3 hour budget, so prompt 10 batched T4-T8: test-first, one commit each, only stop if something doesn't match the spec. Nothing did.

Things I noticed and let go: it gold-plates by default (rejecting "1_000" and Arabic digits in number strings, 250 tests by this point). It was already done and cheap, so not worth undoing.

## Phase 2: API (prompts 11-12)

Prompt 11 asked it to finish T9-T10 and draft API requirements from a short list of what I needed (pagination, sorting across the whole dataset with nulls last, title search that returns a list, strict 1-5 ratings that survive a pipeline rerun).

Two good things here. For T9 it noticed the end-to-end tests passed on the first run because the code already existed, so it broke the duration rule on purpose to check they actually fail, then put it back. And it chose songs in memory plus ratings in SQLite with a clear reason for each.

One bad thing: before drafting the API spec it read review/buggy_api.py and mentioned the sort-within-a-page bug. That file is the one I'm meant to review myself, so prompt 12 opens with "Don't discuss buggy_api.py any further."

Prompt 12 also answered its four open questions, and I overruled two of its recommendations:
- Search: it recommended pure partial matching. That makes "21" also return "21 Guns". I asked for exact match first (ignoring case, spacing and accents) with partial only as a fallback, and a match_type field so the UI can say which happened.
- Punctuation: it recommended not ignoring it, partly so "11:11" wouldn't match "1111". I asked to drop apostrophes and turn other punctuation into a space, so "gods plan" finds God's Plan and "11:11" becomes "11 11", which still doesn't collide. When implementing it, it noticed its own draft removed all spaces and would have brought the collision back, and fixed it.
- Agreed with rejecting 4.0 as a rating and leaving out a DELETE endpoint.

Then batch approval for the rest. It finished the API with 415 tests and checked every endpoint on a running server.

## Phase 3: dashboard (prompts 13-14)

Prompt 13 gave the frontend requirements in one go, same spec cycle. The chart was my idea: duration vs num_segments with the 3 corrected songs highlighted, because that straight line is the evidence for the duration fix.

It built it task by task and then checked it in a real browser against the real API. That check found a bug the unit tests didn't: clicking a column header sometimes didn't register, because the sort button only covered the header text and the columns shifted after the data loaded. It made the button fill the header cell.

Prompt 14: the default table order was by id, which looks random to a user. I asked for title order instead. It changed the dashboard's default, updated the spec and tests, and left the API default as id since that's a stable order for other clients.

## Outside the main session

I also used a separate Claude chat as a sounding board: to read the main session's summaries with me, to sanity-check the setup instructions on a clean copy (it found the README was missing the venv/install steps and that pip install -e failed, which are fixed), and to help with the write-ups. For REVIEW.md I found Issue 1 myself and the AI drafted the rest, which I checked one by one. REFLECTION.md was drafted the same way from what actually happened in the build.

## What I'd do the same next time

Understand the data before code, write the expected result down before implementation, and batch tasks once the spec is solid. The time I spent arguing over requirements paid off; the time spent approving one task at a time didn't.
