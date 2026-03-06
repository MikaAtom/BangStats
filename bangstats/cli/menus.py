import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List
from loguru import logger

from bangstats.adapters.bestdori import RemoteDataService
from bangstats.services.data.event import EventService
from bangstats.services.data.song import SongService
from bangstats.services.data.band import BandService
from bangstats.services.data.screenshot import ScreenshotService
from bangstats.services.data.user import UserService
from bangstats.services.scanning.scan import ScanService
from bangstats.services.data.stats import (
    compute_difficulty_detail,
    compute_general_summary,
    compute_recent_plays,
    compute_song_difficulty_overview,
    compute_top_songs,
)

from scripts.song_data_organize import song_data_organize
from scripts.event_data_organize import event_data_organize
from scripts.band_data_organize import band_data_organize

game_server = "en"  # Default server, can be changed based on user input
SUPPORTED_SERVERS = ["en", "jp", "tw", "cn", "kr"]

song_service = SongService()
event_service = EventService()
band_service = BandService()
user_service = UserService()


def user_login(
    username: str | None = None,
    game_id: str | None = None,
    server: str | None = None,
):
    user = None
    while not user:
        entered_username = username if username is not None else input("Enter your username: ").strip()
        if not entered_username:
            print("Username cannot be empty. Please try again.")
            continue

        user = user_service.get_user_by_username(entered_username)
        if not user:
            resolved_game_id = game_id if game_id is not None else None
            while not resolved_game_id:
                resolved_game_id = input("Enter your game ID: ").strip()
                if not resolved_game_id:
                    print("Game ID cannot be empty. Please try again.")
                    continue

            resolved_server = server.lower() if isinstance(server, str) else None
            while resolved_server not in SUPPORTED_SERVERS:
                resolved_server = input("Enter your server (en/jp/tw/cn/kr): ").strip().lower()
                if resolved_server not in SUPPORTED_SERVERS:
                    print("Invalid server. Please enter one of: en, jp, tw, cn, kr.")
                    continue

            user_data = {
                "game_id": resolved_game_id,
                "username": entered_username,
                "server": resolved_server,
            }

            try:
                user = user_service.create_user(user_data)
                logger.info(
                    f"User created: {user.username} with Game ID: {user.game_id}"
                )
            except ValueError as e:
                logger.error(f"Error creating user: {e}")
                continue
        else:
            logger.info(f"User found: {user.username} with Game ID: {user.game_id}")

    return user


def get_db_counts() -> tuple[int, int, int]:
    return (
        len(song_service.get_all_songs()),
        len(event_service.get_all_events()),
        len(band_service.get_all_bands()),
    )


