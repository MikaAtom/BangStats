"""Helpers for chart metadata (e.g. song level by difficulty)."""

from __future__ import annotations

from typing import Any


def chart_level_for_difficulty(levels: Any, difficulty: str) -> int | None:
    """Resolve chart level from song `levels` JSON for a play difficulty."""
    if not levels or not isinstance(levels, dict) or not difficulty:
        return None
    key = str(difficulty).strip().lower()
    raw = None
    for k, v in levels.items():
        if str(k).strip().lower() == key:
            raw = v
            break
    if raw is None:
        return None
    if isinstance(raw, list):
        if not raw:
            return None
        try:
            return int(raw[0])
        except (TypeError, ValueError):
            return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
