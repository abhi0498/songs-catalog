"""FastAPI app factory and routes (design §9).

Run from backend/:  uvicorn app.main:create_app --factory --reload
There's no module-level app, so importing this module has no side effects.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .models import Page, RatingIn, SearchResult, Song
from .query import Order, SortField, paginate, sort_songs
from .ratings import RatingStore
from .search import search, search_key
from .songs import SongStore, load_songs, with_rating


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    songs = SongStore(load_songs(settings.songs_path))  # fails fast on a bad file (R-CFG-2)
    ratings = RatingStore(settings.ratings_db)

    app = FastAPI(title="Songs API", version="1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "PUT"],
        allow_headers=["Content-Type"],
    )

    def rated(items):
        """Response copies of songs with current ratings attached (R-RATE-7)."""
        current = ratings.all()
        return [with_rating(s, current.get(s["id"])) for s in items]

    def one(song_id: str):
        song = songs.get(song_id)
        if song is None:
            raise HTTPException(status_code=404, detail=f"song '{song_id}' not found")
        return song

    @app.get("/songs", response_model=Page)
    def list_songs(
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
        sort: SortField = "id",
        order: Order = "asc",
    ):
        ordered = sort_songs(rated(songs.all()), sort, order)  # whole dataset, then page
        items, total, total_pages = paginate(ordered, page, size)
        return {"items": items, "page": page, "size": size, "total": total,
                "total_pages": total_pages}

    # Registered before /songs/{song_id} so "search" isn't taken as an id.
    @app.get("/songs/search", response_model=SearchResult)
    def search_songs(title: str = Query(...)):
        if not search_key(title):
            raise RequestValidationError([{
                "type": "value_error",
                "loc": ("query", "title"),
                "msg": "title must contain at least one letter or digit",
                "input": title,
            }])
        match_type, items = search(songs.all(), title)
        return {"query": title, "match_type": match_type, "items": rated(items)}

    @app.get("/songs/{song_id}", response_model=Song)
    def get_song(song_id: str):
        song = one(song_id)
        return with_rating(song, ratings.get(song_id))

    return app
