from pathlib import Path
from copy import deepcopy
from typing import Any

from bangstats_cli.api_client import BangStatsAPI

SUPPORTED_SERVERS = ["en", "jp", "tw", "cn", "kr"]
EDITABLE_SCAN_FIELDS = [
    "song_name_from_top_bar_text",
    "difficulty",
    "live_type",
    "perfect",
    "great",
    "good",
    "bad",
    "miss",
    "fast",
    "slow",
    "max_combo",
    "score",
    "high_score",
    "score_rank",
    "is_new_record",
]


def user_login(
    api: BangStatsAPI,
    username: str | None = None,
    game_id: str | None = None,
    server: str | None = None,
) -> dict:
    user = None
    while not user:
        entered_username = (
            username if username is not None else input("Enter your username: ").strip()
        )
        if not entered_username:
            print("Username cannot be empty. Please try again.")
            continue

        user = api.get_user_by_username(entered_username)
        if not user:
            resolved_game_id = game_id if game_id is not None else ""
            while not resolved_game_id:
                resolved_game_id = input("Enter your game ID: ").strip()
                if not resolved_game_id:
                    print("Game ID cannot be empty. Please try again.")
                    continue

            resolved_server = server.lower() if isinstance(server, str) else ""
            while resolved_server not in SUPPORTED_SERVERS:
                resolved_server = input("Enter your server (en/jp/tw/cn/kr): ").strip().lower()
                if resolved_server not in SUPPORTED_SERVERS:
                    print("Invalid server. Please enter one of: en, jp, tw, cn, kr.")
                    continue

            user = api.create_user(
                {
                    "game_id": resolved_game_id,
                    "username": entered_username,
                    "server": resolved_server,
                }
            )
            print(f"User created: {user['username']} with Game ID: {user['game_id']}")
        else:
            print(f"User found: {user['username']} with Game ID: {user['game_id']}")
    return user


