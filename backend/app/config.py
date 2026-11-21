"""Settings from environment variables (R-CFG-1, R-CFG-4).

Defaults are resolved from this file's location, so the API finds its data
whatever the current directory is.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent

DEFAULT_SONGS = REPO_DIR / "data" / "normalized" / "songs.json"
DEFAULT_RATINGS_DB = BACKEND_DIR / "ratings.db"
DEFAULT_CORS = ("http://localhost:5173",)


@dataclass(frozen=True)
class Settings:
    songs_path: Path = DEFAULT_SONGS
    ratings_db: Path = DEFAULT_RATINGS_DB
    cors_origins: tuple[str, ...] = DEFAULT_CORS

    @classmethod
    def from_env(cls) -> "Settings":
        origins = os.environ.get("CORS_ORIGINS")
        return cls(
            songs_path=Path(os.environ.get("SONGS_PATH", DEFAULT_SONGS)),
            ratings_db=Path(os.environ.get("RATINGS_DB", DEFAULT_RATINGS_DB)),
            cors_origins=(tuple(o.strip() for o in origins.split(",") if o.strip())
                          if origins is not None else DEFAULT_CORS),
        )
