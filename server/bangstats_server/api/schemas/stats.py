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
    estimated_time_played_seconds: int = 0
    estimated_time_played_human: str = "0m"


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
    estimated_time_played_seconds: int = 0
    estimated_time_played_human: str = "0m"
    session_gap_minutes_used: int = 45
    total_sessions: int = 0
    avg_plays_per_session: float = 0.0
    longest_session_plays: int = 0
    longest_session_minutes: int = 0
    practice_burst_count: int = 0
    max_practice_burst_plays: int = 0


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


class SessionInsightSummary(BaseModel):
    total_sessions: int = 0
    avg_session_minutes: float = 0.0
    avg_plays_per_session: float = 0.0
    longest_session_minutes: int = 0
    longest_session_plays: int = 0
    recent_cadence_days: float = 0.0


class SessionInsightItem(BaseModel):
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    plays: int = 0
    unique_songs: int = 0
    duration_minutes: int = 0


class PracticePeriodItem(BaseModel):
    song_id: int
    song_name: Optional[str] = None
    total_plays: int = 0
    burst_count: int = 0
    max_burst_plays: int = 0
    latest_burst_at: Optional[datetime] = None
    estimated_time_played_seconds: int = 0
    estimated_time_played_human: str = "0m"


class RepetitionSongItem(BaseModel):
    song_id: int
    song_name: Optional[str] = None
    play_count: int = 0
    repeated_plays: int = 0
    repeat_ratio: float = 0.0
    max_gap_days: float = 0.0
    estimated_time_played_seconds: int = 0
    estimated_time_played_human: str = "0m"


class RepetitionInsights(BaseModel):
    total_plays: int = 0
    repeated_plays: int = 0
    repeated_ratio: float = 0.0
    most_looped_songs: List[RepetitionSongItem] = Field(default_factory=list)
    revisited_after_break: List[RepetitionSongItem] = Field(default_factory=list)


class InsightRecommendation(BaseModel):
    title: str
    detail: str
    song_id: Optional[int] = None
    song_name: Optional[str] = None


class InsightDataQuality(BaseModel):
    observed_plays: int = 0
    min_recommended_plays: int = 0
    sparse_data: bool = False


class StatsInsightsResponse(BaseModel):
    from_date: str
    to_date: str
    session_gap_minutes: int
    data_quality: InsightDataQuality
    sessions: SessionInsightSummary
    recent_sessions: List[SessionInsightItem] = Field(default_factory=list)
    practice_periods: List[PracticePeriodItem] = Field(default_factory=list)
    repetition: RepetitionInsights
    recommendations: List[InsightRecommendation] = Field(default_factory=list)
