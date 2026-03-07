import argparse

import httpx
from dotenv import load_dotenv

from bangstats_cli.api_client import BangStatsAPI
from bangstats_cli.config import DEFAULT_SERVER_URL
from bangstats_cli.menus import (
    error_correction_menu,
    import_legacy_json,
    scan_screenshots,
    update_user_settings,
    user_login,
    view_sync_jobs,
    view_stats,
)

load_dotenv()

SUPPORTED_SERVERS = {"en", "jp", "tw", "cn", "kr"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bangstats",
        description="BangStats CLI Client",
    )
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL)
    parser.add_argument("--username")
    parser.add_argument("--game-id")
    parser.add_argument("--server", choices=sorted(SUPPORTED_SERVERS))
    parser.add_argument("--screenshots-path")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--exit-after-init", action="store_true")
    parser.add_argument("--flush-remote-cache", action="store_true")
    parser.add_argument("--flush-scan-cache", action="store_true")
    parser.add_argument("--flush-db", action="store_true")
    parser.add_argument("--flush-all", action="store_true")
    return parser


def _flush_requested(args: argparse.Namespace) -> bool:
    return (
        args.flush_all
        or args.flush_remote_cache
        or args.flush_scan_cache
        or args.flush_db
    )


def _apply_flush(api: BangStatsAPI, args: argparse.Namespace) -> None:
    if not _flush_requested(args):
        return
    payload = api.flush(
        remote_cache=args.flush_all or args.flush_remote_cache,
        scan_cache=args.flush_all or args.flush_scan_cache,
        db=args.flush_all or args.flush_db,
    )
    print(f"Flush completed. Backup stored in: {payload.get('backup_root')}")


def run(argv: list[str] | None = None):
    args = build_parser().parse_args(argv)
    api = BangStatsAPI(args.server_url)
    try:
        _apply_flush(api, args)

        user = user_login(
            api,
            username=args.username,
            game_id=args.game_id,
            server=args.server,
        )
        if args.screenshots_path:
            user["screenshots_path"] = args.screenshots_path

        game_server = user["server"]
        if args.skip_sync:
            counts = api.get_db_counts()
        else:
            try:
                sync_job = api.create_sync_job(
                    game_server, requested_by_user_id=int(user["id"])
                )
                print(
                    "Database sync started in background "
                    f"(job #{sync_job.get('id')}, status={sync_job.get('status')})."
                )
            except httpx.HTTPStatusError as exc:
                detail = ""
                try:
                    detail = exc.response.json().get("detail", "")
                except Exception:
                    detail = exc.response.text
                if exc.response.status_code == 409:
                    print(f"Sync already running: {detail}")
                else:
                    print(f"Unable to start sync job: {detail or exc}")
            counts = api.get_db_counts()
        current_event = api.get_current_event(game_server)

        print(f"BangStats successfully initialized and updated with server: {game_server}.")
        if args.exit_after_init:
            print("Exiting after initialization due to --exit-after-init.")
            return

        while True:
            print("\nBangStats Dashboard")
            print(f"Server: {game_server}")
            print(f"Songs in database: {counts.get('songs', 0)}")
            if current_event:
                event_name = current_event.get("event_name", {}).get(game_server, "Unknown Event")
                print(f"Current Event: {event_name} (ID: {current_event.get('event_id')})")
            else:
                print("Off event time")

            print("\nOptions:")
            print("1. Scan screenshots")
            print("2. Import legacy scan JSON folder")
            print("3. Error correction menu")
            print("4. View your stats")
            print("5. Update database")
            print("6. Update user settings")
            print("7. View sync status/history")
            print("8. Exit")

            choice = input("Enter your choice: ").strip()
            if choice == "1":
                scan_screenshots(api, user, screenshots_path_override=args.screenshots_path)
            elif choice == "2":
                import_legacy_json(api, user)
            elif choice == "3":
                error_correction_menu(api, user)
            elif choice == "4":
                view_stats(api, user)
            elif choice == "5":
                try:
                    sync_job = api.create_sync_job(
                        game_server, requested_by_user_id=int(user["id"])
                    )
                    print(
                        "Database sync started in background "
                        f"(job #{sync_job.get('id')}, status={sync_job.get('status')})."
                    )
                except httpx.HTTPStatusError as exc:
                    detail = ""
                    try:
                        detail = exc.response.json().get("detail", "")
                    except Exception:
                        detail = exc.response.text
                    if exc.response.status_code == 409:
                        print(f"Sync already running: {detail}")
                    else:
                        print(f"Unable to start sync job: {detail or exc}")
                counts = api.get_db_counts()
            elif choice == "6":
                user = update_user_settings(api, user)
                game_server = user["server"]
            elif choice == "7":
                view_sync_jobs(api)
                counts = api.get_db_counts()
            elif choice == "8":
                print("Exiting BangStats. Goodbye!")
                return
    finally:
        api.close()
