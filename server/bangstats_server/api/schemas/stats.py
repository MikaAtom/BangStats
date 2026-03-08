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


class MilestoneItem(BaseModel):
    type: str
    label: str
    play_count: int
    meta: Optional[PlayMeta] = None


class StatsMilestonesResponse(BaseModel):
    milestones: List[MilestoneItem] = Field(default_factory=list)
    best_streak_days: int = 0
    current_streak_days: int = 0


class ActivityDelta(BaseModel):
    plays_delta: int = 0
    plays_delta_pct: float = 0.0
    accuracy_delta: float = 0.0


class StatsActivityRangeResponse(BaseModel):
    from_date: str
    to_date: str
    days: int
    summary: Dict[str, Any]
    active_days: int
    avg_plays_per_day: float
    range_streak_days: int
    delta_vs_previous: ActivityDelta


class CalendarDayStats(BaseModel):
    date: str
    plays: int
    fc: int
    ap: int
    accuracy: float
    difficulties: Dict[str, int] = Field(default_factory=dict)


class StatsCalendarResponse(BaseModel):
    year: int
    month: int
    total_days_with_plays: int
    days: List[CalendarDayStats] = Field(default_factory=list)
