from pathlib import Path
from copy import deepcopy
from typing import Any
from getpass import getpass

from bangstats_cli.api_client import BangStatsAPI
from bangstats_cli.cache import resolve_song_name, search_songs

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
    register_mode: bool = False,
) -> dict:
    while True:
        mode = "register" if register_mode else ""
        if not mode:
            print("\nAuth:")
            print("1. Login")
            print("2. Register")
            choice = input("Choose option [1/2]: ").strip()
            mode = "register" if choice == "2" else "login"

        entered_username = username if username is not None else input("Enter your username: ").strip()
        if not entered_username:
            print("Username cannot be empty. Please try again.")
            continue
        password = getpass("Enter your password: ").strip()
        if not password:
            print("Password cannot be empty. Please try again.")
            continue

        try:
            if mode == "register":
                resolved_game_id = game_id if game_id is not None else ""
                while not resolved_game_id:
                    resolved_game_id = input("Enter your game ID: ").strip()
                    if not resolved_game_id:
                        print("Game ID cannot be empty. Please try again.")

                default_server = (server or "en").lower()
                if default_server not in SUPPORTED_SERVERS:
                    default_server = "en"
                entered_server = input(
                    f"Enter your server (en/jp/tw/cn/kr) [{default_server}]: "
                ).strip().lower()
                resolved_server = entered_server or default_server
                if resolved_server not in SUPPORTED_SERVERS:
                    print("Invalid server. Please enter one of: en, jp, tw, cn, kr.")
                    continue

                payload = api.register(
                    {
                        "username": entered_username,
                        "password": password,
                        "game_id": resolved_game_id,
                        "server": resolved_server,
                    }
                )
                user = payload["user"]
                print(f"Registered and logged in as {user['username']} ({user['server'].upper()} server)")
                return user

            payload = api.login(entered_username, password)
            user = payload["user"]
            print(f"Logged in as {user['username']} ({user['server'].upper()} server)")
            return user
        except Exception as exc:
            print(f"Auth failed: {exc}")
            # After a failed forced register attempt, continue with menu flow.
            register_mode = False


def _prompt_local_path(initial_value: str | None = None) -> str | None:
    current = (initial_value or "").strip()
    while True:
        prompt = "Enter local screenshots directory path"
        if current:
            prompt += f" [{current}]"
        prompt += ": "
        entered = input(prompt).strip()
        candidate = entered or current
        if not candidate:
            print("Screenshots path cannot be empty.")
            continue
        path = Path(candidate).expanduser()
        if not path.exists() or not path.is_dir():
            print(f"Path is not a directory: {path}")
            continue
        return str(path)


def _authorize_server_folder_if_needed(api: BangStatsAPI, user: dict) -> dict | None:
    if bool(user.get("server_folder_authorized", False)):
        return user
    print("Server folder access requires master key authorization.")
    master_key = getpass("Enter master key: ").strip()
    if not master_key:
        print("Master key cannot be empty.")
        return None
    try:
        api.authorize_server_folder(master_key=master_key)
        refreshed = api.get_user(int(user["id"]))
        print("Server folder access authorized.")
        return refreshed
    except Exception as exc:
        print(f"Authorization failed: {exc}")
        return None


def _prompt_server_folder_path(api: BangStatsAPI, user: dict, initial_value: str | None = None) -> str | None:
    current = (initial_value or "").strip()
    while True:
        prompt = "Enter server screenshots directory path"
        if current:
            prompt += f" [{current}]"
        prompt += ": "
        entered = input(prompt).strip()
        candidate = entered or current
        if not candidate:
            print("Server folder path cannot be empty.")
            continue
        try:
            locality = api.check_scan_local_path_for_user(
                folder_path=candidate,
                user_id=int(user["id"]),
            )
        except Exception as exc:
            print(f"Server path validation failed: {exc}")
            continue
        if not locality.get("is_local"):
            print("Path is not accessible on server.")
            continue
        return str(locality.get("canonical_path") or candidate)


