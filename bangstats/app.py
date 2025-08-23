import os
from dotenv import load_dotenv

# dotenv
load_dotenv()

from bangstats.config import config
from bangstats.database.db import init_db

from bangstats.services.remote_data_service import RemoteDataService

from bangstats.services.event_service import EventService
from bangstats.services.song_service import SongService
from bangstats.services.band_service import BandService
from bangstats.services.user_service import UserService
from bangstats.services.scan_service import ScanService

from bangstats.scripts.song_data_organize import song_data_organize
from bangstats.scripts.event_data_organize import event_data_organize
from bangstats.scripts.band_data_organize import band_data_organize

from bangstats.utils.setup_loguru import setup_loguru  # noqa
from loguru import logger

game_server = "en"  # Default server, can be changed based on user input

song_service = SongService()
event_service = EventService()
band_service = BandService()
user_service = UserService()


def user_login():
    user = None
    while not user:
        username = "MikaAtom"  # input("Enter your username: ").strip()
        if not username:
            print("Username cannot be empty. Please try again.")
            continue

        user = user_service.get_user_by_username(username)
        if not user:
            game_id = None
            while not game_id:
                game_id = input("Enter your game ID: ").strip()
                if not game_id:
                    print("Game ID cannot be empty. Please try again.")
                    continue

            server = None
            while server not in ["en", "jp", "tw", "cn", "kr"]:
                server = input("Enter your server (en/jp/tw/cn/kr): ").strip().lower()
                if server not in ["en", "jp", "tw", "cn", "kr"]:
                    print("Invalid server. Please enter one of: en, jp, tw, cn, kr.")
                    continue

            user_data = {"game_id": game_id, "username": username, "server": server}

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


def update_db(server):
    remote_data_service = RemoteDataService(server=server)

    songs_in_database = song_service.get_all_songs()
    songs_in_remote = remote_data_service.get_songs_ids()

    logger.info(f"Database initialized with {len(songs_in_database)} songs.")
    logger.info(f"Remote songs fetched: {len(songs_in_remote)} song IDs.")

    songs_in_database_ids = [song.internal_song_id for song in songs_in_database]

    missing_songs = sorted(set(songs_in_remote) - set(songs_in_database_ids))

    if len(missing_songs) > 0:
        logger.info("Mismatch between remote and local song IDs. Updating database...")

        for song_id in missing_songs:
            song_data = remote_data_service.get_song_info(song_id)

            if song_data:
                organized_data = song_data_organize(song_data)
                created_song = song_service.create_song(organized_data)

                logger.info(
                    f"Created song: {created_song.internal_song_id} - {created_song.name[game_server]}"
                )

    events_in_database = event_service.get_all_events()
    events_in_remote = remote_data_service.get_events_info()

    event_in_database_ids = [event.event_id for event in events_in_database]
    events_in_remote_ids = [int(event_id) for event_id in events_in_remote.keys()]

    logger.info(f"Database initialized with {len(events_in_database)} events.")
    logger.info(f"Remote events fetched: {len(events_in_remote)} event IDs.")

    missing_events = sorted(set(events_in_remote_ids) - set(event_in_database_ids))
    if len(missing_events) > 0:
        logger.info("Mismatch between remote and local event IDs. Updating database...")

        for event_id in missing_events:
            event_data = events_in_remote.get(str(event_id))

            if event_data:
                organized_event_data = event_data_organize(event_id, event_data)
                created_event = event_service.create_event(organized_event_data)

                logger.info(
                    f"Created event: {created_event.event_id} - {created_event.event_name[game_server]}"
                )

    bands_in_database = band_service.get_all_bands()
    bands_in_remote = remote_data_service.get_bands_info()

    bands_in_database_ids = [band.internal_band_id for band in bands_in_database]
    bands_in_remote_ids = [int(band_id) for band_id in bands_in_remote.keys()]

    logger.info(f"Database initialized with {len(bands_in_database)} bands.")
    logger.info(f"Remote bands fetched: {len(bands_in_remote)} band IDs.")

    missing_bands = sorted(set(bands_in_remote_ids) - set(bands_in_database_ids))
    if len(missing_bands) > 0:
        logger.info("Mismatch between remote and local band IDs. Updating database...")

        for band_id in missing_bands:
            band_data = bands_in_remote.get(str(band_id))

            if band_data:
                organized_band_data = band_data_organize(band_id, band_data)

                created_band = band_service.create_band(organized_band_data)
                logger.info(
                    f"Created band: {created_band.internal_band_id} - {created_band.name[game_server]}"
                )

    songs_in_database = len(song_service.get_all_songs())
    events_in_database = len(event_service.get_all_events())
    bands_in_database = len(band_service.get_all_bands())

    return songs_in_database, events_in_database, bands_in_database


