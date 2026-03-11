from typing import Literal, Optional

from pydantic import BaseModel


ServerCode = Literal["en", "jp", "tw", "cn", "kr"]


class UserCreate(BaseModel):
    game_id: str
    username: str
    server: ServerCode
    screenshots_source: Literal["local", "server_folder"] = "local"
    screenshots_path: str = ""
    sync_command: Optional[str] = None


class UserUpdate(BaseModel):
    game_id: Optional[str] = None
    username: Optional[str] = None
    server: Optional[ServerCode] = None
    screenshots_source: Optional[Literal["local", "server_folder"]] = None
    screenshots_path: Optional[str] = None
    sync_command: Optional[str] = None
    server_folder_authorized: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    game_id: str
    username: str
    server: str
    screenshots_source: str
    screenshots_path: str
    server_folder_authorized: bool
    sync_command: Optional[str] = None
