"""A1: config & song loading. Traces: R-CFG-1..3, R-SONG-2."""
import copy
import json

import pytest

from app.config import Settings
from app.songs import SONG_KEYS, SongsLoadError, SongStore, load_songs, with_rating

from .conftest import REAL_SONGS, REPO, SMALL


# --- Settings --------------------------------------------------------------

def test_defaults_resolved_from_code_location(monkeypatch, tmp_path):
    for var in ("SONGS_PATH", "RATINGS_DB", "CORS_ORIGINS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    s = Settings.from_env()
    assert s.songs_path == REPO / "data" / "normalized" / "songs.json"
    assert s.ratings_db == REPO / "backend" / "ratings.db"
    assert s.cors_origins == ("http://localhost:5173",)


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("SONGS_PATH", str(tmp_path / "s.json"))
    monkeypatch.setenv("RATINGS_DB", str(tmp_path / "r.db"))
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    s = Settings.from_env()
    assert s.songs_path == tmp_path / "s.json"
    assert s.ratings_db == tmp_path / "r.db"
    assert s.cors_origins == ("http://a.test", "http://b.test")


# --- load_songs ------------------------------------------------------------

def test_load_real_file():
    songs = load_songs(REAL_SONGS)
    assert len(songs) == 25
    assert all(list(s) == list(SONG_KEYS) for s in songs)


def test_song_keys_match_pipeline_contract():
    assert SONG_KEYS[0] == "id" and SONG_KEYS[-4:] == (
        "sources", "field_flags", "flags", "possible_duplicates")
    assert "valence" in SONG_KEYS and "rating" not in SONG_KEYS


def write(tmp_path, obj, raw=None):
    p = tmp_path / "songs.json"
    p.write_text(raw if raw is not None else json.dumps(obj), encoding="utf-8")
    return p


def test_missing_file(tmp_path):
    with pytest.raises(SongsLoadError, match="nope.json"):
        load_songs(tmp_path / "nope.json")


def test_invalid_json(tmp_path):
    with pytest.raises(SongsLoadError, match="invalid JSON"):
        load_songs(write(tmp_path, None, raw="[{"))


def test_not_a_list(tmp_path):
    with pytest.raises(SongsLoadError, match="list"):
        load_songs(write(tmp_path, {"id": "a"}))


def test_record_missing_a_field(tmp_path):
    bad = copy.deepcopy(SMALL)
    del bad[3]["tempo"]
    with pytest.raises(SongsLoadError, match=r"b2.*tempo"):
        load_songs(write(tmp_path, bad))


def test_record_not_an_object(tmp_path):
    with pytest.raises(SongsLoadError, match="object"):
        load_songs(write(tmp_path, [1]))


@pytest.mark.parametrize("bad_id", ["", None, 5])
def test_bad_id(tmp_path, bad_id):
    bad = copy.deepcopy(SMALL)
    bad[0]["id"] = bad_id
    with pytest.raises(SongsLoadError, match="id"):
        load_songs(write(tmp_path, bad))


def test_duplicate_id(tmp_path):
    bad = copy.deepcopy(SMALL) + [copy.deepcopy(SMALL[0])]
    with pytest.raises(SongsLoadError, match=r"duplicate id 'a1'"):
        load_songs(write(tmp_path, bad))


# --- SongStore -------------------------------------------------------------

def test_store_is_id_ordered(songs_file):
    store = SongStore(list(reversed(load_songs(songs_file))))
    assert [s["id"] for s in store.all()] == sorted(s["id"] for s in SMALL)
    assert len(store) == len(SMALL)
    assert store.get("b2")["title"] == "Perfect"
    assert store.get("zzz") is None


def test_with_rating_copies_and_never_mutates(songs_file):
    store = SongStore(load_songs(songs_file))
    original = copy.deepcopy(store.get("a1"))
    out = with_rating(store.get("a1"), 4)
    assert out["rating"] == 4 and list(out)[-1] == "rating"
    assert store.get("a1") == original and "rating" not in store.get("a1")
