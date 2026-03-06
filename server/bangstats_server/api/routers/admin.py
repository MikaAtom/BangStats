import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from bangstats_server.api.schemas.admin import FlushRequest, FlushResponse
from bangstats_server.core.config import DB_PATH, REMOTE_CACHE, SCAN_CACHE

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/admin/flush", response_model=FlushResponse)
def flush_targets(data: FlushRequest):
    requested_targets: list[Path] = []
    if data.remote_cache:
        requested_targets.append(REMOTE_CACHE)
    if data.scan_cache:
        requested_targets.append(SCAN_CACHE)
    if data.db:
        requested_targets.append(DB_PATH)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_root = DB_PATH.parent / "backups" / timestamp
    moved: list[str] = []
    skipped: list[str] = []

    for source_path in requested_targets:
        if not source_path.exists():
            skipped.append(str(source_path))
            continue
        backup_root.mkdir(parents=True, exist_ok=True)
        destination = backup_root / source_path.name
        if destination.exists():
            destination = backup_root / f"{source_path.name}_{datetime.now().timestamp()}"
        shutil.move(str(source_path), str(destination))
        moved.append(str(destination))

    return FlushResponse(
        backup_root=str(backup_root),
        moved=moved,
        skipped=skipped,
    )
