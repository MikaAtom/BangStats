from typing import Optional, List
from sqlmodel import Field, SQLModel, JSON


class User(SQLModel, table=True):
    """User model representing user data in the database."""

    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: str = Field(index=True, unique=True)
    username: str = Field(index=True, unique=True)
    password_hash: str = Field(default="")
    role: str = Field(default="user", index=True)

    server: str = Field(index=True)
    screenshots_source: str = Field(default="local")
    screenshots_path: str = Field(default="")
    server_folder_authorized: bool = Field(default=False)
    sync_command: Optional[str] = Field(default=None)
    excluded_song_ids: List[int] = Field(default_factory=list, sa_type=JSON)
