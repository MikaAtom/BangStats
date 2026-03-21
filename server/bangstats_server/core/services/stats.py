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


def _single_play_accuracy(play: Any) -> float:
    notes = _to_notes_total(play)
    if notes <= 0:
        return 0.0
    return round((int(getattr(play, "perfect", 0)) / notes) * 100, 2)


def _latest_play_meta_for_predicate(plays: List[Any], predicate) -> Optional[Dict[str, Any]]:
    matching = [p for p in plays if predicate(p)]
    if not matching:
        return None
    latest = max(matching, key=lambda p: getattr(p, "timestamp", datetime.min))
    return _to_play_meta(latest)


def _build_recap_daily_digest(
    plays: List[Any],
    from_date: date,
    to_date: date,
) -> List[Dict[str, Any]]:
    by_day: Dict[date, Dict[str, Any]] = defaultdict(
        lambda: {"plays": 0, "fc": 0, "ap": 0, "perfect": 0, "notes": 0}
    )
    for play in plays:
        ts = getattr(play, "timestamp", None)
        if not isinstance(ts, datetime):
            continue
        d = ts.date()
        if not (from_date <= d <= to_date):
            continue
        b = by_day[d]
        b["plays"] += 1
        b["fc"] += 1 if bool(getattr(play, "full_combo", False)) else 0
        b["ap"] += 1 if bool(getattr(play, "all_perfect", False)) else 0
        b["perfect"] += int(getattr(play, "perfect", 0))
        b["notes"] += _to_notes_total(play)
    out: List[Dict[str, Any]] = []
    cur = from_date
    while cur <= to_date:
        b = by_day.get(
            cur,
            {"plays": 0, "fc": 0, "ap": 0, "perfect": 0, "notes": 0},
        )
        notes = int(b.get("notes", 0))
        acc = round((int(b["perfect"]) / notes) * 100, 2) if notes > 0 else 0.0
        out.append(
            {
                "date": cur.isoformat(),
                "plays": int(b["plays"]),
                "fc": int(b["fc"]),
                "ap": int(b["ap"]),
                "accuracy": acc,
            }
        )
        cur += timedelta(days=1)
    return out


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
        "skill_score": compute_skill_score(screenshots),
    }


def compute_top_songs(screenshots: List[Any], n: int = 5) -> List[Dict[str, Any]]:
    grouped: Dict[int, int] = defaultdict(int)
    for s in screenshots:
        sid = int(getattr(s, "song_id", 0))
        if sid > 0:
            grouped[sid] += 1
    ordered = sorted(grouped.items(), key=lambda x: x[1], reverse=True)[:n]
    return [{"song_id": sid, "play_count": count} for sid, count in ordered]


def compute_song_rankings(
    screenshots: List[Any],
    *,
    song_names: Dict[int, str] | None = None,
    sort_by: str = "play_count",
    limit: int = 25,
    offset: int = 0,
) -> tuple[List[Dict[str, Any]], int]:
    grouped: Dict[int, List[Any]] = defaultdict(list)
    for play in screenshots:
        song_id = int(getattr(play, "song_id", 0))
        if song_id > 0:
            grouped[song_id].append(play)

    rows: List[Dict[str, Any]] = []
    for song_id, plays in grouped.items():
        ordered = sorted(plays, key=lambda item: getattr(item, "timestamp", datetime.min))
        rows.append(
            {
                "song_id": song_id,
                "song_name": (song_names or {}).get(song_id),
                "play_count": len(ordered),
                "fc_count": sum(1 for play in ordered if bool(getattr(play, "full_combo", False))),
                "ap_count": sum(1 for play in ordered if bool(getattr(play, "all_perfect", False))),
                "skill_score": compute_skill_score(ordered),
                "latest_play": _to_play_meta(ordered[-1]) if ordered else None,
            }
        )

    sort_key_map = {
        "play_count": lambda item: (int(item["play_count"]), float(item["skill_score"])),
        "skill_score": lambda item: (float(item["skill_score"]), int(item["play_count"])),
        "fc_count": lambda item: (int(item["fc_count"]), int(item["play_count"])),
        "ap_count": lambda item: (int(item["ap_count"]), int(item["play_count"])),
    }
    key_fn = sort_key_map.get(sort_by, sort_key_map["play_count"])
    ordered_rows = sorted(rows, key=key_fn, reverse=True)
    total = len(ordered_rows)
    start = max(0, int(offset))
    end = start + max(1, int(limit))
    return ordered_rows[start:end], total


