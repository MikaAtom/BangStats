import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from bangstats_server.core.config import (
    EVENT_TYPE_TO_LIVE_TYPES,
    FAKE_SCAN_DELAY_MS,
    FAKE_SCAN_ERROR_RATE,
    FAKE_SCAN_ERROR_WEIGHTS,
    FAKE_SCAN_PROFILE,
    FAKE_SCAN_SEED,
)
from bangstats_server.core.services.event import EventService
from bangstats_server.core.services.song import SongService
from bangstats_server.core.timestamps import extract_timestamp_from_filename

ERROR_TYPES = [
    "note_errors",
    "not_found_errors",
    "fast_slow_errors",
    "max_combo_errors",
    "live_errors",
]

PROFILE_WEIGHTS = {
    "beginner": {"perfect": 0.45, "great": 0.25, "good": 0.18, "bad": 0.07, "miss": 0.05},
    "expert": {"perfect": 0.93, "great": 0.06, "good": 0.01, "bad": 0.0, "miss": 0.0},
}


def _parse_error_weights(raw: str) -> dict[str, int]:
    weights: dict[str, int] = {error: 1 for error in ERROR_TYPES}
    for part in raw.split(","):
        chunk = part.strip()
        if not chunk or ":" not in chunk:
            continue
        name, value = chunk.split(":", 1)
        key = name.strip().lower()
        if key not in weights:
            continue
        try:
            parsed = int(value.strip())
        except ValueError:
            continue
        weights[key] = max(0, parsed)
    if sum(weights.values()) <= 0:
        return {error: 1 for error in ERROR_TYPES}
    return weights


def generate_spread_timestamps(
    count: int,
    span_days: int,
    rng: random.Random | None = None,
) -> list[datetime]:
    if count <= 0:
        return []

    resolved_rng = rng or random.Random()
    now = datetime.now()
    start = now - timedelta(days=max(1, span_days))
    span_seconds = max(1, int((now - start).total_seconds()))
    offsets = sorted(resolved_rng.randint(0, span_seconds) for _ in range(count))
    return [start + timedelta(seconds=offset) for offset in offsets]