def _safe_update_user(api: BangStatsAPI, user: dict, payload: dict[str, Any]) -> dict:
    try:
        return api.update_user(int(user["id"]), payload)
    except Exception as exc:
        detail = ""
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                data = response.json()
                detail = str(data.get("detail", "")).strip()
            except Exception:
                detail = str(getattr(response, "text", "")).strip()
        message = detail or str(exc)
        print(f"Unable to update screenshot settings: {message}")
        return user


def _format_api_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            data = response.json()
            detail = str(data.get("detail", "")).strip()
            if detail:
                return detail
        except Exception:
            pass
        text = str(getattr(response, "text", "")).strip()
        if text:
            return text
    return str(exc)


def screenshot_location_setup(
    api: BangStatsAPI,
    user: dict,
    *,
    dev_mode: bool = False,
    dev_config: dict[str, Any] | None = None,
) -> dict:
    _ = dev_mode
    _ = dev_config
    source = str(user.get("screenshots_source", "local") or "local").strip().lower()
    if source == "remote":
        source = "local"
    path = str(user.get("screenshots_path", "") or "").strip()
    has_settings = bool(path)

    if has_settings:
        print("\nCurrent screenshot settings:")
        print(f"  source: {source}")
        print(f"  path: {path}")
        keep = input("Keep current screenshot location settings? (Y/n): ").strip().lower()
        if keep not in {"n", "no"}:
            return user
        print("Update options:")
        print("1. Change source type")
        print("2. Change path only")
        print("3. Change sync command only")
        print("0. Cancel")
        change_choice = input("Choose option: ").strip()
        if change_choice == "0":
            return user
        if change_choice == "3":
            new_sync = input("Enter sync command (blank to clear): ").strip() or None
            return _safe_update_user(api, user, {"sync_command": new_sync})
        if change_choice == "2":
            if source == "server_folder":
                refreshed = _authorize_server_folder_if_needed(api, user)
                if refreshed is None:
                    return user
                user = refreshed
                new_path = _prompt_server_folder_path(api, user, path)
            else:
                new_path = _prompt_local_path(path)
            if not new_path:
                return user
            return _safe_update_user(api, user, {"screenshots_path": new_path})

    print("\nWhere are screenshots located?")
    print("1. On this computer (upload to server)")
    print("2. On server filesystem (requires authorization)")
    source_choice = input("Choose source: ").strip()
    if source_choice not in {"1", "2"}:
        print("Invalid source choice.")
        return user

    if source_choice == "1":
        local_path = _prompt_local_path(path if source == "local" else "")
        if not local_path:
            return user
        return _safe_update_user(
            api,
            user,
            {
                "screenshots_source": "local",
                "screenshots_path": local_path,
            },
        )

    refreshed = _authorize_server_folder_if_needed(api, user)
    if refreshed is None:
        return user
    user = refreshed
    server_path = _prompt_server_folder_path(api, user, path if source == "server_folder" else "")
    if not server_path:
        return user
    sync_command_raw = input("Optional sync command (blank to skip): ").strip()
    payload: dict[str, Any] = {
        "screenshots_source": "server_folder",
        "screenshots_path": server_path,
    }
    payload["sync_command"] = sync_command_raw or None
    return _safe_update_user(api, user, payload)


