from typing import Any, Dict

from pydantic import BaseModel, Field


class ScanResponse(BaseModel):
    total_scanned: int
    successful: int
    errors: Dict[str, int]
    error_files: Dict[str, list[str]]
    validated: int = 0
    persisted: int = 0
    failed_to_persist: int = 0
    skipped_duplicates: int = 0
    additional: Dict[str, Any] = Field(default_factory=dict)


class ScanCapabilitiesResponse(BaseModel):
    provider: str
    available_google_keys: int = 0


class ScanParallelOptions(BaseModel):
    parallel_workers: int | None = Field(default=None, ge=1)
    keys_per_worker: int | None = Field(default=None, ge=1)


class FilenameDiffRequest(BaseModel):
    user_id: int = Field(ge=1)
    filenames: list[str] = Field(default_factory=list)


class FilenameDiffResponse(BaseModel):
    requested_total: int
    already_scanned_count: int
    to_scan_count: int
    already_scanned_filenames: list[str] = Field(default_factory=list)
    to_scan_filenames: list[str] = Field(default_factory=list)


class CheckLocalPathRequest(BaseModel):
    folder_path: str


class CheckLocalPathResponse(BaseModel):
    is_local: bool
    canonical_path: str | None = None


class ScanLocalFolderRequest(BaseModel):
    user_id: int = Field(ge=1)
    folder_path: str
    filenames: list[str] = Field(default_factory=list)
    parallel_workers: int | None = Field(default=None, ge=1)
    keys_per_worker: int | None = Field(default=None, ge=1)


class ImportJsonFolderRequest(BaseModel):
    user_id: int
    folder_path: str
    persist_to_db: bool = True


class ErrorListResponse(BaseModel):
    total: int
    errors: Dict[str, int] = Field(default_factory=dict)
    error_files: Dict[str, list[str]] = Field(default_factory=dict)


class ErrorDetailResponse(BaseModel):
    error_type: str
    json_filename: str
    image_filename: str
    scan_data: Dict[str, Any]
    validation: Dict[str, Any] | None = None


class ErrorCorrectionRequest(BaseModel):
    user_id: int
    corrected_scan_data: Dict[str, Any]
    persist_to_db: bool = True


class ErrorCorrectionResponse(BaseModel):
    image_filename: str
    is_valid: bool
    error_type: str | None = None
    persisted: bool
    skipped_duplicates: bool
    failed_to_persist: bool


class ErrorCategoryActionRequest(BaseModel):
    user_id: int
    persist_to_db: bool = True
    progress_every: int = Field(default=500, ge=1)
    model: str | None = None


class ErrorCategoryActionResponse(BaseModel):
    total_files: int
    processed: int
    successful: int
    persisted: int
    skipped_duplicates: int
    failed_to_persist: int
    missing_image: int = 0
    scan_failed: int = 0
    errors: Dict[str, int] = Field(default_factory=dict)
