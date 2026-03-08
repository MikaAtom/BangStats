from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
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


def _sorted_plays(screenshots: List[Any]) -> List[Any]:
    return sorted(screenshots, key=lambda s: getattr(s, "timestamp", datetime.min))


def _play_date(play: Any) -> date:
    timestamp = getattr(play, "timestamp", None)
    if isinstance(timestamp, datetime):
        return timestamp.date()
    return date.min


def _compute_longest_daily_streak(plays: List[Any]) -> int:
    days = sorted({_play_date(play) for play in plays if isinstance(getattr(play, "timestamp", None), datetime)})
    if not days:
        return 0
    longest = 1
    current = 1
    for idx in range(1, len(days)):
        if days[idx] == days[idx - 1] + timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _compute_current_daily_streak(plays: List[Any]) -> int:
    days = sorted({_play_date(play) for play in plays if isinstance(getattr(play, "timestamp", None), datetime)})
    if not days:
        return 0
    streak = 1
    for idx in range(len(days) - 1, 0, -1):
        if days[idx] == days[idx - 1] + timedelta(days=1):
            streak += 1
        else:
            break
    return streak


def compute_milestones(screenshots: List[Any]) -> Dict[str, Any]:
    ordered = _sorted_plays(screenshots)
    if not ordered:
        return {"milestones": [], "best_streak_days": 0, "current_streak_days": 0}

    milestones: List[Dict[str, Any]] = []
    first_play = ordered[0]
    milestones.append(
        {
            "type": "first_play",
            "label": "First play recorded",
            "play_count": 1,
            "meta": _to_play_meta(first_play),
        }
    )

    first_fc = next((play for play in ordered if bool(getattr(play, "full_combo", False))), None)
    if first_fc:
        milestones.append(
            {
                "type": "first_fc",
                "label": "First Full Combo",
                "play_count": ordered.index(first_fc) + 1,
                "meta": _to_play_meta(first_fc),
            }
        )

    first_ap = next((play for play in ordered if bool(getattr(play, "all_perfect", False))), None)
    if first_ap:
        milestones.append(
            {
                "type": "first_ap",
                "label": "First All Perfect",
                "play_count": ordered.index(first_ap) + 1,
                "meta": _to_play_meta(first_ap),
            }
        )

    thresholds = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
    for threshold in thresholds:
        if len(ordered) >= threshold:
            play = ordered[threshold - 1]
            milestones.append(
                {
                    "type": "play_count",
                    "label": f"Reached {threshold} plays",
                    "play_count": threshold,
                    "meta": _to_play_meta(play),
                }
            )

    milestones = sorted(
        milestones,
        key=lambda item: item.get("meta", {}).get("timestamp") or datetime.min,
    )
    return {
        "milestones": milestones,
        "best_streak_days": _compute_longest_daily_streak(ordered),
        "current_streak_days": _compute_current_daily_streak(ordered),
    }


def compute_activity_range(
    screenshots: List[Any],
    *,
    from_date: date,
    to_date: date,
) -> Dict[str, Any]:
    ordered = _sorted_plays(screenshots)
    in_range = [
        play
        for play in ordered
        if isinstance(getattr(play, "timestamp", None), datetime)
        and from_date <= getattr(play, "timestamp").date() <= to_date
    ]
    days = max(1, (to_date - from_date).days + 1)

    summary = compute_general_summary(in_range)
    active_days = len({_play_date(play) for play in in_range})
    prev_to = from_date - timedelta(days=1)
    prev_from = prev_to - timedelta(days=days - 1)
    previous_range = [
        play
        for play in ordered
        if isinstance(getattr(play, "timestamp", None), datetime)
        and prev_from <= getattr(play, "timestamp").date() <= prev_to
    ]

    previous_summary = compute_general_summary(previous_range)
    previous_plays = int(previous_summary.get("total_plays", 0))
    current_plays = int(summary.get("total_plays", 0))
    plays_delta = current_plays - previous_plays
    if previous_plays > 0:
        plays_delta_pct = round((plays_delta / previous_plays) * 100, 2)
    elif current_plays > 0:
        plays_delta_pct = 100.0
    else:
        plays_delta_pct = 0.0

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "days": days,
        "summary": summary,
        "active_days": active_days,
        "avg_plays_per_day": round(current_plays / days, 2),
        "range_streak_days": _compute_longest_daily_streak(in_range),
        "delta_vs_previous": {
            "plays_delta": plays_delta,
            "plays_delta_pct": plays_delta_pct,
            "accuracy_delta": round(
                float(summary.get("accuracy", 0.0)) - float(previous_summary.get("accuracy", 0.0)),
                2,
            ),
        },
    }


def compute_calendar_month_view(
    screenshots: List[Any],
    *,
    year: int,
    month: int,
) -> Dict[str, Any]:
    ordered = _sorted_plays(screenshots)
    by_day: Dict[str, Dict[str, Any]] = {}

    for play in ordered:
        timestamp = getattr(play, "timestamp", None)
        if not isinstance(timestamp, datetime):
            continue
        if timestamp.year != year or timestamp.month != month:
            continue
        key = timestamp.date().isoformat()
        if key not in by_day:
            by_day[key] = {
                "date": key,
                "plays": 0,
                "fc": 0,
                "ap": 0,
                "perfect": 0,
                "notes": 0,
                "difficulties": defaultdict(int),
            }
        payload = by_day[key]
        payload["plays"] += 1
        payload["fc"] += 1 if bool(getattr(play, "full_combo", False)) else 0
        payload["ap"] += 1 if bool(getattr(play, "all_perfect", False)) else 0
        payload["perfect"] += int(getattr(play, "perfect", 0))
        payload["notes"] += _to_notes_total(play)
        difficulty = str(getattr(play, "difficulty", "")).lower()
        if difficulty:
            payload["difficulties"][difficulty] += 1

    days: List[Dict[str, Any]] = []
    for key in sorted(by_day.keys()):
        item = by_day[key]
        notes = int(item["notes"])
        item["accuracy"] = round((item["perfect"] / notes) * 100, 2) if notes > 0 else 0.0
        item["difficulties"] = dict(item["difficulties"])
        item.pop("perfect", None)
        item.pop("notes", None)
        days.append(item)

    return {
        "year": year,
        "month": month,
        "total_days_with_plays": len(days),
        "days": days,
    }