class FakeScannerService:
    def __init__(self):
        if FAKE_SCAN_SEED:
            try:
                self._rng = random.Random(int(FAKE_SCAN_SEED))
            except ValueError:
                self._rng = random.Random(FAKE_SCAN_SEED)
        else:
            self._rng = random.Random()

        self._song_service = SongService()
        self._event_service = EventService()
        self._songs_cache: list[Any] | None = None
        self._weights = _parse_error_weights(FAKE_SCAN_ERROR_WEIGHTS)

    def _pick_song(self) -> tuple[Any, str, int]:
        if self._songs_cache is None:
            self._songs_cache = self._song_service.get_all_songs()
        if not self._songs_cache:
            raise ValueError("No songs in database. Run sync first for fake scanner.")

        song = self._rng.choice(self._songs_cache)
        levels = getattr(song, "levels", {}) or {}
        available = [diff for diff in ["easy", "normal", "hard", "expert", "special"] if levels.get(diff)]
        difficulty = self._rng.choice(available) if available else "expert"

        note_counts = getattr(song, "note_counts", {}) or {}
        raw = note_counts.get(difficulty)
        if isinstance(raw, list) and raw:
            total_notes = int(raw[0])
        elif isinstance(raw, int):
            total_notes = int(raw)
        else:
            total_notes = self._rng.randint(200, 900)
        return song, difficulty, max(1, total_notes)

    def _profile(self) -> dict[str, float]:
        profile = FAKE_SCAN_PROFILE
        if profile == "mixed":
            chosen = self._rng.choice(["beginner", "expert"])
            return PROFILE_WEIGHTS[chosen]
        return PROFILE_WEIGHTS.get(profile, PROFILE_WEIGHTS["beginner"])

    def _split_notes(self, total_notes: int) -> tuple[int, int, int, int, int]:
        weights = self._profile()
        perfect = int(total_notes * weights["perfect"])
        great = int(total_notes * weights["great"])
        good = int(total_notes * weights["good"])
        bad = int(total_notes * weights["bad"])
        miss = total_notes - perfect - great - good - bad
        if miss < 0:
            miss = 0
        return perfect, great, good, bad, miss

    def _pick_live_type(self, filename: str) -> str:
        timestamp = extract_timestamp_from_filename(filename)
        if not timestamp:
            return self._rng.choice(["free live", "multi live"])
        event = self._event_service.search_events_by_date(timestamp)
        if not event:
            return self._rng.choice(["free live", "multi live"])
        live_types = EVENT_TYPE_TO_LIVE_TYPES.get(getattr(event, "event_type", ""), ["free live", "multi live"])
        return self._rng.choice(live_types)

    def _pick_error_type(self) -> str:
        population = list(self._weights.keys())
        weights = [self._weights[item] for item in population]
        return self._rng.choices(population=population, weights=weights, k=1)[0]

    def _inject_error(self, payload: dict[str, Any], error_type: str) -> None:
        if error_type == "note_errors":
            payload["great"] = int(payload.get("great", 0)) + 3
        elif error_type == "not_found_errors":
            payload["song_name_from_top_bar_text"] = f"fake_missing_{self._rng.randint(1000, 9999)}"
        elif error_type == "fast_slow_errors":
            payload["fast"] = int(payload.get("fast", 0)) + 5
        elif error_type == "max_combo_errors":
            payload["good"] = 0
            payload["bad"] = 0
            payload["miss"] = 0
            payload["max_combo"] = max(0, int(payload.get("max_combo", 0)) - 10)
        elif error_type == "live_errors":
            payload["live_type"] = "challenge live"

    def generate_response(self, model: str, prompt: str, image_path: str) -> dict[str, Any]:
        _ = model
        _ = prompt
        time.sleep(max(0, FAKE_SCAN_DELAY_MS) / 1000)

        song, difficulty, total_notes = self._pick_song()
        perfect, great, good, bad, miss = self._split_notes(total_notes)
        max_combo = max(0, total_notes - miss)

        score_ratio = self._rng.uniform(0.5, 0.7) if FAKE_SCAN_PROFILE == "beginner" else self._rng.uniform(0.95, 1.0)
        if FAKE_SCAN_PROFILE == "mixed":
            score_ratio = self._rng.uniform(0.65, 0.98)

        score = int(1_000_000 * score_ratio)
        high_score = max(score, int(score * self._rng.uniform(1.0, 1.03)))
        rank = "S" if score_ratio >= 0.95 else ("A" if score_ratio >= 0.9 else "B")
        timing_total = great + good + bad
        fast = self._rng.randint(0, timing_total)
        slow = timing_total - fast

        localized_name = getattr(song, "name", {}) or {}
        song_name = (
            localized_name.get("en")
            or next((value for value in localized_name.values() if value), "")
            or f"Song {getattr(song, 'internal_song_id', 0)}"
        )
        base = Path(image_path).name
        payload = {
            "score": score,
            "high_score": high_score,
            "is_new_record": high_score == score,
            "score_rank": rank,
            "live_type": self._pick_live_type(base),
            "free_live_data": {"free_live_song": 0, "free_live_band": 0, "free_live_total": 0},
            "team_live_data": None,
            "perfect": perfect,
            "great": great,
            "good": good,
            "bad": bad,
            "miss": miss,
            "fast": fast,
            "slow": slow,
            "max_combo": max_combo,
            "song_level": int((getattr(song, "levels", {}) or {}).get(difficulty, [0])[0] if isinstance((getattr(song, "levels", {}) or {}).get(difficulty), list) and (getattr(song, "levels", {}) or {}).get(difficulty) else 0),
            "difficulty": difficulty,
            "song_name_from_top_bar_text": song_name,
        }

        if self._rng.randint(1, 100) <= max(0, min(100, FAKE_SCAN_ERROR_RATE)):
            self._inject_error(payload, self._pick_error_type())
        return payload