def scan_screenshots(
    api: BangStatsAPI,
    user: dict,
    screenshots_path_override: str | None = None,
) -> None:
    screenshots_path = screenshots_path_override or user.get("screenshots_path", "")
    if not screenshots_path:
        screenshots_path = input("Enter the path to your screenshots directory: ").strip()
        if not screenshots_path:
            print("Screenshots path cannot be empty. Please try again.")
            return

    screenshots_dir = Path(screenshots_path).expanduser()
    while not screenshots_dir.exists():
        screenshots_path = input("Path does not exist. Enter screenshots directory: ").strip()
        screenshots_dir = Path(screenshots_path).expanduser()

    images = sorted(
        [
            path
            for path in screenshots_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
        ]
    )
    if not images:
        print(f"No images found in {screenshots_dir}.")
        return

    print(f"Found {len(images)} images in {screenshots_dir}.")
    image_filenames = [path.name for path in images]
    try:
        diff = api.get_scan_filename_diff(
            user_id=int(user["id"]),
            filenames=image_filenames,
        )
    except Exception as exc:
        print(f"Filename precheck failed, continuing with full scan: {exc}")
        diff = {
            "requested_total": len(image_filenames),
            "already_scanned_count": 0,
            "to_scan_count": len(image_filenames),
            "to_scan_filenames": image_filenames,
        }

    to_scan_filenames = diff.get("to_scan_filenames", image_filenames)
    requested_total = int(diff.get("requested_total", len(image_filenames)) or 0)
    already_scanned = int(diff.get("already_scanned_count", 0) or 0)
    to_scan_count = int(diff.get("to_scan_count", len(to_scan_filenames)) or 0)
    print(
        "Precheck summary: "
        f"requested={requested_total}, already_scanned={already_scanned}, to_scan={to_scan_count}"
    )
    if to_scan_count <= 0:
        print("All files are already scanned. Nothing to do.")
        return

    parallel_workers = None
    keys_per_worker = None
    try:
        capabilities = api.get_scan_capabilities()
    except Exception:
        capabilities = {"provider": "unknown", "available_google_keys": 0}

    provider = capabilities.get("provider")
    available_keys = int(capabilities.get("available_google_keys", 0) or 0)
    if provider == "gemini" and available_keys > 1:
        enable_parallel = (
            input(
                f"Enable parallel scan? Available Google keys: {available_keys} (y/N): "
            )
            .strip()
            .lower()
        )
        if enable_parallel in {"y", "yes"}:
            print("Choose manual mode: workers x keys_per_worker")
            print(
                "Rule: workers * keys_per_worker must be <= available keys "
                f"({available_keys})."
            )
            workers_raw = input("Workers: ").strip()
            keys_raw = input("Keys per worker: ").strip()
            try:
                parsed_workers = int(workers_raw)
                parsed_keys = int(keys_raw)
                if parsed_workers <= 0 or parsed_keys <= 0:
                    raise ValueError
                if parsed_workers * parsed_keys > available_keys:
                    raise ValueError
                parallel_workers = parsed_workers
                keys_per_worker = parsed_keys
                print(
                    f"Parallel mode enabled: {parallel_workers}x{keys_per_worker}"
                )
            except ValueError:
                print("Invalid parallel mode; falling back to single-worker scan.")

    print("Starting scan...")
    try:
        locality = api.check_scan_local_path(str(screenshots_dir))
    except Exception as exc:
        print(f"Server path locality check failed, using upload fallback: {exc}")
        locality = {"is_local": False, "canonical_path": None}

    if locality.get("is_local"):
        server_path = locality.get("canonical_path") or str(screenshots_dir)
        print(f"Server-local path detected, scanning directly on server: {server_path}")
        scan_result = api.scan_local_folder(
            user_id=int(user["id"]),
            folder_path=server_path,
            filenames=to_scan_filenames,
            parallel_workers=parallel_workers,
            keys_per_worker=keys_per_worker,
        )
    else:
        to_scan_set = set(to_scan_filenames)
        filtered_images = [path for path in images if path.name in to_scan_set]
        print(f"Path is not local to server; uploading {len(filtered_images)} files.")
        scan_result = api.scan_images(
            int(user["id"]),
            filtered_images,
            parallel_workers=parallel_workers,
            keys_per_worker=keys_per_worker,
        )
    print("Scan completed. Results:")
    print(f"Total images scanned: {scan_result.get('total_scanned', 0)}")
    print(f"Successful scans: {scan_result.get('successful', 0)}")
    print(f"Validated scans: {scan_result.get('validated', 0)}")
    print(f"Persisted to DB: {scan_result.get('persisted', 0)}")
    print(f"Failed to persist: {scan_result.get('failed_to_persist', 0)}")
    print(f"Skipped (duplicate): {scan_result.get('skipped_duplicates', 0)}")
    print("Errors:")
    for error_type, count in scan_result.get("errors", {}).items():
        print(f"  {error_type.replace('_', ' ').title()}: {count}")
    additional = scan_result.get("additional", {})
    if additional:
        print("Scan mode:")
        print(f"  Provider: {additional.get('provider', '-')}")
        if additional.get("parallel_enabled"):
            print(f"  Parallel: {additional.get('mode', '-')}")
        else:
            print("  Parallel: disabled")


def import_legacy_json(
    api: BangStatsAPI,
    user: dict,
    json_folder_override: str | None = None,
) -> None:
    folder = json_folder_override or input("Enter legacy JSON folder path: ").strip()
    if not folder:
        print("JSON folder path cannot be empty.")
        return

    folder_path = Path(folder).expanduser()
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"Path is not a directory: {folder_path}")
        return

    persist_choice = input("Persist valid records to DB? (Y/n): ").strip().lower()
    persist_to_db = persist_choice not in {"n", "no"}

    try:
        result = api.import_json_folder(
            user_id=int(user["id"]),
            folder_path=str(folder_path),
            persist_to_db=persist_to_db,
        )
    except Exception as exc:
        print(f"Import failed: {exc}")
        return

    print("Import completed. Results:")
    print(f"Total JSON processed: {result.get('total_scanned', 0)}")
    print(f"Successful validations: {result.get('successful', 0)}")
    print(f"Persisted to DB: {result.get('persisted', 0)}")
    print(f"Failed to persist: {result.get('failed_to_persist', 0)}")
    print(f"Skipped (duplicate): {result.get('skipped_duplicates', 0)}")
    print("Errors:")
    for error_type, count in result.get("errors", {}).items():
        print(f"  {error_type.replace('_', ' ').title()}: {count}")


