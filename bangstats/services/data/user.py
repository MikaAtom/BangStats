from typing import List, Optional, Dict, Any
from loguru import logger
from bangstats.database.repositories.user_repository import UserRepository
from bangstats.database.models.user import User


class UserService:
    def __init__(self):
        self._repo = UserRepository()
        logger.debug("UserService initialized with UserRepository")

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"Invalid user_id: {user_id}")
            return None
        return self._repo.get_by_id(user_id)

    def get_user_by_game_id(self, game_id: str) -> Optional[User]:
        if not game_id or not isinstance(game_id, str):
            logger.warning(f"Invalid game_id: {game_id}")
            return None
        return self._repo.get_by_game_id(game_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        if not username or not isinstance(username, str):
            logger.warning(f"Invalid username: {username}")
            return None
        return self._repo.get_by_username(username)

    def get_all_users(self) -> List[User]:
        return self._repo.get_all()

    def create_user(self, user_data: Dict[str, Any]) -> User:
        required = ["game_id", "username", "server"]
        for f in required:
            if f not in user_data:
                raise ValueError(f"Missing field: {f}")
        if self.get_user_by_game_id(user_data["game_id"]):
            raise ValueError(f"game_id {user_data['game_id']} already exists")
        if self.get_user_by_username(user_data["username"]):
            raise ValueError(f"username {user_data['username']} already exists")
        for field in ["game_id", "username", "server"]:
            if (
                not isinstance(user_data[field], str)
                or not user_data[field].strip()
            ):
                raise ValueError(f"{field} must be a non-empty string")
        # validate optional screenshot fields
        if "screenshots_source" in user_data:
            if (
                not isinstance(user_data["screenshots_source"], str)
                or not user_data["screenshots_source"].strip()
            ):
                raise ValueError("screenshots_source must be a non-empty string")
        if "screenshots_path" in user_data:
            if not isinstance(user_data["screenshots_path"], str):
                raise ValueError("screenshots_path must be a string")
        user, err = self._repo.create(user_data)
        if err:
            raise ValueError(err)
        return user

    def update_user(self, user_id: int, user_data: Dict[str, Any]) -> User:
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user_id")
        if "game_id" in user_data and (
            not isinstance(user_data["game_id"], str) or not user_data["game_id"]
        ):
            raise ValueError("game_id must be a non-empty string")
        if "username" in user_data and (
            not isinstance(user_data["username"], str) or not user_data["username"]
        ):
            raise ValueError("username must be a non-empty string")
        if "server" in user_data and (
            not isinstance(user_data["server"], str) or not user_data["server"]
        ):
            raise ValueError("server must be a non-empty string")
        # validate optional screenshot fields
        if "screenshots_source" in user_data:
            if (
                not isinstance(user_data["screenshots_source"], str)
                or not user_data["screenshots_source"].strip()
            ):
                raise ValueError("screenshots_source must be a non-empty string")
        if "screenshots_path" in user_data:
            if not isinstance(user_data["screenshots_path"], str):
                raise ValueError("screenshots_path must be a string")
        user, err = self._repo.update(user_id, user_data)
        if err:
            raise ValueError(err)
        return user

    def delete_user(self, user_id: int) -> bool:
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user_id")
        ok, err = self._repo.delete(user_id)
        if not ok:
            raise ValueError(err)
        return True
