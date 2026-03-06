from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional


def _to_notes_total(play: Any) -> int:
    return (
        int(getattr(play, "perfect", 0))
        + int(getattr(play, "great", 0))
        + int(getattr(play, "good", 0))
        + int(getattr(play, "bad", 0))
        + int(getattr(play, "miss", 0))
    )


def _to_play_meta(play: Any) -> Dict[str, Any]:
    return {
        "timestamp": getattr(play, "timestamp", None),
        "filename": getattr(play, "filename", None),
    }


def compute_general_summary(screenshots: List[Any]) -> Dict[str, Any]:
    total_plays = len(screenshots)
    total_fc = sum(1 for s in screenshots if bool(getattr(s, "full_combo", False)))
    total_ap = sum(1 for s in screenshots if bool(getattr(s, "all_perfect", False)))
    total_perfects = sum(int(getattr(s, "perfect", 0)) for s in screenshots)
    total_notes = sum(_to_notes_total(s) for s in screenshots)
    accuracy = round((total_perfects / total_notes) * 100, 2) if total_notes > 0 else 0.0
    return {
        "total_plays": total_plays,
        "total_fc": total_fc,
        "total_ap": total_ap,
        "accuracy": accuracy,
    }


def compute_top_songs(screenshots: List[Any], n: int = 5) -> List[Dict[str, Any]]:
    grouped: Dict[int, int] = defaultdict(int)
    for s in screenshots:
        sid = int(getattr(s, "song_id", 0))
        if sid > 0:
            grouped[sid] += 1
    ordered = sorted(grouped.items(), key=lambda x: x[1], reverse=True)[:n]
    return [{"song_id": sid, "play_count": count} for sid, count in ordered]


def compute_recent_plays(screenshots: List[Any], n: int = 5) -> List[Dict[str, Any]]:
    ordered = sorted(
        screenshots,
        key=lambda s: getattr(s, "timestamp", datetime.min),
        reverse=True,
    )[:n]
    return [
        {
            "song_id": int(getattr(s, "song_id", 0)),
            "difficulty": str(getattr(s, "difficulty", "")),
            "timestamp": getattr(s, "timestamp", None),
            "filename": getattr(s, "filename", None),
        }
        for s in ordered
    ]


def compute_song_difficulty_overview(screenshots: List[Any]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Any]] = defaultdict(list)
    for s in screenshots:
        difficulty = str(getattr(s, "difficulty", "")).lower()
        if difficulty:
            grouped[difficulty].append(s)

    result: Dict[str, Dict[str, Any]] = {}
    for diff, plays in grouped.items():
        ordered = sorted(plays, key=lambda p: getattr(p, "timestamp", datetime.min))
        result[diff] = {
            "first_played": _to_play_meta(ordered[0]) if ordered else None,
            "total_plays": len(ordered),
        }
    return result


def compute_difficulty_detail(plays: List[Any]) -> Dict[str, Any]:
    ordered = sorted(plays, key=lambda p: getattr(p, "timestamp", datetime.min))
    total_plays = len(ordered)
    total_fc = sum(1 for p in ordered if bool(getattr(p, "full_combo", False)))
    total_ap = sum(1 for p in ordered if bool(getattr(p, "all_perfect", False)))

    total_perfects = sum(int(getattr(p, "perfect", 0)) for p in ordered)
    total_notes = sum(_to_notes_total(p) for p in ordered)
    accuracy = round((total_perfects / total_notes) * 100, 2) if total_notes > 0 else 0.0

    fc_plays = [p for p in ordered if bool(getattr(p, "full_combo", False))]
    ap_plays = [p for p in ordered if bool(getattr(p, "all_perfect", False))]

    plays_before_fc: Optional[int] = None
    plays_before_ap: Optional[int] = None
    if fc_plays:
        first_fc = fc_plays[0]
        plays_before_fc = next(
            (idx for idx, play in enumerate(ordered) if play is first_fc),
            None,
        )
    if ap_plays:
        first_ap = ap_plays[0]
        plays_before_ap = next(
            (idx for idx, play in enumerate(ordered) if play is first_ap),
            None,
        )

    return {
        "total_plays": total_plays,
        "total_fc": total_fc,
        "total_ap": total_ap,
        "accuracy": accuracy,
        "first_played": _to_play_meta(ordered[0]) if ordered else None,
        "last_played": _to_play_meta(ordered[-1]) if ordered else None,
        "first_fc": _to_play_meta(fc_plays[0]) if fc_plays else None,
        "last_fc": _to_play_meta(fc_plays[-1]) if fc_plays else None,
        "first_ap": _to_play_meta(ap_plays[0]) if ap_plays else None,
        "last_ap": _to_play_meta(ap_plays[-1]) if ap_plays else None,
        "plays_before_fc": plays_before_fc,
        "plays_before_ap": plays_before_ap,
    }