def scan_screenshots(
    api: BangStatsAPI,
    user: dict,
    screenshots_path_override: str | None = None,
    *,
    dev_mode: bool = False,
    dev_config: dict[str, Any] | None = None,
) -> dict:
    source = "local"
    screenshots_path = screenshots_path_override or user.get("screenshots_path", "")
    if screenshots_path_override:
        source = "local"
    else:
        user = screenshot_location_setup(api, user, dev_mode=dev_mode, dev_config=dev_config)
        source = str(user.get("screenshots_source", "local") or "local").strip().lower()
        if source == "remote":
            source = "local"
        screenshots_path = str(user.get("screenshots_path", "") or "")

    if not screenshots_path:
        print("Screenshots path is not configured.")
        return user

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

    print("Starting scan job...")
    if source == "server_folder":
        try:
            locality = api.check_scan_local_path_for_user(
                folder_path=str(screenshots_path),
                user_id=int(user["id"]),
            )
        except Exception as exc:
            print(f"Server path validation failed: {exc}")
            return user
        if not locality.get("is_local"):
            print("Configured server path is not accessible.")
            return user
        server_path = locality.get("canonical_path") or str(screenshots_path)
        try:
            job = api.create_scan_job(
                user_id=int(user["id"]),
                source_type="server_folder",
                folder_path=server_path,
                filenames=[],
                parallel_workers=parallel_workers,
                keys_per_worker=keys_per_worker,
            )
        except Exception as exc:
            print(f"Failed to create scan job: {_format_api_error(exc)}")
            return user
        print(
            f"Scan job #{job.get('id')} started (status={job.get('status')}, total={job.get('total_files', 0)})."
        )
        print("Use option 7 to monitor progress/history while continuing to use the app.")
        return user

    screenshots_dir = Path(str(screenshots_path)).expanduser()
    if not screenshots_dir.exists() or not screenshots_dir.is_dir():
        print(f"Path is not a directory: {screenshots_dir}")
        return user

    allowed_suffixes = {".png", ".jpg", ".jpeg", ".heic", ".heif"}
    images = sorted(
        [
            path
            for path in screenshots_dir.iterdir()
            if path.is_file() and path.suffix.lower() in allowed_suffixes
        ]
    )
    if not images:
        print(f"No images found in {screenshots_dir}.")
        return user

    print(f"Found {len(images)} images in {screenshots_dir}.")
    image_filenames = [path.name for path in images]
    try:
        diff = api.get_scan_filename_diff(
            user_id=int(user["id"]),
            filenames=image_filenames,
        )
    except Exception as exc:
        print(f"Filename precheck failed, continuing with full upload: {exc}")
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
        return user

    to_scan_set = set(to_scan_filenames)
    filtered_images = [path for path in images if path.name in to_scan_set]
    print(f"Uploading {len(filtered_images)} files to server storage...")
    try:
        upload_payload = api.upload_scan_files(int(user["id"]), filtered_images)
    except Exception as exc:
        print(f"Upload failed: {exc}")
        return user

    print(
        f"Upload completed: {upload_payload.get('uploaded_files', 0)} files "
        f"(stored={upload_payload.get('total_uploaded_for_user', 0)}, "
        f"size={upload_payload.get('total_storage_mb_for_user', 0.0)} MB)."
    )
    try:
        job = api.create_scan_job(
            user_id=int(user["id"]),
            source_type="upload",
            filenames=to_scan_filenames,
            parallel_workers=parallel_workers,
            keys_per_worker=keys_per_worker,
        )
    except Exception as exc:
        print(f"Failed to create scan job: {_format_api_error(exc)}")
        return user
    print(
        f"Scan job #{job.get('id')} started (status={job.get('status')}, total={job.get('total_files', 0)})."
    )
    print("Use option 7 to monitor progress/history while continuing to use the app.")
    return user


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


def _format_play_meta(meta: dict[str, Any] | None) -> str:
    if not meta:
        return "--"
    timestamp = meta.get("timestamp")
    filename = meta.get("filename") or "--"
    return f"{timestamp or '--'} {filename}"


def _print_song_difficulty_overview(overview: list[dict[str, Any]]) -> None:
    if not overview:
        print("No difficulty data found for this song.")
        return
    for item in overview:
        difficulty = str(item.get("difficulty", "--"))
        first_played = _format_play_meta(item.get("first_played"))
        total_plays = int(item.get("total_plays", 0) or 0)
        est_time = item.get("estimated_time_played_human", "0m")
        print(
            f"  {difficulty:<8} - first played {first_played} "
            f"(plays: {total_plays}, time: {est_time})"
        )


