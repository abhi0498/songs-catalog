"""Shared fixtures for API tests: a small hand-built dataset and real-data paths."""
import json
from pathlib import Path

import pytest

from pipeline.schema import FIELDS

REPO = Path(__file__).resolve().parents[3]
REAL_SONGS = REPO / "data" / "normalized" / "songs.json"


def make_song(id_, title, **kw):
    """A record shaped like songs.json, with every field present."""
    s = {"id": id_}
    s.update({f.name: None for f in FIELDS})
    s.update(title=title, danceability=0.5, energy=0.5, acousticness=0.1, valence=0.5,
             tempo=100.0, duration_ms=200_000, num_sections=8, num_segments=800, mood=1)
    s.update(sources=[{"file": "songs_part1.json", "row": "0"}], field_flags={}, flags=[],
             possible_duplicates=[])
    s.update(kw)
    return s


# Covers: null tempo, ties, same-title pair, "21"/"21 Guns", punctuation, accents,
# whitespace, mixed case and a null title.
SMALL = [
    make_song("a1", "21", tempo=120.0),
    make_song("a2", "21 Guns", tempo=154.0),
    make_song("b1", "Perfect", tempo=95.05, possible_duplicates=["b2"], flags=["possible_duplicate"]),
    make_song("b2", "Perfect", tempo=95.05, possible_duplicates=["b1"], flags=["possible_duplicate"]),
    make_song("c1", "God's Plan", tempo=77.0),
    make_song("c2", "11:11", tempo=None, field_flags={"tempo": ["out_of_range"]},
              flags=["out_of_range"]),
    make_song("c3", "1111", tempo=100.0),
    make_song("d1", "Naïve", tempo=128.0),
    make_song("d2", "café del mar", tempo=134.0),
    make_song("d3", "Cafe Society", tempo=None, field_flags={"tempo": ["missing_null"]},
              flags=["missing_null"]),
    make_song("e1", "4 walls", tempo=126.0),
    make_song("e2", None, tempo=100.0, field_flags={"title": ["source_conflict"]},
              flags=["source_conflict"]),
]


@pytest.fixture
def songs_file(tmp_path):
    p = tmp_path / "songs.json"
    p.write_text(json.dumps(SMALL, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def make_client(tmp_path):
    """Build a TestClient over a given songs file and a ratings db in tmp_path."""
    from fastapi.testclient import TestClient

    from app.config import DEFAULT_CORS, Settings
    from app.main import create_app

    def _make(songs_path, ratings_db=None):
        settings = Settings(songs_path=songs_path,
                            ratings_db=ratings_db or tmp_path / "ratings.db",
                            cors_origins=DEFAULT_CORS)
        return TestClient(create_app(settings))

    return _make


@pytest.fixture
def client(make_client, songs_file):
    return make_client(songs_file)


@pytest.fixture
def real_client(make_client):
    return make_client(REAL_SONGS)
