from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SyncRequest(BaseModel):
    server: Literal["en", "jp", "tw", "cn", "kr"]
    requested_by_user_id: int | None = Field(default=None, ge=1)


class CountsResponse(BaseModel):
    songs: int
    events: int
    bands: int


class SyncJobResponse(BaseModel):
    id: int
    server: str
    status: str
    requested_by_user_id: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    songs: int | None = None
    events: int | None = None
    bands: int | None = None
    error_message: str | None = None


class SyncJobListResponse(BaseModel):
    jobs: list[SyncJobResponse]
