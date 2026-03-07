from fastapi import APIRouter, HTTPException, Query

from bangstats_server.api.schemas.stats import (
    SongDifficultyDetail,
    SongDifficultyOverviewItem,
    SongSearchItem,
    SongSearchResponse,
    SongStatsResponse,
    StatsResponse,
)
from bangstats_server.core.services.screenshot import ScreenshotService
from bangstats_server.core.services.song import SongService
from bangstats_server.core.services.stats import (
    compute_difficulty_detail,
    compute_general_summary,
    compute_recent_plays,
    compute_song_difficulty_overview,
    compute_top_songs,
)

router = APIRouter()
screenshot_service = ScreenshotService()
song_service = SongService()


def _resolve_song_name(song_id: int, server: str) -> str:
    song = song_service.get_song_by_internal_id(song_id)
    if not song or not isinstance(song.name, dict):
        return f"Song {song_id}"
    return song.name.get(server) or song.name.get("en") or f"Song {song_id}"


def _song_display_name(song, server: str) -> str:
    if not song or not isinstance(song.name, dict):
        return f"Song {getattr(song, 'internal_song_id', '?')}"
    return (
        song.name.get(server)
        or song.name.get("en")
        or next((value for value in song.name.values() if value), "")
        or f"Song {song.internal_song_id}"
    )


def _search_songs_case_insensitive(query: str) -> list:
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


@router.get("/users/{user_id}/stats", response_model=StatsResponse)
def get_user_stats(user_id: int):
    screenshots = screenshot_service.get_screenshots_by_user(user_id)
    if not screenshots:
        raise HTTPException(status_code=404, detail="No screenshots for this user")

    summary = compute_general_summary(screenshots)
    top_songs = compute_top_songs(screenshots, n=5)
    recent = compute_recent_plays(screenshots, n=5)

    enriched_top = []
    for row in top_songs:
        enriched_top.append(
            {
                **row,
                "song_name": _resolve_song_name(row["song_id"], "en"),
            }
        )

    enriched_recent = []
    for row in recent:
        enriched_recent.append(
            {
                **row,
                "song_name": _resolve_song_name(row["song_id"], "en"),
            }
        )

    return StatsResponse(
        summary=summary,
        top_songs=enriched_top,
        recent=enriched_recent,
    )


@router.get("/users/{user_id}/stats/songs/search", response_model=SongSearchResponse)
def search_user_stat_songs(
    user_id: int,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    server: str = Query("en", min_length=2, max_length=2),
):
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
    server: str = Query("en", min_length=2, max_length=2),
):
    song = song_service.get_song_by_internal_id(song_id)
    if not song:
        raise HTTPException(status_code=404, detail=f"Song not found: {song_id}")

    song_name = _song_display_name(song, server)
    song_plays = screenshot_service.get_screenshots_by_song(user_id, song_id)
    if not song_plays:
        raise HTTPException(status_code=404, detail=f"No plays found for {song_name}")

    overview_map = compute_song_difficulty_overview(song_plays)
    overview = [
        SongDifficultyOverviewItem(
            difficulty=diff,
            total_plays=int(payload.get("total_plays", 0)),
            first_played=payload.get("first_played"),
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
                detail=f"No plays found for {song_name} [{normalized_difficulty}]",
            )
        detail = SongDifficultyDetail(**compute_difficulty_detail(plays))

    return SongStatsResponse(
        song_id=song_id,
        song_name=song_name,
        requested_difficulty=normalized_difficulty,
        difficulty_overview=overview,
        detail=detail,
    )
