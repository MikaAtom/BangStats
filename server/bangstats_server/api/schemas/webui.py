from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from bangstats_server.api.schemas.scans import ScanJobResponse, UploadUsageResponse
from bangstats_server.api.schemas.sync import CountsResponse, SyncJobResponse
from bangstats_server.api.schemas.users import UserResponse


class ScreenshotItemResponse(BaseModel):
    id: int
    filename: str | None = None
    song_id: int
    song_name: str | None = None
    difficulty: str
    live_type: str
    score: int
    accuracy: float
    perfect: int
    great: int
    good: int
    bad: int
    miss: int
    fast: int
    slow: int
    max_combo: int
    full_combo: bool
    all_perfect: bool
    anomaly: bool
    timestamp: datetime
    image_available: bool = False
    image_url: str | None = None


class ScreenshotListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ScreenshotItemResponse] = Field(default_factory=list)


class UploadFileItemResponse(BaseModel):
    filename: str
    size_bytes: int
    modified_at: datetime
    image_url: str


class UploadFileListResponse(BaseModel):
    total: int
    items: list[UploadFileItemResponse] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    user: UserResponse
    counts: CountsResponse
    current_event: dict[str, Any] | None = None
    current_event_status: str = ""
    runtime: dict[str, Any] = Field(default_factory=dict)
    upload_usage: UploadUsageResponse
    stats: dict[str, Any] | None = None
    scan_jobs: list[ScanJobResponse] = Field(default_factory=list)
    sync_jobs: list[SyncJobResponse] = Field(default_factory=list)
    scan_errors: dict[str, Any] = Field(default_factory=dict)
    recent_screenshots: list[ScreenshotItemResponse] = Field(default_factory=list)


class MetaSongConfigResponse(BaseModel):
    server_meta_song_ids: list[int] = Field(default_factory=list)
    user_excluded_song_ids: list[int] = Field(default_factory=list)
    effective_song_ids: list[int] = Field(default_factory=list)


class ExportScreenshotReference(BaseModel):
    filename: str | None = None
    path: str | None = None
    image_available: bool = False


class UserDataExportResponse(BaseModel):
    exported_at: datetime
    user: dict[str, Any]
    screenshots: list[dict[str, Any]] = Field(default_factory=list)
    screenshot_references: list[ExportScreenshotReference] = Field(default_factory=list)
    meta_song_config: MetaSongConfigResponse
    stats_summary: dict[str, Any] = Field(default_factory=dict)


class UserDataImportRequest(BaseModel):
    payload: dict[str, Any]


class UserDataImportResponse(BaseModel):
    restored_screenshots: int = 0
    skipped_screenshots: int = 0
    unresolved_screenshot_references: list[str] = Field(default_factory=list)
    updated_user_settings: list[str] = Field(default_factory=list)
