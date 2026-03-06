from typing import Literal, Optional

from pydantic import BaseModel


ServerCode = Literal["en", "jp", "tw", "cn", "kr"]


class UserCreate(BaseModel):
    game_id: str
    username: str
    server: ServerCode
    screenshots_source: str = "local"
    screenshots_path: str = ""


class UserUpdate(BaseModel):
    game_id: Optional[str] = None
    username: Optional[str] = None
    server: Optional[ServerCode] = None
    screenshots_source: Optional[str] = None
    screenshots_path: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    game_id: str
    username: str
    server: str
    screenshots_source: str
    screenshots_path: str