def _coerce_value(raw_value: str, current_value: Any) -> Any:
    if isinstance(current_value, bool):
        return raw_value.strip().lower() in {"1", "true", "t", "yes", "y"}
    if isinstance(current_value, int):
        return int(raw_value.strip())
    return raw_value


def _pick_error_type(error_counts: dict[str, int]) -> str | None:
    options = [(name, count) for name, count in error_counts.items() if count > 0]
    if not options:
        print("No error files available.")
        return None

    print("\nError categories:")
    for idx, (name, count) in enumerate(options, start=1):
        print(f"{idx}. {name} ({count})")
    print("0. Back")

    choice = input("Choose category: ").strip()
    if choice == "0":
        return None
    if not choice.isdigit():
        print("Invalid choice.")
        return None

    index = int(choice) - 1
    if index < 0 or index >= len(options):
        print("Invalid choice.")
        return None
    return options[index][0]


def _pick_error_file(files: list[str]) -> str | None:
    if not files:
        print("No files in this category.")
        return None

    display = files[:50]
    print("\nError files:")
    for idx, name in enumerate(display, start=1):
        print(f"{idx}. {name}")
    if len(files) > len(display):
        print(f"... showing first {len(display)} of {len(files)}")
    print("0. Back")

    choice = input("Choose file: ").strip()
    if choice == "0":
        return None
    if not choice.isdigit():
        print("Invalid choice.")
        return None

    index = int(choice) - 1
    if index < 0 or index >= len(display):
        print("Invalid choice.")
        return None
    return display[index]


