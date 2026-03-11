import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from sqlmodel import Session, create_engine, select

from bangstats_server.core.db.models.screenshot import Screenshot
from bangstats_server.core.db.models.song import Song
from bangstats_server.core.services.validation import ValidationResult, ValidationService

VALIDATION_CHECKS = [
    "Song resolution (exact + fuzzy by note count/difficulty)",
    "Note-count consistency (perfect+great+good+bad+miss)",
    "Fast/Slow consistency (fast+slow vs great+good+bad)",
    "Max-combo consistency for no-miss plays",
    "Live-type validity against event window by filename timestamp",
    "Runtime guardrail failures as validation_errors",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="revalidate-screenshots-db",
        description="Read-only maintenance revalidation for screenshot rows in a DB file.",
    )
    parser.add_argument("--db-path", required=True, help="Path to SQLite DB file")
    parser.add_argument("--user-id", type=int, default=None, help="Optional user filter")
    parser.add_argument("--limit", type=int, default=None, help="Optional max rows to process")
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional output report JSON path",
    )
    return parser


def resolve_db_path(db_path: str) -> Path:
    path = Path(db_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"DB file does not exist: {path}")
    return path


def _song_display_name(song_name_payload: Any) -> str:
    if isinstance(song_name_payload, dict):
        preferred = song_name_payload.get("en")
        if isinstance(preferred, str) and preferred.strip():
            return preferred
        for value in song_name_payload.values():
            if isinstance(value, str) and value.strip():
                return value
    if isinstance(song_name_payload, str) and song_name_payload.strip():
        return song_name_payload
    return ""


def _build_validation_filename(screenshot: Screenshot) -> tuple[str, str | None]:
    if screenshot.filename and str(screenshot.filename).strip():
        return str(screenshot.filename), None
    if screenshot.timestamp:
        synthesized = f"Screenshot_{screenshot.timestamp.strftime('%Y%m%d_%H%M%S')}.png"
        return synthesized, "missing_filename_synthesized_from_timestamp"
    return "Screenshot_19700101_000000.png", "missing_filename_and_timestamp_defaulted"


def build_scan_data(screenshot: Screenshot, song_display_name: str) -> dict[str, Any]:
    return {
        "song_name_from_top_bar_text": song_display_name,
        "difficulty": screenshot.difficulty,
        "perfect": screenshot.perfect,
        "great": screenshot.great,
        "good": screenshot.good,
        "bad": screenshot.bad,
        "miss": screenshot.miss,
        "fast": screenshot.fast if screenshot.fast is not None else -1,
        "slow": screenshot.slow if screenshot.slow is not None else -1,
        "max_combo": screenshot.max_combo,
        "live_type": screenshot.live_type,
        "score": screenshot.score,
        "high_score": screenshot.high_score if screenshot.high_score is not None else screenshot.score,
        "score_rank": screenshot.score_rank if screenshot.score_rank is not None else "",
        "is_new_record": bool(screenshot.is_new_record) if screenshot.is_new_record is not None else False,
    }


def _load_song_names_map(session: Session, song_ids: set[int]) -> dict[int, str]:
    if not song_ids:
        return {}

    ordered_song_ids = sorted(song_ids)
    chunk_size = 500
    result: dict[int, str] = {}
    for start in range(0, len(ordered_song_ids), chunk_size):
        chunk = ordered_song_ids[start : start + chunk_size]
        rows = session.exec(
            select(Song.internal_song_id, Song.name).where(Song.internal_song_id.in_(chunk))
        ).all()
        for internal_song_id, song_name in rows:
            result[int(internal_song_id)] = _song_display_name(song_name)
    return result


def _load_screenshots(session: Session, *, user_id: int | None = None, limit: int | None = None) -> list[Screenshot]:
    stmt = select(Screenshot).order_by(Screenshot.id)
    if user_id is not None:
        stmt = stmt.where(Screenshot.user_id == user_id)
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)
    return list(session.exec(stmt).all())


def revalidate_screenshots(
    screenshots: Iterable[Screenshot],
    song_name_by_id: dict[int, str],
    validator: ValidationService,
) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    error_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    edge_case_counts: Counter[str] = Counter()
    valid_count = 0

    for row in screenshots:
        filename, filename_edge = _build_validation_filename(row)
        if filename_edge:
            edge_case_counts[filename_edge] += 1

        song_name = song_name_by_id.get(int(row.song_id), "")
        if not song_name:
            edge_case_counts["missing_song_reference"] += 1

        payload = build_scan_data(row, song_name)
        result = validator.validate(filename, payload)
        if result.is_valid:
            valid_count += 1
        else:
            error_counts[result.error_type or "validation_errors"] += 1

        for reason in result.reasons:
            reason_counts[reason] += 1

        details.append(
            {
                "screenshot_id": row.id,
                "user_id": row.user_id,
                "song_id": row.song_id,
                "filename": filename,
                "is_valid": result.is_valid,
                "error_type": result.error_type,
                "severity": result.severity,
                "confidence": result.confidence,
                "reasons": result.reasons,
                "resolved_song_id": result.resolved_song_id,
            }
        )

    total = len(details)
    invalid_count = total - valid_count
    return {
        "total": total,
        "valid": valid_count,
        "invalid": invalid_count,
        "error_counts": dict(error_counts),
        "reason_counts": dict(reason_counts),
        "edge_cases": dict(edge_case_counts),
        "details": details,
    }


def print_validation_checks() -> None:
    print("Current validation checks:")
    for idx, item in enumerate(VALIDATION_CHECKS, start=1):
        print(f"{idx}. {item}")


def print_summary(report: dict[str, Any]) -> None:
    print("\nRevalidation summary:")
    print(f"  Total checked: {report['total']}")
    print(f"  Valid: {report['valid']}")
    print(f"  Invalid: {report['invalid']}")
    if report["error_counts"]:
        print("  Errors by type:")
        for error_type, count in sorted(report["error_counts"].items()):
            print(f"    {error_type}: {count}")
    if report["edge_cases"]:
        print("  Edge cases:")
        for edge, count in sorted(report["edge_cases"].items()):
            print(f"    {edge}: {count}")


def write_json_report(report: dict[str, Any], output_path: str) -> Path:
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    return target


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = resolve_db_path(args.db_path)
    if args.user_id is not None and args.user_id <= 0:
        raise ValueError("--user-id must be a positive integer when provided")
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be a positive integer when provided")

    print_validation_checks()
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    validator = ValidationService()

    with Session(engine) as session:
        screenshots = _load_screenshots(session, user_id=args.user_id, limit=args.limit)
        song_ids = {int(row.song_id) for row in screenshots}
        song_map = _load_song_names_map(session, song_ids)

    report = revalidate_screenshots(screenshots, song_map, validator)
    print_summary(report)

    if args.output_json:
        target = write_json_report(report, args.output_json)
        print(f"\nWrote JSON report to: {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
