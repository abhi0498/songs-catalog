"""A6: rating endpoint & persistence. Traces: R-RATE-1..7, D-API-3."""
import json
import shutil

import pytest

from app.ratings import RatingStore
from app.songs import SONG_KEYS
from pipeline.__main__ import main as run_pipeline

from .conftest import REPO, SMALL

NEVER_GONNA = "4uLU6hMCjMI75M1A2tKUQC"


def put(client, song_id, body=None, **kw):
    return client.put(f"/songs/{song_id}/rating", json=body, **kw)


# --- happy path ---------------------------------------------------------------

def test_put_returns_full_song_with_rating(client):
    r = put(client, "b1", {"stars": 4})
    assert r.status_code == 200
    body = r.json()
    assert list(body) == [*SONG_KEYS, "rating"]
    assert body["id"] == "b1" and body["title"] == "Perfect" and body["rating"] == 4


def test_put_is_idempotent_and_replaces(client):
    assert put(client, "b1", {"stars": 2}).json() == put(client, "b1", {"stars": 2}).json()
    assert put(client, "b1", {"stars": 5}).json()["rating"] == 5
    assert client.get("/songs/b1").json()["rating"] == 5


@pytest.mark.parametrize("stars", [1, 2, 3, 4, 5])
def test_every_valid_value(client, stars):
    assert put(client, "a1", {"stars": stars}).json()["rating"] == stars


def test_rating_only_on_the_rated_perfect(client):
    put(client, "b1", {"stars": 3})
    items = client.get("/songs/search", params={"title": "perfect"}).json()["items"]
    assert [(s["id"], s["rating"]) for s in items] == [("b1", 3), ("b2", None)]


# --- strict validation (R-RATE-2) ---------------------------------------------

@pytest.mark.parametrize(
    "raw",
    ['{"stars": "5"}', '{"stars": 4.5}', '{"stars": 4.0}', '{"stars": true}',
     '{"stars": false}', '{"stars": 0}', '{"stars": 6}', '{"stars": -1}', '{"stars": null}',
     '{}', '{"stars": 3, "x": 1}', '[3]', '3', '"3"', 'null', 'not json', ''],
)
def test_rejected_bodies_422(client, tmp_path, raw):
    r = client.put("/songs/a1/rating", content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 422, raw
    assert isinstance(r.json()["detail"], list)
    assert RatingStore(tmp_path / "ratings.db").all() == {}


def test_query_param_instead_of_body_422(client):
    assert client.put("/songs/a1/rating", params={"stars": 3}).status_code == 422


def test_unknown_id_404_and_nothing_stored(client, tmp_path):
    r = put(client, "nope", {"stars": 3})
    assert r.status_code == 404 and "detail" in r.json()
    assert RatingStore(tmp_path / "ratings.db").all() == {}


# --- visible everywhere right away (R-RATE-7) ----------------------------------

def test_rating_visible_in_list_sort_search_get(client):
    put(client, "d1", {"stars": 5})
    put(client, "a1", {"stars": 2})
    listed = {s["id"]: s["rating"] for s in
              client.get("/songs", params={"size": 100}).json()["items"]}
    assert listed["d1"] == 5 and listed["a1"] == 2 and listed["b1"] is None

    by_rating = client.get("/songs", params={"sort": "rating", "order": "desc",
                                             "size": 100}).json()["items"]
    assert [s["id"] for s in by_rating[:2]] == ["d1", "a1"]
    assert all(s["rating"] is None for s in by_rating[2:])

    assert client.get("/songs/search", params={"title": "naive"}).json()["items"][0]["rating"] == 5
    assert client.get("/songs/a1").json()["rating"] == 2


# --- persistence (R-RATE-5/6) --------------------------------------------------

def test_survives_restart(make_client, songs_file):
    put(make_client(songs_file), "c1", {"stars": 4})
    assert make_client(songs_file).get("/songs/c1").json()["rating"] == 4


def test_survives_pipeline_rerun(make_client, tmp_path):
    data = tmp_path / "data"
    shutil.copytree(REPO / "data", data, ignore=shutil.ignore_patterns("normalized"))
    out = data / "normalized"
    args = ["--data-dir", str(data), "--out-dir", str(out)]
    assert run_pipeline(args) == 0

    client = make_client(out / "songs.json")
    assert put(client, NEVER_GONNA, {"stars": 5}).status_code == 200

    before = (out / "songs.json").read_bytes()
    assert run_pipeline(args) == 0          # re-run the pipeline over the same path
    assert (out / "songs.json").read_bytes() == before

    restarted = make_client(out / "songs.json")
    song = restarted.get(f"/songs/{NEVER_GONNA}").json()
    assert song["rating"] == 5 and song["title"] == "Never Gonna Give You Up"
    assert sum(s["rating"] is not None for s in
               restarted.get("/songs", params={"size": 100}).json()["items"]) == 1


def test_orphaned_rating_hidden_then_restored(make_client, tmp_path):
    full = tmp_path / "full.json"
    full.write_text(json.dumps(SMALL), encoding="utf-8")
    without_a1 = tmp_path / "without_a1.json"
    without_a1.write_text(json.dumps([s for s in SMALL if s["id"] != "a1"]), encoding="utf-8")

    put(make_client(full), "a1", {"stars": 3})

    shrunk = make_client(without_a1)
    assert shrunk.get("/songs/a1").status_code == 404
    assert all(s["id"] != "a1" for s in shrunk.get("/songs", params={"size": 100}).json()["items"])
    assert RatingStore(tmp_path / "ratings.db").all() == {"a1": 3}  # kept, not deleted

    assert make_client(full).get("/songs/a1").json()["rating"] == 3


def test_failed_write_is_500_not_success(client, monkeypatch):
    import sqlite3

    def boom(self, song_id, stars):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(RatingStore, "set", boom)
    from fastapi.testclient import TestClient
    c = TestClient(client.app, raise_server_exceptions=False)
    assert c.put("/songs/a1/rating", json={"stars": 3}).status_code == 500
