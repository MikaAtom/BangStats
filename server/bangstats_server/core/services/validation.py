import json
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from bangstats_server.core.config import EVENT_TYPE_TO_LIVE_TYPES, PACKAGE_ROOT
from bangstats_server.core.services.song import SongService
from bangstats_server.core.services.event import EventService
from bangstats_server.core.timestamps import extract_timestamp_from_filename


@dataclass
class ValidationResult:
    is_valid: bool
    error_type: Optional[str]
    resolved_song_id: Optional[int]
    normalized: Dict[str, Any]
    reasons: List[str] = field(default_factory=list)
    severity: str = "info"
    confidence: float = 1.0


class ValidationService:
    """Service for validating scan results with error categorization."""

    def __init__(self):
        self.event_type_to_live_types = EVENT_TYPE_TO_LIVE_TYPES
        self.fuzzy_threshold = 0.8
        self.name_fixes = self._load_name_fixes()

        self.song_service = SongService()
        self.event_service = EventService()

        self.stripped_songs = self._get_stripped_songs(self.song_service.get_all_songs())

    def _load_name_fixes(self, path: Optional[Path] = None) -> Dict[str, str]:
        fixes_path = path or (PACKAGE_ROOT / "adapters" / "ocr" / "name_fixes.json")
        try:
            with open(fixes_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                logger.warning(f"Name fixes file is not a dict: {fixes_path}")
                return {}
            return {str(k): str(v) for k, v in payload.items()}
        except FileNotFoundError:
            logger.warning(f"Name fixes file not found: {fixes_path}")
            return {}
        except Exception as exc:
            logger.warning(f"Failed to load name fixes from {fixes_path}: {exc}")
            return {}

    def _get_stripped_songs(self, all_songs):
        """Get stripped songs from the database."""
        stripped_songs = {}

        for song in all_songs:
            if song.published_at.get("en") is None:
                continue

            song_name = song.name.get("en", "Unknown")
            song_name = self._strip_name(song_name)

            if song_name in stripped_songs:
                continue

            stripped_songs[song_name] = song.internal_song_id

        return stripped_songs

    def _extract_timestamp_from_filename(self, filename: str) -> Optional[int]:
        return extract_timestamp_from_filename(filename)

    def _allowed_live_types(self, timestamp: int) -> List[str]:
        event = self.event_service.search_events_by_date(timestamp)
        if event:
            return self.event_type_to_live_types.get(
                event.event_type, ["free live", "multi live"]
            )
        return ["free live", "multi live"]

    def _strip_name(self, name: str) -> str:
        name = "".join(
            c if (c.isalnum() and c.isascii()) or c.isspace() else "" for c in name
        ).lower().strip()
        return "".join(name.split())

    def _known_name_sanitize(self, name: str) -> str:
        for old, new in getattr(self, "name_fixes", {}).items():
            if old in name:
                name = name.replace(old, new)
        return name

    def _find_song_by_name(self, name: str):
        if name in self.stripped_songs:
            sid = self.stripped_songs[name]
            return self.song_service.get_song_by_internal_id(sid)
        return None

    def _find_similar_song(
        self, target: str, names: List[str], threshold: Optional[float] = None
    ) -> Tuple[Optional[str], float]:
        threshold = threshold if threshold is not None else self.fuzzy_threshold
        best, best_ratio = None, 0.0
        for n in names:
            r = SequenceMatcher(None, target, n).ratio()
            if r >= threshold and r > best_ratio:
                best_ratio, best = r, n
        return best, best_ratio

    def _find_best_song_candidate(
        self,
        target: str,
        songs: List[Any],
        threshold: Optional[float] = None,
    ) -> Tuple[Optional[Any], float]:
        threshold = threshold if threshold is not None else self.fuzzy_threshold
        best_song = None
        best_ratio = 0.0
        for song in songs:
            candidate_name = self._strip_name(song.name.get("en", ""))
            ratio = SequenceMatcher(None, target, candidate_name).ratio()
            if ratio >= threshold and ratio > best_ratio:
                best_song = song
                best_ratio = ratio
        return best_song, best_ratio

    def _resolve_song(self, song_name: str, difficulty: str, total_notes: int):
        reasons: List[str] = []
        song = None
        confidence = 0.0

        if song_name == "silvouspresident":
            if (
                difficulty == "expert"
                and total_notes == 695
                or difficulty == "hard"
                and total_notes == 540
                or difficulty == "normal"
                and total_notes == 293
                or difficulty == "easy"
                and total_notes == 123
            ):
                song = self.song_service.get_song_by_internal_id(462)
                reasons.append("resolved_silvouspresident_variant_462")
                confidence = 0.95

            elif (
                difficulty == "expert"
                and total_notes == 898
                or difficulty == "hard"
                and total_notes == 549
                or difficulty == "normal"
                and total_notes == 273
                or difficulty == "easy"
                and total_notes == 143
            ):
                song = self.song_service.get_song_by_internal_id(389)
                reasons.append("resolved_silvouspresident_variant_389")
                confidence = 0.95
        else:
            song = self._find_song_by_name(song_name)
            if song:
                reasons.append("resolved_exact_name")
                confidence = 1.0

        if song:
            return song, None, reasons, confidence

        # NOTE: candidate search must be by note count + difficulty, not difficulty level.
        possibles = self.song_service.get_songs_by_note_count(total_notes, difficulty)
        if not possibles:
            logger.warning(
                f"Song not found: {song_name} ({difficulty}, {total_notes} notes)"
            )
            return None, "not_found_errors", reasons, 0.0

        fuzzy_song, fuzzy_ratio = self._find_best_song_candidate(song_name, possibles)
        if fuzzy_song is not None:
            reasons.append("resolved_fuzzy_name")
            return fuzzy_song, None, reasons, fuzzy_ratio

        logger.warning(
            f"Could not find similar song for {song_name} ({difficulty}, {total_notes} notes)"
        )
        return None, "not_found_errors", reasons, 0.0

    def _derive_success_severity(self, reasons: List[str]) -> str:
        if "accepted_known_note_exception" in reasons or "resolved_fuzzy_name" in reasons:
            return "warning"
        return "info"

    def _check_note_count(self, song, song_name: str, difficulty: str, total_notes: int):
        if not song:
            return None, []

        reasons: List[str] = []
        expected_raw = song.note_counts.get(difficulty) if song.note_counts else None
        expected = None
        if isinstance(expected_raw, list):
            if expected_raw:
                expected = expected_raw[0]
        elif isinstance(expected_raw, int):
            expected = expected_raw

        if expected and total_notes != expected:
            if not (
                song_name == "romeo"
                and difficulty == "hard"
                and total_notes == 474
                or song_name == "tokimekiexperience"
                and total_notes == 33
            ):
                logger.warning(
                    f"Note count mismatch for {song_name} ({difficulty}): expected {expected}, got {total_notes}"
                )
                return "note_errors", reasons
            reasons.append("accepted_known_note_exception")
        return None, reasons

    def _check_fast_slow(
        self, song_name: str, fast: int, slow: int, great: int, good: int, bad: int, total_notes: int
    ):
        if fast != -1 and slow != -1 and fast + slow != great + good + bad:
            logger.warning(
                f"Fast/Slow mismatch for {song_name}: fast={fast}, slow={slow}, total_notes={total_notes}"
            )
            return "fast_slow_errors"
        return None

    def _check_combo(self, song_name: str, good: int, bad: int, miss: int, max_combo: int, total_notes: int):
        if good + bad + miss == 0 and max_combo != total_notes:
            logger.warning(
                f"Max combo mismatch for {song_name}: expected {total_notes}, got {max_combo}"
            )
            return "max_combo_errors"
        return None

    def _check_live_type(self, song_name: str, timestamp: Optional[int], live_type: str):
        if not timestamp:
            return None, []

        allowed_types = self._allowed_live_types(timestamp)
        if live_type not in allowed_types:
            logger.warning(
                f"Live type mismatch for {song_name}: expected one of {allowed_types}, got {live_type}"
            )
            return "live_errors", [f"allowed_live_types={allowed_types}"]
        return None, []

    def validate(self, filename: str, scan_data: Dict[str, Any]) -> ValidationResult:
        """Validate scan data and return a structured result."""
        reasons: List[str] = []
        try:
            song_name = self._strip_name(scan_data.get("song_name_from_top_bar_text", ""))
            song_name = self._known_name_sanitize(song_name)
            difficulty = scan_data.get("difficulty", "").lower()
            perfect = scan_data.get("perfect", 0)
            great = scan_data.get("great", 0)
            good = scan_data.get("good", 0)
            bad = scan_data.get("bad", 0)
            miss = scan_data.get("miss", 0)
            total_notes = perfect + great + good + bad + miss
            max_combo = scan_data.get("max_combo", 0)
            fast = scan_data.get("fast", -1)
            slow = scan_data.get("slow", -1)
            live_type = scan_data.get("live_type", "").lower()
            timestamp = self._extract_timestamp_from_filename(filename)

            normalized = {
                "song_name": song_name,
                "difficulty": difficulty,
                "total_notes": total_notes,
                "live_type": live_type,
            }

            song, error_type, resolve_reasons, confidence = self._resolve_song(
                song_name, difficulty, total_notes
            )
            reasons.extend(resolve_reasons)
            if error_type:
                return ValidationResult(
                    is_valid=False,
                    error_type=error_type,
                    resolved_song_id=None,
                    normalized=normalized,
                    reasons=reasons,
                    severity="error",
                    confidence=0.0,
                )

            error_type, note_reasons = self._check_note_count(
                song, song_name, difficulty, total_notes
            )
            reasons.extend(note_reasons)
            if error_type:
                return ValidationResult(
                    is_valid=False,
                    error_type=error_type,
                    resolved_song_id=song.internal_song_id if song else None,
                    normalized=normalized,
                    reasons=reasons,
                    severity="error",
                    confidence=confidence,
                )

            error_type = self._check_fast_slow(
                song_name, fast, slow, great, good, bad, total_notes
            )
            if error_type:
                return ValidationResult(
                    is_valid=False,
                    error_type=error_type,
                    resolved_song_id=song.internal_song_id if song else None,
                    normalized=normalized,
                    reasons=reasons,
                    severity="error",
                    confidence=confidence,
                )

            error_type = self._check_combo(
                song_name, good, bad, miss, max_combo, total_notes
            )
            if error_type:
                return ValidationResult(
                    is_valid=False,
                    error_type=error_type,
                    resolved_song_id=song.internal_song_id if song else None,
                    normalized=normalized,
                    reasons=reasons,
                    severity="error",
                    confidence=confidence,
                )

            error_type, live_reasons = self._check_live_type(song_name, timestamp, live_type)
            reasons.extend(live_reasons)
            if error_type:
                return ValidationResult(
                    is_valid=False,
                    error_type=error_type,
                    resolved_song_id=song.internal_song_id if song else None,
                    normalized=normalized,
                    reasons=reasons,
                    severity="error",
                    confidence=confidence,
                )

            return ValidationResult(
                is_valid=True,
                error_type=None,
                resolved_song_id=song.internal_song_id if song else None,
                normalized=normalized,
                reasons=reasons,
                severity=self._derive_success_severity(reasons),
                confidence=confidence,
            )

        except Exception as e:
            logger.error(f"Validation error for {filename}: {e}")
            return ValidationResult(
                is_valid=False,
                error_type="validation_errors",
                resolved_song_id=None,
                normalized={},
                reasons=[str(e)],
                severity="error",
                confidence=0.0,
            )

    def validate_error_type(self, filename: str, scan_data: Dict[str, Any]) -> Optional[str]:
        """Compatibility helper for legacy callers expecting `Optional[str]`."""
        return self.validate(filename, scan_data).error_type
