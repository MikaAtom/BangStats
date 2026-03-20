#!/usr/bin/env python3
import argparse
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from bangstats_server.core.timestamps import extract_timestamp_from_filename


@dataclass
class DuplicateCandidate:
    keep_id: int
    keep_filename: str
    delete_id: int
    delete_filename: str
    delta_ms: int


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


def _resolve_user(
    conn: sqlite3.Connection,
    user_id: Optional[int],
    username: Optional[str],
    game_id: Optional[str],
) -> Optional[int]:
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
        return None

    query = "SELECT id FROM user WHERE " + " AND ".join(filters) + " LIMIT 1"
    row = conn.execute(query, params).fetchone()
    if row is None:
        raise ValueError("User not found with provided selector")
    return int(row["id"])


def _coerce_time_ms(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Heuristic: seconds if too small for ms.
        if value < 10_000_000_000:
            return int(value * 1000)
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            num = int(raw)
            if num < 10_000_000_000:
                return num * 1000
            return num
        try:
            normalized = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            return None
    return None


def _event_time_ms(row: sqlite3.Row) -> Optional[int]:
    filename = str(row["filename"] or "").strip()
    if filename:
        extracted = extract_timestamp_from_filename(filename)
        if extracted is not None:
            return extracted
    return _coerce_time_ms(row["timestamp"])


def _canonical_json(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    return str(value).strip()


def _row_signature(row: sqlite3.Row) -> tuple[Any, ...]:
    return (
        row["song_id"],
        (row["difficulty"] or "").strip().lower(),
        (row["live_type"] or "").strip().lower(),
        row["score"],
        row["high_score"],
        row["is_new_record"],
        row["score_rank"],
        row["perfect"],
        row["great"],
        row["good"],
        row["bad"],
        row["miss"],
        row["fast"],
        row["slow"],
        row["max_combo"],
        row["full_combo"],
        row["all_perfect"],
        row["anomaly"],
        _canonical_json(row["free_live_data"]),
        _canonical_json(row["team_live_data"]),
    )


def _print_items(header: str, items: list[str], limit: int) -> None:
    print(f"{header}: {len(items)}")
    for line in items[:limit]:
        print(f"  - {line}")
    if len(items) > limit:
        print(f"  ... ({len(items) - limit} more)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Find duplicate screenshot DB rows by comparing identical live result data "
            "within a time threshold and deleting newer duplicates"
        )
    )
    parser.add_argument("--db-path", type=Path, default=None, help="Path to bangstats.db")
    parser.add_argument("--user-id", type=int, default=None, help="User ID in DB")
    parser.add_argument("--username", type=str, default=None, help="Username in DB")
    parser.add_argument("--game-id", type=str, default=None, help="Game ID in DB")
    parser.add_argument(
        "--threshold-seconds",
        type=int,
        default=60,
        help="Max time difference to consider duplicates (default: 60)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deletes (default is dry-run)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max lines printed per section",
    )
    args = parser.parse_args()

    if args.threshold_seconds < 0:
        raise ValueError("--threshold-seconds must be >= 0")

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (args.db_path or _default_db_path(repo_root)).expanduser()
    threshold_ms = args.threshold_seconds * 1000

    with _connect(db_path) as conn:
        target_user_id = _resolve_user(conn, args.user_id, args.username, args.game_id)

        query = (
            "SELECT id, user_id, song_id, difficulty, live_type, score, high_score, "
            "is_new_record, score_rank, perfect, great, good, bad, miss, fast, slow, "
            "max_combo, full_combo, all_perfect, anomaly, free_live_data, team_live_data, "
            "filename, timestamp "
            "FROM screenshot"
        )
        params: tuple[Any, ...] = ()
        if target_user_id is not None:
            query += " WHERE user_id = ?"
            params = (target_user_id,)
        query += " ORDER BY user_id, id"

        rows = conn.execute(query, params).fetchall()

        by_user: dict[int, list[sqlite3.Row]] = {}
        for row in rows:
            uid = int(row["user_id"])
            by_user.setdefault(uid, []).append(row)

        to_delete_ids: set[int] = set()
        duplicates: list[DuplicateCandidate] = []
        unresolved_time: list[str] = []

        for uid, user_rows in by_user.items():
            group_map: dict[tuple[Any, ...], list[tuple[int, int, str]]] = {}
            for row in user_rows:
                row_id = int(row["id"])
                t_ms = _event_time_ms(row)
                filename = str(row["filename"] or "")
                if t_ms is None:
                    unresolved_time.append(
                        f"user_id={uid} id={row_id} filename={filename or '-'} (missing parseable time)"
                    )
                    continue
                sig = _row_signature(row)
                group_map.setdefault(sig, []).append((t_ms, row_id, filename))

            for entries in group_map.values():
                if len(entries) < 2:
                    continue
                entries.sort(key=lambda item: (item[0], item[1]))
                keep_time, keep_id, keep_filename = entries[0]
                for time_ms, row_id, filename in entries[1:]:
                    if row_id in to_delete_ids:
                        continue
                    if abs(time_ms - keep_time) <= threshold_ms:
                        to_delete_ids.add(row_id)
                        duplicates.append(
                            DuplicateCandidate(
                                keep_id=keep_id,
                                keep_filename=keep_filename,
                                delete_id=row_id,
                                delete_filename=filename,
                                delta_ms=abs(time_ms - keep_time),
                            )
                        )

        print(f"DB: {db_path}")
        print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
        if target_user_id is not None:
            print(f"User filter: user_id={target_user_id}")
        else:
            print("User filter: ALL users")
        print(f"Rows checked: {len(rows)}")
        print(f"Threshold seconds: {args.threshold_seconds}")
        print()

        duplicate_lines = [
            (
                f"delete id={d.delete_id} ({d.delete_filename or '-'}) "
                f"keep id={d.keep_id} ({d.keep_filename or '-'}) "
                f"delta_ms={d.delta_ms}"
            )
            for d in duplicates
        ]
        _print_items("Duplicates within threshold (newer rows to delete)", duplicate_lines, args.limit)
        print()
        _print_items("Rows skipped due to missing parseable time", unresolved_time, args.limit)

        if not args.apply:
            return

        if not to_delete_ids:
            print("\nNo DB deletes applied.")
            return

        with conn:
            for row_id in sorted(to_delete_ids):
                conn.execute("DELETE FROM screenshot WHERE id = ?", (row_id,))

        print(f"\nApplied duplicate-row deletes: {len(to_delete_ids)}")


if __name__ == "__main__":
    main()
