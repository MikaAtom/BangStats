from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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
    perfect: int = 0
    great: int = 0
    good: int = 0
    bad: int = 0
    miss: int = 0
    fast: int = 0
    slow: int = 0
    max_combo: int = 0
    level: int | None = None
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


class ScanErrorThumbRef(BaseModel):
    error_type: str = Field(..., min_length=1, max_length=200)
    json_filename: str = Field(..., min_length=1, max_length=500)


class ThumbnailWarmRequest(BaseModel):
    """Ask the server to generate cached JPEG thumbnails before the client fetches them."""

    screenshot_ids: list[int] = Field(default_factory=list, max_length=120)
    upload_filenames: list[str] = Field(default_factory=list, max_length=80)
    scan_errors: list[ScanErrorThumbRef] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def _limit_total_refs(self) -> "ThumbnailWarmRequest":
        total = len(self.screenshot_ids) + len(self.upload_filenames) + len(self.scan_errors)
        if total > 150:
            raise ValueError("Too many thumbnail references (max 150 combined).")
        return self


class ThumbnailWarmItemResult(BaseModel):
    kind: Literal["screenshot", "upload", "scan_error"]
    screenshot_id: int | None = None
    filename: str | None = None
    error_type: str | None = None
    json_filename: str | None = None
    ok: bool
    thumbnail_url: str | None = None
    detail: str | None = None


class ThumbnailWarmResponse(BaseModel):
    results: list[ThumbnailWarmItemResult] = Field(default_factory=list)
    warmed: int = 0
    failed: int = 0
