from datetime import datetime
from typing import Any, Optional

from sqlmodel import JSON, Field, SQLModel


class ScanJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    status: str = Field(default="queued", index=True)

    source_type: str = Field(default="upload", index=True)
    folder_path: Optional[str] = Field(default=None)
    cancelled: bool = Field(default=False, index=True)

    total_files: int = Field(default=0)
    processed: int = Field(default=0)
    successful: int = Field(default=0)
    validated: int = Field(default=0)
    persisted: int = Field(default=0)
    failed_to_persist: int = Field(default=0)
    skipped_duplicates: int = Field(default=0)
    errors: dict[str, int] = Field(default_factory=dict, sa_type=JSON)
    error_files: dict[str, list[str]] = Field(default_factory=dict, sa_type=JSON)

    parallel_workers: Optional[int] = None
    keys_per_worker: Optional[int] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
