from typing import Optional
from sqlmodel import select
from bangstats_server.core.db.models.user import User
from bangstats_server.core.db.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    model = User

    def get_by_game_id(self, game_id: str) -> Optional[User]:
        stmt = select(User).where(User.game_id == game_id)
        return self._session.exec(stmt).first()

    def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        return self._session.exec(stmt).first()

    def update(self, user_id: int, user_data: dict) -> tuple[Optional[User], Optional[str]]:
        return super().update(user_id, user_data, f"User with ID {user_id} not found")

    def delete(self, user_id: int) -> tuple[bool, Optional[str]]:
        return super().delete(user_id, f"User with ID {user_id} not found")
