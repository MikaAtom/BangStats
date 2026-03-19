from typing import Literal, Optional

from pydantic import BaseModel, Field


ServerCode = Literal["en", "jp", "tw", "cn", "kr"]
UserRole = Literal["user", "admin"]


class UserCreate(BaseModel):
    game_id: str
    username: str
    server: ServerCode
    screenshots_source: Literal["local", "server_folder"] = "local"
    screenshots_path: str = ""
    sync_command: Optional[str] = None
    excluded_song_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    game_id: Optional[str] = None
    username: Optional[str] = None
    server: Optional[ServerCode] = None
    screenshots_source: Optional[Literal["local", "server_folder"]] = None
    screenshots_path: Optional[str] = None
    sync_command: Optional[str] = None
    server_folder_authorized: Optional[bool] = None
    excluded_song_ids: Optional[list[int]] = None


class UserResponse(BaseModel):
    id: int
    game_id: str
    username: str
    role: UserRole = "user"
    server: str
    screenshots_source: str
    screenshots_path: str
    server_folder_authorized: bool
    sync_command: Optional[str] = None
    excluded_song_ids: list[int] = Field(default_factory=list)
