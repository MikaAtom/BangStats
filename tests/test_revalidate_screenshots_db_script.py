from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "server"
if str(SERVER_PATH) not in sys.path:
    sys.path.insert(0, str(SERVER_PATH))

from bangstats_server.core.db.models.screenshot import Screenshot
from bangstats_server.core.scripts.revalidate_screenshots_db import (
    _build_validation_filename,
    build_scan_data,
    resolve_db_path,
    revalidate_screenshots,
    write_json_report,
)
from bangstats_server.core.services.validation import ValidationResult


def _make_row(
    *,
    row_id: int,
    song_id: int,
    filename: str | None = None,
    timestamp: datetime | None = None,
) -> Screenshot:
    return Screenshot(
        id=row_id,
        user_id=3,
        score=1000,
        high_score=1000,
        is_new_record=False,
        score_rank="S",
        live_type="free live",
        free_live_data=None,
        team_live_data=None,
        perfect=90,
        great=10,
        good=0,
        bad=0,
        miss=0,
        fast=5,
        slow=5,
        max_combo=100,
        full_combo=True,
        all_perfect=False,
        song_id=song_id,
        difficulty="expert",
        anomaly=False,
        filename=filename,
        timestamp=timestamp or datetime(2026, 3, 7, 12, 0, 0),
    )


def test_build_scan_data_reconstructs_expected_fields():
    row = _make_row(row_id=1, song_id=123, filename="Screenshot_20260307_120000.png")
    payload = build_scan_data(row, "Test Song")
    assert payload["song_name_from_top_bar_text"] == "Test Song"
    assert payload["difficulty"] == "expert"
    assert payload["perfect"] == 90
    assert payload["great"] == 10
    assert payload["max_combo"] == 100
    assert payload["live_type"] == "free live"


def test_build_validation_filename_synthesizes_when_missing_filename():
    row = _make_row(row_id=1, song_id=123, filename=None, timestamp=datetime(2024, 6, 8, 15, 59, 58))
    filename, edge = _build_validation_filename(row)
    assert filename == "Screenshot_20240608_155958.png"
    assert edge == "missing_filename_synthesized_from_timestamp"


def test_revalidate_screenshots_aggregates_errors_and_edge_cases():
    rows = [
        _make_row(row_id=1, song_id=10, filename="Screenshot_20260307_120000.png"),
        _make_row(row_id=2, song_id=999, filename=None),
    ]

    class _FakeValidator:
        def validate(self, filename, payload):
            if payload["song_name_from_top_bar_text"] == "":
                return ValidationResult(
                    is_valid=False,
                    error_type="not_found_errors",
                    resolved_song_id=None,
                    normalized={},
                    reasons=["missing_song_reference"],
                    severity="error",
                    confidence=0.0,
                )
            return ValidationResult(
                is_valid=True,
                error_type=None,
                resolved_song_id=10,
                normalized={},
                reasons=["resolved_exact_name"],
                severity="info",
                confidence=1.0,
            )

    report = revalidate_screenshots(
        rows,
        song_name_by_id={10: "Known Song"},
        validator=_FakeValidator(),
    )
    assert report["total"] == 2
    assert report["valid"] == 1
    assert report["invalid"] == 1
    assert report["error_counts"]["not_found_errors"] == 1
    assert report["edge_cases"]["missing_song_reference"] == 1
    assert report["edge_cases"]["missing_filename_synthesized_from_timestamp"] == 1


def test_resolve_db_path_requires_existing_file(tmp_path: Path):
    db_file = tmp_path / "bangstats.db"
    db_file.write_text("x", encoding="utf-8")
    resolved = resolve_db_path(str(db_file))
    assert resolved == db_file.resolve()


def test_write_json_report_creates_file(tmp_path: Path):
    report = {"total": 1, "valid": 1, "invalid": 0, "error_counts": {}, "details": []}
    out_path = tmp_path / "reports" / "audit.json"
    written = write_json_report(report, str(out_path))
    assert written == out_path.resolve()
    assert written.exists()
