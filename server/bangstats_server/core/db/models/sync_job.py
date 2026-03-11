from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class SyncJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    server: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    requested_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id")

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    songs: Optional[int] = None
    events: Optional[int] = None
    bands: Optional[int] = None

    error_message: Optional[str] = None
