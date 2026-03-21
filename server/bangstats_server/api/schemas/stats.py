from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StatsResponse(BaseModel):
    summary: Dict[str, Any]
    top_songs: List[Dict[str, Any]]
    recent: List[Dict[str, Any]]
    exclusion_context: Dict[str, Any] = Field(default_factory=dict)


class SongSearchItem(BaseModel):
    song_id: int
    song_name: str


class SongSearchResponse(BaseModel):
    query: str
    limit: int
    results: List[SongSearchItem] = Field(default_factory=list)


class SongRankingItem(BaseModel):
    song_id: int
    song_name: Optional[str] = None
    play_count: int = 0
    fc_count: int = 0
    ap_count: int = 0
    skill_score: float = 0.0
    latest_play: Optional["PlayMeta"] = None


class SongRankingsResponse(BaseModel):
    sort_by: str
    difficulty: Optional[str] = None
    live_type: Optional[str] = None
    items: List[SongRankingItem] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 0
    exclusion_context: Dict[str, Any] = Field(default_factory=dict)


class PlayMeta(BaseModel):
    timestamp: Optional[datetime] = None
    filename: Optional[str] = None
    image_url: Optional[str] = None


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
    skill_score: float = 0.0


class SongStatsResponse(BaseModel):
    song_id: int
    requested_difficulty: Optional[str] = None
    difficulty_overview: List[SongDifficultyOverviewItem] = Field(default_factory=list)
    detail: Optional[SongDifficultyDetail] = None
    exclusion_context: Dict[str, Any] = Field(default_factory=dict)


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


class CalendarMonthSummary(BaseModel):
    month: int
    plays: int = 0
    fc: int = 0
    ap: int = 0
    active_days: int = 0


class StatsCalendarYearResponse(BaseModel):
    year: int
    months: List[CalendarMonthSummary] = Field(default_factory=list)


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


class EventStatsSongItem(BaseModel):
    song_id: int
    song_name: Optional[str] = None
    play_count: int = 0
    fc_count: int = 0
    ap_count: int = 0
    skill_score: float = 0.0


class EventStatsResponse(BaseModel):
    event_id: int
    event_name: Optional[str] = None
    event_type: Optional[str] = None
    from_date: str
    to_date: str
    summary: Dict[str, Any]
    live_types: Dict[str, int] = Field(default_factory=dict)
    active_hours: Dict[str, int] = Field(default_factory=dict)
    top_songs: List[EventStatsSongItem] = Field(default_factory=list)
    total_sessions: int = 0
    longest_session_minutes: int = 0
    fc_gains: int = 0
    ap_gains: int = 0
    skill_score: float = 0.0
    exclusion_context: Dict[str, Any] = Field(default_factory=dict)


class ProgressionPoint(BaseModel):
    label: str
    from_date: str
    to_date: str
    plays: int = 0
    accuracy: float = 0.0
    skill_score: float = 0.0
    fc: int = 0
    ap: int = 0


class ProgressionResponse(BaseModel):
    scope: str
    points: List[ProgressionPoint] = Field(default_factory=list)
    delta_skill_score: float = 0.0
    delta_accuracy: float = 0.0
    exclusion_context: Dict[str, Any] = Field(default_factory=dict)


class TimelinePoint(BaseModel):
    type: str
    label: str
    timestamp: Optional[datetime] = None
    filename: Optional[str] = None
    image_url: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class SongJourneyResponse(BaseModel):
    song_id: int
    song_name: Optional[str] = None
    difficulty: str
    total_plays: int = 0
    first_played: Optional[PlayMeta] = None
    first_fc: Optional[PlayMeta] = None
    first_ap: Optional[PlayMeta] = None
    plays_before_fc: Optional[int] = None
    plays_before_ap: Optional[int] = None
    skill_score: float = 0.0
    timeline: List[TimelinePoint] = Field(default_factory=list)
    exclusion_context: Dict[str, Any] = Field(default_factory=dict)


class RecapHighlight(BaseModel):
    title: str
    value: str
    detail: str
    screenshot: Optional[PlayMeta] = None


class RecapSongItem(BaseModel):
    song_id: int
    song_name: Optional[str] = None
    play_count: int = 0
    fc_count: int = 0
    ap_count: int = 0
    skill_score: float = 0.0
    latest_play: Optional[PlayMeta] = None


class RecapDailyRow(BaseModel):
    date: str
    plays: int = 0
    fc: int = 0
    ap: int = 0
    accuracy: float = 0.0


class RecapResponse(BaseModel):
    scope: str
    title: str
    from_date: str
    to_date: str
    event_id: Optional[int] = None
    event_name: Optional[str] = None
    summary: Dict[str, Any]
    skill_score: float = 0.0
    skill_score_delta: float = 0.0
    top_songs: List[RecapSongItem] = Field(default_factory=list)
    new_songs: List[RecapSongItem] = Field(default_factory=list)
    most_practiced: List[RecapSongItem] = Field(default_factory=list)
    live_types: Dict[str, int] = Field(default_factory=dict)
    active_hours: Dict[str, int] = Field(default_factory=dict)
    highlights: List[RecapHighlight] = Field(default_factory=list)
    daily_digest: List[RecapDailyRow] = Field(default_factory=list)
    streaks: Dict[str, int] = Field(default_factory=dict)
    exclusion_context: Dict[str, Any] = Field(default_factory=dict)
