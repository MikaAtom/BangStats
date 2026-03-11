from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

from fastapi import UploadFile

from bangstats_server.core.config import (
    SCAN_MAX_AGE_DAYS,
    SCAN_MAX_FILES_PER_USER,
    SCAN_MAX_USER_STORAGE_MB,
    UPLOADS_ROOT,
)


class UploadStorageService:
    def __init__(self):
        self._root = UPLOADS_ROOT

    def _user_dir(self, user_id: int) -> Path:
        return self._root / str(user_id)

    def ensure_user_dir(self, user_id: int) -> Path:
        target = self._user_dir(user_id)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def cleanup_expired(self, user_id: int) -> int:
        now = time.time()
        max_age_seconds = max(1, SCAN_MAX_AGE_DAYS) * 24 * 60 * 60
        removed = 0
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return 0
        for path in user_dir.iterdir():
            if not path.is_file():
                continue
            try:
                age_seconds = now - path.stat().st_mtime
            except OSError:
                continue
            if age_seconds > max_age_seconds:
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def cleanup_all_expired(self) -> int:
        self._root.mkdir(parents=True, exist_ok=True)
        removed = 0
        for child in self._root.iterdir():
            if not child.is_dir():
                continue
            try:
                user_id = int(child.name)
            except ValueError:
                continue
            removed += self.cleanup_expired(user_id)
        return removed

    def get_usage(self, user_id: int) -> dict[str, float | int]:
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return {"file_count": 0, "total_size_mb": 0.0, "oldest_file_age_days": 0.0}
        file_count = 0
        total_size = 0
        oldest_mtime: float | None = None
        for path in user_dir.iterdir():
            if not path.is_file():
                continue
            file_count += 1
            try:
                stat = path.stat()
            except OSError:
                continue
            total_size += stat.st_size
            if oldest_mtime is None or stat.st_mtime < oldest_mtime:
                oldest_mtime = stat.st_mtime
        now = time.time()
        oldest_days = 0.0
        if oldest_mtime is not None:
            oldest_days = max(0.0, (now - oldest_mtime) / (24 * 60 * 60))
        return {
            "file_count": file_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_file_age_days": round(oldest_days, 2),
        }

    def check_limits(
        self,
        user_id: int,
        *,
        incoming_files_count: int,
        incoming_total_bytes: int,
    ) -> tuple[bool, str | None]:
        self.cleanup_expired(user_id)
        usage = self.get_usage(user_id)
        current_count = int(usage["file_count"])
        current_mb = float(usage["total_size_mb"])

        future_count = current_count + max(0, incoming_files_count)
        future_mb = current_mb + (max(0, incoming_total_bytes) / (1024 * 1024))

        if future_count > max(1, SCAN_MAX_FILES_PER_USER):
            return (
                False,
                f"User upload file limit exceeded: {future_count}/{SCAN_MAX_FILES_PER_USER}",
            )
        if future_mb > max(1, SCAN_MAX_USER_STORAGE_MB):
            return (
                False,
                f"User upload storage limit exceeded: {future_mb:.2f}/{SCAN_MAX_USER_STORAGE_MB} MB",
            )
        return True, None

    def save_uploaded_files(self, user_id: int, files: Iterable[UploadFile]) -> list[str]:
        target_dir = self.ensure_user_dir(user_id)
        saved: list[str] = []
        for upload in files:
            if not upload.filename:
                continue
            file_name = Path(upload.filename).name
            payload = upload.file.read()
            if payload is None:
                continue
            destination = target_dir / file_name
            destination.write_bytes(payload)
            saved.append(file_name)
        return saved

    def save_named_payloads(self, user_id: int, payloads: Iterable[tuple[str, bytes]]) -> list[str]:
        target_dir = self.ensure_user_dir(user_id)
        saved: list[str] = []
        for raw_name, content in payloads:
            file_name = Path(raw_name).name
            if not file_name:
                continue
            (target_dir / file_name).write_bytes(content)
            saved.append(file_name)
        return saved