def compute_recent_plays(screenshots: List[Any], n: int = 5) -> List[Dict[str, Any]]:
    ordered = sorted(
        screenshots,
        key=lambda s: getattr(s, "timestamp", datetime.min),
        reverse=True,
    )[:n]
    rows: List[Dict[str, Any]] = []
    for s in ordered:
        perfect = int(getattr(s, "perfect", 0) or 0)
        great = int(getattr(s, "great", 0) or 0)
        good = int(getattr(s, "good", 0) or 0)
        bad = int(getattr(s, "bad", 0) or 0)
        miss = int(getattr(s, "miss", 0) or 0)
        total_notes = perfect + great + good + bad + miss
        accuracy = round((perfect / total_notes) * 100, 2) if total_notes > 0 else 0.0
        fast_raw = getattr(s, "fast", None)
        slow_raw = getattr(s, "slow", None)
        rows.append(
            {
                "song_id": int(getattr(s, "song_id", 0)),
                "difficulty": str(getattr(s, "difficulty", "")),
                "timestamp": getattr(s, "timestamp", None),
                "filename": getattr(s, "filename", None),
                "live_type": str(getattr(s, "live_type", "")),
                "score": int(getattr(s, "score", 0) or 0),
                "accuracy": accuracy,
                "perfect": perfect,
                "great": great,
                "good": good,
                "bad": bad,
                "miss": miss,
                "fast": int(fast_raw) if fast_raw is not None else 0,
                "slow": int(slow_raw) if slow_raw is not None else 0,
                "max_combo": int(getattr(s, "max_combo", 0) or 0),
                "full_combo": bool(getattr(s, "full_combo", False)),
                "all_perfect": bool(getattr(s, "all_perfect", False)),
                "anomaly": bool(getattr(s, "anomaly", False)),
            }
        )
    return rows


def compute_skill_score(screenshots: List[Any]) -> float:
    if not screenshots:
        return 0.0
    total_notes = sum(_to_notes_total(play) for play in screenshots)
    total_perfects = sum(int(getattr(play, "perfect", 0)) for play in screenshots)
    accuracy = (total_perfects / total_notes) * 100 if total_notes > 0 else 0.0
    fc_rate = sum(1 for play in screenshots if bool(getattr(play, "full_combo", False))) / len(screenshots)
    ap_rate = sum(1 for play in screenshots if bool(getattr(play, "all_perfect", False))) / len(screenshots)
    score = accuracy + (fc_rate * 8.0) + (ap_rate * 12.0)
    return round(score, 2)


def filter_excluded_songs(screenshots: List[Any], excluded_song_ids: set[int] | None = None) -> List[Any]:
    if not excluded_song_ids:
        return list(screenshots)
    return [
        play
        for play in screenshots
        if int(getattr(play, "song_id", 0)) not in excluded_song_ids
    ]


def filter_stats_plays(
    screenshots: List[Any],
    *,
    difficulty: str | None = None,
    live_type: str | None = None,
) -> List[Any]:
    normalized_difficulty = difficulty.strip().lower() if isinstance(difficulty, str) and difficulty.strip() else None
    normalized_live_type = live_type.strip().lower() if isinstance(live_type, str) and live_type.strip() else None
    filtered = list(screenshots)
    if normalized_difficulty:
        filtered = [
            play
            for play in filtered
            if str(getattr(play, "difficulty", "")).strip().lower() == normalized_difficulty
        ]
    if normalized_live_type:
        filtered = [
            play
            for play in filtered
            if str(getattr(play, "live_type", "")).strip().lower() == normalized_live_type
        ]
    return filtered


