from typing import List, Optional
from sqlmodel import select
from bangstats_server.core.db.models.song import Song
from bangstats_server.core.db.repositories.base import BaseRepository


class SongRepository(BaseRepository[Song]):
    model = Song

    def get_by_internal_id(self, internal_song_id: int) -> Optional[Song]:
        """Retrieve a song by its internal_song_id."""
        if not isinstance(internal_song_id, int) or internal_song_id <= 0:
            return None

        statement = select(Song).where(Song.internal_song_id == internal_song_id)
        return self._session.exec(statement).first()

    def get_by_tag(self, tag: str) -> List[Song]:
        """Retrieve songs by tag."""
        if not tag or not isinstance(tag, str):
            return []

        statement = select(Song).where(Song.tag == tag)
        return self._session.exec(statement).all()

    def update(self, song_id: int, song_data: dict) -> tuple[Optional[Song], Optional[str]]:
        """
        Update an existing song record.
        Always returns (song, None) or (None, error_message)
        """
        song = self.get_by_id(song_id)
        if not song:
            return None, f"Song with ID {song_id} not found"

        # If updating internal_song_id, check it doesn't conflict
        if "internal_song_id" in song_data and song_data["internal_song_id"] != song.internal_song_id:
            existing = self.get_by_internal_id(song_data["internal_song_id"])
            if existing and existing.id != song_id:
                return None, f"Song with internal_song_id {song_data['internal_song_id']} already exists"

        return super().update(song_id, song_data, f"Song with ID {song_id} not found")

    def delete(self, song_id: int) -> tuple[bool, Optional[str]]:
        """
        Delete a song by its ID.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        return super().delete(song_id, f"Song with ID {song_id} not found")

    def search_by_name(self, name_query: str, language: str = "en") -> List[Song]:
        """Search for songs by name (partial match in specified language)."""
        if not name_query or not isinstance(name_query, str):
            return []

        try:
            statement = select(Song).where(Song.name[language].contains(name_query))
            return self._session.exec(statement).all()
        except Exception:
            return []

    def get_by_band_id(self, band_id: int) -> List[Song]:
        """Get all songs for a specific band."""
        if not isinstance(band_id, int) or band_id <= 0:
            return []

        statement = select(Song).where(Song.band_id == band_id)
        return self._session.exec(statement).all()

    def get_by_note_count(self, note_count: int) -> List[Song]:
        """Get songs by note count (matches any difficulty with the given note count)."""
        if not isinstance(note_count, int) or note_count < 0:
            return []

        try:
            statement = select(Song).where(
                (Song.note_counts["easy"].as_integer() == note_count) |
                (Song.note_counts["normal"].as_integer() == note_count) |
                (Song.note_counts["hard"].as_integer() == note_count) |
                (Song.note_counts["expert"].as_integer() == note_count) |
                (Song.note_counts["special"].as_integer() == note_count)
            )
            return self._session.exec(statement).all()
        except Exception:
            return []

    def get_by_note_count_difficulty(self, note_count: int, difficulty: str) -> List[Song]:
        """Get songs by note count for a specific difficulty."""
        if not isinstance(note_count, int) or note_count < 0 or not difficulty:
            return []

        try:
            statement = select(Song).where(Song.note_counts[difficulty].as_integer() == note_count)
            return self._session.exec(statement).all()
        except Exception:
            return []

    def list_since_id(self, since_id: int, limit: int = 5000) -> List[Song]:
        if not isinstance(since_id, int) or since_id < 0:
            return []
        statement = (
            select(Song)
            .where(Song.id > since_id)
            .order_by(Song.id)
            .limit(limit)
        )
        return self._session.exec(statement).all()
