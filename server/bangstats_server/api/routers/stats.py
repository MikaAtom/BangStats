from fastapi import APIRouter, HTTPException

from bangstats_server.api.schemas.stats import StatsResponse
from bangstats_server.core.services.screenshot import ScreenshotService
from bangstats_server.core.services.song import SongService
from bangstats_server.core.services.stats import (
    compute_general_summary,
    compute_recent_plays,
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
