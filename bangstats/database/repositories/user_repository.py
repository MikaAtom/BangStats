from typing import List, Optional, Dict, Any, Tuple
from sqlmodel import select
from bangstats.database.models.user import User
from bangstats.database.db import get_session

class UserRepository:
    def __init__(self):
        self._session_gen = get_session()
        self._session = next(self._session_gen)

    def close(self):
        self._session_gen.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self._session.get(User, user_id)

    def get_by_game_id(self, game_id: str) -> Optional[User]:
        stmt = select(User).where(User.game_id == game_id)
        return self._session.exec(stmt).first()

    def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        return self._session.exec(stmt).first()

    def get_all(self) -> List[User]:
        stmt = select(User)
        return self._session.exec(stmt).all()

    def create(self, user_data: Dict[str, Any]) -> Tuple[Optional[User], Optional[str]]:
        try:
            user = User(**user_data)
            self._session.add(user)
            self._session.commit()
            self._session.refresh(user)
            return user, None
        except Exception as e:
            self._session.rollback()
            return None, str(e)

    def update(self, user_id: int, user_data: Dict[str, Any]) -> Tuple[Optional[User], Optional[str]]:
        user = self._session.get(User, user_id)
        if not user:
            return None, f"User with ID {user_id} not found"
        try:
            for key, value in user_data.items():
                setattr(user, key, value)
            self._session.add(user)
            self._session.commit()
            self._session.refresh(user)
            return user, None
        except Exception as e:
            self._session.rollback()
            return None, str(e)

    def delete(self, user_id: int) -> Tuple[bool, Optional[str]]:
        user = self._session.get(User, user_id)
        if not user:
            return False, f"User with ID {user_id} not found"
        try:
            self._session.delete(user)
            self._session.commit()
            return True, None
        except Exception as e:
            self._session.rollback()
            return False, str(e)

    def delete(self, user_id: int) -> Tuple[bool, Optional[str]]:
        user = self._session.get(User, user_id)
        if not user:
            return False, f"User with ID {user_id} not found"
        try:
            self._session.delete(user)
            self._session.commit()
            return True, None
        except Exception as e:
            self._session.rollback()
            return False, f"Database error: {e}"
