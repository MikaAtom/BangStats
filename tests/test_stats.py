from datetime import datetime, timedelta
from types import SimpleNamespace

from bangstats_server.core.services.stats import (
    compute_activity_range,
    compute_calendar_month_view,
    compute_difficulty_detail,
    compute_general_summary,
    compute_milestones,
    compute_recent_plays,
    compute_song_difficulty_overview,
    compute_top_songs,
)


def _play(
    *,
    song_id: int,
    difficulty: str,
    timestamp: datetime,
    perfect: int = 100,
    great: int = 0,
    good: int = 0,
    bad: int = 0,
    miss: int = 0,
    full_combo: bool = True,
    all_perfect: bool = False,
    filename: str | None = None,
):
    return SimpleNamespace(
        song_id=song_id,
        difficulty=difficulty,
        timestamp=timestamp,
        perfect=perfect,
        great=great,
        good=good,
        bad=bad,
        miss=miss,
        full_combo=full_combo,
        all_perfect=all_perfect,
        filename=filename,
    )


def test_general_summary():
    base = datetime(2026, 3, 1, 12, 0, 0)
    shots = [
        _play(song_id=1, difficulty="expert", timestamp=base, perfect=90, great=10, full_combo=True),
        _play(song_id=2, difficulty="hard", timestamp=base, perfect=80, great=20, full_combo=False),
    ]
    summary = compute_general_summary(shots)
    assert summary["total_plays"] == 2
    assert summary["total_fc"] == 1
    assert summary["total_ap"] == 0
    assert summary["accuracy"] == 85.0


def test_general_summary_empty():
    summary = compute_general_summary([])
    assert summary == {"total_plays": 0, "total_fc": 0, "total_ap": 0, "accuracy": 0.0}


def test_top_songs():
    base = datetime(2026, 3, 1, 12, 0, 0)
    shots = [
        _play(song_id=1, difficulty="expert", timestamp=base),
        _play(song_id=1, difficulty="hard", timestamp=base + timedelta(minutes=1)),
        _play(song_id=2, difficulty="expert", timestamp=base + timedelta(minutes=2)),
    ]
    top = compute_top_songs(shots, n=2)
    assert top[0] == {"song_id": 1, "play_count": 2}
    assert top[1] == {"song_id": 2, "play_count": 1}


def test_recent_plays():
    base = datetime(2026, 3, 1, 12, 0, 0)
    shots = [
        _play(song_id=1, difficulty="expert", timestamp=base, filename="a.png"),
        _play(song_id=2, difficulty="hard", timestamp=base + timedelta(minutes=1), filename="b.png"),
        _play(song_id=3, difficulty="normal", timestamp=base + timedelta(minutes=2), filename="c.png"),
    ]
    recent = compute_recent_plays(shots, n=2)
    assert len(recent) == 2
    assert recent[0]["song_id"] == 3
    assert recent[1]["song_id"] == 2


def test_difficulty_detail_fc_ap():
    base = datetime(2026, 3, 1, 12, 0, 0)
    plays = [
        _play(song_id=1, difficulty="hard", timestamp=base, full_combo=False, all_perfect=False, filename="1.png"),
        _play(song_id=1, difficulty="hard", timestamp=base + timedelta(days=1), full_combo=True, all_perfect=False, filename="2.png"),
        _play(song_id=1, difficulty="hard", timestamp=base + timedelta(days=2), full_combo=True, all_perfect=True, filename="3.png"),
    ]
    detail = compute_difficulty_detail(plays)
    assert detail["total_plays"] == 3
    assert detail["total_fc"] == 2
    assert detail["total_ap"] == 1
    assert detail["plays_before_fc"] == 1
    assert detail["plays_before_ap"] == 2
    assert detail["first_fc"]["filename"] == "2.png"
    assert detail["first_ap"]["filename"] == "3.png"


def test_difficulty_detail_no_fc():
    base = datetime(2026, 3, 1, 12, 0, 0)
    plays = [
        _play(song_id=1, difficulty="hard", timestamp=base, full_combo=False),
        _play(song_id=1, difficulty="hard", timestamp=base + timedelta(days=1), full_combo=False),
    ]
    detail = compute_difficulty_detail(plays)
    assert detail["first_fc"] is None
    assert detail["last_fc"] is None
    assert detail["plays_before_fc"] is None


def test_song_difficulty_overview():
    base = datetime(2026, 3, 1, 12, 0, 0)
    plays = [
        _play(song_id=1, difficulty="easy", timestamp=base, filename="easy.png"),
        _play(song_id=1, difficulty="hard", timestamp=base + timedelta(days=1), filename="hard.png"),
        _play(song_id=1, difficulty="expert", timestamp=base + timedelta(days=2), filename="exp.png"),
    ]
    overview = compute_song_difficulty_overview(plays)
    assert set(overview.keys()) == {"easy", "hard", "expert"}
    assert overview["easy"]["first_played"]["filename"] == "easy.png"


def test_compute_milestones_includes_firsts_by_difficulty_and_thresholds():
    base = datetime(2026, 3, 1, 12, 0, 0)
    plays = [
        _play(song_id=1, difficulty="hard", timestamp=base, full_combo=False, all_perfect=False),
        _play(song_id=1, difficulty="hard", timestamp=base + timedelta(days=1), full_combo=True),
        _play(song_id=1, difficulty="expert", timestamp=base + timedelta(days=2), full_combo=True),
        _play(song_id=1, difficulty="hard", timestamp=base + timedelta(days=3), all_perfect=True),
        _play(song_id=1, difficulty="expert", timestamp=base + timedelta(days=4), all_perfect=True),
    ]
    for idx in range(5, 10):
        plays.append(
            _play(
                song_id=1,
                difficulty="hard",
                timestamp=base + timedelta(days=idx),
                full_combo=False,
                all_perfect=False,
            )
        )
    result = compute_milestones(plays)
    labels = [item["label"] for item in result["milestones"]]
    assert "First play recorded" in labels
    assert "First Full Combo (hard)" in labels
    assert "First Full Combo (expert)" in labels
    assert "First All Perfect (hard)" in labels
    assert "First All Perfect (expert)" in labels
    assert "Reached 10 plays" in labels
    assert result["best_streak_days"] >= 1


def test_compute_activity_range_returns_delta_and_averages():
    base = datetime(2026, 3, 10, 12, 0, 0)
    plays = [
        _play(song_id=1, difficulty="expert", timestamp=base - timedelta(days=8)),
        _play(song_id=1, difficulty="expert", timestamp=base - timedelta(days=1)),
        _play(song_id=2, difficulty="hard", timestamp=base),
    ]
    result = compute_activity_range(
        plays,
        from_date=(base - timedelta(days=2)).date(),
        to_date=base.date(),
    )
    assert result["summary"]["total_plays"] == 2
    assert result["days"] == 3
    assert result["avg_plays_per_day"] == round(2 / 3, 2)
    assert "delta_vs_previous" in result


def test_compute_calendar_month_view_aggregates_days():
    base = datetime(2026, 4, 2, 12, 0, 0)
    plays = [
        _play(song_id=1, difficulty="expert", timestamp=base, filename="a.png"),
        _play(song_id=2, difficulty="hard", timestamp=base, filename="b.png"),
        _play(song_id=3, difficulty="normal", timestamp=base + timedelta(days=2), filename="c.png"),
    ]
    result = compute_calendar_month_view(plays, year=2026, month=4)
    assert result["total_days_with_plays"] == 2
    assert result["days"][0]["date"] == "2026-04-02"
    assert result["days"][0]["plays"] == 2
