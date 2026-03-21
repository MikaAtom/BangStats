from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse

from bangstats_server.api.dependencies import assert_user_scope, get_current_user
from bangstats_server.api.schemas.scans import ScanJobResponse, UploadUsageResponse
from bangstats_server.api.schemas.sync import CountsResponse, SyncJobResponse
from bangstats_server.api.schemas.webui import (
    DashboardResponse,
    ExportScreenshotReference,
    MetaSongConfigResponse,
    ScreenshotItemResponse,
    ScreenshotListResponse,
    UserDataExportResponse,
    UserDataImportRequest,
    UserDataImportResponse,
    UploadFileItemResponse,
    UploadFileListResponse,
    ThumbnailWarmItemResult,
    ThumbnailWarmRequest,
    ThumbnailWarmResponse,
)
from bangstats_server.core.config import BANGSTATS_ENV, DB_PATH
from bangstats_server.core.config import META_SONG_IDS
from bangstats_server.core.db.models.user import User
from bangstats_server.core.services.event import EventService
from bangstats_server.core.services.scan import ScanService
from bangstats_server.core.services.scan_job import ScanJobService
from bangstats_server.core.services.screenshot import ScreenshotService
from bangstats_server.core.services.song import SongService
from bangstats_server.core.services.sync_job import SyncJobService
from bangstats_server.core.services.image_thumbnail import try_thumbnail_path
from bangstats_server.core.services.upload_storage import UploadStorageService
from bangstats_server.core.services.user import UserService
from bangstats_server.core.sync import get_db_counts
from bangstats_server.core.services.stats import compute_general_summary, filter_excluded_songs, filter_stats_plays
from bangstats_server.core.utils.chart_meta import chart_level_for_difficulty

router = APIRouter()

_SCAN_ERRORS_CACHE_TTL_SECONDS = 10.0
_THUMB_WARM_MAX_WORKERS = 4


def _normalize_image_variant(variant: str | None) -> str | None:
    if variant is None or not str(variant).strip():
        return None
    lowered = str(variant).strip().lower()
    if lowered == "thumb":
        return "thumb"
    raise HTTPException(status_code=400, detail="Invalid image variant; use 'thumb' or omit.")


def _image_file_response(path: Path, *, variant: str | None) -> FileResponse:
    v = _normalize_image_variant(variant)
    if v == "thumb":
        thumb = try_thumbnail_path(path)
        if thumb is not None:
            return FileResponse(thumb, media_type="image/jpeg")
    return FileResponse(path)


_scan_errors_cache: dict[str, object] = {
    "expires_at": 0.0,
    "value": {"total": 0, "errors": {}, "error_files": {}},
}


