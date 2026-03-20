from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from bangstats_server.api.dependencies import assert_user_scope, get_current_user
from bangstats_server.api.schemas.stats import (
    EventStatsResponse,
    ProgressionResponse,
    RecapResponse,
    SongRankingsResponse,
    SongJourneyResponse,
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
from bangstats_server.core.config import META_SONG_IDS
from bangstats_server.core.services.screenshot import ScreenshotService
from bangstats_server.core.services.event import EventService
from bangstats_server.core.services.event_time import parse_event_timestamp_ms
from bangstats_server.core.services.scan import ScanService
from bangstats_server.core.services.upload_storage import UploadStorageService
from bangstats_server.core.services.song import SongService
from bangstats_server.core.services.user import UserService
from bangstats_server.core.db.models.user import User
from bangstats_server.core.services.stats import (
    compute_activity_range,
    compute_event_stats,
    compute_calendar_month_view,
    compute_difficulty_detail,
    compute_general_summary,
    compute_insights,
    compute_milestones,
    compute_progression,
    compute_recent_plays,
    compute_recap,
    compute_song_rankings,
    compute_song_journey,
    compute_song_difficulty_overview,
    compute_top_songs,
    filter_stats_plays,
    filter_excluded_songs,
)

router = APIRouter()
song_service = SongService
screenshot_service = ScreenshotService
event_service = EventService


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


def _songs_by_internal_ids(song_service: SongService, song_ids: Iterable[int]) -> list:
    sanitized = sorted({int(song_id) for song_id in song_ids if int(song_id) > 0})
    if not sanitized:
        return []
    if hasattr(song_service, "get_songs_by_internal_ids"):
        return song_service.get_songs_by_internal_ids(sanitized)
    if hasattr(song_service, "get_song_by_internal_id"):
        return [song_service.get_song_by_internal_id(song_id) for song_id in sanitized]
    if hasattr(song_service, "get_all_songs"):
        all_songs = song_service.get_all_songs()
        by_id = {int(song.internal_song_id): song for song in all_songs}
        return [by_id.get(song_id) for song_id in sanitized if by_id.get(song_id) is not None]
    return []


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
        presets = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
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


def _event_service_instance():
    if isinstance(event_service, type):
        return event_service()
    return event_service


def _resolve_exclusion_context(current_user: User, *, apply_meta_exclusions: bool = True) -> dict:
    server_defaults = sorted({int(song_id) for song_id in META_SONG_IDS if int(song_id) > 0})
    user_excluded = sorted({int(song_id) for song_id in (getattr(current_user, "excluded_song_ids", None) or []) if int(song_id) > 0})
    effective = sorted(set(server_defaults) | set(user_excluded))
    return {
        "server_meta_song_ids": server_defaults,
        "user_excluded_song_ids": user_excluded,
        "effective_song_ids": effective,
        "is_active": bool(effective) and apply_meta_exclusions,
    }


def _filtered_user_screenshots(
    user_id: int,
    current_user: User,
    *,
    difficulty: str | None = None,
    live_type: str | None = None,
    include_meta: bool = False,
):
    screenshots = _get_user_screenshots_or_404(user_id)
    context = _resolve_exclusion_context(current_user, apply_meta_exclusions=not include_meta)
    filtered = list(screenshots)
    if not include_meta:
        filtered = filter_excluded_songs(
            filtered,
            excluded_song_ids=set(context["effective_song_ids"]),
        )
    filtered = filter_stats_plays(filtered, difficulty=difficulty, live_type=live_type)
    return filtered, context


def _song_names_for_ids(song_service: SongService, server: str, song_ids: Iterable[int]) -> dict[int, str]:
    sanitized = sorted({int(song_id) for song_id in song_ids if int(song_id) > 0})
    if not sanitized:
        return {}
    songs = _songs_by_internal_ids(song_service, sanitized)
    by_id = {int(song.internal_song_id): song for song in songs}
    return {
        song_id: _song_display_name(by_id.get(song_id), server, fallback_id=song_id)
        for song_id in sanitized
    }


class _ImageUrlResolver:
    def __init__(self, user_id: int, user: User | None, screenshots: list | None = None):
        self.user_id = user_id
        self.user = user
        self._storage = UploadStorageService()
        self._scan_service = ScanService()
        self._filename_to_screenshot_id: dict[str, int] = {}
        if screenshots:
            self._populate_filename_map(screenshots)

    def _populate_filename_map(self, screenshots: list):
        for screenshot in screenshots:
            filename = str(getattr(screenshot, "filename", "") or "").strip()
            screenshot_id = getattr(screenshot, "id", None)
            if filename and screenshot_id:
                self._filename_to_screenshot_id[filename] = int(screenshot_id)

    def _ensure_filename_map(self):
        if self._filename_to_screenshot_id:
            return
        screenshots = _screenshot_service_instance().get_screenshots_by_user(self.user_id)
        self._populate_filename_map(screenshots)

    def _server_folder_candidate(self, filename: str) -> Path | None:
        if not self.user or getattr(self.user, "screenshots_source", "local") != "server_folder":
            return None
        root = str(getattr(self.user, "screenshots_path", "") or "").strip()
        if not root:
            return None
        candidate = Path(root).expanduser() / Path(filename).name
        if candidate.exists() and candidate.is_file():
            return candidate
        return None

    def resolve(self, filename: str | None) -> str | None:
        if not filename:
            return None
        safe_name = str(filename)

        if self._storage.resolve_user_file(self.user_id, safe_name) is not None:
            return f"/api/users/{self.user_id}/uploads/{safe_name}"

        server_candidate = self._server_folder_candidate(safe_name)
        scan_candidate = self._scan_service.find_success_image_path(safe_name)
        if server_candidate is None and scan_candidate is None:
            return None

        self._ensure_filename_map()
        screenshot_id = self._filename_to_screenshot_id.get(safe_name)
        if screenshot_id:
            return f"/api/users/{self.user_id}/screenshots/{screenshot_id}/image"
        return None


def _with_image_url(image_resolver: _ImageUrlResolver, meta: dict | None):
    if not meta:
        return None
    payload = dict(meta)
    payload["image_url"] = image_resolver.resolve(payload.get("filename"))
    return payload


def _log_route_timing(route_name: str, started_at: float) -> None:
    elapsed_ms = (perf_counter() - started_at) * 1000.0
    logger.debug("route={} elapsed_ms={:.2f}", route_name, elapsed_ms)


def _parse_event_boundary(value, server: str):
    timestamp_ms = parse_event_timestamp_ms(value, language=server)
    if timestamp_ms is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).date()
    except (ValueError, OSError):
        return None


