from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StatsResponse(BaseModel):
    summary: Dict[str, Any]
    top_songs: List[Dict[str, Any]]
    recent: List[Dict[str, Any]]


class SongSearchItem(BaseModel):
    song_id: int
    song_name: str


class SongSearchResponse(BaseModel):
    query: str
    limit: int
    results: List[SongSearchItem] = Field(default_factory=list)


class PlayMeta(BaseModel):
    timestamp: Optional[datetime] = None
    filename: Optional[str] = None


class SongDifficultyOverviewItem(BaseModel):
    difficulty: str
    total_plays: int
    first_played: Optional[PlayMeta] = None


class SongDifficultyDetail(BaseModel):
    total_plays: int
    total_fc: int
    total_ap: int
    accuracy: float
    first_played: Optional[PlayMeta] = None
    last_played: Optional[PlayMeta] = None
    first_fc: Optional[PlayMeta] = None
    last_fc: Optional[PlayMeta] = None
    first_ap: Optional[PlayMeta] = None
    last_ap: Optional[PlayMeta] = None
    plays_before_fc: Optional[int] = None
    plays_before_ap: Optional[int] = None


class SongStatsResponse(BaseModel):
    song_id: int
    song_name: str
    requested_difficulty: Optional[str] = None
    difficulty_overview: List[SongDifficultyOverviewItem] = Field(default_factory=list)
    detail: Optional[SongDifficultyDetail] = None