def _edit_scan_payload(scan_data: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(scan_data)
    while True:
        print("\nEditable fields:")
        for idx, field in enumerate(EDITABLE_SCAN_FIELDS, start=1):
            print(f"{idx}. {field}: {updated.get(field)}")
        print("S. Submit correction")
        print("Q. Cancel")

        choice = input("Select field to edit: ").strip().lower()
        if choice == "s":
            return updated
        if choice == "q":
            return scan_data
        if not choice.isdigit():
            print("Invalid choice.")
            continue

        index = int(choice) - 1
        if index < 0 or index >= len(EDITABLE_SCAN_FIELDS):
            print("Invalid choice.")
            continue
        field = EDITABLE_SCAN_FIELDS[index]
        current_value = updated.get(field)
        raw_value = input(f"New value for {field} (current={current_value}): ")
        try:
            updated[field] = _coerce_value(raw_value, current_value)
        except ValueError as exc:
            print(f"Invalid value: {exc}")


def _print_category_action_result(result: dict[str, Any]) -> None:
    print("Batch action completed:")
    print(f"  Total files: {result.get('total_files', 0)}")
    print(f"  Processed: {result.get('processed', 0)}")
    print(f"  Successful: {result.get('successful', 0)}")
    print(f"  Persisted: {result.get('persisted', 0)}")
    print(f"  Skipped duplicate: {result.get('skipped_duplicates', 0)}")
    print(f"  Failed to persist: {result.get('failed_to_persist', 0)}")
    print(f"  Missing image: {result.get('missing_image', 0)}")
    print(f"  Scan failed: {result.get('scan_failed', 0)}")
    errors = result.get("errors", {})
    if errors:
        print("  Errors by type:")
        for error_type, count in errors.items():
            print(f"    {error_type}: {count}")


def error_correction_menu(api: BangStatsAPI, user: dict) -> None:
    while True:
        try:
            summary = api.list_scan_errors()
        except Exception as exc:
            print(f"Failed to fetch error list: {exc}")
            return

        print(f"\nTotal unresolved error files: {summary.get('total', 0)}")
        error_type = _pick_error_type(summary.get("errors", {}))
        if not error_type:
            return

        files = summary.get("error_files", {}).get(error_type, [])
        print("\nCategory actions:")
        print("1. Review and correct single file")
        print("2. Revalidate whole category")
        print("3. Rescan whole category (needs images in cache)")
        print("0. Back")
        action = input("Choose action: ").strip()
        if action == "0":
            continue
        if action == "2":
            interval_raw = input("Progress update every N files? [500]: ").strip()
            try:
                progress_every = int(interval_raw) if interval_raw else 500
                if progress_every <= 0:
                    raise ValueError
            except ValueError:
                print("Invalid progress interval. Using default 500.")
                progress_every = 500
            try:
                result = api.revalidate_error_category(
                    user_id=int(user["id"]),
                    error_type=error_type,
                    persist_to_db=True,
                    progress_every=progress_every,
                )
                _print_category_action_result(result)
            except Exception as exc:
                print(f"Revalidate failed: {exc}")
            continue
        if action == "3":
            interval_raw = input("Progress update every N files? [500]: ").strip()
            try:
                progress_every = int(interval_raw) if interval_raw else 500
                if progress_every <= 0:
                    raise ValueError
            except ValueError:
                print("Invalid progress interval. Using default 500.")
                progress_every = 500
            model = input("OCR model override (blank for default): ").strip() or None
            try:
                result = api.rescan_error_category(
                    user_id=int(user["id"]),
                    error_type=error_type,
                    persist_to_db=True,
                    progress_every=progress_every,
                    model=model,
                )
                _print_category_action_result(result)
            except Exception as exc:
                print(f"Rescan failed: {exc}")
            continue
        if action != "1":
            print("Invalid choice.")
            continue

        json_filename = _pick_error_file(files)
        if not json_filename:
            continue

        try:
            detail = api.get_scan_error_detail(error_type, json_filename)
        except Exception as exc:
            print(f"Failed to load error detail: {exc}")
            continue

        print(f"\nSelected: {detail.get('json_filename')}")
        validation = detail.get("validation") or {}
        print(f"Current error type: {validation.get('error_type', detail.get('error_type'))}")
        if validation.get("reasons"):
            print(f"Reasons: {', '.join(validation.get('reasons', []))}")
        edited_payload = _edit_scan_payload(detail.get("scan_data", {}))
        if edited_payload == detail.get("scan_data", {}):
            print("No changes submitted.")
            continue

        try:
            outcome = api.correct_scan_error(
                user_id=int(user["id"]),
                error_type=error_type,
                json_filename=json_filename,
                corrected_scan_data=edited_payload,
                persist_to_db=True,
            )
        except Exception as exc:
            print(f"Correction failed: {exc}")
            continue

        print("Correction processed:")
        print(f"  Valid now: {outcome.get('is_valid')}")
        print(f"  New error type: {outcome.get('error_type')}")
        print(f"  Persisted: {outcome.get('persisted')}")
        print(f"  Skipped duplicate: {outcome.get('skipped_duplicates')}")
        print(f"  Failed to persist: {outcome.get('failed_to_persist')}")


def view_stats(api: BangStatsAPI, user: dict) -> None:
    try:
        payload = api.get_user_stats(int(user["id"]))
    except Exception as exc:
        print(f"Unable to fetch stats: {exc}")
        return

    summary = payload.get("summary", {})
    top_songs = payload.get("top_songs", [])
    recent = payload.get("recent", [])

    print("\nGeneral Summary")
    print(f"  Total plays: {summary.get('total_plays', 0)}")
    print(f"  Total FC: {summary.get('total_fc', 0)}")
    print(f"  Total AP: {summary.get('total_ap', 0)}")
    print(f"  Accuracy: {summary.get('accuracy', 0.0)}%")

    print("\nTop 5 songs by play count")
    if not top_songs:
        print("  No data yet.")
    else:
        for idx, row in enumerate(top_songs, start=1):
            print(f"  {idx}. {row.get('song_name', 'Unknown')} - {row.get('play_count', 0)} plays")

    print("\nLast 5 songs")
    if not recent:
        print("  No data yet.")
    else:
        for idx, row in enumerate(recent, start=1):
            print(
                f"  {idx}. {row.get('song_name', 'Unknown')} ({row.get('difficulty', '--')}) - {row.get('timestamp', '--')}"
            )


def view_sync_jobs(api: BangStatsAPI) -> None:
    status_filter_raw = input(
        "Filter by status (queued/running/succeeded/failed, blank for all): "
    ).strip()
    status_filter = status_filter_raw or None
    limit_raw = input("How many recent jobs to show? [10]: ").strip()
    try:
        limit = int(limit_raw) if limit_raw else 10
        if limit <= 0:
            raise ValueError
    except ValueError:
        print("Invalid limit, using 10.")
        limit = 10

    try:
        payload = api.list_sync_jobs(limit=limit, status=status_filter)
    except Exception as exc:
        print(f"Unable to fetch sync jobs: {exc}")
        return

    jobs = payload.get("jobs", [])
    if not jobs:
        print("No sync jobs found.")
        return

    print("\nRecent sync jobs:")
    for job in jobs:
        print(
            f"  #{job.get('id')} | {job.get('status')} | server={job.get('server')} "
            f"| created={job.get('created_at')}"
        )

    detail_raw = input("Enter job ID to view details (blank to go back): ").strip()
    if not detail_raw:
        return
    if not detail_raw.isdigit():
        print("Invalid job ID.")
        return

    try:
        detail = api.get_sync_job(int(detail_raw))
    except Exception as exc:
        print(f"Unable to fetch sync job detail: {exc}")
        return

    print("\nSync job detail:")
    print(f"  ID: {detail.get('id')}")
    print(f"  Status: {detail.get('status')}")
    print(f"  Server: {detail.get('server')}")
    print(f"  Requested by user: {detail.get('requested_by_user_id')}")
    print(f"  Created at: {detail.get('created_at')}")
    print(f"  Started at: {detail.get('started_at')}")
    print(f"  Finished at: {detail.get('finished_at')}")
    print(f"  Songs: {detail.get('songs')}")
    print(f"  Events: {detail.get('events')}")
    print(f"  Bands: {detail.get('bands')}")
    if detail.get("error_message"):
        print(f"  Error: {detail.get('error_message')}")


def update_user_settings(api: BangStatsAPI, user: dict) -> dict:
    leaving = False
    while not leaving:
        print(f"Current settings for user {user['username']}:")
        print(f"Game ID: {user['game_id']}")
        print(f"Server: {user['server']}")
        print(f"Screenshots Source: {user.get('screenshots_source', 'local')}")
        print(f"Screenshots Path: {user.get('screenshots_path', '')}")

        print("\nOptions to update:")
        print("1. Game ID")
        print("2. Server")
        print("3. Screenshots Source")
        print("4. Screenshots Path")
        print("5. Back to main menu")

        choice = input("Enter your choice: ").strip()
        if choice == "1":
            new_game_id = input("Enter new Game ID: ").strip()
            if new_game_id:
                user = api.update_user(int(user["id"]), {"game_id": new_game_id})
                print(f"Game ID updated to {user['game_id']}")
        elif choice == "2":
            new_server = input("Enter new Server (en/jp/tw/cn/kr): ").strip().lower()
            if new_server in SUPPORTED_SERVERS:
                user = api.update_user(int(user["id"]), {"server": new_server})
                print(f"Server updated to {user['server']}")
            else:
                print("Invalid server. Please try again.")
        elif choice == "3":
            new_source = input("Enter new Screenshots Source (local/remote): ").strip().lower()
            if new_source in ["local", "remote"]:
                user = api.update_user(int(user["id"]), {"screenshots_source": new_source})
                print(f"Screenshots Source updated to {user['screenshots_source']}")
            else:
                print("Invalid screenshots source. Please try again.")
        elif choice == "4":
            new_path = input("Enter new Screenshots Path: ").strip()
            if new_path:
                user = api.update_user(int(user["id"]), {"screenshots_path": new_path})
                print(f"Screenshots Path updated to {user['screenshots_path']}")
        elif choice == "5":
            leaving = True
        else:
            print("Invalid choice. Please try again.")

    return user