def _print_song_difficulty_detail(detail: dict[str, Any]) -> None:
    print(f"\n  Total plays: {detail.get('total_plays', 0)}")
    print(f"  Total FC: {detail.get('total_fc', 0)}")
    print(f"  Total AP: {detail.get('total_ap', 0)}")
    print(f"  Accuracy: {detail.get('accuracy', 0.0)}%")
    print(f"  First played: {_format_play_meta(detail.get('first_played'))}")
    print(f"  Last played: {_format_play_meta(detail.get('last_played'))}")
    print(f"  First FC: {_format_play_meta(detail.get('first_fc'))}")
    print(f"  Last FC: {_format_play_meta(detail.get('last_fc'))}")
    print(f"  First AP: {_format_play_meta(detail.get('first_ap'))}")
    print(f"  Last AP: {_format_play_meta(detail.get('last_ap'))}")
    plays_before_fc = detail.get("plays_before_fc")
    plays_before_ap = detail.get("plays_before_ap")
    print(
        "  Times played before first FC: "
        + (str(plays_before_fc) if plays_before_fc is not None else "--")
    )
    print(
        "  Times played before first AP: "
        + (str(plays_before_ap) if plays_before_ap is not None else "--")
    )
    print(f"  Estimated time played: {detail.get('estimated_time_played_human', '0m')}")
    print(
        f"  Sessions (gap {detail.get('session_gap_minutes_used', 45)}m): "
        f"{detail.get('total_sessions', 0)} "
        f"(avg plays/session: {detail.get('avg_plays_per_session', 0.0)})"
    )
    print(
        f"  Longest session: {detail.get('longest_session_plays', 0)} plays, "
        f"{detail.get('longest_session_minutes', 0)} min"
    )
    print(
        f"  Practice bursts (>=3 plays/session): {detail.get('practice_burst_count', 0)} "
        f"(max burst: {detail.get('max_practice_burst_plays', 0)} plays)"
    )


def _song_search_loop(api: BangStatsAPI, user: dict, song_cache: dict[str, Any] | None = None) -> None:
    user_id = int(user["id"])
    user_server = str(user.get("server", "en") or "en")
    while True:
        query = input("\nEnter song name for detailed stats (or q to go back): ").strip()
        if query.lower() == "q":
            return
        if not query:
            print("Song name cannot be empty.")
            continue

        results = search_songs(song_cache or {}, query, server=user_server, limit=20)
        if not results:
            try:
                payload = api.search_user_stat_songs(
                    user_id,
                    query,
                    server=user_server,
                    limit=20,
                )
            except Exception as exc:
                print(f"Song search failed: {exc}")
                continue
            results = payload.get("results", [])
        if not isinstance(results, list) or not results:
            print("No matching songs found.")
            continue

        selected = results[0]
        if len(results) > 1:
            print("\nMultiple matches:")
            for idx, result in enumerate(results, start=1):
                print(
                    f"  {idx}. {result.get('song_name', 'Unknown')} "
                    f"(ID: {result.get('song_id', '?')})"
                )
            picked = input("Pick a song by number (or q to cancel): ").strip().lower()
            if picked == "q":
                continue
            if not picked.isdigit() or not (1 <= int(picked) <= len(results)):
                print("Invalid selection.")
                continue
            selected = results[int(picked) - 1]

        song_id = int(selected.get("song_id", 0) or 0)
        song_name = selected.get("song_name") or f"Song {song_id}"
        if song_id <= 0:
            print("Selected result has invalid song ID.")
            continue

        try:
            song_payload = api.get_user_song_stats(
                user_id,
                song_id,
                server=user_server,
            )
        except Exception as exc:
            print(f"Unable to load song stats: {exc}")
            continue

        overview = song_payload.get("difficulty_overview", [])
        local_name = resolve_song_name(song_cache or {}, song_id, user_server)
        song_payload_name = song_payload.get("song_name") or local_name or song_name
        print(f"\n{song_payload_name}")
        _print_song_difficulty_overview(overview if isinstance(overview, list) else [])

        available_difficulties = {
            str(item.get("difficulty", "")).lower()
            for item in overview
            if isinstance(item, dict) and item.get("difficulty")
        }
        if not available_difficulties:
            continue

        while True:
            difficulty = input("Select difficulty (or q to cancel): ").strip().lower()
            if difficulty == "q":
                break
            if difficulty not in available_difficulties:
                print(
                    "Invalid difficulty. Available: "
                    + ", ".join(sorted(available_difficulties))
                )
                continue
            try:
                detail_payload = api.get_user_song_stats(
                    user_id,
                    song_id,
                    server=user_server,
                    difficulty=difficulty,
                )
            except Exception as exc:
                print(f"Unable to load detailed stats: {exc}")
                break
            detail = detail_payload.get("detail")
            if not isinstance(detail, dict):
                print(f"No detailed stats found for {song_name} [{difficulty}].")
                break
            print(
                f"\nDetailed stats for {detail_payload.get('song_name', song_payload_name or song_name)} "
                f"[{difficulty}]"
            )
            _print_song_difficulty_detail(detail)
            break