def _resolve_event_range(event_id: int, server: str):
    event = _event_service_instance().get_event_by_event_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")
    start = _parse_event_boundary(getattr(event, "event_start_at", None), server)
    end = _parse_event_boundary(getattr(event, "event_end_at", None), server)
    if start is None or end is None:
        raise HTTPException(status_code=400, detail="Event dates not found in repo")
    return event, start, end


def _range_for_scope(scope: str, anchor: date):
    if scope == "weekly":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if scope == "monthly":
        start = anchor.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_month = start.replace(month=start.month + 1, day=1)
        return start, next_month - timedelta(days=1)
    if scope == "seasonal":
        return anchor - timedelta(days=89), anchor
    if scope == "yearly":
        return anchor.replace(month=1, day=1), anchor.replace(month=12, day=31)
    return anchor, anchor


@router.get("/users/{user_id}/stats", response_model=StatsResponse)
def get_user_stats(
    user_id: int,
    difficulty: str | None = Query(None),
    live_type: str | None = Query(None),
    include_meta: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    started_at = perf_counter()
    try:
        user_id = assert_user_scope(user_id, current_user)
        screenshots, exclusion_context = _filtered_user_screenshots(
            user_id,
            current_user,
            difficulty=difficulty,
            live_type=live_type,
            include_meta=include_meta,
        )
        song_service = _song_service_instance()
        image_resolver = _ImageUrlResolver(user_id, current_user, screenshots)

        summary = compute_general_summary(screenshots)
        top_songs = compute_top_songs(screenshots, n=8)
        recent = compute_recent_plays(screenshots, n=5)
        referenced_song_ids = [int(item.get("song_id", 0)) for item in [*top_songs, *recent]]
        song_names = _song_names_for_ids(song_service, current_user.server, referenced_song_ids)
        for item in top_songs:
            song_id = int(item.get("song_id", 0))
            item["song_name"] = song_names.get(song_id, f"Song {song_id}")
        for item in recent:
            song_id = int(item.get("song_id", 0))
            item["song_name"] = song_names.get(song_id, f"Song {song_id}")
            item["image_url"] = image_resolver.resolve(item.get("filename"))

        return StatsResponse(
            summary=summary,
            top_songs=top_songs,
            recent=recent,
            exclusion_context=exclusion_context,
        )
    finally:
        _log_route_timing("stats.overview", started_at)


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


@router.get("/users/{user_id}/stats/songs/rankings", response_model=SongRankingsResponse)
def get_user_song_rankings(
    user_id: int,
    difficulty: str | None = Query(None),
    live_type: str | None = Query(None),
    include_meta: bool = Query(False),
    sort_by: str = Query("play_count"),
    limit: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    screenshots, exclusion_context = _filtered_user_screenshots(
        user_id,
        current_user,
        difficulty=difficulty,
        live_type=live_type,
        include_meta=include_meta,
    )
    song_service = _song_service_instance()
    image_resolver = _ImageUrlResolver(user_id, current_user, screenshots)
    song_ids = [int(getattr(item, "song_id", 0) or 0) for item in screenshots]
    song_names = _song_names_for_ids(song_service, current_user.server, song_ids)
    rankings = compute_song_rankings(
        screenshots,
        song_names=song_names,
        sort_by=sort_by,
        limit=limit,
    )
    for item in rankings:
        item["latest_play"] = _with_image_url(image_resolver, item.get("latest_play"))
    return SongRankingsResponse(
        sort_by=sort_by,
        difficulty=difficulty.strip().lower() if isinstance(difficulty, str) and difficulty.strip() else None,
        live_type=live_type.strip().lower() if isinstance(live_type, str) and live_type.strip() else None,
        items=rankings,
        exclusion_context=exclusion_context,
    )


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
    exclusion_context = _resolve_exclusion_context(current_user)
    song = song_service.get_song_by_internal_id(song_id)
    if not song:
        raise HTTPException(status_code=404, detail=f"Song not found: {song_id}")

    song_plays = screenshot_service.get_screenshots_by_song(user_id, song_id)
    image_resolver = _ImageUrlResolver(user_id, current_user)
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
        detail_payload = compute_difficulty_detail(
            plays,
            song_length_seconds=_song_length_seconds(song),
            session_gap_minutes=session_gap_minutes,
        )
        for field_name in ["first_played", "last_played", "first_fc", "last_fc", "first_ap", "last_ap"]:
            detail_payload[field_name] = _with_image_url(image_resolver, detail_payload.get(field_name))
        detail = SongDifficultyDetail(**detail_payload)

    return SongStatsResponse(
        song_id=song_id,
        requested_difficulty=normalized_difficulty,
        difficulty_overview=[
            SongDifficultyOverviewItem(
                difficulty=item.difficulty,
                total_plays=item.total_plays,
                first_played=_with_image_url(image_resolver, item.first_played.model_dump()) if item.first_played else None,
                estimated_time_played_seconds=item.estimated_time_played_seconds,
                estimated_time_played_human=item.estimated_time_played_human,
            )
            for item in overview
        ],
        detail=detail,
        exclusion_context=exclusion_context,
    )


@router.get("/users/{user_id}/stats/milestones", response_model=StatsMilestonesResponse)
def get_user_stats_milestones(
    user_id: int,
    difficulty: str | None = Query(None),
    live_type: str | None = Query(None),
    include_meta: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    started_at = perf_counter()
    try:
        user_id = assert_user_scope(user_id, current_user)
        screenshots, _ = _filtered_user_screenshots(
            user_id,
            current_user,
            difficulty=difficulty,
            live_type=live_type,
            include_meta=include_meta,
        )
        image_resolver = _ImageUrlResolver(user_id, current_user, screenshots)
        payload = compute_milestones(screenshots)
        for item in payload.get("milestones", []):
            item["meta"] = _with_image_url(image_resolver, item.get("meta"))
        return StatsMilestonesResponse(**payload)
    finally:
        _log_route_timing("stats.milestones", started_at)


@router.get("/users/{user_id}/stats/activity", response_model=StatsActivityRangeResponse)
def get_user_stats_activity(
    user_id: int,
    preset: str = Query("30d"),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    difficulty: str | None = Query(None),
    live_type: str | None = Query(None),
    include_meta: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    screenshots, _ = _filtered_user_screenshots(
        user_id,
        current_user,
        difficulty=difficulty,
        live_type=live_type,
        include_meta=include_meta,
    )
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
    difficulty: str | None = Query(None),
    live_type: str | None = Query(None),
    include_meta: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    screenshots, _ = _filtered_user_screenshots(
        user_id,
        current_user,
        difficulty=difficulty,
        live_type=live_type,
        include_meta=include_meta,
    )

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
    difficulty: str | None = Query(None),
    live_type: str | None = Query(None),
    include_meta: bool = Query(False),
    session_gap_minutes: int = Query(45, ge=5, le=240),
    current_user: User = Depends(get_current_user),
):
    song_service = _song_service_instance()
    user_id = assert_user_scope(user_id, current_user)
    screenshots, _ = _filtered_user_screenshots(
        user_id,
        current_user,
        difficulty=difficulty,
        live_type=live_type,
        include_meta=include_meta,
    )
    range_start, range_end = _resolve_date_range(preset, from_date, to_date)

    song_ids = {
        int(getattr(screenshot, "song_id", 0))
        for screenshot in screenshots
        if int(getattr(screenshot, "song_id", 0)) > 0
    }
    song_map = {int(song.internal_song_id): song for song in _songs_by_internal_ids(song_service, list(song_ids))}
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

    for item in payload.get("practice_periods", []):
        song_id = int(item.get("song_id", 0))
        song = song_map.get(song_id)
        item["song_name"] = _song_display_name(song, current_user.server, fallback_id=song_id)
    repetition = payload.get("repetition", {})
    for key in ["most_looped_songs", "revisited_after_break"]:
        for item in repetition.get(key, []):
            song_id = int(item.get("song_id", 0))
            song = song_map.get(song_id)
            item["song_name"] = _song_display_name(song, current_user.server, fallback_id=song_id)

    return StatsInsightsResponse(**payload)


@router.get("/users/{user_id}/stats/progression", response_model=ProgressionResponse)
def get_user_stats_progression(
    user_id: int,
    scope: str = Query("monthly"),
    count: int = Query(6, ge=2, le=24),
    anchor_date: str | None = Query(None),
    difficulty: str | None = Query(None),
    live_type: str | None = Query(None),
    include_meta: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    started_at = perf_counter()
    try:
        user_id = assert_user_scope(user_id, current_user)
        screenshots, exclusion_context = _filtered_user_screenshots(
            user_id,
            current_user,
            difficulty=difficulty,
            live_type=live_type,
            include_meta=include_meta,
        )
        allowed_scopes = {"weekly", "monthly", "yearly"}
        if scope not in allowed_scopes:
            raise HTTPException(status_code=400, detail=f"Invalid scope: {scope}")
        anchor = _parse_iso_date(anchor_date, "anchor_date") if anchor_date else datetime.now(timezone.utc).date()
        payload = compute_progression(screenshots, scope=scope, anchor=anchor, count=count)
        return ProgressionResponse(**payload, exclusion_context=exclusion_context)
    finally:
        _log_route_timing("stats.progression", started_at)


@router.get("/users/{user_id}/stats/events/{event_id}", response_model=EventStatsResponse)
@router.get("/users/{user_id}/stats/event-focus/{event_id}", response_model=EventStatsResponse)
def get_user_event_stats(
    user_id: int,
    event_id: int,
    difficulty: str | None = Query(None),
    live_type: str | None = Query(None),
    include_meta: bool = Query(False),
    session_gap_minutes: int = Query(45, ge=5, le=240),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    screenshots, exclusion_context = _filtered_user_screenshots(
        user_id,
        current_user,
        difficulty=difficulty,
        live_type=live_type,
        include_meta=include_meta,
    )
    event, start, end = _resolve_event_range(event_id, current_user.server)
    song_service = _song_service_instance()
    song_ids = [int(getattr(item, "song_id", 0) or 0) for item in screenshots]
    song_map = _song_names_for_ids(song_service, current_user.server, song_ids)
    payload = compute_event_stats(
        screenshots,
        song_names=song_map,
        event_name=getattr(event, "event_name", {}).get(current_user.server) if isinstance(getattr(event, "event_name", None), dict) else getattr(event, "event_name", None),
        event_type=getattr(event, "event_type", None),
        event_id=event_id,
        from_date=start,
        to_date=end,
        session_gap_minutes=session_gap_minutes,
    )
    return EventStatsResponse(**payload, exclusion_context=exclusion_context)


@router.get("/users/{user_id}/stats/songs/{song_id}/journey", response_model=SongJourneyResponse)
def get_user_song_journey(
    user_id: int,
    song_id: int,
    difficulty: str | None = Query(None),
    session_gap_minutes: int = Query(45, ge=5, le=240),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    song = _song_service_instance().get_song_by_internal_id(song_id)
    if not song:
        raise HTTPException(status_code=404, detail=f"Song not found: {song_id}")
    all_song_plays = _screenshot_service_instance().get_screenshots_by_song(user_id, song_id)
    if not all_song_plays:
        raise HTTPException(status_code=404, detail=f"No plays found for song {song_id}")
    target_difficulty = difficulty.strip().lower() if isinstance(difficulty, str) and difficulty.strip() else None
    if target_difficulty is None:
        grouped: dict[str, int] = {}
        for play in all_song_plays:
            diff = str(getattr(play, "difficulty", "")).strip().lower()
            if diff:
                grouped[diff] = grouped.get(diff, 0) + 1
        if not grouped:
            raise HTTPException(status_code=404, detail="No playable difficulties found")
        target_difficulty = sorted(grouped.items(), key=lambda item: (-item[1], _difficulty_sort_key(item[0])))[0][0]
    plays = _screenshot_service_instance().get_screenshots_by_song(user_id, song_id, target_difficulty)
    image_resolver = _ImageUrlResolver(user_id, current_user)
    payload = compute_song_journey(
        plays,
        song_id=song_id,
        song_name=_song_display_name(song, current_user.server, fallback_id=song_id),
        difficulty=target_difficulty,
        song_length_seconds=_song_length_seconds(song),
        session_gap_minutes=session_gap_minutes,
    )
    for field_name in ["first_played", "first_fc", "first_ap"]:
        payload[field_name] = _with_image_url(image_resolver, payload.get(field_name))
    for item in payload.get("timeline", []):
        item["image_url"] = image_resolver.resolve(item.get("filename"))
    return SongJourneyResponse(**payload, exclusion_context=_resolve_exclusion_context(current_user))


@router.get("/users/{user_id}/stats/recap", response_model=RecapResponse)
def get_user_recap(
    user_id: int,
    scope: str = Query("monthly"),
    anchor_date: str | None = Query(None),
    event_id: int | None = Query(None),
    difficulty: str | None = Query(None),
    live_type: str | None = Query(None),
    include_meta: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    started_at = perf_counter()
    try:
        user_id = assert_user_scope(user_id, current_user)
        screenshots, exclusion_context = _filtered_user_screenshots(
            user_id,
            current_user,
            difficulty=difficulty,
            live_type=live_type,
            include_meta=include_meta,
        )
        today = datetime.now(timezone.utc).date()
        anchor = _parse_iso_date(anchor_date, "anchor_date") if anchor_date else today
        event_name = None
        if scope == "event":
            if event_id is None:
                raise HTTPException(status_code=400, detail="event_id is required for event scope")
            event, from_date, to_date = _resolve_event_range(event_id, current_user.server)
            event_name = getattr(event, "event_name", {}).get(current_user.server) if isinstance(getattr(event, "event_name", None), dict) else getattr(event, "event_name", None)
        else:
            if scope not in {"weekly", "monthly", "seasonal", "yearly"}:
                raise HTTPException(status_code=400, detail=f"Invalid scope: {scope}")
            from_date, to_date = _range_for_scope(scope, anchor)
        compare_from = from_date - timedelta(days=(to_date - from_date).days + 1)
        compare_to = from_date - timedelta(days=1)
        compare_screenshots = [
            play
            for play in screenshots
            if isinstance(getattr(play, "timestamp", None), datetime)
            and compare_from <= getattr(play, "timestamp").date() <= compare_to
        ]
        song_service = _song_service_instance()
        image_resolver = _ImageUrlResolver(user_id, current_user, screenshots)
        song_ids = [int(getattr(item, "song_id", 0) or 0) for item in screenshots]
        song_map = _song_names_for_ids(song_service, current_user.server, song_ids)
        payload = compute_recap(
            screenshots,
            scope=scope,
            from_date=from_date,
            to_date=to_date,
            song_names=song_map,
            compare_screenshots=compare_screenshots,
            event_id=event_id,
            event_name=event_name,
        )
        for song_key in ["top_songs", "new_songs", "most_practiced"]:
            for item in payload.get(song_key, []):
                item["latest_play"] = _with_image_url(image_resolver, item.get("latest_play"))
        for highlight in payload.get("highlights", []):
            highlight["screenshot"] = _with_image_url(image_resolver, highlight.get("screenshot"))
        return RecapResponse(**payload, exclusion_context=exclusion_context)
    finally:
        _log_route_timing("stats.recap", started_at)
