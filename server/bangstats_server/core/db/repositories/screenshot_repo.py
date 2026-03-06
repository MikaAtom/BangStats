from typing import List, Optional, Dict, Any, Tuple
from sqlmodel import select
from datetime import datetime
from bangstats_server.core.db.models.screenshot import Screenshot
from bangstats_server.core.db import get_session


class ScreenshotRepository:
    def __init__(self):
        self._session_gen = get_session()
        self._session = next(self._session_gen)

    def close(self):
        self._session_gen.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_by_id(self, screenshot_id: int) -> Optional[Screenshot]:
        """Retrieve a screenshot by its primary key ID."""
        if not isinstance(screenshot_id, int) or screenshot_id <= 0:
            return None

        return self._session.get(Screenshot, screenshot_id)

    def get_all(self) -> List[Screenshot]:
        """Retrieve all screenshots from the database."""
        statement = select(Screenshot)
        return self._session.exec(statement).all()

    def get_by_user_id(self, user_id: int) -> List[Screenshot]:
        """Retrieve all screenshots for a specific user."""
        if not isinstance(user_id, int) or user_id <= 0:
            return []

        statement = select(Screenshot).where(Screenshot.user_id == user_id)
        return self._session.exec(statement).all()

    def get_by_song_id(self, user_id: int, song_id: int, difficulty: str) -> List[Screenshot]:
        """Retrieve all screenshots for a specific user, song, and difficulty."""
        if not isinstance(user_id, int) or user_id <= 0:
            return []
        if not isinstance(song_id, int) or song_id <= 0:
            return []
        if not difficulty or not isinstance(difficulty, str):
            return []

        statement = select(Screenshot).where(
            Screenshot.user_id == user_id,
            Screenshot.song_id == song_id,
            Screenshot.difficulty == difficulty
        )
        return self._session.exec(statement).all()

    def get_by_user_and_filename(self, user_id: int, filename: str) -> Optional[Screenshot]:
        """Retrieve a screenshot by user and filename."""
        if not isinstance(user_id, int) or user_id <= 0:
            return None
        if not filename or not isinstance(filename, str):
            return None

        statement = select(Screenshot).where(
            Screenshot.user_id == user_id,
            Screenshot.filename == filename,
        )
        return self._session.exec(statement).first()

    def create(self, screenshot_data: Dict[str, Any]) -> Tuple[Optional[Screenshot], Optional[str]]:
        """
        Create a new screenshot record.
        Always returns (screenshot, None) or (None, error_message)
        """
        try:
            existing = self.get_by_user_and_filename(
                screenshot_data.get("user_id", 0), screenshot_data.get("filename", "")
            )
            if existing is not None:
                return None, "duplicate"

            screenshot = Screenshot(**screenshot_data)
            self._session.add(screenshot)
            self._session.commit()
            self._session.refresh(screenshot)
            return screenshot, None
        except Exception as e:
            return None, f"Database error: {e}"

    def update(self, screenshot_id: int, screenshot_data: Dict[str, Any]) -> Tuple[Optional[Screenshot], Optional[str]]:
        """
        Update an existing screenshot record.
        Always returns (screenshot, None) or (None, error_message)
        """
        screenshot = self._session.get(Screenshot, screenshot_id)
        if not screenshot:
            return None, f"Screenshot with ID {screenshot_id} not found"

        try:
            for key, value in screenshot_data.items():
                setattr(screenshot, key, value)

            self._session.add(screenshot)
            self._session.commit()
            self._session.refresh(screenshot)
            return screenshot, None
        except Exception as e:
            self._session.rollback()
            return None, f"Database error: {e}"

    def delete(self, screenshot_id: int) -> Tuple[bool, Optional[str]]:
        """
        Delete a screenshot by its ID.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        screenshot = self._session.get(Screenshot, screenshot_id)
        if not screenshot:
            return False, f"Screenshot with ID {screenshot_id} not found"

        try:
            self._session.delete(screenshot)
            self._session.commit()
            return True, None
        except Exception as e:
            self._session.rollback()
            return False, f"Database error: {e}"

    def get_by_difficulty(self, user_id: int, difficulty: str) -> List[Screenshot]:
        """Retrieve all screenshots for a specific user and difficulty."""
        if not isinstance(user_id, int) or user_id <= 0:
            return []
        if not difficulty or not isinstance(difficulty, str):
            return []

        statement = select(Screenshot).where(
            Screenshot.user_id == user_id,
            Screenshot.difficulty == difficulty
        )
        return self._session.exec(statement).all()

    def get_full_combos(self, user_id: int, difficulty: str) -> List[Screenshot]:
        """Get all full combo screenshots for a user and difficulty."""
        if not isinstance(user_id, int) or user_id <= 0:
            return []
        if not difficulty or not isinstance(difficulty, str):
            return []

        statement = select(Screenshot).where(
            Screenshot.user_id == user_id,
            Screenshot.difficulty == difficulty,
            Screenshot.full_combo == True
        )
        return self._session.exec(statement).all()

    def get_all_perfects(self, user_id: int, difficulty: str) -> List[Screenshot]:
        """Get all all perfect screenshots for a user and difficulty."""
        if not isinstance(user_id, int) or user_id <= 0:
            return []
        if not difficulty or not isinstance(difficulty, str):
            return []

        statement = select(Screenshot).where(
            Screenshot.user_id == user_id,
            Screenshot.difficulty == difficulty,
            Screenshot.all_perfect == True
        )
        return self._session.exec(statement).all()

    def get_high_scores_by_user(self, user_id: int, difficulty: str) -> List[Screenshot]:
        """Get all screenshots that are new records for a user and difficulty."""
        if not isinstance(user_id, int) or user_id <= 0:
            return []
        if not difficulty or not isinstance(difficulty, str):
            return []

        statement = select(Screenshot).where(
            Screenshot.user_id == user_id,
            Screenshot.difficulty == difficulty,
            Screenshot.is_new_record == True
        )
        return self._session.exec(statement).all()

    def get_anomalies(self, user_id: int, difficulty: str) -> List[Screenshot]:
        """Get all anomaly screenshots for a user and difficulty."""
        if not isinstance(user_id, int) or user_id <= 0:
            return []
        if not difficulty or not isinstance(difficulty, str):
            return []

        statement = select(Screenshot).where(
            Screenshot.user_id == user_id,
            Screenshot.difficulty == difficulty,
            Screenshot.anomaly == True
        )
        return self._session.exec(statement).all()

    def get_by_timestamp(self, user_id: int, timestamp: datetime, difficulty: str) -> Optional[Screenshot]:
        """Get screenshot by user, timestamp, and difficulty."""
        if not isinstance(user_id, int) or user_id <= 0:
            return None
        if not isinstance(timestamp, datetime):
            return None
        if not difficulty or not isinstance(difficulty, str):
            return None

        statement = select(Screenshot).where(
            Screenshot.user_id == user_id,
            Screenshot.timestamp == timestamp,
            Screenshot.difficulty == difficulty
        )
        return self._session.exec(statement).first()

    def get_by_timestamp_interval(self, user_id: int, start_time: datetime, end_time: datetime, difficulty: str) -> List[Screenshot]:
        """Get screenshots by user, timestamp interval, and difficulty."""
        if not isinstance(user_id, int) or user_id <= 0:
            return []
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            return []
        if start_time >= end_time:
            return []
        if not difficulty or not isinstance(difficulty, str):
            return []

        statement = select(Screenshot).where(
            Screenshot.user_id == user_id,
            Screenshot.timestamp >= start_time,
            Screenshot.timestamp <= end_time,
            Screenshot.difficulty == difficulty
        )
        return self._session.exec(statement).all()
