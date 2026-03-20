#!/usr/bin/env python3
import argparse
import os
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"}


@dataclass
class HealCandidate:
    screenshot_id: int
    old_filename: str
    new_filename: str
    reason: str


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
            "Multiple users in DB. Provide --user-id, --username, or --game-id. "
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


def _iter_image_files(folder: Path, recursive: bool):
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    for path in iterator:
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def _normalize(value: str, case_insensitive: bool) -> str:
    return value.casefold() if case_insensitive else value


def _filename_stem_key(filename: str, case_insensitive: bool) -> str:
    stem = Path(filename).stem
    return _normalize(stem, case_insensitive)


def _print_items(header: str, items: list[str], limit: int) -> None:
    print(f"{header}: {len(items)}")
    for line in items[:limit]:
        print(f"  - {line}")
    if len(items) > limit:
        print(f"  ... ({len(items) - limit} more)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Heal screenshot filename extension mismatches in DB by comparing against actual files"
    )
    parser.add_argument("--db-path", type=Path, default=None, help="Path to bangstats.db")
    parser.add_argument("--user-id", type=int, default=None, help="User ID in DB")
    parser.add_argument("--username", type=str, default=None, help="Username in DB")
    parser.add_argument("--game-id", type=str, default=None, help="Game ID in DB")
    parser.add_argument(
        "--folder",
        type=Path,
        default=None,
        help="Screenshot folder (defaults to user.screenshots_path)",
    )
    parser.add_argument(
        "--non-recursive",
        action="store_true",
        help="Only scan top-level files in folder",
    )
    parser.add_argument(
        "--case-insensitive",
        action="store_true",
        help="Match filenames case-insensitively",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates to DB (default is dry-run)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max lines printed per section",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (args.db_path or _default_db_path(repo_root)).expanduser()

    with _connect(db_path) as conn:
        user = _resolve_user(conn, args.user_id, args.username, args.game_id)
        folder = args.folder.expanduser() if args.folder else Path(user["screenshots_path"] or "").expanduser()

        if not str(folder):
            raise ValueError("No folder path provided and user.screenshots_path is empty")
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"Folder does not exist or is not a directory: {folder}")

        file_names_raw = [p.name for p in _iter_image_files(folder, recursive=not args.non_recursive)]
        file_names_norm_map: dict[str, str] = {}
        files_by_stem: dict[str, list[str]] = defaultdict(list)
        for name in file_names_raw:
            name_norm = _normalize(name, args.case_insensitive)
            file_names_norm_map[name_norm] = name
            files_by_stem[_filename_stem_key(name, args.case_insensitive)].append(name)

        rows = conn.execute(
            "SELECT id, filename FROM screenshot WHERE user_id = ? AND filename IS NOT NULL AND TRIM(filename) != ''",
            (int(user["id"]),),
        ).fetchall()

        existing_names = set(
            _normalize(str(row["filename"]).strip(), args.case_insensitive)
            for row in rows
            if str(row["filename"]).strip()
        )

        candidates: list[HealCandidate] = []
        unresolved: list[str] = []
        ambiguous: list[str] = []
        collisions: list[str] = []

        for row in rows:
            screenshot_id = int(row["id"])
            old_name = str(row["filename"]).strip()
            if not old_name:
                continue

            old_name_norm = _normalize(old_name, args.case_insensitive)
            if old_name_norm in file_names_norm_map:
                continue

            stem_key = _filename_stem_key(old_name, args.case_insensitive)
            stem_matches = sorted(set(files_by_stem.get(stem_key, [])))

            if len(stem_matches) == 0:
                unresolved.append(f"id={screenshot_id}: {old_name}")
                continue

            if len(stem_matches) > 1:
                ambiguous.append(
                    f"id={screenshot_id}: {old_name} -> {', '.join(stem_matches)}"
                )
                continue

            fixed_name = stem_matches[0]
            fixed_name_norm = _normalize(fixed_name, args.case_insensitive)
            if fixed_name_norm == old_name_norm:
                continue

            if fixed_name_norm in existing_names:
                collisions.append(f"id={screenshot_id}: {old_name} -> {fixed_name}")
                continue

            reason = f"stem match with extension correction ({Path(old_name).suffix} -> {Path(fixed_name).suffix})"
            candidates.append(
                HealCandidate(
                    screenshot_id=screenshot_id,
                    old_filename=old_name,
                    new_filename=fixed_name,
                    reason=reason,
                )
            )
            existing_names.discard(old_name_norm)
            existing_names.add(fixed_name_norm)

        print(f"DB: {db_path}")
        print(
            "User: "
            f"id={user['id']} username={user['username']} game_id={user['game_id']}"
        )
        print(f"Folder: {folder}")
        print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
        print(f"Rows checked: {len(rows)}")
        print(f"Folder images: {len(file_names_raw)}")
        print()

        candidate_lines = [
            f"id={c.screenshot_id}: {c.old_filename} -> {c.new_filename} ({c.reason})"
            for c in candidates
        ]
        _print_items("Fixable extension mismatches", candidate_lines, args.limit)
        print()
        _print_items("Ambiguous stem matches (manual review)", ambiguous, args.limit)
        print()
        _print_items("Collisions skipped (target already exists in DB)", collisions, args.limit)
        print()
        _print_items("Unresolved (no matching stem in folder)", unresolved, args.limit)

        if not args.apply:
            return

        if not candidates:
            print("\nNo DB updates applied.")
            return

        with conn:
            for item in candidates:
                conn.execute(
                    "UPDATE screenshot SET filename = ? WHERE id = ?",
                    (item.new_filename, item.screenshot_id),
                )

        print(f"\nApplied updates: {len(candidates)}")


if __name__ == "__main__":
    main()
