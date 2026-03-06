from typing import Any, Dict

from pydantic import BaseModel


class ScanResponse(BaseModel):
    total_scanned: int
    successful: int
    errors: Dict[str, int]
    error_files: Dict[str, list[str]]
    validated: int = 0
    persisted: int = 0
    failed_to_persist: int = 0
    skipped_duplicates: int = 0
    additional: Dict[str, Any] = {}
