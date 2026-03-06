from typing import List, Optional, Dict, Any, Tuple, Union
from sqlmodel import select
from bangstats_server.core.db.models.event import Event
from bangstats_server.core.db import get_session


class EventRepository:
    def __init__(self):
        self._session_gen = get_session()
        self._session = next(self._session_gen)

    def close(self):
        self._session_gen.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_by_id(self, event_id: int) -> Optional[Event]:
        """Retrieve an event by its primary key ID."""
        if not isinstance(event_id, int) or event_id <= 0:
            return None

        return self._session.get(Event, event_id)

    def get_by_event_id(self, event_id: int) -> Optional[Event]:
        """Retrieve an event by its event_id field."""
        if not isinstance(event_id, int) or event_id <= 0:
            return None

        statement = select(Event).where(Event.event_id == event_id)
        return self._session.exec(statement).first()

    def get_all(self) -> List[Event]:
        """Retrieve all events from the database."""
        statement = select(Event)
        return self._session.exec(statement).all()

    def create(self, event_data: Dict[str, Any]) -> Tuple[Optional[Event], Optional[str]]:
        """
        Create a new event record.
        Always returns (event, None) or (None, error_message)
        """
        existing = self.get_by_event_id(event_data["event_id"])
        if existing:
            return None, f"Event with event_id {event_data['event_id']} already exists"

        try:
            event = Event(**event_data)
            self._session.add(event)
            self._session.commit()
            self._session.refresh(event)
            return event, None
        except Exception as e:
            return None, f"Database error: {e}"

    def update(self, event_id: int, event_data: Dict[str, Any]) -> Tuple[Optional[Event], Optional[str]]:
        """
        Update an existing event record.
        Always returns (event, None) or (None, error_message)
        """
        event = self._session.get(Event, event_id)
        if not event:
            return None, f"Event with ID {event_id} not found"

        # If updating event_id, check it doesn't conflict
        if "event_id" in event_data and event_data["event_id"] != event.event_id:
            existing = self.get_by_event_id(event_data["event_id"])
            if existing and existing.id != event_id:
                return None, f"Event with event_id {event_data['event_id']} already exists"

        try:
            for key, value in event_data.items():
                setattr(event, key, value)

            self._session.add(event)
            self._session.commit()
            self._session.refresh(event)
            return event, None
        except Exception as e:
            self._session.rollback()
            return None, f"Database error: {e}"

    def delete(self, event_id: int) -> Tuple[bool, Optional[str]]:
        """
        Delete an event by its ID.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        event = self._session.get(Event, event_id)
        if not event:
            return False, f"Event with ID {event_id} not found"

        try:
            self._session.delete(event)
            self._session.commit()
            return True, None
        except Exception as e:
            self._session.rollback()
            return False, f"Database error: {e}"

    def search_by_name(self, name_query: str, language: str = "en") -> List[Event]:
        """Search for events by name (partial match in specified language)."""
        if not name_query or not isinstance(name_query, str):
            return []

        try:
            statement = select(Event).where(Event.event_name[language].contains(name_query))
            return self._session.exec(statement).all()
        except Exception:
            return []

    def search_by_date(
        self, timestamp: Union[int, str], language: str = "en"
    ) -> Optional[Event]:
        """
        Find events active at a specific timestamp (milliseconds since epoch) for a given language.

        Args:
            timestamp: The time to search for (int or str, milliseconds since epoch).
            language: The language key to use for start/end times.

        Returns:
            Event that is active at the given timestamp, or None if no event found.
        """
        if isinstance(timestamp, str):
            try:
                timestamp_int = int(timestamp)
            except ValueError:
                return []
        elif isinstance(timestamp, int):
            timestamp_int = timestamp
        else:
            return None

        statement = select(Event)
        events = self._session.exec(statement).all()
        for event in events:
            start = event.event_start_at.get(language)
            end = event.event_end_at.get(language)
            try:
                start_int = int(start) if start is not None else None
                end_int = int(end) if end is not None else None
            except Exception:
                continue
            if start_int is not None and end_int is not None:
                if start_int <= timestamp_int <= end_int:
                    return event