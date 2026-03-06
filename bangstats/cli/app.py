import argparse
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from bangstats.config import DB_PATH, REMOTE_CACHE, SCAN_CACHE
from bangstats.database.db import init_db
from bangstats.services.data.event import EventService
from bangstats.utils.setup_loguru import setup_loguru  # noqa: F401

from bangstats.cli.menus import (
    get_db_counts,
    user_login,
    update_db,
    scan_screenshots,
    view_stats,
    update_user_settings,
)

event_service = EventService()
SUPPORTED_SERVERS = {"en", "jp", "tw", "cn", "kr"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bangstats",
        description="BangStats CLI",
    )
    parser.add_argument("--username", help="Use this username for login/create flow.")
    parser.add_argument("--game-id", help="Use this game ID for user creation flow.")
    parser.add_argument(
        "--server",
        choices=sorted(SUPPORTED_SERVERS),
        help="Server override for creating a user profile.",
    )
    parser.add_argument(
        "--screenshots-path",
        help="Default screenshots path used by scan flow.",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Skip initial remote database sync.",
    )
    parser.add_argument(
        "--exit-after-init",
        action="store_true",
        help="Exit after initialization (before dashboard loop).",
    )
    parser.add_argument(
        "--flush-remote-cache",
        action="store_true",
        help="Move remote cache to backup folder.",
    )
    parser.add_argument(
        "--flush-scan-cache",
        action="store_true",
        help="Move scan cache to backup folder.",
    )
    parser.add_argument(
        "--flush-db",
        action="store_true",
        help="Move SQLite DB file to backup folder.",
    )
    parser.add_argument(
        "--flush-all",
        action="store_true",
        help="Flush remote cache, scan cache, and DB in one command.",
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
    backup_root = DB_PATH.parent / "backups" / timestamp

    logger.info(f"Flush requested. Backup root: {backup_root}")
    moved_any = False

    for source_path, fallback_name in targets:
        if not source_path.exists():
            logger.info(f"Flush target missing, skipping: {source_path}")
            continue

        backup_root.mkdir(parents=True, exist_ok=True)
        destination_name = source_path.name or fallback_name
        destination = backup_root / destination_name

        if destination.exists():
            destination = backup_root / f"{destination_name}_{datetime.now().timestamp()}"

        shutil.move(str(source_path), str(destination))
        moved_any = True
        logger.info(f"Moved {source_path} -> {destination}")

    if moved_any:
        print(f"Flush completed. Backup stored in: {backup_root}")
    else:
        print("Flush requested, but no matching targets existed.")


def run(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)

    logger.info("Starting BangStats update process...")
    _flush_with_backup(args)

    # Initialize the database
    init_db()
    logger.info("Database initialized successfully.")

    # User login or creation
    user = user_login(username=args.username, game_id=args.game_id, server=args.server)
    if args.screenshots_path:
        user.screenshots_path = args.screenshots_path

    # Get user's server
    game_server = user.server

    # Update the database with remote data
    songs = events = bands = 0
    if not args.skip_sync:
        songs, events, bands = update_db(game_server)
    else:
        songs, events, bands = get_db_counts()
        logger.info("Skipping initial remote sync due to --skip-sync.")

    current_event = event_service.get_current_event()

    logger.info("BangStats update process completed successfully.")

    print(f"BangStats successfully initialized and updated with server: {game_server}.")
    if args.exit_after_init:
        print("Exiting after initialization due to --exit-after-init.")
        return

    while True:
        print("\nBangStats Dashboard")
        print(f"Server: {game_server}")
        print(f"Songs in database: {songs}")
        if current_event:
            print(
                f"Current Event: {current_event.event_name[game_server]} (ID: {current_event.event_id})"
            )
        else:
            print("Off event time")

        print("\nOptions:")
        print("1. Scan screenshots")
        print("2. View your stats")
        print("3. Update database")
        print("4. Update user settings")
        print("5. Exit")

        choice = input("Enter your choice: ").strip()
        if choice == "1":
            scan_screenshots(user, screenshots_path_override=args.screenshots_path)
        elif choice == "2":
            view_stats(user)
        elif choice == "3":
            update_db(game_server)
        elif choice == "4":
            update_user_settings(user)
        elif choice == "5":
            print("Exiting BangStats. Goodbye!")
            break
