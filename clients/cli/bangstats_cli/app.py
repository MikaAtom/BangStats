import argparse
import random
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

from bangstats_cli.api_client import BangStatsAPI
from bangstats_cli.cache import sync_reference_cache
from bangstats_cli.config import DEFAULT_SERVER_URL
from bangstats_cli.menus import (
    error_correction_menu,
    import_legacy_json,
    scan_screenshots,
    update_user_settings,
    user_login,
    view_jobs,
    view_stats,
)

load_dotenv()

SUPPORTED_SERVERS = {"en", "jp", "tw", "cn", "kr"}
_DUMMY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0bIDATx\x9cc`\x00\x02\x00\x00\x05\x00\x01"
    b"\x0d\n\x2d\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bangstats",
        description="BangStats CLI Client",
    )
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL)
    parser.add_argument("--username")
    parser.add_argument("--game-id")
    parser.add_argument("--server", choices=sorted(SUPPORTED_SERVERS))
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--screenshots-path")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--exit-after-init", action="store_true")
    parser.add_argument("--flush-remote-cache", action="store_true")
    parser.add_argument("--flush-scan-cache", action="store_true")
    parser.add_argument("--flush-db", action="store_true")
    parser.add_argument("--flush-all", action="store_true")
    parser.add_argument("--dev", action="store_true")
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


def _dev_auto_login(api: BangStatsAPI) -> dict:
    payload = {
        "username": "dev_user",
        "password": "dev123",
        "game_id": "dev_gid",
        "server": "en",
    }
    try:
        registered = api.register(payload)
        print("[DEV] Logged in as dev_user (registered).")
        return registered["user"]
    except Exception:
        logged_in = api.login(payload["username"], payload["password"])
        print("[DEV] Logged in as dev_user.")
        return logged_in["user"]


def _spread_unix_ms(count: int, span_days: int) -> list[int]:
    if count <= 0:
        return []
    now = datetime.now()
    start = now - timedelta(days=max(1, span_days))
    span_seconds = max(1, int((now - start).total_seconds()))
    offsets = sorted(random.randint(0, span_seconds) for _ in range(count))
    return [int((start + timedelta(seconds=offset)).timestamp() * 1000) for offset in offsets]


def _scan_screenshots_dev(api: BangStatsAPI, user: dict) -> None:
    count_raw = input("How many dummy screenshots to generate? [20]: ").strip()
    try:
        count = int(count_raw) if count_raw else 20
        if count <= 0:
            raise ValueError
    except ValueError:
        print("Invalid count, using 20.")
        count = 20

    time_span_days = 90
    try:
        dev_cfg = api.dev_config()
        parsed = int(dev_cfg.get("fake_time_span_days", 90))
        if parsed > 0:
            time_span_days = parsed
    except Exception:
        time_span_days = 90

    timestamps = _spread_unix_ms(count, time_span_days)
    with tempfile.TemporaryDirectory(prefix="bangstats-dev-shots-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        for timestamp in timestamps:
            filename = tmp_path / f"Screenshot_{timestamp}.png"
            filename.write_bytes(_DUMMY_PNG_BYTES)
        scan_screenshots(api, user, screenshots_path_override=str(tmp_path))


def _dev_tools_menu(api: BangStatsAPI, user: dict, game_server: str) -> dict:
    def _prompt_int(
        prompt: str,
        default: int,
        *,
        minimum: int = 1,
        maximum: int | None = None,
    ) -> int:
        raw = input(prompt).strip()
        if not raw:
            return default
        try:
            parsed = int(raw)
        except ValueError:
            print("Invalid number, using default.")
            return default
        if parsed < minimum:
            print("Value too small, using default.")
            return default
        if maximum is not None and parsed > maximum:
            print(f"Value too large (max {maximum}), using {maximum}.")
            return maximum
        return parsed

    def _prompt_yes_no(prompt: str, *, default_yes: bool = True) -> bool:
        raw = input(prompt).strip().lower()
        if not raw:
            return default_yes
        return raw in {"y", "yes"}

    def _maybe_set_prepared_path(
        *,
        source: str,
        path: str,
    ) -> None:
        nonlocal user
        if not _prompt_yes_no("Set as your screenshot path now? (Y/n): ", default_yes=True):
            print("Skipped updating screenshot source/path.")
            return
        try:
            user = api.update_user(
                int(user["id"]),
                {"screenshots_source": source, "screenshots_path": path},
            )
            print(f"Updated user screenshot source to '{source}' with path: {path}")
        except Exception as exc:
            print(f"Failed to update screenshot source/path: {exc}")

    def _prepare_simulated(target: str) -> None:
        try:
            cfg = api.dev_config()
            default_days = int(cfg.get("fake_time_span_days", 90) or 90)
        except Exception:
            default_days = 90

        count = _prompt_int("Image count [20]: ", 20, maximum=10000)
        time_span_days = _prompt_int(
            f"Time span days [{default_days}]: ",
            default_days,
            maximum=3650,
        )
        clear_existing = _prompt_yes_no("Clear existing .png files first? (Y/n): ", default_yes=True)

        result = api.dev_prepare_simulated_folders(
            user_id=int(user["id"]),
            target=target,
            count=count,
            time_span_days=time_span_days,
            clear_existing=clear_existing,
        )

        local_path = result.get("local_path")
        server_path = result.get("server_path")
        if local_path:
            print(
                "[DEV] Local simulated folder: "
                f"existing_before={result.get('local_existing_before', 0)}, "
                f"created={result.get('local_created', 0)}"
            )
            print(f"  path: {local_path}")
        if server_path:
            print(
                "[DEV] Server simulated folder: "
                f"existing_before={result.get('server_existing_before', 0)}, "
                f"created={result.get('server_created', 0)}"
            )
            print(f"  path: {server_path}")

        if target == "local" and local_path:
            _maybe_set_prepared_path(source="local", path=local_path)
            return
        if target == "server" and server_path:
            _maybe_set_prepared_path(source="server_folder", path=server_path)
            return
        if target == "both":
            set_choice = input("Set which prepared path now? [l]ocal / [s]erver / [n]one [n]: ").strip().lower()
            if set_choice == "l" and local_path:
                _maybe_set_prepared_path(source="local", path=local_path)
            elif set_choice == "s" and server_path:
                _maybe_set_prepared_path(source="server_folder", path=server_path)
            else:
                print("Skipped updating screenshot source/path.")

    while True:
        print("\n[DEV] Dev tools")
        print("1. Seed N screenshots directly to DB")
        print("2. Reset dev DB (flush db + trigger sync)")
        print("3. Show dev config")
        print("4. Prepare simulated local source folder")
        print("5. Prepare simulated server folder")
        print("6. Prepare both simulated folders")
        print("0. Back")
        choice = input("Choose option: ").strip()
        if choice == "0":
            return user
        if choice == "1":
            count_raw = input("Seed count [100]: ").strip()
            try:
                count = int(count_raw) if count_raw else 100
                if count <= 0:
                    raise ValueError
            except ValueError:
                print("Invalid count.")
                continue
            try:
                result = api.dev_seed(user_id=int(user["id"]), count=count)
                print(
                    f"Seeded {result.get('seeded', 0)} screenshots "
                    f"(attempted={result.get('attempted', 0)}, requested={result.get('requested', count)})."
                )
            except Exception as exc:
                print(f"Dev seed failed: {exc}")
            continue
        if choice == "2":
            try:
                payload = api.flush(db=True)
                print(f"DB flushed. Backup: {payload.get('backup_root')}")
                sync_job = api.create_sync_job(game_server, requested_by_user_id=int(user["id"]))
                print(
                    "Database sync started in background "
                    f"(job #{sync_job.get('id')}, status={sync_job.get('status')})."
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {401, 403, 404}:
                    print("[DEV] Session invalid after DB reset, re-authenticating and retrying...")
                    try:
                        user = _dev_auto_login(api)
                        sync_job = api.create_sync_job(
                            game_server, requested_by_user_id=int(user["id"])
                        )
                        print(
                            "Database sync started in background "
                            f"(job #{sync_job.get('id')}, status={sync_job.get('status')})."
                        )
                    except Exception as retry_exc:
                        print(f"Reset failed after re-login retry: {retry_exc}")
                else:
                    print(f"Reset failed: {exc}")
            except Exception as exc:
                print(f"Reset failed: {exc}")
            continue
        if choice == "3":
            try:
                cfg = api.dev_config()
                print("[DEV] Server config:")
                for key in sorted(cfg.keys()):
                    print(f"  {key}: {cfg[key]}")
            except Exception as exc:
                print(f"Unable to fetch dev config: {exc}")
            continue
        if choice == "4":
            try:
                _prepare_simulated("local")
            except Exception as exc:
                print(f"Prepare simulated local folder failed: {exc}")
            continue
        if choice == "5":
            try:
                _prepare_simulated("server")
            except Exception as exc:
                print(f"Prepare simulated server folder failed: {exc}")
            continue
        if choice == "6":
            try:
                _prepare_simulated("both")
            except Exception as exc:
                print(f"Prepare simulated folders failed: {exc}")
            continue
        print("Invalid choice.")


def run(argv: list[str] | None = None):
    args = build_parser().parse_args(argv)
    api = BangStatsAPI(args.server_url)
    dev_config_cache: dict | None = None
    try:
        if args.dev:
            user = _dev_auto_login(api)
        else:
            user = user_login(
                api,
                username=args.username,
                game_id=args.game_id,
                server=args.server,
                register_mode=args.register,
            )
        _apply_flush(api, args)
        if args.screenshots_path:
            user["screenshots_path"] = args.screenshots_path
        if args.dev:
            try:
                dev_config_cache = api.dev_config()
            except Exception:
                dev_config_cache = None
        try:
            reference_cache = sync_reference_cache(api)
        except Exception as exc:
            print(f"Reference cache sync failed, continuing without cache: {exc}")
            reference_cache = {}

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
        try:
            health = api.get_health()
        except Exception:
            health = {"db_path": "unknown", "mode": "unknown"}
        current_event = api.get_current_event(game_server)

        mode_label = ""
        if args.dev:
            try:
                health = api.get_health()
                if str(health.get("mode", "")).lower() == "dev":
                    mode_label = "[DEV] "
            except Exception:
                mode_label = "[DEV] "
        print(f"{mode_label}BangStats successfully initialized and updated with server: {game_server}.")
        if args.exit_after_init:
            print("Exiting after initialization due to --exit-after-init.")
            return

        while True:
            active_line = ""
            try:
                scan_jobs = (api.list_scan_jobs(limit=20) or {}).get("jobs", [])
                active_scan = next(
                    (j for j in scan_jobs if str(j.get("status")) in {"queued", "running"}),
                    None,
                )
                if active_scan:
                    total = int(active_scan.get("total_files", 0) or 0)
                    processed = int(active_scan.get("processed", 0) or 0)
                    pct = round((processed / total) * 100, 1) if total > 0 else 0.0
                    active_line = (
                        f"[Scan #{active_scan.get('id')}: {processed}/{total} ({pct}%) "
                        f"{active_scan.get('status')}]"
                    )
                else:
                    sync_jobs = (api.list_sync_jobs(limit=20) or {}).get("jobs", [])
                    active_sync = next(
                        (j for j in sync_jobs if str(j.get("status")) in {"queued", "running"}),
                        None,
                    )
                    if active_sync:
                        active_line = (
                            f"[Sync #{active_sync.get('id')}: {active_sync.get('status')} "
                            f"server={active_sync.get('server')}]"
                        )
            except Exception:
                active_line = ""

            print("\nBangStats Dashboard")
            if args.dev:
                print("[DEV] mode enabled")
                if dev_config_cache and bool(dev_config_cache.get("dev_simulate_screenshot_locations", False)):
                    print(
                        f"[DEV] simulated local root: {dev_config_cache.get('dev_simulated_client_upload_source_root')}"
                    )
                    print(
                        f"[DEV] simulated server root: {dev_config_cache.get('dev_simulated_server_folder_root')}"
                    )
            if active_line:
                print(active_line)
            print(f"Server: {game_server}")
            print(f"DB: {health.get('db_path', 'unknown')}")
            print(f"Songs in database: {counts.get('songs', 0)}")
            if current_event:
                event_name = current_event.get("event_name", {}).get(game_server, "Unknown Event")
                print(f"Current Event: {event_name} (ID: {current_event.get('event_id')})")
            else:
                print(
                    "No event found for this server at current UTC time "
                    f"(server={game_server}, db={health.get('db_path', 'unknown')})"
                )

            print("\nOptions:")
            print("1. Scan screenshots")
            print("2. Import legacy scan JSON folder")
            print("3. Error correction menu")
            print("4. View your stats")
            print("5. Update database")
            print("6. Update user settings")
            print("7. View jobs (scan + sync)")
            print("8. Exit")
            if args.dev:
                print("9. Dev tools")

            choice = input("Enter your choice: ").strip()
            if choice == "1":
                user = scan_screenshots(
                    api,
                    user,
                    screenshots_path_override=args.screenshots_path,
                    dev_mode=args.dev,
                    dev_config=dev_config_cache,
                )
            elif choice == "2":
                import_legacy_json(api, user)
            elif choice == "3":
                error_correction_menu(api, user)
            elif choice == "4":
                view_stats(api, user, reference_cache=reference_cache)
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
                view_jobs(api)
                counts = api.get_db_counts()
            elif choice == "8":
                print("Exiting BangStats. Goodbye!")
                return
            elif choice == "9" and args.dev:
                user = _dev_tools_menu(api, user, game_server)
    finally:
        api.close()
