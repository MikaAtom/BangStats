import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

if "--dev" in sys.argv:
    load_dotenv(".env.dev", override=True)
else:
    load_dotenv()

from bangstats_server.api.routers import api_router
import bangstats_server.core.logging  # noqa: F401

from bangstats_server.core.admin import flush_with_backup
from bangstats_server.core.config import (
    BANGSTATS_ENV,
    DB_PATH,
    DEV_SIMULATE_SCREENSHOT_LOCATIONS,
    ENV_STORAGE_ROOT,
    DISABLE_LEGACY_CACHE_MIGRATION,
    REMOTE_CACHE,
    SCAN_CACHE,
    migrate_legacy_cache_dirs,
    migrate_legacy_storage_dirs,
)
from bangstats_server.core.db import init_db
from bangstats_server.core.services.scan_job import ScanJobService
from bangstats_server.core.services.upload_storage import UploadStorageService
from bangstats_server.core.services.sync_job import SyncJobService
from bangstats_server.core.services.dev_simulation import DevSimulationService


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("BangStats server starting (env={})", BANGSTATS_ENV)
    if not DISABLE_LEGACY_CACHE_MIGRATION:
        migrate_legacy_cache_dirs()
        migrate_legacy_storage_dirs()
    init_db()
    if BANGSTATS_ENV == "dev" and DEV_SIMULATE_SCREENSHOT_LOCATIONS:
        DevSimulationService().ensure_for_existing_users()
    SyncJobService().fail_all_active_jobs(
        error_message="Marked failed after server restart during sync execution."
    )
    ScanJobService().fail_all_active_jobs(
        error_message="Marked failed after server restart during scan execution."
    )
    UploadStorageService().cleanup_all_expired()
    yield
    logger.info("BangStats server stopping")


def create_app() -> FastAPI:
    app = FastAPI(
        title="BangStats API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bangstats-server",
        description="BangStats API Server",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host for uvicorn server.")
    parser.add_argument("--port", type=int, default=8000, help="Port for uvicorn server.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn reload mode for development.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run server using .env.dev and development providers.",
    )
    parser.add_argument(
        "--flush-remote-cache",
        action="store_true",
        help="Move remote cache to backup folder before startup.",
    )
    parser.add_argument(
        "--flush-scan-cache",
        action="store_true",
        help="Move scan cache to backup folder before startup.",
    )
    parser.add_argument(
        "--flush-db",
        action="store_true",
        help="Move SQLite DB file to backup folder before startup.",
    )
    parser.add_argument(
        "--flush-all",
        action="store_true",
        help="Flush remote cache, scan cache, and DB before startup.",
    )
    return parser


def _build_flush_targets(args: argparse.Namespace) -> list[tuple[Path, str]]:
    flush_remote = args.flush_all or args.flush_remote_cache
    flush_scan = args.flush_all or args.flush_scan_cache
    flush_db = args.flush_all or args.flush_db

    targets: list[tuple[Path, str]] = []
    if flush_remote:
        targets.append((REMOTE_CACHE, "remote_data_cache"))
    if flush_scan:
        targets.append((SCAN_CACHE, "scan_data_cache"))
    if flush_db:
        targets.append((DB_PATH, "bangstats.db"))
    return targets


def _flush_with_backup(args: argparse.Namespace) -> None:
    targets = _build_flush_targets(args)
    if not targets:
        return

    backup_root, moved, _ = flush_with_backup(
        targets=targets,
        backup_base=ENV_STORAGE_ROOT,
        include_deleted_files_dir=True,
    )
    if moved:
        print(f"Flush completed. Backup stored in: {backup_root}")
    else:
        print("Flush requested, but no matching targets existed.")


def run(argv: list[str] | None = None) -> None:
    import uvicorn

    args = build_parser().parse_args(argv)
    if args.dev:
        load_dotenv(".env.dev", override=True)
        print("[DEV] Running in development mode.")
    _flush_with_backup(args)
    uvicorn.run(
        "bangstats_server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