def update_db(server):
    def _localized_name(value, locale, fallback="Unknown"):
        if isinstance(value, dict):
            return value.get(locale) or fallback
        return fallback

    remote_data_service = RemoteDataService(server=server)

    songs_in_database = song_service.get_all_songs()
    print("Fetching songs from Bestdori...")
    songs_in_remote = remote_data_service.get_songs_ids()

    logger.info(f"Database initialized with {len(songs_in_database)} songs.")
    logger.info(f"Remote songs fetched: {len(songs_in_remote)} song IDs.")

    songs_in_database_ids = [song.internal_song_id for song in songs_in_database]

    missing_songs = sorted(set(songs_in_remote) - set(songs_in_database_ids))

    if len(missing_songs) > 0:
        total_songs = len(missing_songs)
        print(f"\n--- Updating songs ({total_songs} new) ---")
        logger.info("Mismatch between remote and local song IDs. Updating database...")

        songs_data_by_id = {}
        print("Fetching song details...")
        fetched_count = 0
        max_workers = min(8, total_songs)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_song_id = {
                executor.submit(remote_data_service.get_song_info, song_id): song_id
                for song_id in missing_songs
            }

            for future in as_completed(future_to_song_id):
                song_id = future_to_song_id[future]
                fetched_count += 1
                try:
                    song_data = future.result()
                    if song_data:
                        songs_data_by_id[song_id] = song_data
                except Exception as exc:
                    logger.error(f"Error fetching song {song_id}: {exc}")

                print(f"Fetching song details... ({fetched_count}/{total_songs})")

        for index, song_id in enumerate(missing_songs, start=1):
            song_data = songs_data_by_id.get(song_id)
            if not song_data:
                logger.warning(f"Skipping song {song_id}: no data received")
                continue

            organized_data = song_data_organize(song_data)
            created_song = song_service.create_song(organized_data)
            song_name = _localized_name(created_song.name, server)

            print(f"Updating song: {song_name} ({index}/{total_songs})")

            logger.info(
                f"Created song: {created_song.internal_song_id} - {song_name}"
            )
    else:
        print("\n--- Songs are up to date ---")

    events_in_database = event_service.get_all_events()
    print("Fetching events from Bestdori...")
    events_in_remote = remote_data_service.get_events_info()

    event_in_database_ids = [event.event_id for event in events_in_database]
    events_in_remote_ids = [int(event_id) for event_id in events_in_remote.keys()]

    logger.info(f"Database initialized with {len(events_in_database)} events.")
    logger.info(f"Remote events fetched: {len(events_in_remote)} event IDs.")

    missing_events = sorted(set(events_in_remote_ids) - set(event_in_database_ids))
    if len(missing_events) > 0:
        total_events = len(missing_events)
        print(f"\n--- Updating events ({total_events} new) ---")
        logger.info("Mismatch between remote and local event IDs. Updating database...")

        for index, event_id in enumerate(missing_events, start=1):
            event_data = events_in_remote.get(str(event_id))

            if event_data:
                organized_event_data = event_data_organize(event_id, event_data)
                created_event = event_service.create_event(organized_event_data)
                event_name = _localized_name(created_event.event_name, server)

                print(f"Updating event: {event_name} ({index}/{total_events})")

                logger.info(
                    f"Created event: {created_event.event_id} - {event_name}"
                )
    else:
        print("\n--- Events are up to date ---")

    bands_in_database = band_service.get_all_bands()
    print("Fetching bands from Bestdori...")
    bands_in_remote = remote_data_service.get_bands_info()

    bands_in_database_ids = [band.internal_band_id for band in bands_in_database]
    bands_in_remote_ids = [int(band_id) for band_id in bands_in_remote.keys()]

    logger.info(f"Database initialized with {len(bands_in_database)} bands.")
    logger.info(f"Remote bands fetched: {len(bands_in_remote)} band IDs.")

    missing_bands = sorted(set(bands_in_remote_ids) - set(bands_in_database_ids))
    if len(missing_bands) > 0:
        total_bands = len(missing_bands)
        print(f"\n--- Updating bands ({total_bands} new) ---")
        logger.info("Mismatch between remote and local band IDs. Updating database...")

        for index, band_id in enumerate(missing_bands, start=1):
            band_data = bands_in_remote.get(str(band_id))

            if band_data:
                organized_band_data = band_data_organize(band_id, band_data)

                created_band = band_service.create_band(organized_band_data)
                band_name = _localized_name(created_band.name, server)
                print(f"Updating band: {band_name} ({index}/{total_bands})")
                logger.info(
                    f"Created band: {created_band.internal_band_id} - {band_name}"
                )
    else:
        print("\n--- Bands are up to date ---")

    songs_in_database = len(song_service.get_all_songs())
    events_in_database = len(event_service.get_all_events())
    bands_in_database = len(band_service.get_all_bands())

    return songs_in_database, events_in_database, bands_in_database


def scan_screenshots(user, screenshots_path_override: str | None = None):
    leaving = False
    scan_service = ScanService()

    while not leaving:
        screenshots_source = user.screenshots_source
        screenshots_path = screenshots_path_override or user.screenshots_path

        if screenshots_source != "local":
            print("Remote screenshots source is not supported yet. Setting to local.")
            screenshots_source = "local"
        if not screenshots_path:
            screenshots_path = input("Enter the path to your screenshots directory: ").strip()
            if not screenshots_path:
                print("Screenshots path cannot be empty. Please try again.")
                return

        while not os.path.exists(screenshots_path):
            print(f"Path {screenshots_path} does not exist. Please try again.")
            screenshots_path = input("Enter the path to your screenshots directory: ").strip()

        images = [
            f
            for f in os.listdir(screenshots_path)
            if f.lower().endswith((".png", ".jpg", ".jpeg"))
        ]
        if not images:
            print(
                f"No images found in {screenshots_path}. Please add some screenshots and try again."
            )
            return
        images.sort()
        print(f"Found {len(images)} images in {screenshots_path}.")
        print("Starting scan...")

        scan_result = scan_service.scan_images(
            screenshots_path,
            images,
            user_id=user.id,
            persist_to_db=True,
        )

        print("Scan completed. Results:")
        print(f"Total images scanned: {scan_result['total_scanned']}")
        print(f"Successful scans: {scan_result['successful']}")
        print(f"Validated scans: {scan_result.get('validated', 0)}")
        print(f"Persisted to DB: {scan_result.get('persisted', 0)}")
        print(f"Failed to persist: {scan_result.get('failed_to_persist', 0)}")
        print(f"Skipped (duplicate): {scan_result.get('skipped_duplicates', 0)}")
        print("Errors:")
        for error_type, count in scan_result["errors"].items():
            print(f"  {error_type.replace('_', ' ').title()}: {count}")
            if count > 0:
                print(
                    f"    Files with {error_type.replace('_', ' ')}: {', '.join(scan_result['error_files'][error_type])}"
                )

        leaving = True


