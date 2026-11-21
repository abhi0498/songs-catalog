# Review of review/buggy_api.py

I wouldn't approve this. It runs and returns data, but paging and sorting give the wrong songs without any error, ratings accept anything, and a couple of endpoints crash on the nulls in our cleaned data. Ranking is at the bottom.

## Issue 1

```python
def get_songs(page: int = 1, size: int = 10, sort_by: str = "title", order: str = "asc"):
    songs = load_songs()
    start = page * size
    end = start + size
```

Page defaults to 1 but the offset is calculated as if pages start at 0, so page 1 returns rows 10-19. The first 10 songs never show up unless someone asks for page=0, which nobody will. Negative pages aren't rejected either. Fix: start = (page - 1) * size and validate page >= 1.

## Issue 2

```python
page_items = songs[start:end]
page_items = sorted(page_items, key=lambda s: s[sort_by], reverse=reverse)
```

It cuts out the page first and then sorts just those 10 rows. So "sort by tempo desc" gives you the fastest songs on that page, not the fastest songs overall, and the order across pages makes no sense. This one is easy to miss because it looks right when there's only one page of data. Fix: sort the full list, then slice.

## Issue 3

```python
@app.post("/songs/{title}/rating")
def rate_song(title: str, stars: int):
    ratings[title] = stars
```

There's no check on stars, so 99 or -5 get saved and returned as a success. Ratings are also keyed by title, and titles aren't unique: rating "Perfect" sets the rating on both Perfect songs. Rating a title that doesn't exist still returns 200. Fix: rate by song id, validate stars is 1-5, return 404 if the song doesn't exist.

## Issue 4

sort_by goes straight into s[sort_by] with no check. An unknown column gives a KeyError, and any column with a null in it (energy, danceability, tempo, etc. in our data) gives a TypeError because Python can't compare None with a float. Both are 500s, so clicking those column headers in the UI just breaks. order also accepts anything and treats typos as ascending. Fix: only allow known column names and asc/desc, and sort with nulls last, e.g. key=lambda s: (s[f] is None, s[f]).

## Issue 5

```python
if song["title"] == title:
    return song
```

The title lookup is an exact, case-sensitive match and returns only the first hit. "perfect" or " Perfect " finds nothing, and the second Perfect can never be found. Fix: compare lowercased, trimmed titles (and ignore accents) and return all matches.

## Issue 6

When nothing matches it returns {"error": "not found"} with a 200 status. A client checking the status code will treat that as a song. Fix: return a 404, or an empty list if lookup returns a list.

## Issue 7

```python
def load_songs(_cache=[]):
```

The cache is a mutable default argument and gets filled with a check-then-append. FastAPI runs these endpoints in a thread pool, so two requests on a cold start can both see an empty cache and both append, and then every song is in the list twice until the server restarts. The cached dicts also get modified by rate_song, which makes the shared state hard to reason about. Fix: load the data once at startup into a normal variable.

## Issue 8

Ratings only live in memory (in two places: the ratings dict, which is never read, and the cached song dicts). A restart wipes them, and with more than one worker each one has different ratings. Only rated songs get a "rating" key, so the response shape isn't consistent. Fix: store ratings in SQLite by song id and always return rating, null if unrated.

## Issue 9

```python
total += s["duration_ms"] / 1000
avg_seconds = total / len(songs)
```

A null duration crashes this, and an empty file gives a ZeroDivisionError. The bigger problem is that it assumes every value is in milliseconds. The source data has some durations in seconds (158, 270, 356), and if those weren't fixed upstream the average comes out wrong without any error. Fix: skip nulls, divide by the number of real values, and make sure the unit is fixed in the data first.

## Issue 10 (nit)

open("songs.json") is relative to wherever the server was started, so running it from another folder fails on the first request. There's no encoding either, so on Windows titles like Naïve can come out garbled. Fix: build the path from the file's location and pass encoding="utf-8".

## Issue 11 (nit)

Smaller API things: rating should be a PUT with a JSON body instead of a POST with a query param, size has no upper limit, there are no response models, and the paging response has no total_pages.

## Ranking

I'd block the PR on 1, 2, 3 and 4. 1 and 2 are the worst because they return wrong data with a 200 and nobody would notice. 3 lets bad data into the system. 4 crashes on our real data the first time someone sorts. 5 to 9 should be fixed before merging but aren't as serious on their own. 10 and 11 are nits.
