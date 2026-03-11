from typing import Any, Optional, Protocol, TypeVar

from loguru import logger

ModelT = TypeVar("ModelT")


class CRUDRepoProtocol(Protocol[ModelT]):
    def get_by_id(self, entity_id: int) -> Optional[ModelT]: ...
    def get_all(self) -> list[ModelT]: ...
    def create(self, entity_data: dict[str, Any]) -> tuple[Optional[ModelT], Optional[str]]: ...
    def update(
        self, entity_id: int, entity_data: dict[str, Any]
    ) -> tuple[Optional[ModelT], Optional[str]]: ...
    def delete(self, entity_id: int) -> tuple[bool, Optional[str]]: ...


class BaseCRUDService:
    """Shared validation and error-mapping helpers for CRUD services."""

    def _validate_positive_int(self, value: int, field_name: str) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"Invalid {field_name}")

    def _safe_get_by_id(self, repo: CRUDRepoProtocol[ModelT], entity_id: int) -> Optional[ModelT]:
        if not isinstance(entity_id, int) or entity_id <= 0:
            logger.warning(f"Invalid entity_id provided: {entity_id}")
            return None
        return repo.get_by_id(entity_id)

    def _get_all(self, repo: CRUDRepoProtocol[ModelT]) -> list[ModelT]:
        return repo.get_all()

    def _create_or_raise(self, repo: CRUDRepoProtocol[ModelT], data: dict[str, Any]) -> ModelT:
        entity, err = repo.create(data)
        if err:
            raise ValueError(err)
        return entity

    def _update_or_raise(
        self, repo: CRUDRepoProtocol[ModelT], entity_id: int, data: dict[str, Any]
    ) -> ModelT:
        entity, err = repo.update(entity_id, data)
        if err:
            raise ValueError(err)
        return entity

    def _delete_or_raise(self, repo: CRUDRepoProtocol[ModelT], entity_id: int) -> bool:
        success, err = repo.delete(entity_id)
        if not success:
            raise ValueError(err)
        return True