def _resolve_song_name(song_id: int, server: str = "en") -> str:
    song = song_service.get_song_by_internal_id(song_id)
    if not song or not isinstance(song.name, dict):
        return f"Song {song_id}"
    return song.name.get(server) or song.name.get("en") or f"Song {song_id}"


def _format_play_meta(meta: Dict[str, Any] | None) -> str:
    if not meta:
        return "--"
    timestamp = meta.get("timestamp")
    filename = meta.get("filename") or "--"
    if timestamp is None:
        return f"-- {filename}"
    return f"{timestamp:%Y-%m-%d %H:%M:%S} {filename}"


def _display_general_summary(summary: Dict[str, Any]) -> None:
    print("\nGeneral Summary")
    print(f"  Total plays: {summary['total_plays']}")
    print(f"  Total FC: {summary['total_fc']}")
    print(f"  Total AP: {summary['total_ap']}")
    print(f"  Accuracy: {summary['accuracy']}%")


def _display_top_songs(top_songs: List[Dict[str, Any]], server: str) -> None:
    print("\nTop 5 songs by play count")
    if not top_songs:
        print("  No data yet.")
        return
    for idx, row in enumerate(top_songs, start=1):
        name = _resolve_song_name(row["song_id"], server)
        print(f"  {idx}. {name} - {row['play_count']} plays")


def _display_recent_plays(recent: List[Dict[str, Any]], server: str) -> None:
    print("\nLast 5 songs")
    if not recent:
        print("  No data yet.")
        return
    for idx, row in enumerate(recent, start=1):
        name = _resolve_song_name(row["song_id"], server)
        timestamp = row.get("timestamp")
        when = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else "--"
        print(f"  {idx}. {name} ({row['difficulty']}) - {when}")


def _display_difficulty_detail(detail: Dict[str, Any]) -> None:
    print(f"\n  Total plays: {detail['total_plays']}")
    print(f"  Total FC: {detail['total_fc']}")
    print(f"  Total AP: {detail['total_ap']}")
    print(f"  Accuracy: {detail['accuracy']}%")
    print(f"  First played: {_format_play_meta(detail['first_played'])}")
    print(f"  Last played: {_format_play_meta(detail['last_played'])}")
    print(f"  First FC: {_format_play_meta(detail['first_fc'])}")
    print(f"  Last FC: {_format_play_meta(detail['last_fc'])}")
    print(f"  First AP: {_format_play_meta(detail['first_ap'])}")
    print(f"  Last AP: {_format_play_meta(detail['last_ap'])}")
    print(
        "  Times played before first FC: "
        + (str(detail["plays_before_fc"]) if detail["plays_before_fc"] is not None else "--")
    )
    print(
        "  Times played before first AP: "
        + (str(detail["plays_before_ap"]) if detail["plays_before_ap"] is not None else "--")
    )


def _search_songs_case_insensitive(name_query: str) -> List[Any]:
    languages = ["en", "jp", "tw", "cn", "kr"]
    merged = {}
    for lang in languages:
        for song in song_service.search_songs_by_name(name_query, language=lang):
            merged[song.internal_song_id] = song
    return list(merged.values())


