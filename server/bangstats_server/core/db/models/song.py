from typing import Dict, List, Optional, TYPE_CHECKING
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
    levels: Dict[str, List[int]] = Field(sa_type=JSON)
    note_counts: Dict[str, List[int]] = Field(sa_type=JSON)
    bpm: float
    length: float
    published_at: Dict[str, datetime] = Field(sa_type=JSON)
    closed_at: Optional[Dict[str, datetime]] = Field(default=None, sa_type=JSON)
    special: Optional[Dict[str, str]] = Field(default=None, sa_type=JSON)
