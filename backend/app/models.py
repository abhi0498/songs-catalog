"""Request and response models (design §8)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .search import MatchType


class RatingIn(BaseModel):
    """Strict: "5", 4.5, 4.0, true and null are rejected, as are extra fields (R-RATE-2)."""

    model_config = ConfigDict(extra="forbid", strict=True)
    stars: int = Field(ge=1, le=5)


class SourceRef(BaseModel):
    file: str
    row: str


class Song(BaseModel):
    """A songs.json record plus its rating (R-SONG-1). Values pass through unchanged."""

    id: str
    title: str | None
    danceability: float | None
    energy: float | None
    acousticness: float | None
    valence: float | None
    tempo: float | None
    duration_ms: int | None
    num_sections: int | None
    num_segments: int | None
    mood: int | None
    sources: list[SourceRef]
    field_flags: dict[str, list[str]]
    flags: list[str]
    possible_duplicates: list[str]
    rating: int | None


class Page(BaseModel):
    items: list[Song]
    page: int
    size: int
    total: int
    total_pages: int


class SearchResult(BaseModel):
    query: str
    match_type: MatchType
    items: list[Song]
