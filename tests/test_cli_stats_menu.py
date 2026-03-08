from __future__ import annotations

import builtins
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = ROOT / "clients" / "cli"
if str(CLIENT_PATH) not in sys.path:
    sys.path.insert(0, str(CLIENT_PATH))

from bangstats_cli.menus import view_stats


class _FakeStatsAPI:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_user_stats(self, user_id: int) -> dict[str, Any]:
        self.calls.append(("get_user_stats", {"user_id": user_id}))
        return {
            "summary": {
                "total_plays": 10,
                "total_fc": 3,
                "total_ap": 1,
                "accuracy": 95.5,
            },
            "top_songs": [{"song_id": 125, "song_name": "Unite! From A To Z", "play_count": 4}],
            "recent": [
                {
                    "song_id": 125,
                    "song_name": "Unite! From A To Z",
                    "difficulty": "hard",
                    "timestamp": "2026-03-07T00:00:00",
                }
            ],
        }

    def search_user_stat_songs(
        self,
        user_id: int,
        query: str,
        *,
        server: str = "en",
        limit: int = 20,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "search_user_stat_songs",
                {
                    "user_id": user_id,
                    "query": query,
                    "server": server,
                    "limit": limit,
                },
            )
        )
        if query.lower() == "unite":
            return {
                "query": query,
                "limit": limit,
                "results": [{"song_id": 125, "song_name": "Unite! From A To Z"}],
            }
        return {"query": query, "limit": limit, "results": []}

    def get_user_song_stats(
        self,
        user_id: int,
        song_id: int,
        *,
        server: str = "en",
        difficulty: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "get_user_song_stats",
                {
                    "user_id": user_id,
                    "song_id": song_id,
                    "server": server,
                    "difficulty": difficulty,
                },
            )
        )
        if difficulty is None:
            return {
                "song_id": song_id,
                "song_name": "Unite! From A To Z",
                "requested_difficulty": None,
                "difficulty_overview": [
                    {
                        "difficulty": "hard",
                        "total_plays": 4,
                        "first_played": {
                            "timestamp": "2026-03-01T12:00:00",
                            "filename": "a.png",
                        },
                    }
                ],
                "detail": None,
            }
        return {
            "song_id": song_id,
            "song_name": "Unite! From A To Z",
            "requested_difficulty": difficulty,
            "difficulty_overview": [],
            "detail": {
                "total_plays": 4,
                "total_fc": 2,
                "total_ap": 1,
                "accuracy": 95.0,
                "first_played": {"timestamp": "2026-03-01T12:00:00", "filename": "a.png"},
                "last_played": {"timestamp": "2026-03-07T12:00:00", "filename": "b.png"},
                "first_fc": {"timestamp": "2026-03-02T12:00:00", "filename": "x.png"},
                "last_fc": {"timestamp": "2026-03-06T12:00:00", "filename": "y.png"},
                "first_ap": {"timestamp": "2026-03-05T12:00:00", "filename": "z.png"},
                "last_ap": {"timestamp": "2026-03-05T12:00:00", "filename": "z.png"},
                "plays_before_fc": 1,
                "plays_before_ap": 3,
            },
        }

    def get_user_stats_milestones(self, user_id: int) -> dict[str, Any]:
        self.calls.append(("get_user_stats_milestones", {"user_id": user_id}))
        return {
            "milestones": [
                {
                    "type": "first_play",
                    "label": "First play recorded",
                    "play_count": 1,
                    "meta": {"timestamp": "2026-03-01T12:00:00", "filename": "a.png"},
                }
            ],
            "best_streak_days": 3,
            "current_streak_days": 2,
        }

    def get_user_stats_activity(
        self,
        user_id: int,
        *,
        preset: str | None = "30d",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "get_user_stats_activity",
                {
                    "user_id": user_id,
                    "preset": preset,
                    "from_date": from_date,
                    "to_date": to_date,
                },
            )
        )
        return {
            "from_date": "2026-03-01",
            "to_date": "2026-03-31",
            "days": 31,
            "summary": {"total_plays": 42, "total_fc": 10, "total_ap": 3, "accuracy": 95.0},
            "active_days": 12,
            "avg_plays_per_day": 1.35,
            "range_streak_days": 4,
            "delta_vs_previous": {"plays_delta": 5, "plays_delta_pct": 13.5, "accuracy_delta": 0.8},
        }

    def get_user_stats_calendar(
        self,
        user_id: int,
        *,
        year: int | None = None,
        month: int | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "get_user_stats_calendar",
                {"user_id": user_id, "year": year, "month": month},
            )
        )
        return {
            "year": 2026,
            "month": 3,
            "total_days_with_plays": 1,
            "days": [
                {
                    "date": "2026-03-01",
                    "plays": 2,
                    "fc": 1,
                    "ap": 0,
                    "accuracy": 95.0,
                    "difficulties": {"expert": 2},
                }
            ],
        }


def test_view_stats_song_search_flow(monkeypatch, capsys):
    api = _FakeStatsAPI()
    prompts = iter(["1", "unite", "hard", "q", "q"])
    monkeypatch.setattr(
        builtins,
        "input",
        lambda _prompt="": next(prompts),
    )

    view_stats(api, {"id": 7, "server": "en"})
    output = capsys.readouterr().out

    assert "General Summary" in output
    assert "Detailed stats for Unite! From A To Z [hard]" in output
    assert any(name == "search_user_stat_songs" for name, _ in api.calls)
    assert any(
        name == "get_user_song_stats" and payload.get("difficulty") == "hard"
        for name, payload in api.calls
    )


def test_view_stats_song_search_handles_empty_results(monkeypatch, capsys):
    api = _FakeStatsAPI()
    prompts = iter(["1", "missing-song", "q", "q"])
    monkeypatch.setattr(
        builtins,
        "input",
        lambda _prompt="": next(prompts),
    )

    view_stats(api, {"id": 7, "server": "en"})
    output = capsys.readouterr().out
    assert "No matching songs found." in output


def test_view_stats_milestones_activity_calendar(monkeypatch, capsys):
    api = _FakeStatsAPI()
    prompts = iter(
        [
            "2",  # milestones
            "3",  # activity
            "2",  # 30d
            "4",  # calendar
            "2026",
            "3",
            "q",  # exit stats loop
        ]
    )
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(prompts))

    view_stats(api, {"id": 7, "server": "en"})
    output = capsys.readouterr().out
    assert "Milestones" in output
    assert "Activity 2026-03-01 -> 2026-03-31" in output
    assert "Calendar 2026-03" in output
