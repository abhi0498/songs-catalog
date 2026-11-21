"""Load and hold the pipeline's songs.json (design §4, R-CFG-2, A1).

Songs are read once and never mutated. Responses get a copy with `rating`
attached (with_rating).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.schema import FIELDS, ID_FIELD

# The songs.json record contract, in order. Field names come from the pipeline
# so the contract is defined in one place.
SONG_KEYS: tuple[str, ...] = (
    ID_FIELD, *(f.name for f in FIELDS), "sources", "field_flags", "flags", "possible_duplicates",
)

Song = dict[str, Any]


class SongsLoadError(Exception):
    """songs.json is missing or doesn't match the contract. The API won't start."""


def load_songs(path: Path | str) -> list[Song]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SongsLoadError(f"{path}: cannot read songs file ({e.strerror})") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise SongsLoadError(f"{path}: invalid JSON ({e})") from e

    if not isinstance(data, list):
        raise SongsLoadError(f"{path}: top level must be a list of songs")
    seen: set[str] = set()
    for n, song in enumerate(data):
        if not isinstance(song, dict):
            raise SongsLoadError(f"{path}: item {n} must be an object")
        sid = song.get(ID_FIELD)
        if not isinstance(sid, str) or not sid:
            raise SongsLoadError(f"{path}: item {n} has no valid id")
        missing = [k for k in SONG_KEYS if k not in song]
        if missing:
            raise SongsLoadError(f"{path}: song '{sid}' is missing {', '.join(missing)}")
        if sid in seen:
            raise SongsLoadError(f"{path}: duplicate id '{sid}'")
        seen.add(sid)
    return data


class SongStore:
    """Read-only, id-ordered songs."""

    def __init__(self, songs: list[Song]):
        self._songs = sorted(songs, key=lambda s: s[ID_FIELD])
        self._by_id = {s[ID_FIELD]: s for s in self._songs}

    def all(self) -> list[Song]:
        return list(self._songs)

    def get(self, song_id: str) -> Song | None:
        return self._by_id.get(song_id)

    def __len__(self) -> int:
        return len(self._songs)


def with_rating(song: Song, rating: int | None) -> Song:
    """A response copy of song with `rating` added last. The stored song is untouched."""
    return {**song, "rating": rating}
