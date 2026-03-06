from typing import List, Optional, Dict, Any, Tuple
from bangstats.database.repositories.song_repository import SongRepository
from bangstats.database.models.song import Song
from loguru import logger


class SongService:
    """Service layer for song operations with business logic and validation."""

    def __init__(self):
        self._repo = SongRepository()
        logger.debug("SongService initialized with SongRepository")

    def get_song_by_id(self, song_id: int) -> Optional[Song]:
        """Get a song by its ID with validation."""
        if not isinstance(song_id, int) or song_id <= 0:
            logger.warning(f"Invalid song_id provided: {song_id}")
            return None
        logger.debug(f"Fetching song by id: {song_id}")
        return self._repo.get_by_id(song_id)

    def get_song_by_internal_id(self, internal_song_id: int) -> Optional[Song]:
        """Get a song by its internal ID with validation."""
        if not isinstance(internal_song_id, int) or internal_song_id <= 0:
            logger.warning(f"Invalid internal_song_id provided: {internal_song_id}")
            return None
        logger.debug(f"Fetching song by internal id: {internal_song_id}")
        return self._repo.get_by_internal_id(internal_song_id)

    def get_all_songs(self) -> List[Song]:
        """Get all songs from the database."""
        logger.debug("Fetching all songs from database")
        return self._repo.get_all()

    def create_song(self, song_data: Dict[str, Any]) -> Song:
        """
        Create a new song with validation.
        Raises:
            ValueError on validation or if already exists.
        """
        logger.debug(f"Attempting to create song with data: {song_data}")
        required_fields = ["internal_song_id", "name", "band_id"]
        for field in required_fields:
            if field not in song_data:
                raise ValueError(f"Missing required field: {field}")

        if self.get_song_by_internal_id(song_data["internal_song_id"]):
            raise ValueError(
                f"Song with internal_song_id {song_data['internal_song_id']} already exists"
            )

        if (
            not isinstance(song_data["internal_song_id"], int)
            or song_data["internal_song_id"] <= 0
        ):
            raise ValueError("internal_song_id must be a positive integer")

        if not isinstance(song_data["name"], dict):
            raise ValueError("name must be a dictionary with language keys")

        if not isinstance(song_data["band_id"], int) or song_data["band_id"] <= 0:
            raise ValueError("band_id must be a positive integer")

        result, err = self._repo.create(song_data)
        if err:
            raise ValueError(err)
        logger.debug(f"Song created successfully: {result}")
        return result

    def update_song(self, song_id: int, song_data: Dict[str, Any]) -> Song:
        """
        Update a song with validation.
        Raises:
            ValueError on invalid ID, validation error, or repository error.
        """
        logger.debug(f"Attempting to update song {song_id} with data: {song_data}")
        if not isinstance(song_id, int) or song_id <= 0:
            raise ValueError("Invalid song ID")

        if "internal_song_id" in song_data:
            if (
                not isinstance(song_data["internal_song_id"], int)
                or song_data["internal_song_id"] <= 0
            ):
                raise ValueError("internal_song_id must be a positive integer")

        if "name" in song_data and not isinstance(song_data["name"], dict):
            raise ValueError("name must be a dictionary with language keys")

        if "band_id" in song_data:
            if not isinstance(song_data["band_id"], int) or song_data["band_id"] <= 0:
                raise ValueError("band_id must be a positive integer")

        result, err = self._repo.update(song_id, song_data)
        if err:
            raise ValueError(err)
        logger.debug(f"Song {song_id} updated successfully")
        return result

    def delete_song(self, song_id: int) -> bool:
        """
        Delete a song with validation.
        Raises:
            ValueError on invalid ID or if delete failed.
        """
        logger.debug(f"Attempting to delete song {song_id}")
        if not isinstance(song_id, int) or song_id <= 0:
            raise ValueError("Invalid song ID")

        success, err = self._repo.delete(song_id)
        if not success:
            raise ValueError(err)
        logger.debug(f"Song {song_id} deleted successfully")
        return True

    def search_songs_by_name(self, name_query: str, language: str = "en") -> List[Song]:
        """Search songs by name with validation."""
        if not name_query or not isinstance(name_query, str):
            logger.warning("Invalid name_query for search")
            return []

        if not language or not isinstance(language, str):
            logger.warning("Invalid language for search, defaulting to 'en'")
            language = "en"

        logger.debug(
            f"Searching songs by name '{name_query.strip()}' in language '{language}'"
        )
        return self._repo.search_by_name(name_query.strip(), language)

    def get_songs_by_band(self, band_id: int) -> List[Song]:
        """Get all songs for a specific band."""
        if not isinstance(band_id, int) or band_id <= 0:
            logger.warning(f"Invalid band_id for get_songs_by_band: {band_id}")
            return []
        logger.debug(f"Fetching songs for band_id: {band_id}")
        return self._repo.get_by_band_id(band_id)

    def get_songs_by_tag(self, tag: str) -> List[Song]:
        """Get songs by tag with validation."""
        if not tag or not isinstance(tag, str):
            logger.warning("Invalid tag for get_songs_by_tag")
            return []
        logger.debug(f"Fetching songs by tag: {tag.strip()}")
        return self._repo.get_by_tag(tag.strip())

    def get_songs_by_difficulty(self, difficulty: str, level: int) -> List[Song]:
        """Get songs by difficulty level with validation."""
        valid_difficulties = ["easy", "normal", "hard", "expert", "special"]
        if difficulty not in valid_difficulties:
            logger.warning(
                f"Invalid difficulty for get_songs_by_difficulty: {difficulty}"
            )
            return []

        if not isinstance(level, int) or level < 1 or level > 35:
            logger.warning(f"Invalid level for get_songs_by_difficulty: {level}")
            return []

        logger.debug(f"Fetching songs by difficulty '{difficulty}' and level {level}")
        return self._repo.get_by_difficulty(difficulty, level)

    def get_songs_by_note_count(
        self, note_count: int, difficulty: Optional[str] = None
    ) -> List[Song]:
        """Get songs by note count, optionally filtered by difficulty."""
        if not isinstance(note_count, int) or note_count < 0:
            logger.warning(f"Invalid note_count for get_songs_by_note_count: {note_count}")
            return []

        if difficulty:
            valid_difficulties = ["easy", "normal", "hard", "expert", "special"]
            if difficulty not in valid_difficulties:
                logger.warning(
                    f"Invalid difficulty for get_songs_by_note_count: {difficulty}"
                )
                return []
            logger.debug(
                f"Fetching songs by note_count {note_count} and difficulty '{difficulty}'"
            )
            return self._repo.get_by_note_count_difficulty(note_count, difficulty)

        logger.debug(f"Fetching songs by note_count {note_count}")
        return self._repo.get_by_note_count(note_count)

    def get_song_statistics(self) -> Dict[str, Any]:
        """Get general statistics about songs in the database."""
        logger.debug("Calculating song statistics")
        all_songs = self._repo.get_all()

        if not all_songs:
            logger.debug("No songs found in database for statistics")
            return {"total_songs": 0, "bands": {}, "difficulties": {}, "tags": {}}

        band_counts = {}
        difficulty_counts = {
            "easy": 0,
            "normal": 0,
            "hard": 0,
            "expert": 0,
            "special": 0,
        }
        tag_counts = {}

        for song in all_songs:
            # Count by band
            if song.band_id:
                band_counts[song.band_id] = band_counts.get(song.band_id, 0) + 1

            # Count by difficulty levels
            if song.levels:
                for difficulty in difficulty_counts:
                    if difficulty in song.levels and song.levels[difficulty]:
                        difficulty_counts[difficulty] += 1

            # Count by tags
            if song.tag:
                tag_counts[song.tag] = tag_counts.get(song.tag, 0) + 1

        logger.debug(f"Song statistics calculated: total_songs={len(all_songs)}")
        return {
            "total_songs": len(all_songs),
            "bands": band_counts,
            "difficulties": difficulty_counts,
            "tags": tag_counts,
        }

    def validate_song_data(
        self, song_data: Dict[str, Any], is_update: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate song data structure.

        Args:
            song_data: The song data to validate
            is_update: Whether this is for an update operation (less strict validation)

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        logger.debug(f"Validating song data: {song_data} (is_update={is_update})")
        if not isinstance(song_data, dict):
            logger.error("Song data must be a dictionary")
            return False, "Song data must be a dictionary"

        # Required fields for creation
        if not is_update:
            required_fields = ["internal_song_id", "name", "band_id"]
            for field in required_fields:
                if field not in song_data:
                    logger.error(f"Missing required field: {field}")
                    return False, f"Missing required field: {field}"

        # Validate specific fields if present
        if "internal_song_id" in song_data:
            if (
                not isinstance(song_data["internal_song_id"], int)
                or song_data["internal_song_id"] <= 0
            ):
                logger.error("internal_song_id must be a positive integer")
                return False, "internal_song_id must be a positive integer"

        if "name" in song_data:
            if not isinstance(song_data["name"], dict):
                logger.error("name must be a dictionary with language keys")
                return False, "name must be a dictionary with language keys"

        if "band_id" in song_data:
            if not isinstance(song_data["band_id"], int) or song_data["band_id"] <= 0:
                logger.error("band_id must be a positive integer")
                return False, "band_id must be a positive integer"

        if "levels" in song_data and song_data["levels"] is not None:
            if not isinstance(song_data["levels"], dict):
                logger.error("levels must be a dictionary")
                return False, "levels must be a dictionary"

        if "note_counts" in song_data and song_data["note_counts"] is not None:
            if not isinstance(song_data["note_counts"], dict):
                logger.error("note_counts must be a dictionary")
                return False, "note_counts must be a dictionary"

        logger.debug("Song data validation passed")
        return True, None