def _view_stats_milestones(api: BangStatsAPI, user: dict) -> None:
    try:
        payload = api.get_user_stats_milestones(int(user["id"]))
    except Exception as exc:
        print(f"Unable to fetch milestones: {exc}")
        return

    print("\nMilestones")
    print(f"  Best streak: {payload.get('best_streak_days', 0)} days")
    print(f"  Current streak: {payload.get('current_streak_days', 0)} days")
    milestones = payload.get("milestones", [])
    if not isinstance(milestones, list) or not milestones:
        print("  No milestones yet.")
        return
    for idx, milestone in enumerate(milestones, start=1):
        meta = milestone.get("meta") if isinstance(milestone, dict) else None
        print(
            f"  {idx}. {milestone.get('label', '--')} "
            f"(play #{milestone.get('play_count', '--')}) "
            f"- {_format_play_meta(meta if isinstance(meta, dict) else None)}"
        )


def _view_stats_activity(api: BangStatsAPI, user: dict) -> None:
    print("\nActivity ranges")
    print("  1. Last 7 days")
    print("  2. Last 30 days")
    print("  3. Last 90 days")
    print("  4. Custom range")
    choice = input("Select range (or q to go back): ").strip().lower()
    if choice == "q":
        return

    try:
        if choice == "1":
            payload = api.get_user_stats_activity(int(user["id"]), preset="7d")
        elif choice == "2":
            payload = api.get_user_stats_activity(int(user["id"]), preset="30d")
        elif choice == "3":
            payload = api.get_user_stats_activity(int(user["id"]), preset="90d")
        elif choice == "4":
            from_date = input("From date (YYYY-MM-DD): ").strip()
            to_date = input("To date (YYYY-MM-DD): ").strip()
            payload = api.get_user_stats_activity(
                int(user["id"]),
                preset=None,
                from_date=from_date,
                to_date=to_date,
            )
        else:
            print("Invalid option.")
            return
    except Exception as exc:
        print(f"Unable to fetch activity stats: {exc}")
        return

    summary = payload.get("summary", {})
    delta = payload.get("delta_vs_previous", {})
    print(
        f"\nActivity {payload.get('from_date', '--')} -> {payload.get('to_date', '--')} "
        f"({payload.get('days', 0)} days)"
    )
    print(f"  Plays: {summary.get('total_plays', 0)}")
    print(f"  FC: {summary.get('total_fc', 0)}")
    print(f"  AP: {summary.get('total_ap', 0)}")
    print(f"  Accuracy: {summary.get('accuracy', 0.0)}%")
    print(f"  Active days: {payload.get('active_days', 0)}")
    print(f"  Avg plays/day: {payload.get('avg_plays_per_day', 0.0)}")
    print(f"  Best streak in range: {payload.get('range_streak_days', 0)} days")
    print(
        f"  Delta vs previous window: plays {delta.get('plays_delta', 0)} "
        f"({delta.get('plays_delta_pct', 0.0)}%), accuracy {delta.get('accuracy_delta', 0.0)}%"
    )


def _view_stats_calendar(api: BangStatsAPI, user: dict) -> None:
    year_raw = input("Year [current]: ").strip()
    month_raw = input("Month 1-12 [current]: ").strip()

    kwargs: dict[str, Any] = {}
    if year_raw:
        if not year_raw.isdigit():
            print("Invalid year.")
            return
        kwargs["year"] = int(year_raw)
    if month_raw:
        if not month_raw.isdigit():
            print("Invalid month.")
            return
        kwargs["month"] = int(month_raw)

    try:
        payload = api.get_user_stats_calendar(int(user["id"]), **kwargs)
    except Exception as exc:
        print(f"Unable to fetch calendar stats: {exc}")
        return

    print(f"\nCalendar {payload.get('year')}-{int(payload.get('month', 0)):02d}")
    print(f"  Days with plays: {payload.get('total_days_with_plays', 0)}")
    days = payload.get("days", [])
    if not isinstance(days, list) or not days:
        print("  No plays in this month.")
        return
    for day in days:
        difficulties = day.get("difficulties", {})
        diffs = ", ".join(f"{k}:{v}" for k, v in sorted(difficulties.items())) if difficulties else "--"
        print(
            f"  {day.get('date')} | plays={day.get('plays', 0)} "
            f"fc={day.get('fc', 0)} ap={day.get('ap', 0)} "
            f"acc={day.get('accuracy', 0.0)}% | {diffs}"
        )


