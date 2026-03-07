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


def test_view_stats_song_search_flow(monkeypatch, capsys):
    api = _FakeStatsAPI()
    prompts = iter(["unite", "hard", "q"])
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
    prompts = iter(["missing-song", "q"])
    monkeypatch.setattr(
        builtins,
        "input",
        lambda _prompt="": next(prompts),
    )

    view_stats(api, {"id": 7, "server": "en"})
    output = capsys.readouterr().out
    assert "No matching songs found." in output
