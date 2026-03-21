from datetime import date, datetime, timedelta
from types import SimpleNamespace

from bangstats_server.core.services.stats import (
    compute_activity_range,
    compute_active_hours,
    compute_calendar_month_view,
    compute_difficulty_detail,
    compute_general_summary,
    compute_insights,
    compute_milestones,
    compute_recent_plays,
    compute_calendar_year_view,
    compute_recap,
    compute_song_journey,
    compute_song_rankings,
    compute_song_difficulty_overview,
    compute_top_songs,
    filter_stats_plays,
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
    live_type: str = "multi_live",
    score: int = 0,
    fast: int | None = None,
    slow: int | None = None,
    max_combo: int = 100,
    anomaly: bool = False,
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
        live_type=live_type,
        score=score,
        fast=fast,
        slow=slow,
        max_combo=max_combo,
        anomaly=anomaly,
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
    assert summary == {"total_plays": 0, "total_fc": 0, "total_ap": 0, "accuracy": 0.0, "skill_score": 0.0}


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
        _play(
            song_id=3,
            difficulty="normal",
            timestamp=base + timedelta(minutes=2),
            filename="c.png",
            perfect=90,
            great=10,
            miss=0,
            score=2880513,
            fast=7,
            slow=23,
            max_combo=476,
        ),
    ]
    recent = compute_recent_plays(shots, n=2)
    assert len(recent) == 2
    assert recent[0]["song_id"] == 3
    assert recent[1]["song_id"] == 2
    assert recent[0]["perfect"] == 90
    assert recent[0]["great"] == 10
    assert recent[0]["miss"] == 0
    assert recent[0]["score"] == 2880513
    assert recent[0]["fast"] == 7
    assert recent[0]["slow"] == 23
    assert recent[0]["max_combo"] == 476
    assert recent[0]["accuracy"] == 90.0  # 90 perfect / 100 notes


def test_difficulty_detail_fc_ap():
    base = datetime(2026, 3, 1, 12, 0, 0)
    plays = [
        _play(song_id=1, difficulty="hard", timestamp=base, full_combo=False, all_perfect=False, filename="1.png"),
        _play(song_id=1, difficulty="hard", timestamp=base + timedelta(days=1), full_combo=True, all_perfect=False, filename="2.png"),
        _play(song_id=1, difficulty="hard", timestamp=base + timedelta(days=2), full_combo=True, all_perfect=True, filename="3.png"),
    ]
    detail = compute_difficulty_detail(plays, song_length_seconds=120, session_gap_minutes=45)
    assert detail["total_plays"] == 3
    assert detail["total_fc"] == 2
    assert detail["total_ap"] == 1
    assert detail["plays_before_fc"] == 1
    assert detail["plays_before_ap"] == 2
    assert detail["first_fc"]["filename"] == "2.png"
    assert detail["first_ap"]["filename"] == "3.png"
    assert detail["estimated_time_played_seconds"] == 360
    assert detail["total_sessions"] == 3
    assert detail["practice_burst_count"] == 0


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
    overview = compute_song_difficulty_overview(plays, song_length_seconds=120)
    assert set(overview.keys()) == {"easy", "hard", "expert"}
    assert overview["easy"]["first_played"]["filename"] == "easy.png"
    assert overview["hard"]["estimated_time_played_seconds"] == 120


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


def test_compute_insights_sessionization_practice_repetition_and_guards():
    base = datetime(2026, 3, 10, 12, 0, 0)
    plays = [
        _play(song_id=1, difficulty="expert", timestamp=base),
        _play(song_id=1, difficulty="expert", timestamp=base + timedelta(minutes=10)),
        _play(song_id=1, difficulty="expert", timestamp=base + timedelta(minutes=20)),
        _play(song_id=2, difficulty="hard", timestamp=base + timedelta(hours=2)),
        _play(song_id=2, difficulty="hard", timestamp=base + timedelta(hours=2, minutes=8)),
        _play(song_id=1, difficulty="expert", timestamp=base + timedelta(days=2)),
    ]
    result = compute_insights(
        plays,
        from_date=base.date(),
        to_date=(base + timedelta(days=3)).date(),
        session_gap_minutes=45,
        song_lengths_seconds={1: 120, 2: 150},
        min_recommended_plays=10,
    )
    assert result["sessions"]["total_sessions"] == 3
    assert len(result["practice_periods"]) == 1
    assert result["practice_periods"][0]["song_id"] == 1
    assert result["practice_periods"][0]["max_burst_plays"] == 3
    assert result["practice_periods"][0]["estimated_time_played_seconds"] == 480
    assert result["repetition"]["repeated_plays"] == 3
    assert result["repetition"]["most_looped_songs"][0]["song_id"] in {1, 2}
    assert result["data_quality"]["sparse_data"] is True
    assert result["recommendations"] == []