def _view_stats_insights(
    api: BangStatsAPI,
    user: dict,
    song_cache: dict[str, Any] | None = None,
) -> None:
    print("\nInsights range")
    print("  1. Last 7 days")
    print("  2. Last 30 days")
    print("  3. Last 90 days")
    print("  4. Custom range")
    choice = input("Select range (or q to go back): ").strip().lower()
    if choice == "q":
        return

    session_gap_raw = input("Session gap in minutes [45]: ").strip()
    try:
        session_gap = int(session_gap_raw) if session_gap_raw else 45
        if session_gap < 5 or session_gap > 240:
            raise ValueError
    except ValueError:
        print("Invalid session gap, using default 45.")
        session_gap = 45

    try:
        if choice == "1":
            payload = api.get_user_stats_insights(
                int(user["id"]),
                preset="7d",
                session_gap_minutes=session_gap,
            )
        elif choice == "2":
            payload = api.get_user_stats_insights(
                int(user["id"]),
                preset="30d",
                session_gap_minutes=session_gap,
            )
        elif choice == "3":
            payload = api.get_user_stats_insights(
                int(user["id"]),
                preset="90d",
                session_gap_minutes=session_gap,
            )
        elif choice == "4":
            from_date = input("From date (YYYY-MM-DD): ").strip()
            to_date = input("To date (YYYY-MM-DD): ").strip()
            payload = api.get_user_stats_insights(
                int(user["id"]),
                preset=None,
                from_date=from_date,
                to_date=to_date,
                session_gap_minutes=session_gap,
            )
        else:
            print("Invalid option.")
            return
    except Exception as exc:
        print(f"Unable to fetch insights: {exc}")
        return

    print(
        f"\nInsights {payload.get('from_date', '--')} -> {payload.get('to_date', '--')} "
        f"(session gap: {payload.get('session_gap_minutes', session_gap)}m)"
    )
    data_quality = payload.get("data_quality", {})
    if data_quality.get("sparse_data"):
        print(
            "  Data quality: sparse "
            f"({data_quality.get('observed_plays', 0)}/"
            f"{data_quality.get('min_recommended_plays', 0)} recommended plays)"
        )
    else:
        print("  Data quality: sufficient")

    sessions = payload.get("sessions", {})
    print("\nSession habits")
    print(f"  Total sessions: {sessions.get('total_sessions', 0)}")
    print(f"  Avg session length: {sessions.get('avg_session_minutes', 0.0)} min")
    print(f"  Avg plays/session: {sessions.get('avg_plays_per_session', 0.0)}")
    print(f"  Longest session: {sessions.get('longest_session_minutes', 0)} min")
    print(f"  Longest session plays: {sessions.get('longest_session_plays', 0)}")
    print(f"  Recent cadence: every {sessions.get('recent_cadence_days', 0.0)} days")

    recent_sessions = payload.get("recent_sessions", [])
    if recent_sessions:
        print("\nRecent sessions")
        for item in recent_sessions:
            print(
                f"  {item.get('started_at', '--')} -> {item.get('ended_at', '--')} | "
                f"plays={item.get('plays', 0)} unique_songs={item.get('unique_songs', 0)} "
                f"duration={item.get('duration_minutes', 0)}m"
            )

    practice_periods = payload.get("practice_periods", [])
    print("\nTop practiced songs")
    if not practice_periods:
        print("  No dense practice periods detected.")
    else:
        for row in practice_periods:
            song_label = resolve_song_name(
                song_cache or {},
                int(row.get("song_id", 0) or 0),
                str(user.get("server", "en")),
            )
            print(
                f"  {song_label} | "
                f"bursts={row.get('burst_count', 0)} "
                f"max_burst={row.get('max_burst_plays', 0)} "
                f"plays={row.get('total_plays', 0)} "
                f"time={row.get('estimated_time_played_human', '0m')}"
            )

    repetition = payload.get("repetition", {})
    print("\nRepetition")
    print(
        f"  Repeated plays: {repetition.get('repeated_plays', 0)}/"
        f"{repetition.get('total_plays', 0)} "
        f"({round(float(repetition.get('repeated_ratio', 0.0)) * 100, 1)}%)"
    )
    for row in repetition.get("most_looped_songs", [])[:3]:
        song_label = resolve_song_name(
            song_cache or {},
            int(row.get("song_id", 0) or 0),
            str(user.get("server", "en")),
        )
        print(
            f"  Loop: {song_label} | "
            f"repeat_ratio={round(float(row.get('repeat_ratio', 0.0)) * 100, 1)}% "
            f"plays={row.get('play_count', 0)} "
            f"time={row.get('estimated_time_played_human', '0m')}"
        )

    recommendations = payload.get("recommendations", [])
    if recommendations:
        print("\nRecommendations")
        for rec in recommendations:
            target = (
                f" ({resolve_song_name(song_cache or {}, int(rec.get('song_id', 0) or 0), str(user.get('server', 'en')))})"
                if rec.get("song_id")
                else ""
            )
            print(f"  - {rec.get('title', '--')}{target}: {rec.get('detail', '--')}")


