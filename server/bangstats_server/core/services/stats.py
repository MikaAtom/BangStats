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


def format_duration_human(total_seconds: int) -> str:
    seconds = max(0, int(total_seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m"
    return f"{secs}s"


def _estimate_time_fields(total_plays: int, song_length_seconds: int) -> Dict[str, Any]:
    estimated_seconds = max(0, int(total_plays)) * max(0, int(song_length_seconds))
    return {
        "estimated_time_played_seconds": estimated_seconds,
        "estimated_time_played_human": format_duration_human(estimated_seconds),
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


def compute_song_difficulty_overview(
    screenshots: List[Any],
    *,
    song_length_seconds: int = 0,
) -> Dict[str, Dict[str, Any]]:
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
            **_estimate_time_fields(len(ordered), song_length_seconds),
        }
    return result


def compute_difficulty_detail(
    plays: List[Any],
    *,
    song_length_seconds: int = 0,
    session_gap_minutes: int = 45,
) -> Dict[str, Any]:
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

    sessions = _sessionize_plays(ordered, session_gap_minutes=session_gap_minutes)
    session_items = [_to_session_item(session) for session in sessions]
    total_sessions = len(session_items)
    avg_plays_per_session = (
        round(total_plays / total_sessions, 2) if total_sessions > 0 else 0.0
    )
    practice_sessions = [
        item for item in session_items if int(item.get("plays", 0)) >= 3
    ]

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
        **_estimate_time_fields(total_plays, song_length_seconds),
        "session_gap_minutes_used": int(session_gap_minutes),
        "total_sessions": total_sessions,
        "avg_plays_per_session": avg_plays_per_session,
        "longest_session_plays": max(
            [int(item.get("plays", 0)) for item in session_items],
            default=0,
        ),
        "longest_session_minutes": max(
            [int(item.get("duration_minutes", 0)) for item in session_items],
            default=0,
        ),
        "practice_burst_count": len(practice_sessions),
        "max_practice_burst_plays": max(
            [int(item.get("plays", 0)) for item in practice_sessions],
            default=0,
        ),
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

    seen_fc_difficulties: set[str] = set()
    seen_ap_difficulties: set[str] = set()
    for index, play in enumerate(ordered, start=1):
        difficulty = str(getattr(play, "difficulty", "")).strip().lower() or "unknown"

        if bool(getattr(play, "full_combo", False)) and difficulty not in seen_fc_difficulties:
            milestones.append(
                {
                    "type": "first_fc",
                    "label": f"First Full Combo ({difficulty})",
                    "play_count": index,
                    "meta": _to_play_meta(play),
                }
            )
            seen_fc_difficulties.add(difficulty)

        if bool(getattr(play, "all_perfect", False)) and difficulty not in seen_ap_difficulties:
            milestones.append(
                {
                    "type": "first_ap",
                    "label": f"First All Perfect ({difficulty})",
                    "play_count": index,
                    "meta": _to_play_meta(play),
                }
            )
            seen_ap_difficulties.add(difficulty)

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


def _filter_plays_in_date_range(
    screenshots: List[Any],
    *,
    from_date: date,
    to_date: date,
) -> List[Any]:
    ordered = _sorted_plays(screenshots)
    return [
        play
        for play in ordered
        if isinstance(getattr(play, "timestamp", None), datetime)
        and from_date <= getattr(play, "timestamp").date() <= to_date
    ]


def _sessionize_plays(plays: List[Any], *, session_gap_minutes: int) -> List[List[Any]]:
    if not plays:
        return []
    gap = timedelta(minutes=max(1, int(session_gap_minutes)))
    sessions: List[List[Any]] = [[plays[0]]]
    for play in plays[1:]:
        prev = sessions[-1][-1]
        prev_ts = getattr(prev, "timestamp", None)
        curr_ts = getattr(play, "timestamp", None)
        if not isinstance(prev_ts, datetime) or not isinstance(curr_ts, datetime):
            sessions[-1].append(play)
            continue
        if curr_ts - prev_ts > gap:
            sessions.append([play])
        else:
            sessions[-1].append(play)
    return sessions


def _to_session_item(session: List[Any]) -> Dict[str, Any]:
    if not session:
        return {
            "started_at": None,
            "ended_at": None,
            "plays": 0,
            "unique_songs": 0,
            "duration_minutes": 0,
        }
    started_at = getattr(session[0], "timestamp", None)
    ended_at = getattr(session[-1], "timestamp", None)
    duration_minutes = 0
    if isinstance(started_at, datetime) and isinstance(ended_at, datetime):
        duration_minutes = max(0, int((ended_at - started_at).total_seconds() // 60))
    return {
        "started_at": started_at if isinstance(started_at, datetime) else None,
        "ended_at": ended_at if isinstance(ended_at, datetime) else None,
        "plays": len(session),
        "unique_songs": len({int(getattr(play, "song_id", 0)) for play in session if int(getattr(play, "song_id", 0)) > 0}),
        "duration_minutes": duration_minutes,
    }


def _compute_practice_periods(
    plays: List[Any],
    *,
    song_lengths_seconds: Optional[Dict[int, int]] = None,
    burst_gap_minutes: int = 60,
    min_burst_plays: int = 3,
) -> List[Dict[str, Any]]:
    by_song: Dict[int, List[Any]] = defaultdict(list)
    for play in plays:
        song_id = int(getattr(play, "song_id", 0))
        if song_id > 0:
            by_song[song_id].append(play)

    results: List[Dict[str, Any]] = []
    burst_gap = timedelta(minutes=max(1, int(burst_gap_minutes)))
    for song_id, song_plays in by_song.items():
        ordered = sorted(
            [
                play
                for play in song_plays
                if isinstance(getattr(play, "timestamp", None), datetime)
            ],
            key=lambda play: getattr(play, "timestamp"),
        )
        if not ordered:
            continue
        bursts: List[List[Any]] = [[ordered[0]]]
        for play in ordered[1:]:
            prev = bursts[-1][-1]
            if getattr(play, "timestamp") - getattr(prev, "timestamp") <= burst_gap:
                bursts[-1].append(play)
            else:
                bursts.append([play])
        qualified = [burst for burst in bursts if len(burst) >= max(2, int(min_burst_plays))]
        if not qualified:
            continue
        latest_burst = max(qualified, key=lambda burst: getattr(burst[-1], "timestamp"))
        total_plays = len(ordered)
        length_seconds = int((song_lengths_seconds or {}).get(song_id, 0))
        results.append(
            {
                "song_id": song_id,
                "total_plays": total_plays,
                "burst_count": len(qualified),
                "max_burst_plays": max(len(burst) for burst in qualified),
                "latest_burst_at": getattr(latest_burst[-1], "timestamp"),
                **_estimate_time_fields(total_plays, length_seconds),
            }
        )
    return sorted(
        results,
        key=lambda item: (int(item.get("max_burst_plays", 0)), int(item.get("total_plays", 0))),
        reverse=True,
    )


def _compute_repetition_metrics(
    plays: List[Any],
    *,
    song_lengths_seconds: Optional[Dict[int, int]] = None,
) -> Dict[str, Any]:
    if not plays:
        return {
            "total_plays": 0,
            "repeated_plays": 0,
            "repeated_ratio": 0.0,
            "most_looped_songs": [],
            "revisited_after_break": [],
        }

    repeated_plays = 0
    by_song_count: Dict[int, int] = defaultdict(int)
    by_song_repeated: Dict[int, int] = defaultdict(int)
    by_song_timestamps: Dict[int, List[datetime]] = defaultdict(list)
    prev_song_id: Optional[int] = None

    for play in plays:
        song_id = int(getattr(play, "song_id", 0))
        if song_id <= 0:
            prev_song_id = None
            continue
        by_song_count[song_id] += 1
        timestamp = getattr(play, "timestamp", None)
        if isinstance(timestamp, datetime):
            by_song_timestamps[song_id].append(timestamp)
        if prev_song_id == song_id:
            repeated_plays += 1
            by_song_repeated[song_id] += 1
        prev_song_id = song_id

    song_rows: List[Dict[str, Any]] = []
    for song_id, play_count in by_song_count.items():
        timestamps = sorted(by_song_timestamps.get(song_id, []))
        max_gap_days = 0.0
        for idx in range(1, len(timestamps)):
            gap_days = (timestamps[idx] - timestamps[idx - 1]).total_seconds() / 86400.0
            max_gap_days = max(max_gap_days, gap_days)
        repeated_for_song = int(by_song_repeated.get(song_id, 0))
        length_seconds = int((song_lengths_seconds or {}).get(song_id, 0))
        song_rows.append(
            {
                "song_id": song_id,
                "play_count": int(play_count),
                "repeated_plays": repeated_for_song,
                "repeat_ratio": round(repeated_for_song / play_count, 3) if play_count > 0 else 0.0,
                "max_gap_days": round(max_gap_days, 2),
                **_estimate_time_fields(play_count, length_seconds),
            }
        )

    most_looped = sorted(
        [row for row in song_rows if int(row.get("play_count", 0)) >= 2],
        key=lambda row: (float(row.get("repeat_ratio", 0.0)), int(row.get("play_count", 0))),
        reverse=True,
    )[:5]
    revisited_after_break = sorted(
        [row for row in song_rows if float(row.get("max_gap_days", 0.0)) >= 7.0],
        key=lambda row: float(row.get("max_gap_days", 0.0)),
        reverse=True,
    )[:5]

    total_plays = sum(int(row.get("play_count", 0)) for row in song_rows)
    repeated_ratio = round(repeated_plays / total_plays, 3) if total_plays > 0 else 0.0
    return {
        "total_plays": total_plays,
        "repeated_plays": repeated_plays,
        "repeated_ratio": repeated_ratio,
        "most_looped_songs": most_looped,
        "revisited_after_break": revisited_after_break,
    }


def compute_insights(
    screenshots: List[Any],
    *,
    from_date: date,
    to_date: date,
    session_gap_minutes: int = 45,
    song_lengths_seconds: Optional[Dict[int, int]] = None,
    min_recommended_plays: int = 10,
) -> Dict[str, Any]:
    plays = _filter_plays_in_date_range(screenshots, from_date=from_date, to_date=to_date)
    sessions = _sessionize_plays(plays, session_gap_minutes=session_gap_minutes)
    session_items = [_to_session_item(session) for session in sessions]
    total_sessions = len(session_items)
    total_plays = len(plays)

    avg_session_minutes = round(
        sum(int(item["duration_minutes"]) for item in session_items) / total_sessions,
        2,
    ) if total_sessions > 0 else 0.0
    avg_plays_per_session = round(total_plays / total_sessions, 2) if total_sessions > 0 else 0.0

    ordered_starts = [
        item["started_at"]
        for item in session_items
        if isinstance(item.get("started_at"), datetime)
    ]
    recent_cadence_days = 0.0
    if len(ordered_starts) >= 2:
        gaps = [
            (ordered_starts[idx] - ordered_starts[idx - 1]).total_seconds() / 86400.0
            for idx in range(1, len(ordered_starts))
        ]
        recent_slice = gaps[-5:]
        recent_cadence_days = round(sum(recent_slice) / len(recent_slice), 2) if recent_slice else 0.0

    practice_periods = _compute_practice_periods(
        plays,
        song_lengths_seconds=song_lengths_seconds,
    )[:5]
    repetition = _compute_repetition_metrics(
        plays,
        song_lengths_seconds=song_lengths_seconds,
    )

    sparse_data = total_plays < max(1, int(min_recommended_plays))
    recommendations: List[Dict[str, Any]] = []
    if sparse_data:
        recommendations.append(
            {
                "title": "Need more sample size",
                "detail": (
                    f"Insights are limited with {total_plays} plays in range; "
                    f"aim for at least {min_recommended_plays}."
                ),
            }
        )
    if float(repetition.get("repeated_ratio", 0.0)) >= 0.45 and repetition.get("most_looped_songs"):
        most_looped = repetition["most_looped_songs"][0]
        recommendations.append(
            {
                "title": "High repetition detected",
                "detail": (
                    f"About {round(float(repetition['repeated_ratio']) * 100, 1)}% of plays are repeats. "
                    "Consider rotating songs to broaden consistency."
                ),
                "song_id": most_looped.get("song_id"),
            }
        )
    if practice_periods:
        top_practice = practice_periods[0]
        recommendations.append(
            {
                "title": "Focused practice pattern",
                "detail": (
                    f"Song {top_practice.get('song_id')} shows "
                    f"{top_practice.get('burst_count', 0)} dense practice periods."
                ),
                "song_id": top_practice.get("song_id"),
            }
        )
    if total_sessions >= 3 and avg_plays_per_session <= 2.5:
        recommendations.append(
            {
                "title": "Many short sessions",
                "detail": "Your recent sessions are short; try one longer focused block for progression-heavy songs.",
            }
        )

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "session_gap_minutes": int(session_gap_minutes),
        "data_quality": {
            "observed_plays": total_plays,
            "min_recommended_plays": int(min_recommended_plays),
            "sparse_data": sparse_data,
        },
        "sessions": {
            "total_sessions": total_sessions,
            "avg_session_minutes": avg_session_minutes,
            "avg_plays_per_session": avg_plays_per_session,
            "longest_session_minutes": max(
                [int(item["duration_minutes"]) for item in session_items],
                default=0,
            ),
            "longest_session_plays": max(
                [int(item["plays"]) for item in session_items],
                default=0,
            ),
            "recent_cadence_days": recent_cadence_days,
        },
        "recent_sessions": sorted(
            session_items,
            key=lambda item: item.get("started_at") or datetime.min,
            reverse=True,
        )[:5],
        "practice_periods": practice_periods,
        "repetition": repetition,
        "recommendations": recommendations[:5],
    }
