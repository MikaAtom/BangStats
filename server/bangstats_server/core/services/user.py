from typing import List, Optional, Dict, Any
from loguru import logger
from bangstats_server.core.db.repositories.user_repository import UserRepository
from bangstats_server.core.db.models.user import User
from bangstats_server.core.services.base import BaseCRUDService


class UserService(BaseCRUDService):
    def __init__(self):
        self._repo = UserRepository()
        logger.debug("UserService initialized with UserRepository")

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self._safe_get_by_id(self._repo, user_id)

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
        return self._get_all(self._repo)

    def create_user(self, user_data: Dict[str, Any]) -> User:
        if user_data.get("screenshots_source") == "remote":
            user_data["screenshots_source"] = "local"
        if "role" not in user_data:
            user_data["role"] = "admin" if not self.get_all_users() else "user"
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
            if user_data["screenshots_source"] not in {"local", "server_folder"}:
                raise ValueError("screenshots_source must be either 'local' or 'server_folder'")
        if "screenshots_path" in user_data:
            if not isinstance(user_data["screenshots_path"], str):
                raise ValueError("screenshots_path must be a string")
        if "sync_command" in user_data and user_data["sync_command"] is not None:
            if not isinstance(user_data["sync_command"], str):
                raise ValueError("sync_command must be a string or null")
        if "excluded_song_ids" in user_data:
            if user_data["excluded_song_ids"] is None:
                user_data["excluded_song_ids"] = []
            if not isinstance(user_data["excluded_song_ids"], list):
                raise ValueError("excluded_song_ids must be a list of integers")
            cleaned_ids: list[int] = []
            for item in user_data["excluded_song_ids"]:
                if not isinstance(item, int) or item <= 0:
                    raise ValueError("excluded_song_ids must contain positive integers")
                if item not in cleaned_ids:
                    cleaned_ids.append(item)
            user_data["excluded_song_ids"] = cleaned_ids
        if "server_folder_authorized" in user_data:
            if not isinstance(user_data["server_folder_authorized"], bool):
                raise ValueError("server_folder_authorized must be a boolean")
        if "password_hash" in user_data:
            if (
                not isinstance(user_data["password_hash"], str)
                or not user_data["password_hash"].strip()
            ):
                raise ValueError("password_hash must be a non-empty string")
        if "role" in user_data:
            if user_data["role"] not in {"user", "admin"}:
                raise ValueError("role must be either 'user' or 'admin'")
        return self._create_or_raise(self._repo, user_data)

    def update_user(self, user_id: int, user_data: Dict[str, Any]) -> User:
        if user_data.get("screenshots_source") == "remote":
            user_data["screenshots_source"] = "local"
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
            if user_data["screenshots_source"] not in {"local", "server_folder"}:
                raise ValueError("screenshots_source must be either 'local' or 'server_folder'")
        if "screenshots_path" in user_data:
            if not isinstance(user_data["screenshots_path"], str):
                raise ValueError("screenshots_path must be a string")
        if "sync_command" in user_data and user_data["sync_command"] is not None:
            if not isinstance(user_data["sync_command"], str):
                raise ValueError("sync_command must be a string or null")
        if "excluded_song_ids" in user_data:
            if user_data["excluded_song_ids"] is None:
                user_data["excluded_song_ids"] = []
            if not isinstance(user_data["excluded_song_ids"], list):
                raise ValueError("excluded_song_ids must be a list of integers")
            cleaned_ids: list[int] = []
            for item in user_data["excluded_song_ids"]:
                if not isinstance(item, int) or item <= 0:
                    raise ValueError("excluded_song_ids must contain positive integers")
                if item not in cleaned_ids:
                    cleaned_ids.append(item)
            user_data["excluded_song_ids"] = cleaned_ids
        if "server_folder_authorized" in user_data:
            if not isinstance(user_data["server_folder_authorized"], bool):
                raise ValueError("server_folder_authorized must be a boolean")
        if "password_hash" in user_data:
            if (
                not isinstance(user_data["password_hash"], str)
                or not user_data["password_hash"].strip()
            ):
                raise ValueError("password_hash must be a non-empty string")
        if "role" in user_data and user_data["role"] not in {"user", "admin"}:
            raise ValueError("role must be either 'user' or 'admin'")
        return self._update_or_raise(self._repo, user_id, user_data)

    def delete_user(self, user_id: int) -> bool:
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user_id")
        return self._delete_or_raise(self._repo, user_id)
