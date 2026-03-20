from typing import Any, Dict, Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, JSON


class Song(SQLModel, table=True):
    """Song model representing a music track in the database."""

    id: Optional[int] = Field(default=None, primary_key=True)
    internal_song_id: int = Field(index=True)
    tag: str
    name: Dict[str, str] = Field(sa_type=JSON)
    band_id: int = Field(foreign_key="band.internal_band_id", index=True)
    lyricist: Dict[str, str] = Field(sa_type=JSON)
    composer: Dict[str, str] = Field(sa_type=JSON)
    arranger: Dict[str, str] = Field(sa_type=JSON)
    # Upstream datasets contain mixed scalar/list shapes for chart metadata.
    levels: Dict[str, int | list[int]] = Field(sa_type=JSON)
    note_counts: Dict[str, int | list[int]] = Field(sa_type=JSON)
    bpm: float
    length: float
    # Timestamps are stored as milliseconds in some datasets.
    published_at: Dict[str, datetime | int | str | None] = Field(sa_type=JSON)
    closed_at: Optional[Dict[str, datetime | int | str | None]] = Field(default=None, sa_type=JSON)
    # `special` can be a boolean or metadata object depending on source.
    special: Optional[bool | Dict[str, Any]] = Field(default=None, sa_type=JSON)
