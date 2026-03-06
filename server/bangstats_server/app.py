import argparse
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from bangstats_server.api.routers import api_router

from bangstats_server.core.config import DB_PATH, REMOTE_CACHE, SCAN_CACHE
from bangstats_server.core.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


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

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_root = DB_PATH.parent / "backups" / timestamp / "deleted files"
    moved_any = False

    for source_path, fallback_name in targets:
        if not source_path.exists():
            continue

        backup_root.mkdir(parents=True, exist_ok=True)
        destination_name = source_path.name or fallback_name
        destination = backup_root / destination_name

        if destination.exists():
            destination = backup_root / f"{destination_name}_{datetime.now().timestamp()}"

        shutil.move(str(source_path), str(destination))
        moved_any = True

    if moved_any:
        print(f"Flush completed. Backup stored in: {backup_root}")
    else:
        print("Flush requested, but no matching targets existed.")


def run(argv: list[str] | None = None) -> None:
    import uvicorn

    args = build_parser().parse_args(argv)
    _flush_with_backup(args)
    uvicorn.run(
        "bangstats_server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