def _stats_views_loop(
    api: BangStatsAPI,
    user: dict,
    song_cache: dict[str, Any] | None = None,
) -> None:
    while True:
        print("\nStats views")
        print("  1. Song search and difficulty drill-down")
        print("  2. Historic milestones")
        print("  3. Activity ranges")
        print("  4. Calendar view")
        print("  5. Insights")
        print("  q. Back to dashboard")
        choice = input("Choose stats view: ").strip().lower()
        if choice == "q":
            return
        if choice == "1":
            _song_search_loop(api, user, song_cache=song_cache)
        elif choice == "2":
            _view_stats_milestones(api, user)
        elif choice == "3":
            _view_stats_activity(api, user)
        elif choice == "4":
            _view_stats_calendar(api, user)
        elif choice == "5":
            _view_stats_insights(api, user, song_cache=song_cache)
        else:
            print("Invalid choice.")


def view_stats(
    api: BangStatsAPI,
    user: dict,
    reference_cache: dict[str, Any] | None = None,
) -> None:
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

    song_cache = (reference_cache or {}).get("songs", {})

    print("\nTop 5 songs by play count")
    if not top_songs:
        print("  No data yet.")
    else:
        for idx, row in enumerate(top_songs, start=1):
            song_label = resolve_song_name(song_cache, int(row.get("song_id", 0) or 0), str(user.get("server", "en")))
            print(f"  {idx}. {song_label} - {row.get('play_count', 0)} plays")

    print("\nLast 5 songs")
    if not recent:
        print("  No data yet.")
    else:
        for idx, row in enumerate(recent, start=1):
            song_label = resolve_song_name(song_cache, int(row.get("song_id", 0) or 0), str(user.get("server", "en")))
            print(
                f"  {idx}. {song_label} ({row.get('difficulty', '--')}) - {row.get('timestamp', '--')}"
            )

    _stats_views_loop(api, user, song_cache=song_cache)


