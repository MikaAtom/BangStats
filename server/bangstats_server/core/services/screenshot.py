from typing import Any, Callable, Dict, List, Optional, TypeVar
from bangstats_server.core.db.repositories.screenshot_repo import ScreenshotRepository
from bangstats_server.core.db.models.screenshot import Screenshot
from bangstats_server.core.services.song import SongService
from loguru import logger
from datetime import datetime

T = TypeVar("T")


class ScreenshotService:
    """Service layer for screenshot operations with business logic and validation."""

    def __init__(self):
        self._repo = ScreenshotRepository()
        self._song_service = SongService()
        logger.debug(
            "ScreenshotService initialized with ScreenshotRepository and SongService"
        )

    def _get_available_difficulties(self, song_id: Optional[int] = None) -> List[str]:
        """Get available difficulties, optionally filtered by song."""
        base_difficulties = ["easy", "normal", "hard", "expert"]

        if song_id:
            song = self._song_service.get_song_by_internal_id(song_id)
            if song and song.special and song.special.get("available", False):
                return base_difficulties + ["special"]

        return base_difficulties

    def _validate_user_id(self, user_id: int) -> bool:
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id provided: {user_id}")
            return False
        return True

    def _validate_difficulty(self, difficulty: Optional[str]) -> bool:
        if difficulty is not None and not isinstance(difficulty, str):
            logger.warning(f"Invalid difficulty provided: {difficulty}")
            return False
        return True

    def _collect_across_difficulties(
        self,
        user_id: int,
        difficulty: Optional[str],
        query_fn: Callable[[int, str], List[T]],
        action_label: str,
        song_id: Optional[int] = None,
    ) -> List[T]:
        if not self._validate_user_id(user_id) or not self._validate_difficulty(difficulty):
            return []

        if difficulty:
            logger.debug(f"Fetching {action_label} for user {user_id} with difficulty {difficulty}")
            return query_fn(user_id, difficulty)

        difficulties = self._get_available_difficulties(song_id)
        logger.debug(
            f"Fetching {action_label} for user {user_id} across difficulties: {difficulties}"
        )
        all_results: List[T] = []
        for diff in difficulties:
            all_results.extend(query_fn(user_id, diff))
        logger.debug(f"Found {len(all_results)} {action_label} across available difficulties")
        return all_results

    def get_screenshot_by_id(self, screenshot_id: int) -> Optional[Screenshot]:
        if not isinstance(screenshot_id, int) or screenshot_id <= 0:
            logger.warning(f"Invalid screenshot_id provided: {screenshot_id}")
            return None

        logger.debug(f"Fetching screenshot by id: {screenshot_id}")
        return self._repo.get_by_id(screenshot_id)

    def get_all_screenshots(self) -> List[Screenshot]:
        logger.debug("Fetching all screenshots from database")
        return self._repo.get_all()

    def get_screenshots_by_user(self, user_id: int) -> List[Screenshot]:
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id provided: {user_id}")
            return []

        logger.debug(f"Fetching screenshots for user: {user_id}")
        return self._repo.get_by_user_id(user_id)

    def get_screenshots_by_song(
        self, user_id: int, song_id: int, difficulty: Optional[str] = None
    ) -> List[Screenshot]:
        if not self._validate_user_id(user_id):
            return []
        if not isinstance(song_id, int) or song_id <= 0:
            logger.warning(f"Invalid song_id provided: {song_id}")
            return []
        return self._collect_across_difficulties(
            user_id=user_id,
            difficulty=difficulty,
            query_fn=lambda uid, diff: self._repo.get_by_song_id(uid, song_id, diff),
            action_label=f"screenshots for song {song_id}",
            song_id=song_id,
        )

    def get_existing_filenames_for_user(
        self,
        user_id: int,
        filenames: List[str],
    ) -> List[str]:
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id provided: {user_id}")
            return []
        if not filenames:
            return []
        return self._repo.get_existing_filenames_for_user(user_id, filenames)

    def create_screenshot(self, screenshot_data: Dict[str, Any]) -> Optional[Screenshot]:
        """
        Create a new screenshot with validation.
        Raises:
            ValueError on validation or repository error.
        """
        logger.debug(f"Attempting to create screenshot with data: {screenshot_data}")

        required = [
            "user_id",
            "score",
            "live_type",
            "perfect",
            "great",
            "good",
            "bad",
            "miss",
            "max_combo",
            "song_id",
            "difficulty",
        ]

        for field in required:
            if field not in screenshot_data:
                raise ValueError(f"Missing required field: {field}")

        if not isinstance(screenshot_data["user_id"], int) or screenshot_data["user_id"] <= 0:
            raise ValueError("user_id must be a positive integer")

        if not isinstance(screenshot_data["song_id"], int) or screenshot_data["song_id"] <= 0:
            raise ValueError("song_id must be a positive integer")

        if not isinstance(screenshot_data["score"], int) or screenshot_data["score"] < 0:
            raise ValueError("score must be a non-negative integer")

        if not isinstance(screenshot_data["live_type"], str) or not screenshot_data["live_type"]:
            raise ValueError("live_type must be a non-empty string")

        if not isinstance(screenshot_data["difficulty"], str) or not screenshot_data["difficulty"]:
            raise ValueError("difficulty must be a non-empty string")

        # Validate note counts
        note_fields = ["perfect", "great", "good", "bad", "miss", "max_combo"]
        for field in note_fields:
            if field in screenshot_data and (
                not isinstance(screenshot_data[field], int) or screenshot_data[field] < 0
            ):
                raise ValueError(f"{field} must be a non-negative integer")

        # Validate boolean fields
        boolean_fields = ["full_combo", "all_perfect", "is_new_record", "anomaly"]
        for field in boolean_fields:
            if field in screenshot_data and not isinstance(screenshot_data[field], bool):
                raise ValueError(f"{field} must be a boolean")

        result, err = self._repo.create(screenshot_data)
        if err == "duplicate":
            logger.info(
                "Duplicate screenshot skipped for user_id={} filename={}",
                screenshot_data.get("user_id"),
                screenshot_data.get("filename"),
            )
            return None
        if err:
            raise ValueError(err)

        logger.debug(f"Screenshot created successfully: {result}")
        return result

    def update_screenshot(self, screenshot_id: int, screenshot_data: Dict[str, Any]) -> Screenshot:
        """
        Update a screenshot with validation.
        Raises:
            ValueError on invalid ID, validation error, or repository error.
        """
        logger.debug(
            f"Attempting to update screenshot {screenshot_id} with data: {screenshot_data}"
        )

        if not isinstance(screenshot_id, int) or screenshot_id <= 0:
            raise ValueError("Invalid screenshot ID")

        if "user_id" in screenshot_data:
            if not isinstance(screenshot_data["user_id"], int) or screenshot_data["user_id"] <= 0:
                raise ValueError("user_id must be a positive integer")

        if "song_id" in screenshot_data:
            if not isinstance(screenshot_data["song_id"], int) or screenshot_data["song_id"] <= 0:
                raise ValueError("song_id must be a positive integer")

        if "score" in screenshot_data:
            if not isinstance(screenshot_data["score"], int) or screenshot_data["score"] < 0:
                raise ValueError("score must be a non-negative integer")

        if "live_type" in screenshot_data:
            if not isinstance(screenshot_data["live_type"], str) or not screenshot_data["live_type"]:
                raise ValueError("live_type must be a non-empty string")

        if "difficulty" in screenshot_data:
            if not isinstance(screenshot_data["difficulty"], str) or not screenshot_data["difficulty"]:
                raise ValueError("difficulty must be a non-empty string")

        # Validate note counts if present
        note_fields = ["perfect", "great", "good", "bad", "miss", "max_combo"]
        for field in note_fields:
            if field in screenshot_data and (
                not isinstance(screenshot_data[field], int) or screenshot_data[field] < 0
            ):
                raise ValueError(f"{field} must be a non-negative integer")

        # Validate boolean fields if present
        boolean_fields = ["full_combo", "all_perfect", "is_new_record", "anomaly"]
        for field in boolean_fields:
            if field in screenshot_data and not isinstance(screenshot_data[field], bool):
                raise ValueError(f"{field} must be a boolean")

        result, err = self._repo.update(screenshot_id, screenshot_data)
        if err:
            raise ValueError(err)

        logger.debug(f"Screenshot {screenshot_id} updated successfully")
        return result

    def delete_screenshot(self, screenshot_id: int) -> bool:
        """
        Delete a screenshot with validation.
        Raises:
            ValueError on invalid ID or if delete failed.
        """
        logger.debug(f"Attempting to delete screenshot {screenshot_id}")
        if not isinstance(screenshot_id, int) or screenshot_id <= 0:
            raise ValueError("Invalid screenshot ID")

        success, err = self._repo.delete(screenshot_id)
        if not success:
            raise ValueError(err)

        logger.debug(f"Screenshot {screenshot_id} deleted successfully")
        return True

    def delete_screenshots_by_filenames(self, user_id: int, filenames: List[str]) -> int:
        if not isinstance(user_id, int) or user_id <= 0:
            return 0
        if not filenames:
            return 0
        return self._repo.delete_by_user_and_filenames(user_id, filenames)

    def get_screenshots_by_difficulty(
        self, user_id: int, difficulty: Optional[str] = None
    ) -> List[Screenshot]:
        """Get all screenshots for a specific user and difficulty."""
        return self._collect_across_difficulties(
            user_id=user_id,
            difficulty=difficulty,
            query_fn=self._repo.get_by_difficulty,
            action_label="screenshots",
        )

    def get_full_combos_by_user(
        self, user_id: int, difficulty: Optional[str] = None
    ) -> List[Screenshot]:
        """Get all full combo screenshots for a user."""
        return self._collect_across_difficulties(
            user_id=user_id,
            difficulty=difficulty,
            query_fn=self._repo.get_full_combos,
            action_label="full combos",
        )

    def get_all_perfects_by_user(
        self, user_id: int, difficulty: Optional[str] = None
    ) -> List[Screenshot]:
        """Get all all perfect screenshots for a user."""
        return self._collect_across_difficulties(
            user_id=user_id,
            difficulty=difficulty,
            query_fn=self._repo.get_all_perfects,
            action_label="all perfects",
        )

    def get_high_scores_by_user(
        self, user_id: int, difficulty: Optional[str] = None
    ) -> List[Screenshot]:
        """Get all high score screenshots for a user."""
        return self._collect_across_difficulties(
            user_id=user_id,
            difficulty=difficulty,
            query_fn=self._repo.get_high_scores_by_user,
            action_label="high scores",
        )

    def get_anomalies_by_user(
        self, user_id: int, difficulty: Optional[str] = None
    ) -> List[Screenshot]:
        """Get all anomaly screenshots for a user."""
        return self._collect_across_difficulties(
            user_id=user_id,
            difficulty=difficulty,
            query_fn=self._repo.get_anomalies,
            action_label="anomalies",
        )

    def get_screenshot_by_timestamp(
        self, user_id: int, timestamp: datetime, difficulty: Optional[str] = None
    ) -> Optional[Screenshot]:
        """Get screenshot by user and timestamp. If difficulty not provided, searches all difficulties."""
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id provided: {user_id}")
            return None
        if not isinstance(timestamp, datetime):
            logger.warning(f"Invalid timestamp provided: {timestamp}")
            return None

        if difficulty:
            if not isinstance(difficulty, str):
                logger.warning(f"Invalid difficulty provided: {difficulty}")
                return None
            logger.debug(
                f"Fetching screenshot for user {user_id} at timestamp {timestamp} with difficulty {difficulty}"
            )
            return self._repo.get_by_timestamp(user_id, timestamp, difficulty)

        # Get all available difficulties
        difficulties = self._get_available_difficulties()
        logger.debug(
            f"Fetching screenshot for user {user_id} at timestamp {timestamp} across difficulties: {difficulties}"
        )

        for diff in difficulties:
            result = self._repo.get_by_timestamp(user_id, timestamp, diff)
            if result:
                logger.debug(f"Found screenshot with difficulty {diff}")
                return result

        logger.debug("No screenshot found for any difficulty")
        return None

    def get_screenshots_by_timestamp_interval(
        self,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
        difficulty: Optional[str] = None,
    ) -> List[Screenshot]:
        """Get screenshots by user and timestamp interval. If difficulty not provided, searches all difficulties."""
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id provided: {user_id}")
            return []
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            logger.warning(f"Invalid timestamps provided: {start_time}, {end_time}")
            return []
        if start_time >= end_time:
            logger.warning(
                "Invalid timestamp interval: start_time must be before end_time"
            )
            return []

        if difficulty:
            if not isinstance(difficulty, str):
                logger.warning(f"Invalid difficulty provided: {difficulty}")
                return []
            logger.debug(
                f"Fetching screenshots for user {user_id} between {start_time} and {end_time} with difficulty {difficulty}"
            )
            return self._repo.get_by_timestamp_interval(
                user_id, start_time, end_time, difficulty
            )

        # Get all available difficulties
        difficulties = self._get_available_difficulties()
        logger.debug(
            f"Fetching screenshots for user {user_id} between {start_time} and {end_time} across difficulties: {difficulties}"
        )

        all_results = []
        for diff in difficulties:
            results = self._repo.get_by_timestamp_interval(user_id, start_time, end_time, diff)
            all_results.extend(results)

        logger.debug(f"Found {len(all_results)} screenshots across available difficulties")
        return all_results
