"""Title search key and exact-then-partial matching (design §5, R-SEARCH, D-API-1/2)."""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from typing import Iterable, Literal

from .songs import Song

MatchType = Literal["exact", "partial", "none"]

APOSTROPHES = frozenset("'’‘ʼ")


@lru_cache(maxsize=4096)
def search_key(text: str) -> str:
    """Accent-, case-, spacing- and punctuation-insensitive key (R-SEARCH-2).

    Apostrophes are dropped ("God's" → "gods"). Other punctuation becomes a
    space ("11:11" → "11 11"), so words stay apart and "11:11" ≠ "1111".
    """
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = "".join(
        "" if c in APOSTROPHES else " " if unicodedata.category(c).startswith("P") else c
        for c in s
    )
    return " ".join(s.split())


def search(songs: Iterable[Song], query: str) -> tuple[MatchType, list[Song]]:
    """Exact key matches if any, else substring matches, else none.

    Keeps the input order (the store gives id order). Songs with a null title never
    match. The caller rejects an empty query key (422) before calling this.
    """
    q = search_key(query)
    if not q:
        raise ValueError("empty search key")
    keyed = [(search_key(s["title"]), s) for s in songs if s["title"] is not None]
    exact = [s for k, s in keyed if k == q]
    if exact:
        return "exact", exact
    partial = [s for k, s in keyed if q in k]
    return ("partial", partial) if partial else ("none", [])