def view_jobs(api: BangStatsAPI) -> None:
    status_filter_raw = input(
        "Filter by status (queued/running/succeeded/failed/cancelled, blank for all): "
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

    scan_jobs = []
    sync_jobs = []
    try:
        scan_jobs = (api.list_scan_jobs(limit=limit, status=status_filter) or {}).get("jobs", [])
    except Exception as exc:
        print(f"Unable to fetch scan jobs: {exc}")
    try:
        sync_jobs = (api.list_sync_jobs(limit=limit, status=status_filter) or {}).get("jobs", [])
    except Exception as exc:
        print(f"Unable to fetch sync jobs: {exc}")

    if not scan_jobs and not sync_jobs:
        print("No jobs found.")
        return

    if scan_jobs:
        print("\nRecent scan jobs:")
        for job in scan_jobs:
            total = int(job.get("total_files", 0) or 0)
            processed = int(job.get("processed", 0) or 0)
            pct = round((processed / total) * 100, 1) if total > 0 else 0.0
            print(
                f"  s{job.get('id')} | {job.get('status')} | "
                f"progress={processed}/{total} ({pct}%) | created={job.get('created_at')}"
            )

    if sync_jobs:
        print("\nRecent sync jobs:")
        for job in sync_jobs:
            print(
                f"  y{job.get('id')} | {job.get('status')} | server={job.get('server')} "
                f"| created={job.get('created_at')}"
            )

    detail_raw = input("Enter job ID (s<ID> for scan, y<ID> for sync, blank to go back): ").strip().lower()
    if not detail_raw:
        return
    job_type = ""
    job_id_raw = detail_raw
    if detail_raw.startswith("s"):
        job_type = "scan"
        job_id_raw = detail_raw[1:]
    elif detail_raw.startswith("y"):
        job_type = "sync"
        job_id_raw = detail_raw[1:]
    if not job_id_raw.isdigit():
        print("Invalid job ID format.")
        return
    job_id = int(job_id_raw)

    if job_type == "scan":
        try:
            detail = api.get_scan_job(job_id)
        except Exception as exc:
            print(f"Unable to fetch scan job detail: {exc}")
            return
        print("\nScan job detail:")
        print(f"  ID: {detail.get('id')}")
        print(f"  Status: {detail.get('status')}")
        print(f"  Source type: {detail.get('source_type')}")
        print(f"  Folder path: {detail.get('folder_path')}")
        print(f"  Created at: {detail.get('created_at')}")
        print(f"  Started at: {detail.get('started_at')}")
        print(f"  Finished at: {detail.get('finished_at')}")
        print(f"  Total files: {detail.get('total_files')}")
        print(f"  Processed: {detail.get('processed')}")
        print(f"  Successful: {detail.get('successful')}")
        print(f"  Validated: {detail.get('validated')}")
        print(f"  Persisted: {detail.get('persisted')}")
        print(f"  Failed to persist: {detail.get('failed_to_persist')}")
        print(f"  Skipped duplicates: {detail.get('skipped_duplicates')}")
        if detail.get("error_message"):
            print(f"  Error: {detail.get('error_message')}")
        if detail.get("status") in {"queued", "running"}:
            cancel = input("Cancel this job? (y/N): ").strip().lower()
            if cancel in {"y", "yes"}:
                try:
                    updated = api.cancel_scan_job(job_id)
                    print(f"Job status is now: {updated.get('status')}")
                except Exception as exc:
                    print(f"Cancel failed: {exc}")
        return

    try:
        detail = api.get_sync_job(job_id)
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
        print(f"Server folder authorized: {bool(user.get('server_folder_authorized', False))}")
        print(f"Sync command: {user.get('sync_command') or '-'}")

        print("\nOptions to update:")
        print("1. Game ID")
        print("2. Server")
        print("3. Screenshot location setup")
        print("4. Sync command")
        print("5. Show upload storage usage")
        print("6. Back to main menu")

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
            user = screenshot_location_setup(api, user)
        elif choice == "4":
            source = str(user.get("screenshots_source", "local")).lower()
            if source != "server_folder":
                print("Sync command is available only for server_folder source.")
                continue
            new_command = input("Enter sync command (blank to clear): ").strip() or None
            user = api.update_user(int(user["id"]), {"sync_command": new_command})
            print("Sync command updated.")
        elif choice == "5":
            try:
                usage = api.get_upload_usage(user_id=int(user["id"]))
                print("Upload storage usage:")
                print(f"  File count: {usage.get('file_count', 0)}")
                print(f"  Total size: {usage.get('total_size_mb', 0.0)} MB")
                print(f"  Oldest file age: {usage.get('oldest_file_age_days', 0.0)} days")
            except Exception as exc:
                print(f"Unable to fetch upload usage: {exc}")
        elif choice == "6":
            leaving = True
        else:
            print("Invalid choice. Please try again.")

    return user
