import re
import datetime
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional
from loguru import logger

from bangstats.config import config
from bangstats.services.song_service import SongService
from bangstats.services.event_service import EventService

class ValidationService:
    """Service for validating scan results with error categorization."""

    def __init__(self):
        self.event_type_to_live_types = config.get("EVENT_TYPE_TO_LIVE_TYPES")

        self.song_service = SongService()
        self.event_service = EventService()
    
        self.stripped_songs = self._get_stripped_songs(self.song_service.get_all_songs())

    def _get_stripped_songs(self, all_songs):
        """Get stripped songs from the database."""
        songs_from_db = all_songs
        stripped_songs = {}

        for song in songs_from_db:
            if song.published_at.get('en') is None:
                continue

            song_name = song.name.get('en', 'Unknown')

            # allow only ASCII alphanumeric characters and spaces
            song_name = self._strip_name(song_name)

            # check if there is already such key
            if song_name in stripped_songs:
                # print(f"Duplicate song name found: {song_name}, skipping.")
                continue

            stripped_songs[song_name] = song.internal_song_id
    
        return stripped_songs

    def _extract_timestamp_from_filename(self, filename: str) -> Optional[int]:
        match = re.search(r'Screenshot_(\d{8})[-_](\d{6})', filename)
        if not match:
            logger.warning(f"Could not extract timestamp from filename: {filename}")
            return None
        dt = datetime.datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
        return int(dt.timestamp() * 1000)

    def _validate_live_type(self, timestamp: int, live_type: str) -> bool:
        event = self.event_service.search_events_by_date(timestamp)

        if event:
            allowed_types = self.event_type_to_live_types.get(
                event.event_type,
                ["free live", "multi live"]
            )
        else:
            allowed_types = ["free live", "multi live"]

        return live_type in allowed_types

    def _strip_name(self, name: str) -> str:
        name = ''.join(c if (c.isalnum() and c.isascii()) or c.isspace() else '' for c in name).lower().strip()
        return ''.join(name.split())

    def _known_name_sanitize(self, name: str) -> str:
        issues = [("judgelight","level5judgelight"),("expert",""),("letitring","letssingletitring"),("root","riot")]
        for old, new in issues:
            if old in name:
                name = name.replace(old, new)
        return name

    def _find_song_by_name(self, name: str):
        if name in self.stripped_songs:
            sid = self.stripped_songs[name]

            return self.song_service.get_song_by_internal_id(sid)

        return None

    def _find_similar_song(self, target: str, names: List[str], threshold: float = 0.8) -> Optional[str]:
        best, best_ratio = None, 0
        for n in names:
            r = SequenceMatcher(None, target, n).ratio()
            if r >= threshold and r > best_ratio:
                best_ratio, best = r, n
        return best

    def validate(self, filename: str, scan_data: Dict[str, Any]) -> Optional[str]:
        """Return error type or None if valid."""
        try:
            # Extract and sanitize names/counts
            song_name = self._strip_name(scan_data.get("song_name_from_top_bar_text", ""))
            song_name = self._known_name_sanitize(song_name)
            difficulty = scan_data.get("difficulty", "").lower()
            perfect = scan_data.get("perfect", 0)
            great = scan_data.get("great", 0)
            good = scan_data.get("good", 0)
            bad = scan_data.get("bad", 0)
            miss = scan_data.get("miss", 0)
            total_notes = perfect + great + good + bad + miss
            max_combo   = scan_data.get("max_combo", 0)

            fast = scan_data.get("fast", -1)
            slow = scan_data.get("slow", -1)

            live_type = scan_data.get("live_type", "").lower()

            # Special case for "silvouspresident"
            # because they added two different versions of the song
            # with the same fucking name.
            # Maybe there is a better way to handle this
            # but for now this will do
            if song_name == "silvouspresident":
                if difficulty == "expert" and total_notes == 695 \
                or difficulty == "hard" and total_notes == 540 \
                or difficulty == "normal" and total_notes == 293\
                or difficulty == "easy" and total_notes == 123:
                    song = self.song_service.get_song_by_internal_id(462)
                
                elif difficulty == "expert" and total_notes == 898 \
                or difficulty == "hard" and total_notes == 549 \
                or difficulty == "normal" and total_notes == 273\
                or difficulty == "easy" and total_notes == 143:
                    song = self.song_service.get_song_by_internal_id(389)

            else:
                song = self._find_song_by_name(song_name)

            # 1. Note count checks
            if song:
                expected = song.note_counts.get(difficulty) if song.note_counts else None
                if expected and total_notes != expected:
                    if not (
                        song_name == "romeo" and difficulty == "hard" and total_notes == 474
                        or song_name == "tokimekiexperience" and total_notes == 33
                    ):
                        logger.warning(f"Note count mismatch for {song_name} ({difficulty}): expected {expected}, got {total_notes}")
                        return "note_errors"
            else:
                possibles = self.song_service.get_songs_by_difficulty(difficulty, total_notes)
                if not possibles:
                    logger.warning(f"Song not found: {song_name} ({difficulty}, {total_notes} notes)")

                    return "not_found_errors"

                names = [self._strip_name(s.name.get('en', '')) for s in possibles]

                if not self._find_similar_song(song_name, names):
                    logger.warning(f"Could not find similar song for {song_name} ({difficulty}, {total_notes} notes)")

                    return "not_found_errors"

            # 2. Fast/slow
            if fast != -1 and slow != -1 and fast + slow != great + good + bad:
                logger.warning(f"Fast/Slow mismatch for {song_name}: fast={fast}, slow={slow}, total_notes={total_notes}")

                return "fast_slow_errors"

            # 3. Combo
            if good + bad + miss == 0 and max_combo != total_notes:
                logger.warning(f"Max combo mismatch for {song_name}: expected {total_notes}, got {max_combo}")

                return "max_combo_errors"

            # 4. Live type validation
            timestamp = self._extract_timestamp_from_filename(filename)

            if timestamp:
                event = self.event_service.search_events_by_date(timestamp)

                if event:
                    allowed_types = self.event_type_to_live_types.get(
                        event.event_type,
                        ["free live", "multi live"]
                    )
                else:
                    allowed_types = ["free live", "multi live"]

                if not self._validate_live_type(timestamp, live_type):
                    logger.warning(
                        f"Live type mismatch for {song_name}: "
                        f"expected one of {allowed_types}, got {live_type}"
                    )
                    return "live_errors"

            return None

        except Exception as e:
            logger.error(f"Validation error for {filename}: {e}")
            return "validation_errors"