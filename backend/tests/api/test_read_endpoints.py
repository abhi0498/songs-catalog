"""A5: app factory & read endpoints.

Traces: R-SONG-1..2, R-LIST-1..4, R-SEARCH-1, R-SEARCH-5, R-SEARCH-7, R-GET-1, R-CFG-2,
R-CFG-4, R-ERR-1.
"""
import json

import pytest

from app.config import Settings
from app.main import create_app
from app.songs import SONG_KEYS, SongsLoadError

from .conftest import REAL_SONGS, SMALL

REAL = json.loads(REAL_SONGS.read_text("utf-8"))


def ids(items):
    return [s["id"] for s in items]


# --- song shape (R-SONG-1/2) ----------------------------------------------

def test_song_shape_and_values_match_songs_json(real_client):
    body = real_client.get("/songs", params={"size": 100}).json()
    by_id = {s["id"]: s for s in REAL}
    assert len(body["items"]) == 25
    for item in body["items"]:
        assert list(item) == [*SONG_KEYS, "rating"]
        assert item["rating"] is None
        assert {k: v for k, v in item.items() if k != "rating"} == by_id[item["id"]]


# --- GET /songs -------------------------------------------------------------

def test_defaults(real_client):
    body = real_client.get("/songs").json()
    assert (body["page"], body["size"], body["total"], body["total_pages"]) == (1, 10, 25, 3)
    assert ids(body["items"]) == sorted(s["id"] for s in REAL)[:10]


def test_page_two_of_desc_sort_is_whole_dataset_sort(real_client):
    """R-LIST-5: sort first, then page."""
    everything = real_client.get("/songs", params={"size": 100, "sort": "tempo",
                                                   "order": "desc"}).json()["items"]
    page2 = real_client.get("/songs", params={"page": 2, "sort": "tempo",
                                              "order": "desc"}).json()["items"]
    assert ids(page2) == ids(everything[10:20])
    tempos = [s["tempo"] for s in everything]
    assert tempos[-1] is None  # Blinding Lights, nulls last on desc
    non_null = [t for t in tempos if t is not None]
    assert non_null == sorted(non_null, reverse=True)


def test_nulls_last_ascending_too(real_client):
    items = real_client.get("/songs", params={"size": 100, "sort": "tempo"}).json()["items"]
    assert items[-1]["tempo"] is None and items[0]["tempo"] is not None


def test_page_past_end(real_client):
    body = real_client.get("/songs", params={"page": 4}).json()
    assert body["items"] == [] and body["total"] == 25 and body["total_pages"] == 3


def test_sort_by_title(client):
    items = client.get("/songs", params={"size": 100, "sort": "title"}).json()["items"]
    assert ids(items)[:2] == ["c2", "c3"] and ids(items)[-1] == "e2"


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page": -1}, {"page": "abc"}, {"page": 1.5}, {"size": 0}, {"size": 101},
     {"sort": "loudness"}, {"sort": "TEMPO"}, {"order": "up"}],
)
def test_bad_list_params_422(client, params):
    assert client.get("/songs", params=params).status_code == 422


def test_bad_sort_lists_allowed_values(client):
    detail = client.get("/songs", params={"sort": "loudness"}).json()["detail"]
    msg = detail[0]["msg"]
    for col in ("'id'", "'title'", "'tempo'", "'rating'"):
        assert col in msg


# --- GET /songs/search ------------------------------------------------------

def test_search_exact(client):
    body = client.get("/songs/search", params={"title": "21"}).json()
    assert body["query"] == "21" and body["match_type"] == "exact"
    assert ids(body["items"]) == ["a1"]


def test_search_partial(client):
    body = client.get("/songs/search", params={"title": "Guns"}).json()
    assert body["match_type"] == "partial" and ids(body["items"]) == ["a2"]


def test_search_none_is_200_empty_list(client):
    r = client.get("/songs/search", params={"title": "zzz"})
    assert r.status_code == 200
    assert r.json() == {"query": "zzz", "match_type": "none", "items": []}


def test_search_both_perfects_with_flags_and_rating(real_client):
    body = real_client.get("/songs/search", params={"title": "  PERFECT "}).json()
    assert body["match_type"] == "exact"
    assert ids(body["items"]) == ["0tgVpDi06FyKpA1z0VMD4v", "7dNsHhGeGU5MV01r06O8gK"]
    for item in body["items"]:
        assert "possible_duplicate" in item["flags"] and item["rating"] is None


@pytest.mark.parametrize("q, title", [("gods plan", "God's Plan"), ("naive", "Naïve"),
                                       ("CAFE DEL MAR", "Café del Mar"), ("4walls", None),
                                       ("4 WALLS", "4 walls")])
def test_search_real_variants(real_client, q, title):
    body = real_client.get("/songs/search", params={"title": q}).json()
    if title is None:
        assert body["match_type"] == "none"
    else:
        assert body["match_type"] == "exact" and [s["title"] for s in body["items"]] == [title]


@pytest.mark.parametrize("params", [{}, {"title": ""}, {"title": "   "}, {"title": "!!!"}])
def test_search_empty_422(client, params):
    r = client.get("/songs/search", params=params)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list)


# --- GET /songs/{id} --------------------------------------------------------

def test_get_one(client):
    r = client.get("/songs/b2")
    assert r.status_code == 200 and r.json()["title"] == "Perfect" and r.json()["rating"] is None


def test_get_unknown_404(client):
    r = client.get("/songs/nope")
    assert r.status_code == 404 and "detail" in r.json()


def test_search_path_is_not_an_id(client):
    """/songs/search without a title is a 422 from search, not a 404 lookup of id 'search'."""
    assert client.get("/songs/search").status_code == 422


# --- startup & CORS ---------------------------------------------------------

def test_bad_songs_file_fails_at_startup(tmp_path):
    p = tmp_path / "songs.json"
    p.write_text("{}")
    with pytest.raises(SongsLoadError):
        create_app(Settings(songs_path=p, ratings_db=tmp_path / "r.db"))


def test_missing_songs_file_fails_at_startup(tmp_path):
    with pytest.raises(SongsLoadError):
        create_app(Settings(songs_path=tmp_path / "missing.json", ratings_db=tmp_path / "r.db"))


def preflight(client, origin):
    return client.options("/songs/a1/rating", headers={
        "Origin": origin, "Access-Control-Request-Method": "PUT",
        "Access-Control-Request-Headers": "content-type"})


def test_cors_allows_dashboard_origin(client):
    r = preflight(client, "http://localhost:5173")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_other_origins(client):
    r = preflight(client, "http://evil.test")
    assert "access-control-allow-origin" not in r.headers


def test_small_fixture_sanity(client):
    assert client.get("/songs").json()["total"] == len(SMALL)
