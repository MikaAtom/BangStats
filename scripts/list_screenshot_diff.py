#!/usr/bin/env python3
import argparse
import os
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Iterable


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"}


def _default_db_path(repo_root: Path) -> Path:
    env_name = (os.getenv("BANGSTATS_ENV", "production") or "production").strip().lower()
    override = (os.getenv("BANGSTATS_DB_PATH", "") or "").strip()
    if override:
        return Path(override).expanduser()
    return repo_root / "storage" / env_name / "bangstats.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"DB file does not exist: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_user(conn: sqlite3.Connection, user_id: int | None, username: str | None, game_id: str | None) -> sqlite3.Row:
    filters: list[str] = []
    params: list[object] = []
    if user_id is not None:
        filters.append("id = ?")
        params.append(user_id)
    if username:
        filters.append("username = ?")
        params.append(username)
    if game_id:
        filters.append("game_id = ?")
        params.append(game_id)

    if not filters:
        rows = conn.execute(
            "SELECT id, username, game_id, screenshots_path FROM user ORDER BY id"
        ).fetchall()
        if len(rows) == 1:
            return rows[0]
        if not rows:
            raise ValueError("No users found in DB")
        details = ", ".join(f"id={r['id']} username={r['username']}" for r in rows)
        raise ValueError(
            "Multiple users in DB. Pick one with --user-id, --username, or --game-id. "
            f"Available: {details}"
        )

    query = (
        "SELECT id, username, game_id, screenshots_path FROM user WHERE "
        + " AND ".join(filters)
        + " LIMIT 1"
    )
    row = conn.execute(query, params).fetchone()
    if row is None:
        raise ValueError("User not found with provided selector")
    return row


def _iter_folder_filenames(folder: Path, recursive: bool) -> Iterable[str]:
    if recursive:
        iterator = folder.rglob("*")
    else:
        iterator = folder.glob("*")
    for path in iterator:
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path.name


def _normalize_names(names: Iterable[str], case_insensitive: bool) -> list[str]:
    if case_insensitive:
        return [name.casefold() for name in names]
    return list(names)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List filename diff between screenshots in DB and files in folder"
    )
    parser.add_argument("--db-path", type=Path, default=None, help="Path to bangstats.db")
    parser.add_argument("--user-id", type=int, default=None, help="User ID in DB")
    parser.add_argument("--username", type=str, default=None, help="Username in DB")
    parser.add_argument("--game-id", type=str, default=None, help="Game ID in DB")
    parser.add_argument(
        "--folder",
        type=Path,
        default=None,
        help="Folder to compare against (defaults to user.screenshots_path)",
    )
    parser.add_argument(
        "--non-recursive",
        action="store_true",
        help="Only check top-level files in folder",
    )
    parser.add_argument(
        "--case-insensitive",
        action="store_true",
        help="Compare filenames case-insensitively",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum filenames to print per section (default: 200)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (args.db_path or _default_db_path(repo_root)).expanduser()

    with _connect(db_path) as conn:
        user = _resolve_user(conn, args.user_id, args.username, args.game_id)

        user_folder = args.folder.expanduser() if args.folder else Path(user["screenshots_path"] or "").expanduser()
        if not str(user_folder):
            raise ValueError("No folder path provided and user.screenshots_path is empty")
        if not user_folder.exists() or not user_folder.is_dir():
            raise FileNotFoundError(f"Folder does not exist or is not a directory: {user_folder}")

        db_rows = conn.execute(
            "SELECT filename FROM screenshot WHERE user_id = ? AND filename IS NOT NULL",
            (user["id"],),
        ).fetchall()

    db_filenames_raw = [str(row["filename"]).strip() for row in db_rows if str(row["filename"]).strip()]
    fs_filenames_raw = list(_iter_folder_filenames(user_folder, recursive=not args.non_recursive))

    db_names = _normalize_names(db_filenames_raw, args.case_insensitive)
    fs_names = _normalize_names(fs_filenames_raw, args.case_insensitive)

    db_counts = Counter(db_names)
    fs_counts = Counter(fs_names)

    db_set = set(db_counts)
    fs_set = set(fs_counts)

    only_in_db = sorted(db_set - fs_set)
    only_in_folder = sorted(fs_set - db_set)
    duplicated_in_db = sorted((name, count) for name, count in db_counts.items() if count > 1)

    print(f"DB: {db_path}")
    print(
        "User: "
        f"id={user['id']} username={user['username']} game_id={user['game_id']}"
    )
    print(f"Folder: {user_folder}")
    print(f"Compare mode: {'case-insensitive' if args.case_insensitive else 'case-sensitive'}")
    print(f"DB filename rows: {len(db_filenames_raw)}")
    print(f"Folder image files: {len(fs_filenames_raw)}")
    print()

    print(f"Only in DB (not in folder): {len(only_in_db)}")
    for name in only_in_db[: args.limit]:
        print(f"  - {name}")
    if len(only_in_db) > args.limit:
        print(f"  ... ({len(only_in_db) - args.limit} more)")

    print()
    print(f"Only in folder (not in DB): {len(only_in_folder)}")
    for name in only_in_folder[: args.limit]:
        print(f"  - {name}")
    if len(only_in_folder) > args.limit:
        print(f"  ... ({len(only_in_folder) - args.limit} more)")

    print()
    print(f"Duplicate filenames in DB: {len(duplicated_in_db)}")
    for name, count in duplicated_in_db[: args.limit]:
        print(f"  - {name}: {count} rows")
    if len(duplicated_in_db) > args.limit:
        print(f"  ... ({len(duplicated_in_db) - args.limit} more)")


if __name__ == "__main__":
    main()