def _dedupe_ints_preserve_order(values: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _dedupe_strs_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = str(v)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _cached_scan_errors(scan_service: ScanService):
    now = monotonic()
    expires_at = float(_scan_errors_cache.get("expires_at", 0.0) or 0.0)
    if expires_at > now:
        return _scan_errors_cache.get("value")
    value = scan_service.list_error_files()
    _scan_errors_cache["value"] = value
    _scan_errors_cache["expires_at"] = now + _SCAN_ERRORS_CACHE_TTL_SECONDS
    return value


def _song_name_map(server: str, song_ids: set[int] | None = None) -> dict[int, str]:
    names: dict[int, str] = {}
    song_service = SongService()
    songs = []
    if song_ids and hasattr(song_service, "get_songs_by_internal_ids"):
        songs = song_service.get_songs_by_internal_ids(sorted(song_ids))
    if not songs:
        songs = song_service.get_all_songs()
    for song in songs:
        if isinstance(song.name, dict):
            names[int(song.internal_song_id)] = (
                song.name.get(server)
                or song.name.get("en")
                or next((value for value in song.name.values() if value), "")
                or f"Song {song.internal_song_id}"
            )
        else:
            names[int(song.internal_song_id)] = f"Song {song.internal_song_id}"
    return names


def _songs_by_internal_id_map(song_ids: set[int] | None) -> dict[int, object]:
    """Map internal_song_id -> Song row for level/name resolution."""
    song_service = SongService()
    songs: list = []
    if song_ids and hasattr(song_service, "get_songs_by_internal_ids"):
        songs = song_service.get_songs_by_internal_ids(sorted(song_ids))
    if not songs:
        songs = song_service.get_all_songs()
    return {int(getattr(s, "internal_song_id", 0) or 0): s for s in songs if int(getattr(s, "internal_song_id", 0) or 0) > 0}


def _resolve_server_folder_image_path(user: User | None, filename: str | None) -> Path | None:
    if not user or not filename:
        return None
    if getattr(user, "screenshots_source", "local") != "server_folder":
        return None
    root = str(getattr(user, "screenshots_path", "") or "").strip()
    if not root:
        return None
    safe_name = Path(filename).name
    if not safe_name:
        return None
    candidate = Path(root).expanduser() / safe_name
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def _resolve_screenshot_image_path(user_id: int, user: User | None, filename: str | None, scan_service: ScanService) -> Path | None:
    if not filename:
        return None
    storage_path = UploadStorageService().resolve_user_file(user_id, filename)
    if storage_path:
        return storage_path
    server_folder_path = _resolve_server_folder_image_path(user, filename)
    if server_folder_path:
        return server_folder_path
    success_path = scan_service.find_success_image_path(filename)
    if success_path:
        return success_path
    return None


def _screenshot_item(
    screenshot,
    *,
    user_id: int,
    user: User,
    song_names: dict[int, str],
    scan_service: ScanService,
    songs_by_id: dict[int, object] | None = None,
) -> ScreenshotItemResponse:
    image_path = _resolve_screenshot_image_path(user_id, user, getattr(screenshot, "filename", None), scan_service)
    image_url = None
    if image_path is not None:
        image_url = f"/api/users/{user_id}/screenshots/{int(screenshot.id)}/image"
    perfect = int(getattr(screenshot, "perfect", 0) or 0)
    great = int(getattr(screenshot, "great", 0) or 0)
    good = int(getattr(screenshot, "good", 0) or 0)
    bad = int(getattr(screenshot, "bad", 0) or 0)
    miss = int(getattr(screenshot, "miss", 0) or 0)
    total_notes = perfect + great + good + bad + miss
    accuracy = round((perfect / total_notes) * 100, 2) if total_notes > 0 else 0.0
    fast_raw = getattr(screenshot, "fast", None)
    slow_raw = getattr(screenshot, "slow", None)
    fast = int(fast_raw) if fast_raw is not None else 0
    slow = int(slow_raw) if slow_raw is not None else 0
    max_combo = int(getattr(screenshot, "max_combo", 0) or 0)
    sid = int(screenshot.song_id)
    level = None
    if songs_by_id:
        song_row = songs_by_id.get(sid)
        level = chart_level_for_difficulty(getattr(song_row, "levels", None) if song_row else None, str(screenshot.difficulty))

    return ScreenshotItemResponse(
        id=int(screenshot.id or 0),
        filename=screenshot.filename,
        song_id=sid,
        song_name=song_names.get(sid),
        difficulty=screenshot.difficulty,
        live_type=screenshot.live_type,
        score=int(screenshot.score),
        accuracy=accuracy,
        perfect=perfect,
        great=great,
        good=good,
        bad=bad,
        miss=miss,
        fast=fast,
        slow=slow,
        max_combo=max_combo,
        level=level,
        full_combo=bool(screenshot.full_combo),
        all_perfect=bool(screenshot.all_perfect),
        anomaly=bool(screenshot.anomaly),
        timestamp=screenshot.timestamp,
        image_available=image_path is not None,
        image_url=image_url,
    )


def _screenshot_sort_key(
    screenshot,
    *,
    sort_by: str,
    song_names: dict[int, str],
):
    if sort_by == "score":
        return int(getattr(screenshot, "score", 0) or 0)
    if sort_by == "accuracy":
        perfect = int(getattr(screenshot, "perfect", 0) or 0)
        great = int(getattr(screenshot, "great", 0) or 0)
        good = int(getattr(screenshot, "good", 0) or 0)
        bad = int(getattr(screenshot, "bad", 0) or 0)
        miss = int(getattr(screenshot, "miss", 0) or 0)
        total_notes = perfect + great + good + bad + miss
        return (perfect / total_notes) if total_notes > 0 else 0.0
    if sort_by == "song_name":
        return song_names.get(int(getattr(screenshot, "song_id", 0) or 0), "")
    return getattr(screenshot, "timestamp", datetime.min)


def _sync_job_response(job) -> SyncJobResponse:
    return SyncJobResponse(
        id=int(job.id or 0),
        server=job.server,
        status=job.status,
        requested_by_user_id=job.requested_by_user_id,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        songs=job.songs,
        events=job.events,
        bands=job.bands,
        error_message=job.error_message,
    )


def _scan_job_response(job) -> ScanJobResponse:
    payload = jsonable_encoder(job)
    return ScanJobResponse(**payload)


def _meta_song_config_for_user(user: User) -> MetaSongConfigResponse:
    user_excluded = sorted({int(song_id) for song_id in (getattr(user, "excluded_song_ids", None) or []) if int(song_id) > 0})
    server_defaults = sorted({int(song_id) for song_id in META_SONG_IDS if int(song_id) > 0})
    return MetaSongConfigResponse(
        server_meta_song_ids=server_defaults,
        user_excluded_song_ids=user_excluded,
        effective_song_ids=sorted(set(server_defaults) | set(user_excluded)),
    )


def _apply_screenshot_filters(
    screenshots,
    *,
    current_user: User,
    song_names: dict[int, str],
    difficulty: str | None = None,
    live_type: str | None = None,
    song_query: str | None = None,
    include_meta: bool = False,
    from_date: str | None = None,
    to_date: str | None = None,
):
    filtered = list(screenshots)
    if not include_meta:
        config = _meta_song_config_for_user(current_user)
        filtered = filter_excluded_songs(filtered, excluded_song_ids=set(config.effective_song_ids))
    filtered = filter_stats_plays(filtered, difficulty=difficulty, live_type=live_type)
    if song_query:
        lowered_query = song_query.strip().lower()
        if lowered_query:
            filtered = [
                screenshot
                for screenshot in filtered
                if lowered_query in song_names.get(int(getattr(screenshot, "song_id", 0) or 0), "").lower()
            ]
    if from_date or to_date:
        if not from_date or not to_date:
            raise HTTPException(status_code=400, detail="Both from_date and to_date are required")
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
        filtered = [
            screenshot
            for screenshot in filtered
            if isinstance(getattr(screenshot, "timestamp", None), datetime)
            and start <= screenshot.timestamp.date() <= end
        ]
    return filtered


def _encoded_user_payload(user: User) -> dict:
    payload = jsonable_encoder(user)
    if payload.get("excluded_song_ids") is None:
        payload["excluded_song_ids"] = []
    return payload


@router.get("/users/{user_id}/dashboard", response_model=DashboardResponse)
def get_dashboard(
    user_id: int,
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    user = UserService().get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    screenshot_service = ScreenshotService()
    scan_service = ScanService()
    screenshots = screenshot_service.get_screenshots_by_user(user_id)
    recent_screenshots = sorted(
        screenshots,
        key=lambda item: item.timestamp,
        reverse=True,
    )[:8]
    recent_song_ids = {
        int(getattr(screenshot, "song_id", 0) or 0)
        for screenshot in recent_screenshots
        if int(getattr(screenshot, "song_id", 0) or 0) > 0
    }
    song_names = _song_name_map(user.server, recent_song_ids)
    songs_by_id = _songs_by_internal_id_map(recent_song_ids)

    counts = get_db_counts()
    current_event = EventService().get_current_event(language=user.server)
    upload_usage = UploadStorageService().get_usage(user_id)
    scan_jobs = ScanJobService().list_jobs_for_user(user_id=user_id, limit=8, status=None)
    sync_jobs = SyncJobService().list_jobs(limit=8, status=None)

    stats_payload = None
    if screenshots:
        stats_payload = compute_general_summary(screenshots)
    legacy_db_path = DB_PATH.parent.parent / "_bangstats.db"
    runtime = {
        "db_path": str(DB_PATH),
        "env": BANGSTATS_ENV,
        "legacy_db_path": str(legacy_db_path),
        "legacy_db_exists": legacy_db_path.exists(),
        "server": user.server,
    }
    current_event_status = (
        f"Current event resolved for server {user.server}."
        if current_event is not None
        else f"No event found for server {user.server} at current UTC time using {DB_PATH}."
    )

    return DashboardResponse(
        user=_encoded_user_payload(user),
        counts=CountsResponse(songs=counts[0], events=counts[1], bands=counts[2]),
        current_event=jsonable_encoder(current_event) if current_event is not None else None,
        current_event_status=current_event_status,
        runtime=runtime,
        upload_usage=UploadUsageResponse(
            file_count=int(upload_usage["file_count"]),
            total_size_mb=float(upload_usage["total_size_mb"]),
            oldest_file_age_days=float(upload_usage["oldest_file_age_days"]),
        ),
        stats=stats_payload,
        scan_jobs=[_scan_job_response(job) for job in scan_jobs],
        sync_jobs=[_sync_job_response(job) for job in sync_jobs if job.requested_by_user_id in {None, user_id}],
        scan_errors=_cached_scan_errors(scan_service),
        recent_screenshots=[
            _screenshot_item(
                screenshot,
                user_id=user_id,
                user=user,
                song_names=song_names,
                scan_service=scan_service,
                songs_by_id=songs_by_id,
            )
            for screenshot in recent_screenshots
        ],
    )


@router.get("/users/{user_id}/screenshots", response_model=ScreenshotListResponse)
def list_screenshots(
    user_id: int,
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    song_id: int | None = Query(None, ge=1),
    song_query: str | None = Query(None),
    sort_by: str = Query("timestamp", pattern="^(timestamp|song_name|score|accuracy)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    difficulty: str | None = Query(None),
    live_type: str | None = Query(None),
    include_meta: bool = Query(False),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    screenshot_service = ScreenshotService()
    scan_service = ScanService()

    if song_id is not None:
        screenshots = screenshot_service.get_screenshots_by_song(
            user_id,
            song_id,
            difficulty.strip().lower() if difficulty else None,
        )
    else:
        screenshots = screenshot_service.get_screenshots_by_user(user_id)

    song_ids = {
        int(getattr(screenshot, "song_id", 0) or 0)
        for screenshot in screenshots
        if int(getattr(screenshot, "song_id", 0) or 0) > 0
    }
    song_names = _song_name_map(current_user.server, song_ids)
    songs_by_id = _songs_by_internal_id_map(song_ids)

    screenshots = _apply_screenshot_filters(
        screenshots,
        current_user=current_user,
        song_names=song_names,
        difficulty=difficulty,
        live_type=live_type,
        song_query=song_query,
        include_meta=include_meta,
        from_date=from_date,
        to_date=to_date,
    )

    ordered = sorted(
        screenshots,
        key=lambda item: _screenshot_sort_key(item, sort_by=sort_by, song_names=song_names),
        reverse=sort_order == "desc",
    )
    page = ordered[offset : offset + limit]
    return ScreenshotListResponse(
        total=len(ordered),
        limit=limit,
        offset=offset,
        items=[
            _screenshot_item(
                screenshot,
                user_id=user_id,
                user=current_user,
                song_names=song_names,
                scan_service=scan_service,
                songs_by_id=songs_by_id,
            )
            for screenshot in page
        ],
    )


def _thumbnail_url_for_warm_unit(user_id: int, unit: dict) -> str:
    kind = str(unit.get("kind") or "")
    if kind == "screenshot":
        sid = int(unit["screenshot_id"])
        return f"/api/users/{user_id}/screenshots/{sid}/image?variant=thumb"
    if kind == "upload":
        fn = str(unit["filename"])
        return f"/api/users/{user_id}/uploads/{quote(fn, safe='')}/image?variant=thumb"
    et = str(unit["error_type"])
    jf = str(unit["json_filename"])
    return f"/api/scans/errors/{quote(et, safe='')}/{quote(jf, safe='')}/image?variant=thumb"


@router.post("/users/{user_id}/thumbnails/warm", response_model=ThumbnailWarmResponse)
def warm_thumbnails(
    user_id: int,
    body: ThumbnailWarmRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Pre-generate cached thumbnail JPEGs for many images in one request.

    The client can then fetch each ``thumbnail_url`` cheaply from disk cache.
    """
    user_id = assert_user_scope(user_id, current_user)
    owner = UserService().get_user_by_id(user_id)
    if not owner:
        raise HTTPException(status_code=404, detail="User not found")

    scan_service = ScanService()
    screenshot_service = ScreenshotService()
    storage = UploadStorageService()

    units: list[dict[str, object]] = []

    for sid in _dedupe_ints_preserve_order(body.screenshot_ids):
        if sid <= 0:
            units.append(
                {
                    "kind": "screenshot",
                    "screenshot_id": sid,
                    "filename": None,
                    "error_type": None,
                    "json_filename": None,
                    "path": None,
                    "detail": "Invalid screenshot id",
                }
            )
            continue
        shot = screenshot_service.get_screenshot_by_id(sid)
        if not shot or int(shot.user_id) != user_id:
            units.append(
                {
                    "kind": "screenshot",
                    "screenshot_id": sid,
                    "filename": None,
                    "error_type": None,
                    "json_filename": None,
                    "path": None,
                    "detail": "Screenshot not found",
                }
            )
            continue
        path = _resolve_screenshot_image_path(user_id, owner, shot.filename, scan_service)
        if path is None:
            units.append(
                {
                    "kind": "screenshot",
                    "screenshot_id": sid,
                    "filename": None,
                    "error_type": None,
                    "json_filename": None,
                    "path": None,
                    "detail": "Image file not found",
                }
            )
        else:
            units.append(
                {
                    "kind": "screenshot",
                    "screenshot_id": sid,
                    "filename": None,
                    "error_type": None,
                    "json_filename": None,
                    "path": path,
                    "detail": None,
                }
            )

    for raw_name in _dedupe_strs_preserve_order(body.upload_filenames):
        safe_name = Path(str(raw_name)).name
        if not safe_name:
            units.append(
                {
                    "kind": "upload",
                    "screenshot_id": None,
                    "filename": str(raw_name),
                    "error_type": None,
                    "json_filename": None,
                    "path": None,
                    "detail": "Invalid filename",
                }
            )
            continue
        path = storage.resolve_user_file(user_id, safe_name)
        if path is None:
            units.append(
                {
                    "kind": "upload",
                    "screenshot_id": None,
                    "filename": safe_name,
                    "error_type": None,
                    "json_filename": None,
                    "path": None,
                    "detail": "Uploaded file not found",
                }
            )
        else:
            units.append(
                {
                    "kind": "upload",
                    "screenshot_id": None,
                    "filename": safe_name,
                    "error_type": None,
                    "json_filename": None,
                    "path": path,
                    "detail": None,
                }
            )

    for ref in body.scan_errors:
        path = scan_service._find_error_image_path(ref.error_type, ref.json_filename)
        if path is None:
            units.append(
                {
                    "kind": "scan_error",
                    "screenshot_id": None,
                    "filename": None,
                    "error_type": ref.error_type,
                    "json_filename": ref.json_filename,
                    "path": None,
                    "detail": "Error image not found",
                }
            )
        else:
            units.append(
                {
                    "kind": "scan_error",
                    "screenshot_id": None,
                    "filename": None,
                    "error_type": ref.error_type,
                    "json_filename": ref.json_filename,
                    "path": path,
                    "detail": None,
                }
            )

    paths_to_warm: list[Path] = []
    for u in units:
        p = u.get("path")
        if isinstance(p, Path):
            paths_to_warm.append(p)

    warmed_paths: list[Path | None] = []
    if paths_to_warm:
        with ThreadPoolExecutor(max_workers=_THUMB_WARM_MAX_WORKERS) as pool:
            warmed_paths = list(pool.map(try_thumbnail_path, paths_to_warm))

    wi = 0
    results: list[ThumbnailWarmItemResult] = []
    warmed_count = 0
    failed_count = 0
    for u in units:
        kind = str(u["kind"])
        path = u.get("path")
        detail = u.get("detail")
        if not isinstance(path, Path):
            results.append(
                ThumbnailWarmItemResult(
                    kind=kind,  # type: ignore[arg-type]
                    screenshot_id=u.get("screenshot_id") if u.get("screenshot_id") is not None else None,
                    filename=u.get("filename") if isinstance(u.get("filename"), str) else None,
                    error_type=u.get("error_type") if isinstance(u.get("error_type"), str) else None,
                    json_filename=u.get("json_filename") if isinstance(u.get("json_filename"), str) else None,
                    ok=False,
                    thumbnail_url=None,
                    detail=str(detail) if detail else "Missing file",
                )
            )
            failed_count += 1
            continue
        got = warmed_paths[wi]
        wi += 1
        ok = got is not None
        if ok:
            warmed_count += 1
            thumb_url = _thumbnail_url_for_warm_unit(user_id, u)
        else:
            failed_count += 1
            thumb_url = None
        results.append(
            ThumbnailWarmItemResult(
                kind=kind,  # type: ignore[arg-type]
                screenshot_id=int(u["screenshot_id"]) if u.get("screenshot_id") is not None else None,
                filename=u.get("filename") if isinstance(u.get("filename"), str) else None,
                error_type=u.get("error_type") if isinstance(u.get("error_type"), str) else None,
                json_filename=u.get("json_filename") if isinstance(u.get("json_filename"), str) else None,
                ok=ok,
                thumbnail_url=thumb_url,
                detail=None if ok else "Thumbnail generation failed",
            )
        )

    return ThumbnailWarmResponse(results=results, warmed=warmed_count, failed=failed_count)


@router.get("/users/{user_id}/screenshots/{screenshot_id}/image")
def get_screenshot_image(
    user_id: int,
    screenshot_id: int,
    variant: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    screenshot = ScreenshotService().get_screenshot_by_id(screenshot_id)
    if not screenshot or int(screenshot.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    path = _resolve_screenshot_image_path(user_id, current_user, screenshot.filename, ScanService())
    if path is None:
        raise HTTPException(status_code=404, detail="Screenshot image not found")
    return _image_file_response(path, variant=variant)


@router.get("/users/{user_id}/uploads", response_model=UploadFileListResponse)
def list_uploaded_files(
    user_id: int,
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    storage = UploadStorageService()
    files = storage.list_user_files(user_id)
    items = []
    for file_path in files:
        stat = file_path.stat()
        items.append(
            UploadFileItemResponse(
                filename=file_path.name,
                size_bytes=int(stat.st_size),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                image_url=f"/api/users/{user_id}/uploads/{file_path.name}",
            )
        )
    return UploadFileListResponse(total=len(items), items=items)


@router.get("/users/{user_id}/uploads/{filename}")
def get_uploaded_file(
    user_id: int,
    filename: str,
    variant: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    path = UploadStorageService().resolve_user_file(user_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Uploaded file not found")
    return _image_file_response(path, variant=variant)


@router.get("/users/{user_id}/meta-song-config", response_model=MetaSongConfigResponse)
def get_meta_song_config(
    user_id: int,
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    user = UserService().get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _meta_song_config_for_user(user)


@router.get("/users/{user_id}/export", response_model=UserDataExportResponse)
def export_user_data(
    user_id: int,
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    user = UserService().get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    screenshot_service = ScreenshotService()
    scan_service = ScanService()
    storage = UploadStorageService()
    screenshots = screenshot_service.get_screenshots_by_user(user_id)
    encoded_screenshots = [jsonable_encoder(item) for item in screenshots]

    references: list[ExportScreenshotReference] = []
    for screenshot in screenshots:
        filename = getattr(screenshot, "filename", None)
        image_path = _resolve_screenshot_image_path(user_id, user, filename, scan_service)
        direct_path = storage.resolve_user_file(user_id, filename) if filename else None
        references.append(
            ExportScreenshotReference(
                filename=filename,
                path=str(direct_path) if direct_path is not None else (str(image_path) if image_path is not None else None),
                image_available=image_path is not None,
            )
        )

    user_payload = _encoded_user_payload(user)
    user_payload.pop("password_hash", None)

    return UserDataExportResponse(
        exported_at=datetime.now(timezone.utc),
        user=user_payload,
        screenshots=encoded_screenshots,
        screenshot_references=references,
        meta_song_config=_meta_song_config_for_user(user),
        stats_summary=compute_general_summary(screenshots),
    )


@router.post("/users/{user_id}/import", response_model=UserDataImportResponse)
def import_user_data(
    user_id: int,
    data: UserDataImportRequest,
    current_user: User = Depends(get_current_user),
):
    user_id = assert_user_scope(user_id, current_user)
    user_service = UserService()
    screenshot_service = ScreenshotService()
    storage = UploadStorageService()

    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    payload = data.payload or {}
    restored = 0
    skipped = 0
    unresolved: list[str] = []
    updated_fields: list[str] = []

    imported_user = payload.get("user")
    if isinstance(imported_user, dict):
        user_updates = {}
        for field in ["screenshots_source", "screenshots_path", "sync_command", "excluded_song_ids"]:
            if field in imported_user:
                user_updates[field] = imported_user[field]
        if user_updates:
            user_service.update_user(user_id, user_updates)
            updated_fields = sorted(user_updates.keys())

    seen_existing = set(
        screenshot_service.get_existing_filenames_for_user(
            user_id,
            [item.get("filename") for item in payload.get("screenshots", []) if isinstance(item, dict) and item.get("filename")],
        )
    )

    for raw in payload.get("screenshots", []):
        if not isinstance(raw, dict):
            skipped += 1
            continue
        screenshot_data = dict(raw)
        screenshot_data["user_id"] = user_id
        filename = screenshot_data.get("filename")
        if filename and filename in seen_existing:
            skipped += 1
            continue
        timestamp = screenshot_data.get("timestamp")
        if isinstance(timestamp, str):
            try:
                screenshot_data["timestamp"] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                screenshot_data.pop("timestamp", None)
        screenshot_data.pop("id", None)
        try:
            created = screenshot_service.create_screenshot(screenshot_data)
        except ValueError:
            skipped += 1
            continue
        if created is None:
            skipped += 1
            continue
        restored += 1

    for raw in payload.get("screenshot_references", []):
        if not isinstance(raw, dict):
            continue
        filename = raw.get("filename")
        if not filename:
            continue
        if storage.resolve_user_file(user_id, filename) is None:
            unresolved.append(str(filename))

    return UserDataImportResponse(
        restored_screenshots=restored,
        skipped_screenshots=skipped,
        unresolved_screenshot_references=sorted(set(unresolved)),
        updated_user_settings=updated_fields,
    )


@router.get("/scans/errors/{error_type}/{json_filename}/image")
def get_scan_error_image(
    error_type: str,
    json_filename: str,
    variant: str | None = Query(None),
    _: User = Depends(get_current_user),
):
    path = ScanService()._find_error_image_path(error_type, json_filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Error image not found")
    return _image_file_response(path, variant=variant)
