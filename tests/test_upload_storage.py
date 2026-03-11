import os
import time
from pathlib import Path

import pytest

from bangstats_server.core.services import upload_storage as upload_storage_module


def test_upload_storage_limits_and_usage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(upload_storage_module, "UPLOADS_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(upload_storage_module, "SCAN_MAX_FILES_PER_USER", 5)
    monkeypatch.setattr(upload_storage_module, "SCAN_MAX_USER_STORAGE_MB", 1)
    monkeypatch.setattr(upload_storage_module, "SCAN_MAX_AGE_DAYS", 365)

    service = upload_storage_module.UploadStorageService()
    saved = service.save_named_payloads(
        7,
        [
            ("a.png", b"x" * 100),
            ("b.png", b"x" * 200),
        ],
    )
    assert saved == ["a.png", "b.png"]

    usage = service.get_usage(7)
    assert usage["file_count"] == 2
    assert usage["total_size_mb"] >= 0

    allowed, message = service.check_limits(
        7,
        incoming_files_count=10,
        incoming_total_bytes=0,
    )
    assert allowed is False
    assert "limit exceeded" in str(message)


def test_upload_storage_cleanup_expired(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(upload_storage_module, "UPLOADS_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(upload_storage_module, "SCAN_MAX_AGE_DAYS", 1)

    service = upload_storage_module.UploadStorageService()
    user_dir = service.ensure_user_dir(7)
    old_file = user_dir / "old.png"
    new_file = user_dir / "new.png"
    old_file.write_bytes(b"x")
    new_file.write_bytes(b"x")

    now = time.time()
    two_days = 2 * 24 * 60 * 60
    os.utime(old_file, (now - two_days, now - two_days))

    removed = service.cleanup_expired(7)
    assert removed == 1
    assert not old_file.exists()
    assert new_file.exists()
