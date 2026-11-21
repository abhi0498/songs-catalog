"""A3: sorting & pagination. Traces: R-LIST-3, R-LIST-5..8."""
import copy

import pytest

from app.query import SORTABLE, paginate, sort_songs
from app.songs import SongStore, with_rating

from .conftest import SMALL


def songs(ratings=None):
    ratings = ratings or {}
    return [with_rating(s, ratings.get(s["id"])) for s in SongStore(SMALL).all()]


def ids(items):
    return [s["id"] for s in items]


def test_sortable_columns():
    assert SORTABLE == ("id", "title", "danceability", "energy", "acousticness", "valence",
                        "tempo", "duration_ms", "num_sections", "num_segments", "mood", "rating")


def test_numeric_asc_nulls_last_ties_by_id():
    assert ids(sort_songs(songs(), "tempo", "asc")) == [
        "c1", "b1", "b2", "c3", "e2", "a1", "e1", "d1", "d2", "a2", "c2", "d3"]


def test_numeric_desc_nulls_still_last_ties_still_by_id():
    assert ids(sort_songs(songs(), "tempo", "desc")) == [
        "a2", "d2", "d1", "e1", "a1", "c3", "e2", "b1", "b2", "c1", "c2", "d3"]


def test_all_equal_values_fall_back_to_id_in_both_directions():
    for order in ("asc", "desc"):
        assert ids(sort_songs(songs(), "mood", order)) == sorted(s["id"] for s in SMALL)


def test_title_sorts_by_search_key():
    assert ids(sort_songs(songs(), "title", "asc")) == [
        "c2", "c3", "a1", "a2", "e1", "d2", "d3", "c1", "d1", "b1", "b2", "e2"]


def test_title_desc_null_last():
    out = ids(sort_songs(songs(), "title", "desc"))
    assert out[:3] == ["b1", "b2", "d1"] and out[-1] == "e2"


def test_rating_with_unrated_last():
    rated = songs({"d1": 5, "a1": 3, "b2": 3})
    assert ids(sort_songs(rated, "rating", "desc"))[:3] == ["d1", "a1", "b2"]
    assert ids(sort_songs(rated, "rating", "asc"))[:3] == ["a1", "b2", "d1"]
    assert len(sort_songs(rated, "rating", "asc")) == len(SMALL)


def test_id_sort():
    assert ids(sort_songs(songs(), "id", "desc")) == sorted((s["id"] for s in SMALL), reverse=True)


def test_input_not_mutated():
    data = songs()
    before = copy.deepcopy(data)
    sort_songs(data, "tempo", "desc")
    assert data == before


# --- paginate -------------------------------------------------------------

ITEMS = list(range(25))


@pytest.mark.parametrize(
    "page, size, expected, total_pages",
    [
        (1, 10, list(range(10)), 3),
        (2, 10, list(range(10, 20)), 3),
        (3, 10, list(range(20, 25)), 3),
        (4, 10, [], 3),
        (1, 25, ITEMS, 1),
        (1, 100, ITEMS, 1),
        (25, 1, [24], 25),
    ],
)
def test_paginate(page, size, expected, total_pages):
    assert paginate(ITEMS, page, size) == (expected, 25, total_pages)


def test_paginate_empty():
    assert paginate([], 1, 10) == ([], 0, 0)
