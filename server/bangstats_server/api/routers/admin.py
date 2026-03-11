from pathlib import Path

from fastapi import APIRouter, Depends

from bangstats_server.api.dependencies import get_current_user
from bangstats_server.api.schemas.admin import FlushRequest, FlushResponse
from bangstats_server.core.admin import flush_with_backup
from bangstats_server.core.config import (
    BANGSTATS_ENV,
    DB_PATH,
    ENV_STORAGE_ROOT,
    REMOTE_CACHE,
    SCAN_CACHE,
)
from bangstats_server.core.db import reset_db_engine
from bangstats_server.core.db.models.user import User

router = APIRouter()


@router.get("/health")
def health():
    mode = "dev" if BANGSTATS_ENV == "dev" else "production"
    return {"status": "ok", "mode": mode}


@router.post("/admin/flush", response_model=FlushResponse)
def flush_targets(data: FlushRequest, _: User = Depends(get_current_user)):
    requested_targets: list[tuple[Path, str]] = []
    if data.remote_cache:
        requested_targets.append((REMOTE_CACHE, "remote_data_cache"))
    if data.scan_cache:
        requested_targets.append((SCAN_CACHE, "scan_data_cache"))
    if data.db:
        requested_targets.append((DB_PATH, "bangstats.db"))

    backup_root, moved, skipped = flush_with_backup(
        targets=requested_targets,
        backup_base=ENV_STORAGE_ROOT,
    )
    db_target_name = DB_PATH.name or "bangstats.db"
    db_flushed = data.db and any(Path(path).name.startswith(db_target_name) for path in moved)
    if db_flushed:
        reset_db_engine()

    return FlushResponse(
        backup_root=str(backup_root),
        moved=moved,
        skipped=skipped,
    )