def _song_search_loop(user, screenshot_service: ScreenshotService) -> None:
    while True:
        query = input("\nEnter song name for detailed stats (or q to go back): ").strip()
        if query.lower() == "q":
            return
        if not query:
            print("Song name cannot be empty.")
            continue

        songs = _search_songs_case_insensitive(query)
        if not songs:
            print("No matching songs found.")
            continue

        selected_song = songs[0]
        if len(songs) > 1:
            print("\nMultiple matches:")
            for idx, song in enumerate(songs, start=1):
                song_name = song.name.get(user.server) or song.name.get("en") or "Unknown"
                print(f"  {idx}. {song_name} (ID: {song.internal_song_id})")
            picked = input("Pick a song by number (or q to cancel): ").strip()
            if picked.lower() == "q":
                continue
            if not picked.isdigit() or not (1 <= int(picked) <= len(songs)):
                print("Invalid selection.")
                continue
            selected_song = songs[int(picked) - 1]

        song_name = (
            selected_song.name.get(user.server)
            or selected_song.name.get("en")
            or "Unknown"
        )
        song_plays = screenshot_service.get_screenshots_by_song(user.id, selected_song.internal_song_id)
        if not song_plays:
            print(f"No plays found for {song_name}.")
            continue

        print(f"\n{song_name}")
        overview = compute_song_difficulty_overview(song_plays)
        difficulties = sorted(overview.keys())
        for difficulty in difficulties:
            first_played = _format_play_meta(overview[difficulty]["first_played"])
            print(f"  {difficulty:<8} - first played {first_played}")

        difficulty = input("Select difficulty (or q to cancel): ").strip().lower()
        if difficulty == "q":
            continue
        if difficulty not in overview:
            print("Invalid difficulty.")
            continue

        plays = screenshot_service.get_screenshots_by_song(
            user.id, selected_song.internal_song_id, difficulty
        )
        detail = compute_difficulty_detail(plays)
        print(f"\nDetailed stats for {song_name} [{difficulty}]")
        _display_difficulty_detail(detail)


def view_stats(user) -> None:
    screenshot_service = ScreenshotService()
    screenshots = screenshot_service.get_screenshots_by_user(user.id)
    if not screenshots:
        print("No screenshots found for this user yet.")
        return

    summary = compute_general_summary(screenshots)
    top_songs = compute_top_songs(screenshots, n=5)
    recent = compute_recent_plays(screenshots, n=5)

    _display_general_summary(summary)
    _display_top_songs(top_songs, user.server)
    _display_recent_plays(recent, user.server)
    _song_search_loop(user, screenshot_service)


def update_user_settings(user):
    leaving = False
    while not leaving:
        print(f"Current settings for user {user.username}:")
        print(f"Game ID: {user.game_id}")
        print(f"Server: {user.server}")
        print(f"Screenshots Source: {user.screenshots_source}")
        print(f"Screenshots Path: {user.screenshots_path}")

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
                user_data = {"game_id": new_game_id}
                try:
                    updated_user = user_service.update_user(user.id, user_data)
                    print(f"Game ID updated to {updated_user.game_id}")
                except ValueError as err:
                    print(f"Error updating Game ID: {err}")
        elif choice == "2":
            new_server = input("Enter new Server (en/jp/tw/cn/kr): ").strip().lower()
            if new_server in SUPPORTED_SERVERS:
                user_data = {"server": new_server}
                try:
                    updated_user = user_service.update_user(user.id, user_data)
                    print(f"Server updated to {updated_user.server}")
                except ValueError as err:
                    print(f"Error updating Server: {err}")
            else:
                print("Invalid server. Please try again.")
        elif choice == "3":
            new_screenshots_source = (
                input("Enter new Screenshots Source (local/remote): ").strip().lower()
            )
            if new_screenshots_source in ["local", "remote"]:
                user_data = {"screenshots_source": new_screenshots_source}
                try:
                    updated_user = user_service.update_user(user.id, user_data)
                    print(
                        f"Screenshots Source updated to {updated_user.screenshots_source}"
                    )
                except ValueError as err:
                    print(f"Error updating Screenshots Source: {err}")
            else:
                print("Invalid screenshots source. Please try again.")
        elif choice == "4":
            new_screenshots_path = input("Enter new Screenshots Path: ").strip()
            if new_screenshots_path:
                user_data = {"screenshots_path": new_screenshots_path}
                try:
                    updated_user = user_service.update_user(user.id, user_data)
                    print(f"Screenshots Path updated to {updated_user.screenshots_path}")
                except ValueError as err:
                    print(f"Error updating Screenshots Path: {err}")
        elif choice == "5":
            leaving = True
        else:
            print("Invalid choice. Please try again.")
