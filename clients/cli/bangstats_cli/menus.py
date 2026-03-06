from pathlib import Path

from bangstats_cli.api_client import BangStatsAPI

SUPPORTED_SERVERS = ["en", "jp", "tw", "cn", "kr"]


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
    print("Starting scan...")
    scan_result = api.scan_images(int(user["id"]), images)
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
