from typing import Optional, Dict
from datetime import datetime
from sqlmodel import Field, SQLModel, JSON


class Screenshot(SQLModel, table=True):
    """Screenshot data model representing user performance statistics for a live."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    # New structure fields
    score: int
    high_score: Optional[int] = None
    is_new_record: Optional[bool] = None
    score_rank: Optional[str] = None
    live_type: str

    free_live_data: Optional[Dict] = Field(default=None, sa_type=JSON)
    team_live_data: Optional[Dict] = Field(default=None, sa_type=JSON)

    perfect: int
    great: int
    good: int
    bad: int
    miss: int
    fast: Optional[int] = None
    slow: Optional[int] = None
    max_combo: int

    full_combo: bool = Field(default=False)
    all_perfect: bool = Field(default=False)

    song_id: int = Field(foreign_key="song.internal_song_id", index=True)
    difficulty: str

    # Metadata
    anomaly: bool = Field(default=False)
    filename: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
