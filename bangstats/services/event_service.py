from typing import List, Optional, Dict, Any, Union
from bangstats.database.repositories.event_repository import EventRepository
from bangstats.database.models.event import Event
from loguru import logger

from datetime import datetime

class EventService:
    """Service layer for event operations with business logic and validation."""

    def __init__(self):
        self._repo = EventRepository()
        logger.debug("EventService initialized with EventRepository")

    def get_event_by_id(self, event_id: int) -> Optional[Event]:
        if not isinstance(event_id, int) or event_id <= 0:
            logger.warning(f"Invalid event_id provided: {event_id}")
            return None

        logger.debug(f"Fetching event by id: {event_id}")
        return self._repo.get_by_id(event_id)

    def get_event_by_event_id(self, event_id: int) -> Optional[Event]:
        if not isinstance(event_id, int) or event_id <= 0:
            logger.warning(f"Invalid event_id provided for get_event_by_event_id: {event_id}")
            return None

        logger.debug(f"Fetching event by event_id: {event_id}")
        return self._repo.get_by_event_id(event_id)

    def get_all_events(self) -> List[Event]:
        logger.debug("Fetching all events from database")
        return self._repo.get_all()

    def create_event(self, event_data: Dict[str, Any]) -> Event:
        """
        Create a new event with validation.
        Raises:
            ValueError on validation or if already exists.
        """
        logger.debug(f"Attempting to create event with data: {event_data}")
        required = ["event_id", "event_type", "event_name", "event_start_at", "event_end_at"]
    
        for field in required:
            if field not in event_data:
                raise ValueError(f"Missing required field: {field}")
        if not isinstance(event_data["event_id"], int) or event_data["event_id"] <= 0:
            raise ValueError("event_id must be a positive integer")

        if not isinstance(event_data["event_name"], dict):
            raise ValueError("event_name must be a dictionary")

        if not isinstance(event_data["event_start_at"], dict) or not isinstance(event_data["event_end_at"], dict):
            raise ValueError("event_start_at/end_at must be dictionaries")

        result, err = self._repo.create(event_data)
        if err:
            raise ValueError(err)

        logger.debug(f"Event created successfully: {result}")
        return result

    def update_event(self, event_id: int, event_data: Dict[str, Any]) -> Event:
        """
        Update an event with validation.
        Raises:
            ValueError on invalid ID, validation error, or repository error.
        """
        logger.debug(f"Attempting to update event {event_id} with data: {event_data}")

        if not isinstance(event_id, int) or event_id <= 0:
            raise ValueError("Invalid event ID")

        if "event_id" in event_data:
            if not isinstance(event_data["event_id"], int) or event_data["event_id"] <= 0:
                raise ValueError("event_id must be a positive integer")

        if "event_name" in event_data and not isinstance(event_data["event_name"], dict):
            raise ValueError("event_name must be a dictionary")

        if "event_start_at" in event_data and not isinstance(event_data["event_start_at"], dict):
            raise ValueError("event_start_at must be a dictionary")

        if "event_end_at" in event_data and not isinstance(event_data["event_end_at"], dict):
            raise ValueError("event_end_at must be a dictionary")

        result, err = self._repo.update(event_id, event_data)
        if err:
            raise ValueError(err)

        logger.debug(f"Event {event_id} updated successfully")
        return result

    def delete_event(self, event_id: int) -> bool:
        """
        Delete an event with validation.
        Raises:
            ValueError on invalid ID or if delete failed.
        """
        logger.debug(f"Attempting to delete event {event_id}")
        if not isinstance(event_id, int) or event_id <= 0:
            raise ValueError("Invalid event ID")

        success, err = self._repo.delete(event_id)
        if not success:
            raise ValueError(err)

        logger.debug(f"Event {event_id} deleted successfully")
        return True

    def search_events_by_name(self, name_query: str, language: str = "en") -> List[Event]:
        if not name_query or not isinstance(name_query, str):
            logger.warning("Invalid name_query for search_events_by_name")
            return []

        if not isinstance(language, str):
            logger.warning("Invalid language for search_events_by_name, defaulting to 'en'")
            language = "en"

        logger.debug(f"Searching events by name '{name_query.strip()}' in language '{language}'")
        return self._repo.search_by_name(name_query.strip(), language)

    def search_events_by_date(self, timestamp: Union[int, str], language: str = "en") -> Optional[Event]:
        if isinstance(timestamp, str):
            try:
                int(timestamp)
            except ValueError:
                logger.warning(f"Invalid timestamp string for search_events_by_date: {timestamp}")
                return None

        elif not isinstance(timestamp, int):
            logger.warning(f"Invalid timestamp type for search_events_by_date: {timestamp}")
            return None

        if not isinstance(language, str):
            logger.warning("Invalid language for search_events_by_date, defaulting to 'en'")
            language = "en"

        logger.debug(f"Searching event by date '{timestamp}' in language '{language}'")
        return self._repo.search_by_date(timestamp, language)

    def get_current_event(self, language: str = "en") -> Optional[Event]:
        """
        Get the current event based on the current date.
        Returns:
            Event if found, None otherwise.
        """
        if not isinstance(language, str):
            logger.warning("Invalid language for get_current_event, defaulting to 'en'")
            language = "en"

        current_time = int(datetime.now().timestamp() * 1000)  # Convert to milliseconds
        logger.debug(f"Fetching current event at timestamp {current_time} in language '{language}'")
        event = self._repo.search_by_date(current_time, language)

        if not event:
            logger.info("No current event found")
            return None

        logger.debug(f"Current event found: {event}")
        return event