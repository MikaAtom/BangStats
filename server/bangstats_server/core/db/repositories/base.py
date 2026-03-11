from typing import Any, Generic, Optional, TypeVar

from sqlmodel import SQLModel

from bangstats_server.core.db import get_session

ModelT = TypeVar("ModelT", bound=SQLModel)


class BaseRepository(Generic[ModelT]):
    """Shared CRUD helpers for SQLModel repositories."""

    model: type[ModelT]

    def __init__(self):
        self._session_gen = get_session()
        self._session = next(self._session_gen)

    def close(self):
        self._session_gen.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_by_id(self, entity_id: int) -> Optional[ModelT]:
        if not isinstance(entity_id, int) or entity_id <= 0:
            return None
        return self._session.get(self.model, entity_id)

    def get_all(self) -> list[ModelT]:
        from sqlmodel import select

        statement = select(self.model)
        return self._session.exec(statement).all()

    def create(self, entity_data: dict[str, Any]) -> tuple[Optional[ModelT], Optional[str]]:
        try:
            entity = self.model(**entity_data)
            self._session.add(entity)
            self._session.commit()
            self._session.refresh(entity)
            return entity, None
        except Exception as e:
            self._session.rollback()
            return None, f"Database error: {e}"

    def update(
        self, entity_id: int, entity_data: dict[str, Any], not_found_message: str
    ) -> tuple[Optional[ModelT], Optional[str]]:
        entity = self.get_by_id(entity_id)
        if not entity:
            return None, not_found_message

        try:
            for key, value in entity_data.items():
                setattr(entity, key, value)
            self._session.add(entity)
            self._session.commit()
            self._session.refresh(entity)
            return entity, None
        except Exception as e:
            self._session.rollback()
            return None, f"Database error: {e}"

    def delete(self, entity_id: int, not_found_message: str) -> tuple[bool, Optional[str]]:
        entity = self.get_by_id(entity_id)
        if not entity:
            return False, not_found_message

        try:
            self._session.delete(entity)
            self._session.commit()
            return True, None
        except Exception as e:
            self._session.rollback()
            return False, f"Database error: {e}"