def compute_live_type_distribution(screenshots: List[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for play in screenshots:
        live_type = str(getattr(play, "live_type", "")).strip().lower() or "unknown"
        counts[live_type] += 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def compute_active_hours(screenshots: List[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for play in screenshots:
        timestamp = getattr(play, "timestamp", None)
        if isinstance(timestamp, datetime):
            counts[str(int(timestamp.hour))] += 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


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
        "skill_score": compute_skill_score(ordered),
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


def compute_calendar_year_view(screenshots: List[Any], *, year: int) -> Dict[str, Any]:
    buckets: Dict[int, Dict[str, Any]] = {
        m: {"plays": 0, "fc": 0, "ap": 0, "days": set()} for m in range(1, 13)
    }
    y = int(year)
    for play in screenshots:
        ts = getattr(play, "timestamp", None)
        if not isinstance(ts, datetime) or ts.year != y:
            continue
        m = int(ts.month)
        b = buckets[m]
        b["plays"] += 1
        b["fc"] += 1 if bool(getattr(play, "full_combo", False)) else 0
        b["ap"] += 1 if bool(getattr(play, "all_perfect", False)) else 0
        b["days"].add(ts.date())
    months: List[Dict[str, Any]] = []
    for m in range(1, 13):
        b = buckets[m]
        months.append(
            {
                "month": m,
                "plays": int(b["plays"]),
                "fc": int(b["fc"]),
                "ap": int(b["ap"]),
                "active_days": len(b["days"]),
            }
        )
    return {"year": y, "months": months}


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
        "recommendations": [],
    }


def _date_range_label(scope: str, *, from_date: date, to_date: date) -> str:
    if scope == "weekly":
        return f"Week of {from_date.isoformat()}"
    if scope == "monthly":
        return from_date.strftime("%B %Y")
    if scope == "seasonal":
        return f"Season {from_date.isoformat()} to {to_date.isoformat()}"
    if scope == "yearly":
        return str(from_date.year)
    if scope == "event":
        return f"Event {from_date.isoformat()} to {to_date.isoformat()}"
    return f"{from_date.isoformat()} to {to_date.isoformat()}"


def build_period_windows(
    *,
    scope: str,
    anchor: date,
    count: int,
) -> List[tuple[str, date, date]]:
    windows: List[tuple[str, date, date]] = []
    safe_count = max(1, int(count))
    if scope == "weekly":
        current = anchor - timedelta(days=anchor.weekday())
        for _ in range(safe_count):
            start = current
            end = current + timedelta(days=6)
            windows.append((f"{start.isoformat()}", start, end))
            current = start - timedelta(days=7)
    elif scope == "monthly":
        year = anchor.year
        month = anchor.month
        for _ in range(safe_count):
            start = date(year, month, 1)
            if month == 12:
                next_month = date(year + 1, 1, 1)
            else:
                next_month = date(year, month + 1, 1)
            end = next_month - timedelta(days=1)
            windows.append((start.strftime("%Y-%m"), start, end))
            month -= 1
            if month == 0:
                month = 12
                year -= 1
    elif scope == "yearly":
        year = anchor.year
        for _ in range(safe_count):
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            windows.append((str(year), start, end))
            year -= 1
    else:
        windows.append((_date_range_label(scope, from_date=anchor, to_date=anchor), anchor, anchor))
    windows.reverse()
    return windows


def compute_progression(
    screenshots: List[Any],
    *,
    scope: str,
    anchor: date,
    count: int = 6,
) -> Dict[str, Any]:
    points: List[Dict[str, Any]] = []
    for label, from_date, to_date in build_period_windows(scope=scope, anchor=anchor, count=count):
        plays = _filter_plays_in_date_range(screenshots, from_date=from_date, to_date=to_date)
        summary = compute_general_summary(plays)
        points.append(
            {
                "label": label,
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "plays": int(summary.get("total_plays", 0)),
                "accuracy": float(summary.get("accuracy", 0.0)),
                "skill_score": float(summary.get("skill_score", 0.0)),
                "fc": int(summary.get("total_fc", 0)),
                "ap": int(summary.get("total_ap", 0)),
            }
        )
    delta_skill = 0.0
    delta_accuracy = 0.0
    if len(points) >= 2:
        delta_skill = round(float(points[-1]["skill_score"]) - float(points[-2]["skill_score"]), 2)
        delta_accuracy = round(float(points[-1]["accuracy"]) - float(points[-2]["accuracy"]), 2)
    return {
        "scope": scope,
        "points": points,
        "delta_skill_score": delta_skill,
        "delta_accuracy": delta_accuracy,
    }


def compute_event_stats(
    screenshots: List[Any],
    *,
    song_names: Optional[Dict[int, str]] = None,
    event_name: Optional[str] = None,
    event_type: Optional[str] = None,
    event_id: int = 0,
    from_date: date,
    to_date: date,
    session_gap_minutes: int = 45,
) -> Dict[str, Any]:
    plays = _filter_plays_in_date_range(screenshots, from_date=from_date, to_date=to_date)
    summary = compute_general_summary(plays)
    sessions = _sessionize_plays(plays, session_gap_minutes=session_gap_minutes)
    by_song: Dict[int, Dict[str, Any]] = defaultdict(lambda: {"play_count": 0, "fc_count": 0, "ap_count": 0, "plays": []})
    for play in plays:
        song_id = int(getattr(play, "song_id", 0))
        if song_id <= 0:
            continue
        by_song[song_id]["play_count"] += 1
        by_song[song_id]["fc_count"] += 1 if bool(getattr(play, "full_combo", False)) else 0
        by_song[song_id]["ap_count"] += 1 if bool(getattr(play, "all_perfect", False)) else 0
        by_song[song_id]["plays"].append(play)
    top_songs = sorted(
        [
            {
                "song_id": song_id,
                "song_name": (song_names or {}).get(song_id),
                "play_count": payload["play_count"],
                "fc_count": payload["fc_count"],
                "ap_count": payload["ap_count"],
                "skill_score": compute_skill_score(payload["plays"]),
            }
            for song_id, payload in by_song.items()
        ],
        key=lambda item: (int(item["play_count"]), float(item["skill_score"])),
        reverse=True,
    )[:8]
    return {
        "event_id": int(event_id),
        "event_name": event_name,
        "event_type": event_type,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "summary": summary,
        "live_types": compute_live_type_distribution(plays),
        "active_hours": compute_active_hours(plays),
        "top_songs": top_songs,
        "total_sessions": len(sessions),
        "longest_session_minutes": max([_to_session_item(session)["duration_minutes"] for session in sessions], default=0),
        "fc_gains": int(summary.get("total_fc", 0)),
        "ap_gains": int(summary.get("total_ap", 0)),
        "skill_score": float(summary.get("skill_score", 0.0)),
    }


def compute_song_journey(
    plays: List[Any],
    *,
    song_id: int,
    song_name: Optional[str],
    difficulty: str,
    song_length_seconds: int = 0,
    session_gap_minutes: int = 45,
) -> Dict[str, Any]:
    detail = compute_difficulty_detail(
        plays,
        song_length_seconds=song_length_seconds,
        session_gap_minutes=session_gap_minutes,
    )
    ordered = sorted(
        [p for p in plays if isinstance(getattr(p, "timestamp", None), datetime)],
        key=lambda play: getattr(play, "timestamp"),
    )
    events: List[tuple[datetime, str, Any, str, Dict[str, Any]]] = []
    milestone_play_ids: set[int] = set()

    if ordered:
        p0 = ordered[0]
        events.append((p0.timestamp, "first_play", p0, "First play", {}))
        milestone_play_ids.add(id(p0))

    for threshold in (25, 50, 100, 250, 500):
        if len(ordered) >= threshold:
            p = ordered[threshold - 1]
            events.append((p.timestamp, "play_milestone", p, f"After {threshold} plays", {"threshold": threshold}))
            milestone_play_ids.add(id(p))

    if len(ordered) > 1:
        best_i = max(range(len(ordered)), key=lambda i: _single_play_accuracy(ordered[i]))
        bp = ordered[best_i]
        acc = _single_play_accuracy(bp)
        first_acc = _single_play_accuracy(ordered[0])
        if acc > first_acc + 1.0 or acc >= 99.0:
            events.append((bp.timestamp, "best_accuracy", bp, f"Best accuracy ({acc}%)", {"accuracy": acc}))

    fc_i = next((i for i, p in enumerate(ordered) if bool(getattr(p, "full_combo", False))), None)
    if fc_i is not None:
        p = ordered[fc_i]
        events.append(
            (p.timestamp, "first_fc", p, "First Full Combo", {"plays_to_fc": fc_i + 1}),
        )

    ap_i = next((i for i, p in enumerate(ordered) if bool(getattr(p, "all_perfect", False))), None)
    if ap_i is not None:
        p = ordered[ap_i]
        events.append(
            (p.timestamp, "first_ap", p, "First All Perfect", {"plays_to_ap": ap_i + 1}),
        )

    events.sort(key=lambda x: x[0])
    seen_keys: set[tuple[Any, str, Any]] = set()
    timeline: List[Dict[str, Any]] = []
    for ts, typ, play, label, det in events:
        fn = getattr(play, "filename", None)
        key = (ts, typ, fn)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        meta = _to_play_meta(play)
        timeline.append(
            {
                "type": typ,
                "label": label,
                "timestamp": meta.get("timestamp"),
                "filename": meta.get("filename"),
                "details": det,
            }
        )

    return {
        "song_id": song_id,
        "song_name": song_name,
        "difficulty": difficulty,
        "total_plays": len(ordered),
        "first_played": detail.get("first_played"),
        "first_fc": detail.get("first_fc"),
        "first_ap": detail.get("first_ap"),
        "plays_before_fc": detail.get("plays_before_fc"),
        "plays_before_ap": detail.get("plays_before_ap"),
        "skill_score": detail.get("skill_score", 0.0),
        "timeline": timeline,
    }


def compute_recap(
    screenshots: List[Any],
    *,
    scope: str,
    from_date: date,
    to_date: date,
    song_names: Optional[Dict[int, str]] = None,
    compare_screenshots: Optional[List[Any]] = None,
    event_id: Optional[int] = None,
    event_name: Optional[str] = None,
) -> Dict[str, Any]:
    plays = _filter_plays_in_date_range(screenshots, from_date=from_date, to_date=to_date)
    summary = compute_general_summary(plays)
    compare_summary = compute_general_summary(compare_screenshots or [])
    top_song_rows: List[Dict[str, Any]] = []
    by_song: Dict[int, List[Any]] = defaultdict(list)
    for play in plays:
        song_id = int(getattr(play, "song_id", 0))
        if song_id > 0:
            by_song[song_id].append(play)
    for song_id, song_plays in by_song.items():
        ordered = sorted(song_plays, key=lambda play: getattr(play, "timestamp", datetime.min))
        top_song_rows.append(
            {
                "song_id": song_id,
                "song_name": (song_names or {}).get(song_id),
                "play_count": len(song_plays),
                "fc_count": sum(1 for play in song_plays if bool(getattr(play, "full_combo", False))),
                "ap_count": sum(1 for play in song_plays if bool(getattr(play, "all_perfect", False))),
                "skill_score": compute_skill_score(song_plays),
                "latest_play": _to_play_meta(ordered[-1]),
            }
        )
    top_song_rows = sorted(top_song_rows, key=lambda item: (int(item["play_count"]), float(item["skill_score"])), reverse=True)
    current_song_ids = set(by_song.keys())
    prior_song_ids = {
        int(getattr(play, "song_id", 0))
        for play in (compare_screenshots or [])
        if int(getattr(play, "song_id", 0)) > 0
    }
    new_song_rows = [row for row in top_song_rows if row["song_id"] not in prior_song_ids][:8]
    milestones = compute_milestones(plays)
    daily_digest = _build_recap_daily_digest(plays, from_date, to_date)
    highlights: List[Dict[str, Any]] = []
    if top_song_rows:
        highlights.append(
            {
                "title": "Most played song",
                "value": top_song_rows[0]["song_name"] or f"Song {top_song_rows[0]['song_id']}",
                "detail": f"{top_song_rows[0]['play_count']} plays in this {scope}.",
                "screenshot": top_song_rows[0].get("latest_play"),
            }
        )
    fc_shot = _latest_play_meta_for_predicate(plays, lambda p: bool(getattr(p, "full_combo", False)))
    if summary.get("total_fc", 0):
        highlights.append(
            {
                "title": "Full Combo push",
                "value": str(summary["total_fc"]),
                "detail": "Full Combo clears recorded in this range.",
                "screenshot": fc_shot,
            }
        )
    ap_shot = _latest_play_meta_for_predicate(plays, lambda p: bool(getattr(p, "all_perfect", False)))
    if summary.get("total_ap", 0):
        highlights.append(
            {
                "title": "All Perfect streak",
                "value": str(summary["total_ap"]),
                "detail": "All Perfect clears recorded in this range.",
                "screenshot": ap_shot,
            }
        )

    overdue_min = 40
    overdue_fc_rows = [row for row in top_song_rows if int(row["play_count"]) >= overdue_min and int(row["fc_count"]) == 0]
    if overdue_fc_rows:
        worst = max(overdue_fc_rows, key=lambda r: int(r["play_count"]))
        highlights.append(
            {
                "title": "Long overdue Full Combo",
                "value": worst["song_name"] or f"Song {worst['song_id']}",
                "detail": f"{worst['play_count']} plays in this range with no FC yet.",
                "screenshot": worst.get("latest_play"),
            }
        )
    overdue_ap_rows = [
        row
        for row in top_song_rows
        if int(row["play_count"]) >= overdue_min and int(row["fc_count"]) > 0 and int(row["ap_count"]) == 0
    ]
    if overdue_ap_rows:
        worst_ap = max(overdue_ap_rows, key=lambda r: int(r["play_count"]))
        highlights.append(
            {
                "title": "Long overdue All Perfect",
                "value": worst_ap["song_name"] or f"Song {worst_ap['song_id']}",
                "detail": f"{worst_ap['play_count']} plays with FC but no AP in this range.",
                "screenshot": worst_ap.get("latest_play"),
            }
        )

    if len(plays) >= 3:
        peak_play = max(plays, key=_single_play_accuracy)
        peak_acc = _single_play_accuracy(peak_play)
        if peak_acc >= 95.0:
            sid = int(getattr(peak_play, "song_id", 0))
            peak_name = (song_names or {}).get(sid) if sid else None
            highlights.append(
                {
                    "title": "Peak accuracy",
                    "value": f"{peak_acc}%",
                    "detail": f"Best single-play accuracy in this range"
                    + (f" ({peak_name})." if peak_name else "."),
                    "screenshot": _to_play_meta(peak_play),
                }
            )

    return {
        "scope": scope,
        "title": _date_range_label(scope, from_date=from_date, to_date=to_date),
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "event_id": event_id,
        "event_name": event_name,
        "summary": summary,
        "skill_score": float(summary.get("skill_score", 0.0)),
        "skill_score_delta": round(float(summary.get("skill_score", 0.0)) - float(compare_summary.get("skill_score", 0.0)), 2),
        "top_songs": top_song_rows[:8],
        "new_songs": new_song_rows,
        "most_practiced": [],
        "live_types": compute_live_type_distribution(plays),
        "active_hours": compute_active_hours(plays),
        "highlights": highlights,
        "daily_digest": daily_digest,
        "streaks": {
            "best_daily": milestones.get("best_streak_days", 0),
            "current_daily": milestones.get("current_streak_days", 0),
        },
    }
