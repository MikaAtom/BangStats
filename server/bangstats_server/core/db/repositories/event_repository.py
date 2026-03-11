from typing import List, Optional, Union
from sqlmodel import select
from bangstats_server.core.db.models.event import Event
from bangstats_server.core.db.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event]):
    model = Event

    def get_by_event_id(self, event_id: int) -> Optional[Event]:
        """Retrieve an event by its event_id field."""
        if not isinstance(event_id, int) or event_id <= 0:
            return None

        statement = select(Event).where(Event.event_id == event_id)
        return self._session.exec(statement).first()

    def create(self, event_data: dict) -> tuple[Optional[Event], Optional[str]]:
        """
        Create a new event record.
        Always returns (event, None) or (None, error_message)
        """
        existing = self.get_by_event_id(event_data["event_id"])
        if existing:
            return None, f"Event with event_id {event_data['event_id']} already exists"

        return super().create(event_data)

    def update(self, event_id: int, event_data: dict) -> tuple[Optional[Event], Optional[str]]:
        """
        Update an existing event record.
        Always returns (event, None) or (None, error_message)
        """
        event = self.get_by_id(event_id)
        if not event:
            return None, f"Event with ID {event_id} not found"

        # If updating event_id, check it doesn't conflict
        if "event_id" in event_data and event_data["event_id"] != event.event_id:
            existing = self.get_by_event_id(event_data["event_id"])
            if existing and existing.id != event_id:
                return None, f"Event with event_id {event_data['event_id']} already exists"

        return super().update(event_id, event_data, f"Event with ID {event_id} not found")

    def delete(self, event_id: int) -> tuple[bool, Optional[str]]:
        """
        Delete an event by its ID.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        return super().delete(event_id, f"Event with ID {event_id} not found")

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
                return None
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

    def list_since_id(self, since_id: int, limit: int = 5000) -> List[Event]:
        if not isinstance(since_id, int) or since_id < 0:
            return []
        statement = (
            select(Event)
            .where(Event.id > since_id)
            .order_by(Event.id)
            .limit(limit)
        )
        return self._session.exec(statement).all()