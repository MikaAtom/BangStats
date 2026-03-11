from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from bangstats_server.api.dependencies import assert_user_scope, get_current_user
from bangstats_server.api.schemas.stats import (
    StatsActivityRangeResponse,
    StatsCalendarResponse,
    StatsInsightsResponse,
    StatsMilestonesResponse,
    SongDifficultyDetail,
    SongDifficultyOverviewItem,
    SongSearchItem,
    SongSearchResponse,
    SongStatsResponse,
    StatsResponse,
)
from bangstats_server.core.services.screenshot import ScreenshotService
from bangstats_server.core.services.song import SongService
from bangstats_server.core.db.models.user import User
from bangstats_server.core.services.stats import (
    compute_activity_range,
    compute_calendar_month_view,
    compute_difficulty_detail,
    compute_general_summary,
    compute_insights,
    compute_milestones,
    compute_recent_plays,
    compute_song_difficulty_overview,
    compute_top_songs,
)

router = APIRouter()
song_service = SongService
screenshot_service = ScreenshotService


def _song_service_instance():
    if isinstance(song_service, type):
        return song_service()
    return song_service


def _screenshot_service_instance():
    if isinstance(screenshot_service, type):
        return screenshot_service()
    return screenshot_service


def _song_display_name(song, server: str, fallback_id: int | None = None) -> str:
    if not song or not isinstance(song.name, dict):
        fallback_song_id = fallback_id if fallback_id is not None else getattr(song, "internal_song_id", "?")
        return f"Song {fallback_song_id}"
    return (
        song.name.get(server)
        or song.name.get("en")
        or next((value for value in song.name.values() if value), "")
        or f"Song {song.internal_song_id}"
    )


def _search_songs_case_insensitive(query: str) -> list:
    song_service = _song_service_instance()
    languages = ["en", "jp", "tw", "cn", "kr"]
    merged = {}
    for language in languages:
        for song in song_service.search_songs_by_name(query, language=language):
            merged[song.internal_song_id] = song
    return list(merged.values())


def _difficulty_sort_key(difficulty: str) -> tuple[int, str]:
    order = {"easy": 0, "normal": 1, "hard": 2, "expert": 3, "special": 4}
    lowered = difficulty.lower()
    return order.get(lowered, 99), lowered


