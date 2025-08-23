from typing import Optional
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User model representing user data in the database."""

    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: str = Field(index=True, unique=True)
    username: str = Field(index=True, unique=True)

    server: str = Field(index=True)
    screenshots_source: str = Field(default="local")
    screenshots_path: str = Field(default="")
