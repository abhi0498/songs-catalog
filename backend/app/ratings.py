"""Star ratings in SQLite, keyed by song id (design §7, R-RATE-4..6).

Separate from songs.json, so re-running the pipeline never touches ratings.
Rows are never deleted. Ids missing from the current dataset are just not served.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS ratings (
  song_id    TEXT PRIMARY KEY,
  stars      INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
  updated_at TEXT NOT NULL
)
"""


class RatingStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as conn:
            conn.execute(SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Short-lived connection per call: commit on success, roll back on error, always close."""
        with closing(sqlite3.connect(self.path)) as conn:
            with conn:
                yield conn

    def get(self, song_id: str) -> int | None:
        with self._tx() as conn:
            row = conn.execute("SELECT stars FROM ratings WHERE song_id = ?", (song_id,)).fetchone()
        return None if row is None else row[0]

    def all(self) -> dict[str, int]:
        with self._tx() as conn:
            return dict(conn.execute("SELECT song_id, stars FROM ratings ORDER BY song_id"))

    def set(self, song_id: str, stars: int) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO ratings (song_id, stars, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(song_id) DO UPDATE SET stars = excluded.stars, "
                "updated_at = excluded.updated_at",
                (song_id, stars, now),
            )