def _parse_iso_date(value: str, field_name: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {value}") from exc


def _get_user_screenshots_or_404(user_id: int):
    screenshot_service = _screenshot_service_instance()
    screenshots = screenshot_service.get_screenshots_by_user(user_id)
    if not screenshots:
        raise HTTPException(status_code=404, detail="No screenshots for this user")
    return screenshots


def _resolve_date_range(preset: str, from_date: str | None, to_date: str | None):
    today = datetime.now(timezone.utc).date()
    if from_date or to_date:
        if not from_date or not to_date:
            raise HTTPException(
                status_code=400,
                detail="Both from_date and to_date are required for custom range",
            )
        range_start = _parse_iso_date(from_date, "from_date")
        range_end = _parse_iso_date(to_date, "to_date")
    else:
        presets = {"7d": 7, "30d": 30, "90d": 90}
        days = presets.get(preset)
        if days is None:
            raise HTTPException(status_code=400, detail=f"Invalid preset: {preset}")
        range_end = today
        range_start = today - timedelta(days=days - 1)

    if range_start > range_end:
        raise HTTPException(status_code=400, detail="from_date must be <= to_date")
    return range_start, range_end


def _song_length_seconds(song: object | None) -> int:
    raw = getattr(song, "length", 0)
    try:
        return max(0, int(round(float(raw))))
    except (TypeError, ValueError):
        return 0


@router.get("/users/{user_id}/stats", response_model=StatsResponse)
def get_user_stats(user_id: int, current_user: User = Depends(get_current_user)):
    user_id = assert_user_scope(user_id, current_user)
    screenshots = _get_user_screenshots_or_404(user_id)

    summary = compute_general_summary(screenshots)
    top_songs = compute_top_songs(screenshots, n=5)
    recent = compute_recent_plays(screenshots, n=5)

    return StatsResponse(
        summary=summary,
        top_songs=top_songs,
        recent=recent,
    )


@router.get("/users/{user_id}/stats/songs/search", response_model=SongSearchResponse)
def search_user_stat_songs(
    user_id: int,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    server: str = Query("en", min_length=2, max_length=2),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    # Keep legacy behavior: search globally, then filter by user's plays during detail lookup.
    _ = user_id
    query = q.strip()
    songs = _search_songs_case_insensitive(query)
    lowered_query = query.casefold()
    songs = sorted(
        songs,
        key=lambda song: (
            0 if _song_display_name(song, server).casefold().startswith(lowered_query) else 1,
            _song_display_name(song, server).casefold(),
            int(song.internal_song_id),
        ),
    )

    results = [
        SongSearchItem(
            song_id=int(song.internal_song_id),
            song_name=_song_display_name(song, server),
        )
        for song in songs[:limit]
    ]
    return SongSearchResponse(query=query, limit=limit, results=results)


@router.get("/users/{user_id}/stats/songs/{song_id}", response_model=SongStatsResponse)
def get_user_song_stats(
    user_id: int,
    song_id: int,
    difficulty: str | None = Query(None),
    session_gap_minutes: int = Query(45, ge=5, le=240),
    server: str = Query("en", min_length=2, max_length=2),
    current_user: User = Depends(get_current_user),
):
    song_service = _song_service_instance()
    screenshot_service = _screenshot_service_instance()
    user_id = assert_user_scope(user_id, current_user)
    song = song_service.get_song_by_internal_id(song_id)
    if not song:
        raise HTTPException(status_code=404, detail=f"Song not found: {song_id}")

    song_plays = screenshot_service.get_screenshots_by_song(user_id, song_id)
    if not song_plays:
        raise HTTPException(status_code=404, detail=f"No plays found for song {song_id}")

    overview_map = compute_song_difficulty_overview(
        song_plays,
        song_length_seconds=_song_length_seconds(song),
    )
    overview = [
        SongDifficultyOverviewItem(
            difficulty=diff,
            total_plays=int(payload.get("total_plays", 0)),
            first_played=payload.get("first_played"),
            estimated_time_played_seconds=int(payload.get("estimated_time_played_seconds", 0)),
            estimated_time_played_human=str(payload.get("estimated_time_played_human", "0m")),
        )
        for diff, payload in sorted(
            overview_map.items(),
            key=lambda item: _difficulty_sort_key(item[0]),
        )
    ]

    normalized_difficulty = difficulty.strip().lower() if isinstance(difficulty, str) else None
    detail = None
    if normalized_difficulty:
        plays = screenshot_service.get_screenshots_by_song(
            user_id,
            song_id,
            normalized_difficulty,
        )
        if not plays:
            raise HTTPException(
                status_code=404,
                detail=f"No plays found for song {song_id} [{normalized_difficulty}]",
            )
        detail = SongDifficultyDetail(
            **compute_difficulty_detail(
                plays,
                song_length_seconds=_song_length_seconds(song),
                session_gap_minutes=session_gap_minutes,
            )
        )

    return SongStatsResponse(
        song_id=song_id,
        requested_difficulty=normalized_difficulty,
        difficulty_overview=overview,
        detail=detail,
    )


@router.get("/users/{user_id}/stats/milestones", response_model=StatsMilestonesResponse)
def get_user_stats_milestones(user_id: int, current_user: User = Depends(get_current_user)):
    user_id = assert_user_scope(user_id, current_user)
    screenshots = _get_user_screenshots_or_404(user_id)
    return StatsMilestonesResponse(**compute_milestones(screenshots))


@router.get("/users/{user_id}/stats/activity", response_model=StatsActivityRangeResponse)
def get_user_stats_activity(
    user_id: int,
    preset: str = Query("30d"),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    screenshots = _get_user_screenshots_or_404(user_id)
    range_start, range_end = _resolve_date_range(preset, from_date, to_date)

    return StatsActivityRangeResponse(
        **compute_activity_range(
            screenshots,
            from_date=range_start,
            to_date=range_end,
        )
    )


@router.get("/users/{user_id}/stats/calendar", response_model=StatsCalendarResponse)
def get_user_stats_calendar(
    user_id: int,
    year: int | None = Query(None, ge=2000, le=2200),
    month: int | None = Query(None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    screenshots = _get_user_screenshots_or_404(user_id)

    now = datetime.now(timezone.utc)
    selected_year = year if year is not None else now.year
    selected_month = month if month is not None else now.month

    return StatsCalendarResponse(
        **compute_calendar_month_view(
            screenshots,
            year=selected_year,
            month=selected_month,
        )
    )


@router.get("/users/{user_id}/stats/insights", response_model=StatsInsightsResponse)
def get_user_stats_insights(
    user_id: int,
    preset: str = Query("30d"),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    session_gap_minutes: int = Query(45, ge=5, le=240),
    current_user: User = Depends(get_current_user),
):
    song_service = _song_service_instance()
    user_id = assert_user_scope(user_id, current_user)
    screenshots = _get_user_screenshots_or_404(user_id)
    range_start, range_end = _resolve_date_range(preset, from_date, to_date)

    song_ids = {
        int(getattr(screenshot, "song_id", 0))
        for screenshot in screenshots
        if int(getattr(screenshot, "song_id", 0)) > 0
    }
    song_map = {
        song_id: song_service.get_song_by_internal_id(song_id)
        for song_id in song_ids
    }
    song_lengths_seconds = {
        song_id: _song_length_seconds(song)
        for song_id, song in song_map.items()
    }

    payload = compute_insights(
        screenshots,
        from_date=range_start,
        to_date=range_end,
        session_gap_minutes=session_gap_minutes,
        song_lengths_seconds=song_lengths_seconds,
    )

    return StatsInsightsResponse(**payload)
