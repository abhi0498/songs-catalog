"""Whole-dataset sorting and pagination (design §6, R-LIST-3, R-LIST-5..8)."""
from __future__ import annotations

import math
from typing import Literal, Sequence, TypeVar

from .search import search_key
from .songs import Song

SORTABLE = ("id", "title", "danceability", "energy", "acousticness", "valence", "tempo",
            "duration_ms", "num_sections", "num_segments", "mood", "rating")
SortField = Literal["id", "title", "danceability", "energy", "acousticness", "valence", "tempo",
                    "duration_ms", "num_sections", "num_segments", "mood", "rating"]
Order = Literal["asc", "desc"]

T = TypeVar("T")


def sort_songs(songs: Sequence[Song], field: str, order: str) -> list[Song]:
    """Nulls last in both directions. Ties (and nulls) ordered by id ascending.

    Sorting by id first and then by value with Python's stable sort keeps ties in
    id order even with reverse=True.
    """
    value = (lambda s: search_key(s[field])) if field == "title" else (lambda s: s[field])
    by_id = sorted(songs, key=lambda s: s["id"])
    present = [s for s in by_id if s[field] is not None]
    missing = [s for s in by_id if s[field] is None]
    present.sort(key=value, reverse=(order == "desc"))
    return present + missing


def paginate(items: Sequence[T], page: int, size: int) -> tuple[list[T], int, int]:
    """1-based page. Returns (page items, total, total_pages). Past the end → []."""
    total = len(items)
    start = (page - 1) * size
    return list(items[start:start + size]), total, math.ceil(total / size)
