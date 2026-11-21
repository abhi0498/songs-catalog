"""A2: search key & matching. Traces: R-SEARCH-2..4, R-SEARCH-6, D-API-1, D-API-2."""
import unicodedata

import pytest

from app.search import search, search_key
from app.songs import SongStore

from .conftest import SMALL

SONGS = SongStore(SMALL).all()


@pytest.mark.parametrize(
    "text, key",
    [
        # requirements R-SEARCH-2 table
        ("God's Plan", "gods plan"),
        ("11:11", "11 11"),
        ("Mr. Brightside", "mr brightside"),
        ("Naïve", "naive"),
        (" 4 walls  ", "4 walls"),
        # extra variants
        ("GODS PLAN", "gods plan"),
        ("God’s Plan", "gods plan"),       # curly apostrophe
        ("Godʼs Plan", "gods plan"),       # modifier-letter apostrophe
        ("  naïve ", "naive"),
        ("NAIVE", "naive"),
        (unicodedata.normalize("NFD", "Naïve"), "naive"),
        ("Café del Mar", "cafe del mar"),
        ("Sweet Child O' Mine", "sweet child o mine"),
        ("Rock-n-Roll", "rock n roll"),
        ("a\t\n b", "a b"),
        ("!!!", ""),
        ("   ", ""),
    ],
)
def test_search_key(text, key):
    assert search_key(text) == key


def test_colon_keeps_words_apart():
    assert search_key("11:11") != search_key("1111")


def ids(items):
    return [s["id"] for s in items]


def test_exact_beats_partial():
    match_type, items = search(SONGS, "21")
    assert match_type == "exact" and ids(items) == ["a1"]


def test_partial_when_no_exact():
    match_type, items = search(SONGS, "guns")
    assert match_type == "partial" and ids(items) == ["a2"]


def test_both_perfects_in_id_order():
    assert search(SONGS, "PERFECT") == ("exact", [s for s in SONGS if s["title"] == "Perfect"])
    assert ids(search(SONGS, "perfect")[1]) == ["b1", "b2"]


@pytest.mark.parametrize("q, expected", [("gods plan", ["c1"]), ("naive", ["d1"]),
                                         ("4   WALLS", ["e1"]), ("11 11", ["c2"]),
                                         ("1111", ["c3"])])
def test_exact_variants(q, expected):
    assert search(SONGS, q) == ("exact", [s for s in SONGS if s["id"] in expected])


def test_partial_across_accents_returns_all_in_id_order():
    match_type, items = search(SONGS, "caf")
    assert match_type == "partial" and ids(items) == ["d2", "d3"]


def test_partial_does_not_cross_word_spacing():
    """'11:11' is '11 11', so '1111' must not partially match it either."""
    assert ids(search(SONGS, "1111")[1]) == ["c3"]


def test_no_match():
    assert search(SONGS, "zzz") == ("none", [])


def test_null_title_never_matches():
    assert all(s["id"] != "e2" for q in ("none", "null", "") for s in search(SONGS, q or "x")[1])


@pytest.mark.parametrize("q", ["", "   ", "!!!", "'"])
def test_empty_key_is_rejected(q):
    with pytest.raises(ValueError):
        search(SONGS, q)