def test_compute_song_rankings_and_stat_filters():
    base = datetime(2026, 3, 10, 12, 0, 0)
    plays = [
        _play(song_id=1, difficulty="expert", timestamp=base, filename="a.png", all_perfect=True),
        _play(song_id=1, difficulty="expert", timestamp=base + timedelta(minutes=5), filename="b.png"),
        _play(song_id=2, difficulty="hard", timestamp=base + timedelta(minutes=10), filename="c.png", full_combo=False),
    ]
    for play, live_type in zip(plays, ["normal_live", "normal_live", "event_live"], strict=True):
        setattr(play, "live_type", live_type)

    filtered = filter_stats_plays(plays, difficulty="expert", live_type="normal_live")
    assert len(filtered) == 2
    assert all(play.song_id == 1 for play in filtered)

    rankings, total = compute_song_rankings(
        plays,
        song_names={1: "Song A", 2: "Song B"},
        sort_by="skill_score",
        limit=5,
    )
    assert total == 2
    assert rankings[0]["song_name"] == "Song A"
    assert rankings[0]["play_count"] == 2
    assert rankings[0]["latest_play"]["filename"] == "b.png"

    page, total2 = compute_song_rankings(
        plays,
        song_names={1: "Song A", 2: "Song B"},
        sort_by="skill_score",
        limit=1,
        offset=1,
    )
    assert total2 == 2
    assert len(page) == 1
    assert page[0]["song_id"] == 2


def test_compute_active_hours_uses_numeric_hour_keys():
    base = datetime(2026, 3, 10, 0, 5, 0)
    plays = [
        _play(song_id=1, difficulty="expert", timestamp=base),
        _play(song_id=1, difficulty="expert", timestamp=base.replace(hour=8, minute=30)),
        _play(song_id=1, difficulty="expert", timestamp=base.replace(hour=8, minute=45)),
        _play(song_id=1, difficulty="expert", timestamp=base.replace(hour=19, minute=10)),
    ]

    result = compute_active_hours(plays)

    assert result == {"0": 1, "8": 2, "19": 1}


def test_compute_recap_fc_highlight_uses_latest_fc_play():
    base = datetime(2026, 3, 10, 12, 0, 0)
    plays = [
        _play(song_id=1, difficulty="expert", timestamp=base, filename="nofc.png", full_combo=False),
        _play(song_id=1, difficulty="expert", timestamp=base + timedelta(hours=1), filename="fc.png", full_combo=True),
        _play(song_id=1, difficulty="expert", timestamp=base + timedelta(hours=2), filename="later.png", full_combo=False),
    ]
    fr = date(2026, 3, 10)
    to = date(2026, 3, 10)
    payload = compute_recap(plays, scope="weekly", from_date=fr, to_date=to, song_names={1: "S1"})
    fc_h = next(h for h in payload["highlights"] if h["title"] == "Full Combo push")
    assert fc_h["screenshot"]["filename"] == "fc.png"
    assert len(payload["daily_digest"]) == 1
    assert payload["daily_digest"][0]["plays"] == 3


def test_compute_song_journey_has_no_practice_period_type():
    base = datetime(2026, 3, 1, 12, 0, 0)
    plays = [
        _play(
            song_id=1,
            difficulty="expert",
            timestamp=base + timedelta(hours=i),
            filename=f"{i}.png",
            full_combo=(i >= 4),
        )
        for i in range(5)
    ]
    out = compute_song_journey(plays, song_id=1, song_name="S", difficulty="expert")
    assert "practice_periods" not in out
    assert all(t["type"] != "practice_period" for t in out["timeline"])
    assert any(t["type"] == "first_fc" for t in out["timeline"])


def test_compute_calendar_year_view_month_buckets():
    base = datetime(2026, 6, 15, 12, 0, 0)
    plays = [_play(song_id=1, difficulty="expert", timestamp=base, full_combo=True)]
    res = compute_calendar_year_view(plays, year=2026)
    assert res["year"] == 2026
    assert res["months"][5]["month"] == 6
    assert res["months"][5]["plays"] == 1