def scan_screenshots(user):
    leaving = False
    scan_service = ScanService()

    while not leaving:
        # Get user's screenshots source and path
        screenshots_source = user.screenshots_source
        screenshots_path = user.screenshots_path

        if screenshots_source != "local":
            print("Remote screenshots source is not supported yet. Setting to local.")
            screenshots_source = "local"
        if not screenshots_path:
            screenshots_path = input(
                "Enter the path to your screenshots directory: "
            ).strip()
            if not screenshots_path:
                print("Screenshots path cannot be empty. Please try again.")
                return

        while not os.path.exists(screenshots_path):
            print(f"Path {screenshots_path} does not exist. Please try again.")
            screenshots_path = input(
                "Enter the path to your screenshots directory: "
            ).strip()

        # List images in the screenshots directory (png, jpg, jpeg)
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
        # Sort images by name
        images.sort()
        print(f"Found {len(images)} images in {screenshots_path}.")
        print("Starting scan...")

        scan_result = scan_service.scan_images(screenshots_path, images)

        print(f"Scan completed. Results:")
        print(f"Total images scanned: {scan_result['total_scanned']}")
        print(f"Successful scans: {scan_result['successful']}")
        print(f"Errors:")
        for error_type, count in scan_result["errors"].items():
            print(f"  {error_type.replace('_', ' ').title()}: {count}")
            if count > 0:
                print(
                    f"    Files with {error_type.replace('_', ' ')}: {', '.join(scan_result['error_files'][error_type])}"
                )

        leaving = True


def update_user_settings(user):
    leaving = False
    while not leaving:
        print(f"Current settings for user {user.username}:")
        print(f"Game ID: {user.game_id}")
        print(f"Server: {user.server}")
        print(f"Screenshots Source: {user.screenshots_source}")
        print(f"Screenshots Path: {user.screenshots_path}")

        # choose what to update
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
            if new_server in ["en", "jp", "tw", "cn", "kr"]:
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
                    print(
                        f"Screenshots Path updated to {updated_user.screenshots_path}"
                    )
                except ValueError as err:
                    print(f"Error updating Screenshots Path: {err}")
        elif choice == "5":
            leaving = True
        else:
            print("Invalid choice. Please try again.")


def run():
    logger.info("Starting BangStats update process...")

    # Initialize the database
    init_db()
    logger.info("Database initialized successfully.")

    # User login or creation
    user = user_login()

    # Get user's server
    game_server = user.server

    # Update the database with remote data
    songs, events, bands = update_db(game_server)
    current_event = event_service.get_current_event()

    logger.info("BangStats update process completed successfully.")

    print(f"BangStats successfully initialized and updated with server: {game_server}.")

    # options
    # 1. Scan screenshots
    # 2. View your stats
    # 3. Update database
    # 4. Update user settings
    # 5. Exit

    while True:
        # Print nice header with songs, events, bands, and current event
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
            scan_screenshots(user)
        elif choice == "2":
            pass
        elif choice == "3":
            update_db(game_server)
        elif choice == "4":
            update_user_settings(user)
        elif choice == "5":
            print("Exiting BangStats. Goodbye!")
            break
