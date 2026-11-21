"""A4: rating store. Traces: R-RATE-4..6."""
import sqlite3

import pytest

from app.ratings import RatingStore


@pytest.fixture
def db(tmp_path):
    return tmp_path / "ratings.db"


def test_set_and_get(db):
    store = RatingStore(db)
    assert store.get("a") is None
    store.set("a", 4)
    assert store.get("a") == 4


def test_overwrite_replaces(db):
    store = RatingStore(db)
    store.set("a", 2)
    store.set("a", 5)
    assert store.get("a") == 5
    assert store.all() == {"a": 5}


def test_all(db):
    store = RatingStore(db)
    store.set("b", 1)
    store.set("a", 3)
    assert store.all() == {"a": 3, "b": 1}


def test_persists_across_instances(db):
    RatingStore(db).set("a", 3)
    assert RatingStore(db).get("a") == 3


def test_creates_parent_dir(tmp_path):
    store = RatingStore(tmp_path / "nested" / "dir" / "ratings.db")
    store.set("a", 1)
    assert (tmp_path / "nested" / "dir" / "ratings.db").exists()


@pytest.mark.parametrize("stars", [0, 6, -1])
def test_check_constraint_backs_up_validation(db, stars):
    store = RatingStore(db)
    with pytest.raises(sqlite3.IntegrityError):
        store.set("a", stars)
    assert store.get("a") is None


def test_rows_for_any_id_are_kept(db):
    """The store doesn't know the dataset. Orphaned ids stay (R-RATE-6)."""
    store = RatingStore(db)
    store.set("gone-from-dataset", 2)
    assert RatingStore(db).all() == {"gone-from-dataset": 2}


def test_updated_at_recorded(db):
    RatingStore(db).set("a", 4)
    with sqlite3.connect(db) as conn:
        (updated_at,) = conn.execute("SELECT updated_at FROM ratings WHERE song_id='a'").fetchone()
    assert updated_at.endswith("+00:00")
